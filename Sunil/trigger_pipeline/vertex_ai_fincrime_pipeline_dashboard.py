"""
Vertex AI FinCrime Proof-of-Concept with Enhanced Dashboard

Includes:
- Risk-level pie chart
- Score histogram
- Interactive transaction table
- **Network graph** of counterparties
- **Timeline view** of transactions
- **Heatmap** of risk scores vs transaction amounts

Run:
-----
1) Install deps
pip install --upgrade google-cloud-aiplatform vertexai pandas requests tqdm python-dotenv tenacity streamlit plotly networkx pyvis

2) Run pipeline to produce enriched_transactions.csv
python vertex_ai_fincrime_pipeline.py --input_csv transactions.csv --output_csv enriched_transactions.csv --project $GCP_PROJECT --location $GCP_LOCATION

3) Launch dashboard
streamlit run vertex_ai_fincrime_pipeline.py
"""
from __future__ import annotations

import argparse
import os
import re
import pandas as pd

# Streamlit / Plotly / NetworkX for UI
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from pyvis.network import Network

# ----------------------------- Utility ---------------------------------------

def normalize_company_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    n = name.strip().upper()
    n = re.sub(r"[^A-Z0-9 &]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()

# ----------------------------- Dashboard -------------------------------------

def launch_dashboard(csv_path: str):
    st.set_page_config(page_title="FinCrime LLM Analysis", layout="wide")
    st.title("💸 FinCrime Transaction Analysis Dashboard")

    df = pd.read_csv(csv_path)

    st.sidebar.header("Filters")
    risk_filter = st.sidebar.multiselect("Risk Level", options=df["risk"].dropna().unique(), default=list(df["risk"].dropna().unique()))
    df_filtered = df[df["risk"].isin(risk_filter)] if "risk" in df.columns else df

    # Risk Pie Chart
    st.subheader("📊 Risk Distribution")
    if "risk" in df_filtered.columns:
        risk_counts = df_filtered["risk"].value_counts().reset_index()
        risk_counts.columns = ["risk", "count"]
        fig = px.pie(risk_counts, names="risk", values="count", title="Risk Levels")
        st.plotly_chart(fig, use_container_width=True)

    # Score Histogram
    if "score" in df_filtered.columns:
        st.subheader("📈 Score Histogram")
        fig2 = px.histogram(df_filtered, x="score", nbins=20, title="Distribution of Plausibility Scores")
        st.plotly_chart(fig2, use_container_width=True)

    # Timeline
    if "date" in df_filtered.columns:
        st.subheader("⏳ Transaction Timeline")
        fig3 = px.scatter(df_filtered, x="date", y="score", color="risk", size="amount", hover_data=["originator_name","beneficiary_name","description"], title="Timeline of Transactions")
        st.plotly_chart(fig3, use_container_width=True)

    # Heatmap: Risk vs Amount
    if "amount" in df_filtered.columns and "risk" in df_filtered.columns:
        st.subheader("🔥 Risk vs Amount Heatmap")
        fig4 = px.density_heatmap(df_filtered, x="risk", y="amount", title="Heatmap of Risk by Amount")
        st.plotly_chart(fig4, use_container_width=True)

    # Network Graph
    st.subheader("🌐 Counterparty Network Graph")
    G = nx.from_pandas_edgelist(df_filtered, "originator_name", "beneficiary_name", edge_attr=True, create_using=nx.Graph())
    net = Network(height="500px", width="100%", notebook=False)
    net.from_nx(G)
    net.save_graph("network.html")
    st.components.v1.html(open("network.html").read(), height=550, scrolling=True)

    # Transaction Table
    st.subheader("📑 Transaction Table")
    st.dataframe(df_filtered, use_container_width=True)

    if st.checkbox("Show raw data"):
        st.write(df)

# ---------------------------- CLI Pipeline ------------------------------------

def run_pipeline(input_csv: str, output_csv: str, project: str, location: str) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    # Stub: enrichment + Gemini scoring
    df["score"] = 80
    df["risk"] = "low"
    df["rationale"] = "Stubbed rationale"
    df.to_csv(output_csv, index=False)
    return df


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input_csv")
    p.add_argument("--output_csv")
    p.add_argument("--project")
    p.add_argument("--location", default="us-central1")
    return p.parse_args()


def main():
    if st._is_running_with_streamlit:
        default_csv = "enriched_transactions.csv"
        if not os.path.exists(default_csv):
            st.warning(f"No {default_csv} found. Please run pipeline first.")
        else:
            launch_dashboard(default_csv)
    else:
        args = parse_args()
        run_pipeline(args.input_csv, args.output_csv, args.project, args.location)
        print(f"Enriched CSV written to {args.output_csv}")

if __name__ == "__main__":
    main()
