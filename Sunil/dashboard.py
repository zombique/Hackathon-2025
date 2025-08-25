import streamlit as st
import pandas as pd
import plotly.express as px
from pyvis.network import Network
import networkx as nx

# ---------------------
# Config
# ---------------------
DECISIONS_CSV = "decisions.csv"
RISK_SUMMARY_CSV = "risk_summary.csv"
REASON_SUMMARY_CSV = "reason_summary.csv"
RATIONALE_SUMMARY_CSV = "rationale_summary.csv"

st.set_page_config(page_title="FinCrime Risk Dashboard", layout="wide")
st.title("💼 FinCrime Risk Dashboard")

# ---------------------
# Load Data
# ---------------------
@st.cache_data
def load_data():
    decisions = pd.read_csv(DECISIONS_CSV)
    risk_summary = pd.read_csv(RISK_SUMMARY_CSV)
    reason_summary = pd.read_csv(REASON_SUMMARY_CSV)
    rationale_summary = pd.read_csv(RATIONALE_SUMMARY_CSV)
    return decisions, risk_summary, reason_summary, rationale_summary

decisions, risk_summary, reason_summary, rationale_summary = load_data()

# ---------------------
# Sidebar Filters
# ---------------------
st.sidebar.header("🔎 Filters")
selected_risks = st.sidebar.multiselect("Risk Level", options=decisions["risk_level"].unique(), default=list(decisions["risk_level"].unique()))
selected_countries = st.sidebar.multiselect("Originator Country", options=decisions["originator_country"].dropna().unique(), default=list(decisions["originator_country"].dropna().unique()))

filtered_decisions = decisions[
    (decisions["risk_level"].isin(selected_risks)) &
    (decisions["originator_country"].isin(selected_countries))
]

# ---------------------
# Risk Distribution Pie
# ---------------------
st.subheader("📊 Risk Distribution")
fig_pie = px.pie(risk_summary, names="risk_level", values="count", color="risk_level", hole=0.4)
st.plotly_chart(fig_pie, use_container_width=True)

# ---------------------
# Top Reasons & Rationales (Stacked Section with Color Coding)
# ---------------------
st.subheader("🔎 Top Drivers of Risk")

st.markdown("#### 🔎 Top Risk Reasons")
fig_reason = px.bar(
    reason_summary.head(10),
    x="count", y="reasons", orientation="h",
    color="count", color_continuous_scale="Blues"
)
st.plotly_chart(fig_reason, use_container_width=True)

st.markdown("#### 🧠 Top Rationales")
fig_rationale = px.bar(
    rationale_summary.head(10),
    x="count", y="rationale", orientation="h",
    color="count", color_continuous_scale="Greens"
)
st.plotly_chart(fig_rationale, use_container_width=True)

# ---------------------
# Counterparty Network (Colored, Sized & Tooltip Details)
# ---------------------
st.subheader("🌍 Counterparty Network")
G = nx.from_pandas_edgelist(filtered_decisions, "originator_company", "beneficiary_company", create_using=nx.DiGraph())

# Calculate node transaction counts
node_counts = {}
for node in G.nodes():
    node_counts[node] = G.degree(node)

# Create PyVis network with risk coloring, sizing, and tooltips
net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

risk_colors = {"LOW": "#90ee90", "MEDIUM": "#ffd700", "HIGH": "#ff4500"}

for _, row in filtered_decisions.iterrows():
    origin = row["originator_company"]
    beneficiary = row["beneficiary_company"]
    risk = row["risk_level"] if "risk_level" in row else "MEDIUM"
    color = risk_colors.get(risk, "#87CEEB")

    size_origin = 15 + node_counts.get(origin, 1) * 3
    size_beneficiary = 15 + node_counts.get(beneficiary, 1) * 3

    # Tooltip info
    origin_title = f"Company: {origin}<br>Country: {row['originator_country']}<br>Risk: {risk}"
    beneficiary_title = f"Company: {beneficiary}<br>Country: {row['beneficiary_country']}<br>Risk: {risk}"

    net.add_node(origin, label=origin, color=color, size=size_origin, title=origin_title)
    net.add_node(beneficiary, label=beneficiary, color=color, size=size_beneficiary, title=beneficiary_title)
    net.add_edge(origin, beneficiary, title=f"Transaction Risk: {risk}")

net.save_graph("network.html")
st.components.v1.html(open("network.html").read(), height=520)

# ---------------------
# Detailed Decisions Table
# ---------------------
st.subheader("📝 Detailed Decisions")
search = st.text_input("Search transactions:")
filtered = filtered_decisions[filtered_decisions.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)] if search else filtered_decisions
st.dataframe(filtered, use_container_width=True)
