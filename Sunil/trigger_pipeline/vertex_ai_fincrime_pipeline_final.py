"""
Vertex AI FinCrime Proof-of-Concept

Pipeline + Dashboard
--------------------
- Enrich counterparties with registry (OpenCorporates or stub)
- Assess plausibility with Vertex AI Gemini
- Save enriched CSV
- Interactive Streamlit dashboard:
    * Risk-level pie chart
    * Score histogram
    * Transaction timeline
    * Heatmap of risk vs amount
    * Counterparty network graph
    * Transaction table
    * Sidebar "Run pipeline" button

Usage
-----
1) Install deps:
   pip install --upgrade google-cloud-aiplatform vertexai pandas requests tqdm python-dotenv tenacity streamlit plotly networkx pyvis

2) Run pipeline (CLI mode):
   python vertex_ai_fincrime_pipeline.py --input_csv transactions.csv --output_csv enriched.csv --project $GCP_PROJECT --location $GCP_LOCATION

3) Launch dashboard (Streamlit mode):
   streamlit run vertex_ai_fincrime_pipeline.py -- --output_csv enriched.csv
   # OR run dashboard + trigger pipeline interactively
   streamlit run vertex_ai_fincrime_pipeline.py -- --input_csv transactions.csv --output_csv enriched.csv --project $GCP_PROJECT --location $GCP_LOCATION
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

# Streamlit / Plotly / NetworkX for UI
import streamlit as st
import plotly.express as px
import networkx as nx
from pyvis.network import Network

# ----------------------------- Vertex AI (Gemini) -----------------------------
try:
    from vertexai import init as vertex_init
    from vertexai.generative_models import GenerativeModel
except Exception:  # pragma: no cover
    GenerativeModel = None
    vertex_init = None


# --------------------------- Utility / Normalization --------------------------

def normalize_company_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.strip().upper()
    n = re.sub(
        r"\b(LTD|LIMITED|PLC|LLC|INC|INCORPORATED|GMBH|S\.A\.|SAS|BV|OY|AB|AG|NV|PTY|PTE|KFT|SRL|SL|SA)\b",
        "",
        n,
    )
    n = re.sub(r"[^A-Z0-9 &]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


# ------------------------ Corporate Registry Enrichment -----------------------

@dataclass
class CompanyProfile:
    input_name: str
    canonical_name: str
    jurisdiction: Optional[str]
    registry_url: Optional[str]
    sic: Optional[str]
    nace: Optional[str]
    naics: Optional[str]
    industry_label: Optional[str]
    source: str


def _fallback_stub_profile(name: str) -> CompanyProfile:
    heuristics: Dict[str, Tuple[str, str]] = {
        "SHELL": ("4731", "Wholesale of fuel"),
        "TESCO": ("4711", "Supermarkets"),
        "MICROSOFT": ("6201", "Software development"),
        "APPLE": ("4651", "Wholesale of computers"),
        "AMAZON": ("4791", "E-commerce"),
    }
    n = normalize_company_name(name)
    code, label = heuristics.get(n.split(" ")[0], (None, None))
    return CompanyProfile(
        input_name=name,
        canonical_name=name,
        jurisdiction=None,
        registry_url=None,
        sic=None,
        nace=code,
        naics=None,
        industry_label=label,
        source="stub",
    )


class OpenCorporatesClient:
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("OPENCORP_API_TOKEN")
        self.base = "https://api.opencorporates.com/v0.4"

    def enabled(self) -> bool:
        return bool(self.api_token)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(requests.RequestException),
    )
    def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        params = {"q": query, "api_token": self.api_token}
        r = requests.get(f"{self.base}/companies/search", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        items = data.get("results", {}).get("companies", [])
        return items[0] if items else None

    def fetch_industry(self, company: Dict[str, Any]) -> CompanyProfile:
        c = company.get("company", {})
        name = c.get("name")
        jurisdiction = c.get("jurisdiction_code")
        openc_id = c.get("opencorporates_url")

        sic = None
        nace = None
        naics = None
        label = None
        ic_list = c.get("industry_codes") or []
        for ic in ic_list:
            code = (ic.get("industry_code") or {}).get("code")
            desc = (ic.get("industry_code") or {}).get("description")
            scheme = (ic.get("industry_code") or {}).get(
                "industry_code_scheme_name", ""
            ).lower()
            if "sic" in scheme and not sic:
                sic = code
                label = desc or label
            elif "nace" in scheme and not nace:
                nace = code
                label = desc or label
            elif "naics" in scheme and not naics:
                naics = code
                label = desc or label

        return CompanyProfile(
            input_name=name,
            canonical_name=name,
            jurisdiction=jurisdiction,
            registry_url=openc_id,
            sic=sic,
            nace=nace,
            naics=naics,
            industry_label=label,
            source="opencorporates",
        )

    def lookup(self, name: str) -> CompanyProfile:
        if not self.enabled():
            return _fallback_stub_profile(name)
        try:
            res = self.search_company(name)
            if not res:
                return _fallback_stub_profile(name)
            return self.fetch_industry(res)
        except Exception:
            return _fallback_stub_profile(name)


# ------------------------- Vertex AI: LLM Assessment --------------------------

def init_vertex(project: str, location: str):
    if vertex_init is None:
        raise RuntimeError("vertexai library not installed. Run: pip install vertexai")
    vertex_init(project=project, location=location)


def get_model(model_name: str = "gemini-2.5-flash-lite") -> GenerativeModel:
    return GenerativeModel(model_name)


def build_prompt(tx: Dict[str, Any]) -> str:
    return (
        "You are a FinCrime analyst. Given two companies with industry metadata, "
        "assess whether the payment is commercially plausible. Return STRICT JSON "
        "with keys: score (0-100), risk: 'low'|'medium'|'high', rationale (<=80 words).\n\n"
        f"Originator: {tx.get('originator_name')} | Industry: {tx.get('originator_industry_label')} | Codes: SIC={tx.get('originator_sic')}, NACE={tx.get('originator_nace')}, NAICS={tx.get('originator_naics')}\n"
        f"Beneficiary: {tx.get('beneficiary_name')} | Industry: {tx.get('beneficiary_industry_label')} | Codes: SIC={tx.get('beneficiary_sic')}, NACE={tx.get('beneficiary_nace')}, NAICS={tx.get('beneficiary_naics')}\n"
        f"Amount: {tx.get('amount')} {tx.get('currency','')} | Description: {tx.get('description','')}\n"
        "Scoring rules: 0=very implausible, 50=unclear, 100=very plausible. "
        "Consider industry compatibility, amount relative to typical trade, and description."
    )


def assess_with_gemini(model: GenerativeModel, tx_row: Dict[str, Any]) -> Dict[str, Any]:
    prompt = build_prompt(tx_row)
    response = model.generate_content(
        [prompt],
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 256,
            "response_mime_type": "application/json",
        },
    )
    try:
        parsed = json.loads(response.text)
        parsed["score"] = int(parsed.get("score", 50))
        parsed["risk"] = str(parsed.get("risk", "medium")).lower()
        parsed["rationale"] = str(parsed.get("rationale", ""))
        return parsed
    except Exception:
        return {"score": 50, "risk": "medium", "rationale": "Model returned non-JSON."}


# --------------------------------- Pipeline ----------------------------------

def enrich_companies(df: pd.DataFrame, oc: OpenCorporatesClient) -> pd.DataFrame:
    comps = set(df["originator_name"].dropna().astype(str)) | set(
        df["beneficiary_name"].dropna().astype(str)
    )
    profiles: Dict[str, CompanyProfile] = {}

    for name in tqdm(comps, desc="Enriching companies"):
        profiles[name] = oc.lookup(name)
        time.sleep(0.2)

    def attach(side: str, row: pd.Series) -> pd.Series:
        name = row[f"{side}_name"]
        prof = profiles.get(name) or _fallback_stub_profile(name)
        row[f"{side}_canonical_name"] = prof.canonical_name
        row[f"{side}_jurisdiction"] = prof.jurisdiction
        row[f"{side}_registry_url"] = prof.registry_url
        row[f"{side}_sic"] = prof.sic
        row[f"{side}_nace"] = prof.nace
        row[f"{side}_naics"] = prof.naics
        row[f"{side}_industry_label"] = prof.industry_label
        row[f"{side}_industry_source"] = prof.source
        return row

    df = df.apply(lambda r: attach("originator", r), axis=1)
    df = df.apply(lambda r: attach("beneficiary", r), axis=1)
    return df


def run_pipeline(
    input_csv: str,
    output_csv: str,
    project: str,
    location: str,
    model_name: str = "gemini-2.5-flash-lite",
    preview_only: bool = False,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    required_cols = {"originator_name", "beneficiary_name"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")

    oc = OpenCorporatesClient()

    df = enrich_companies(df, oc)

    if not preview_only:
        init_vertex(project, location)
        model = get_model(model_name)
        assessments: List[Dict[str, Any]] = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="LLM assessing"):
            tx = row.to_dict()
            assessments.append(assess_with_gemini(model, tx))
        assess_df = pd.DataFrame(assessments)
        df = pd.concat([df.reset_index(drop=True), assess_df], axis=1)

    df.to_csv(output_csv, index=False)
    return df


# ----------------------------- Dashboard -------------------------------------

def launch_dashboard(csv_path: str, args):
    st.set_page_config(page_title="FinCrime LLM Analysis", layout="wide")
    st.title("💸 FinCrime Transaction Analysis Dashboard")

    # Sidebar controls
    st.sidebar.header("Controls")
    if st.sidebar.button("Run pipeline"):
        if not args.input_csv:
            st.error("You must provide --input_csv to run the pipeline.")
        else:
            with st.spinner("Running pipeline..."):
                run_pipeline(
                    input_csv=args.input_csv,
                    output_csv=args.output_csv,
                    project=args.project,
                    location=args.location,
                    model_name=args.model,
                    preview_only=args.preview_only,
                )
            st.success(f"Pipeline complete. Reloading {args.output_csv}...")

    if not os.path.exists(csv_path):
        st.warning(f"No {csv_path} found. Please run pipeline first.")
        return

    df = pd.read_csv(csv_path)

    # Filters
    st.sidebar.header("Filters")
    risk_filter = st.sidebar.multiselect(
        "Risk Level",
        options=df["risk"].dropna().unique() if "risk" in df.columns else [],
        default=list(df["risk"].dropna().unique()) if "risk" in df.columns else [],
    )
    df_filtered = df[df["risk"].isin(risk_filter)] if "risk" in df.columns else df

    # Risk Pie Chart
    if "risk" in df_filtered.columns:
        st.subheader("📊 Risk Distribution")
        risk_counts = df_filtered["risk"].value_counts().reset_index()
        risk_counts.columns = ["risk", "count"]
        fig = px.pie(risk_counts, names="risk", values="count", title="Risk Levels")
        st.plotly_chart(fig, use_container_width=True)

    # Score Histogram
    if "score" in df_filtered.columns:
        st.subheader("📈 Score Histogram")
        fig2 = px.histogram(
            df_filtered, x="score", nbins=20, title="Distribution of Plausibility Scores"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Timeline
    if "date" in df_filtered.columns:
        st.subheader("⏳ Transaction Timeline")
        fig3 = px.scatter(
            df_filtered,
            x="date",
            y="score",
            color="risk",
            size="amount" if "amount" in df_filtered.columns else None,
            hover_data=["originator_name", "beneficiary_name", "description"],
            title="Timeline of Transactions",
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Heatmap
    if "amount" in df_filtered.columns and "risk" in df_filtered.columns:
        st.subheader("🔥 Risk vs Amount Heatmap")
        fig4 = px.density_heatmap(
            df_filtered, x="risk", y="amount", title="Heatmap of Risk by Amount"
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Network Graph
    if "originator_name" in df_filtered.columns and "beneficiary_name" in df_filtered.columns:
        st.subheader("🌐 Counterparty Network Graph")
        G = nx.from_pandas_edgelist(
            df_filtered,
            "originator_name",
            "beneficiary_name",
            edge_attr=True,
            create_using=nx.Graph(),
        )
        net = Network(height="500px", width="100%", notebook=False)
        net.from_nx(G)
        net.save_graph("network.html")
        st.components.v1.html(open("network.html").read(), height=550, scrolling=True)

    # Transaction Table
    st.subheader("📑 Transaction Table")
    st.dataframe(df_filtered, use_container_width=True)

    if st.checkbox("Show raw data"):
        st.write(df)


# ---------------------------------- CLI --------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vertex AI FinCrime POC")
    p.add_argument("--input_csv", help="Path to input transactions CSV")
    p.add_argument("--output_csv", default="enriched_transactions.csv",
                   help="Path to write enriched CSV (dashboard also reads this)")
    p.add_argument("--project", default=os.getenv("GCP_PROJECT"), help="GCP project ID")
    p.add_argument("--location", default=os.getenv("GCP_LOCATION", "us-central1"), help="Vertex AI region")
    p.add_argument("--model", default="gemini-2.5-flash-lite", help="Vertex model name")
    p.add_argument("--preview_only", action="store_true", help="Skip LLM calls (schema/profiling only)")
    return p.parse_args()


def main():
    args = parse_args()

    if st._is_running_with_streamlit:
        launch_dashboard(args.output_csv, args)
    else:
        # CLI mode
        if not args.input_csv or not args.output_csv:
            print("Error: --input_csv and --output_csv are required in CLI mode")
            return
        df = run_pipeline(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            project=args.project,
            location=args.location,
            model_name=args.model,
            preview_only=args.preview_only,
        )
        print(f"Wrote {len(df)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
