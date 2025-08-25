"""
Vertex AI FinCrime Proof-of-Concept: Transaction Counterparty Reasonability

Idea
----
Take originators and beneficiaries from transactions, map each to corporate
registry data to look up industry codes (SIC/NACE), then ask a Vertex AI model
(Gemini) to decide whether it makes sense for Company A to be doing business
with Company B. The model returns a score and short rationale.

Usage
-----
# 1) Install deps
pip install --upgrade google-cloud-aiplatform vertexai pandas requests tqdm python-dotenv tenacity

# 2) Auth to GCP (one of):
- gcloud auth application-default login
- Or set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON key

# 3) Export environment variables
export GCP_PROJECT="your-project-id"
export GCP_LOCATION="us-central1"   # or your Vertex region
# Optional: if you want OpenCorporates enrichment
export OPENCORP_API_TOKEN="ocapikey_..."  # https://api.opencorporates.com/

# 4) Run
python vertex_ai_fincrime_pipeline.py \
  --input_csv transactions_sample.csv \
  --output_csv enriched_transactions.csv \
  --project $GCP_PROJECT --location $GCP_LOCATION

Notes
-----
- The OpenCorporates call is optional. If no token is present, a light
  fuzzy/stub lookup is used so the pipeline still runs.
- The Gemini response is requested in strict JSON. Adjust the prompt as needed.
- This is a PoC; for production, consider stronger entity resolution,
  vendor data SLAs, caching, retries, and monitoring.
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

# ----------------------------- Vertex AI (Gemini) -----------------------------
try:
    from vertexai import init as vertex_init
    from vertexai.generative_models import GenerativeModel, Part
except Exception as e:  # pragma: no cover
    GenerativeModel = None  # type: ignore
    vertex_init = None  # type: ignore


# --------------------------- Utility / Normalization --------------------------

def normalize_company_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.strip().upper()
    # Remove common suffixes
    n = re.sub(r"\b(LTD|LIMITED|PLC|LLC|INC|INCORPORATED|GMBH|S\.A\.|SAS|BV|OY|AB|AG|NV|PTY|PTE|KFT|SRL|SL|SA)\b", "", n)
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
    # Very small heuristic mapping for demo continuity
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

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), retry=retry_if_exception_type(requests.RequestException))
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

        # Some filings include industry codes under "industry_codes" or similar
        sic = None
        nace = None
        naics = None
        label = None
        ic_list = c.get("industry_codes") or []
        for ic in ic_list:
            code = (ic.get("industry_code") or {}).get("code")
            desc = (ic.get("industry_code") or {}).get("description")
            scheme = (ic.get("industry_code") or {}).get("industry_code_scheme_name", "").lower()
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
    # Ask Gemini for JSON only
    response = model.generate_content(
        [prompt],
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 256,
            "response_mime_type": "application/json",
        },
        safety_settings=None,
    )
    try:
        parsed = json.loads(response.text)
        # Basic normalization
        parsed["score"] = int(parsed.get("score", 50))
        parsed["risk"] = str(parsed.get("risk", "medium")).lower()
        parsed["rationale"] = str(parsed.get("rationale", ""))
        return parsed
    except Exception:
        # Fallback if model returns non-JSON
        return {"score": 50, "risk": "medium", "rationale": "Model returned non-JSON."}


# --------------------------------- Pipeline ----------------------------------

def enrich_companies(df: pd.DataFrame, oc: OpenCorporatesClient) -> pd.DataFrame:
    comps = set(df["originator_name"].dropna().astype(str)) | set(df["beneficiary_name"].dropna().astype(str))
    profiles: Dict[str, CompanyProfile] = {}

    for name in tqdm(comps, desc="Enriching companies"):
        profiles[name] = oc.lookup(name)
        time.sleep(0.2)  # be gentle with public APIs

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

    # 1) Enrich counterparties with registry data
    df = enrich_companies(df, oc)

    # 2) LLM assessment (skip if preview_only)
    if not preview_only:
        init_vertex(project, location)
        model = get_model(model_name)
        assessments: List[Dict[str, Any]] = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="LLM assessing"):
            tx = row.to_dict()
            assessments.append(assess_with_gemini(model, tx))
        assess_df = pd.DataFrame(assessments)
        df = pd.concat([df.reset_index(drop=True), assess_df], axis=1)

    # 3) Persist
    df.to_csv(output_csv, index=False)
    return df


# ---------------------------------- CLI --------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vertex AI FinCrime POC")
    p.add_argument("--input_csv", required=True, help="Path to input transactions CSV")
    p.add_argument("--output_csv", required=True, help="Path to write enriched CSV")
    p.add_argument("--project", default=os.getenv("GCP_PROJECT"), help="GCP project ID")
    p.add_argument("--location", default=os.getenv("GCP_LOCATION", "us-central1"), help="Vertex AI region")
    p.add_argument("--model", default="gemini-2.5-flash-lite", help="Vertex model name")
    p.add_argument("--preview_only", action="store_true", help="Skip LLM calls (schema/profiling only)")
    a = p.parse_args()
    if not a.project:
        p.error("--project not provided and GCP_PROJECT env var not set")
    return a


def main():
    args = parse_args()
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
