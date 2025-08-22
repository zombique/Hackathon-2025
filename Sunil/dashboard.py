import streamlit as st
import pandas as pd

st.set_page_config(page_title="FinCrime Counterparty Risk Dashboard", layout="wide")
st.title("💼 FinCrime Counterparty Risk Dashboard")

# Paths: set to local files or GCS-mounted paths
DECISIONS_CSV = "decisions.csv"
RISK_SUMMARY_CSV = "risk_summary.csv"
REASON_SUMMARY_CSV = "reason_summary.csv"

@st.cache_data
def load_data():
    decisions = pd.read_csv(DECISIONS_CSV)
    risk_summary = pd.read_csv(RISK_SUMMARY_CSV)
    reason_summary = pd.read_csv(REASON_SUMMARY_CSV)
    return decisions, risk_summary, reason_summary

decisions, risk_summary, reason_summary = load_data()

st.subheader("📊 Risk Level Distribution")
st.bar_chart(risk_summary.set_index("risk_level"))

st.subheader("🔎 Top Risk Reasons")
st.bar_chart(reason_summary.set_index("reasons").head(10))

st.subheader("📝 Transaction Decisions")
required_cols = [
    "transaction_id","originator_name","beneficiary_name",
    "amount","currency","value_date",
    "originator_country","beneficiary_country","purpose",
    "risk_level","reasons","suggested_actions"
]
optional_cols = [c for c in decisions.columns if c not in required_cols]
ordered_cols = [c for c in required_cols if c in decisions.columns] + optional_cols
st.dataframe(decisions[ordered_cols], use_container_width=True)

st.sidebar.header("Filters")
selected_risk = st.sidebar.multiselect("Filter by Risk Level", decisions["risk_level"].unique())

filtered = decisions[decisions["risk_level"].isin(selected_risk)] if selected_risk else decisions
st.subheader("📂 Filtered Transactions")
st.dataframe(filtered[ordered_cols], use_container_width=True)

st.download_button(
    label="Download Full Decisions CSV",
    data=decisions.to_csv(index=False).encode("utf-8"),
    file_name="decisions.csv",
    mime="text/csv",
)