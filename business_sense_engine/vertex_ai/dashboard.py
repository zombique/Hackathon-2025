import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pyvis.network import Network
import tempfile
import streamlit.components.v1 as components

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("decisions.csv")
    return df

df = load_data()

# -----------------------------
# 🎨 Page Config
# -----------------------------
st.set_page_config(page_title="Business Sense Dashboard", layout="wide")

st.title("🚨 Business Sense Engin Dashboard")

# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("🔎 Filters")

risk_filter = st.sidebar.multiselect(
    "Filter by Risk Level",
    options=df["risk_level"].dropna().unique(),
    default=list(df["risk_level"].dropna().unique())
)

country_filter = st.sidebar.multiselect(
    "Filter by Originator Country",
    options=df["originator_country"].dropna().unique(),
    default=list(df["originator_country"].dropna().unique())
)

# Apply filters
filtered_df = df[
    (df["risk_level"].isin(risk_filter)) &
    (df["originator_country"].isin(country_filter))
]

# -----------------------------
# 📊 Risk Distribution + 🌍 Counterparty Network
# -----------------------------
st.subheader("📊 Risk Insights")

col1, col2 = st.columns([1, 2])  # Pie chart smaller, network larger

# --- Pie Chart ---
with col1:
    st.markdown("**Risk Distribution**")
    risk_counts = filtered_df["risk_level"].value_counts()

    fig, ax = plt.subplots(figsize=(2.8, 2.8))   # Smaller size
    ax.pie(
        risk_counts,
        labels=risk_counts.index,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 8}
    )
    ax.axis("equal")
    st.pyplot(fig, use_container_width=False)

# --- Counterparty Network ---
with col2:
    st.markdown("**Counterparty Network**")

    net = Network(height="400px", width="100%", bgcolor="#ffffff", font_color="black")

    for _, row in filtered_df.iterrows():
        risk = row["risk_level"]
        color = "green" if risk == "LOW" else "orange" if risk == "MEDIUM" else "red"

        # Originator node with tooltip
        net.add_node(
            row["originator_company"],
            label=row["originator_company"],
            color=color,
            title=(
                f"<b>Originator:</b> {row['originator_company']}<br>"
                f"<b>Country:</b> {row['originator_country']}<br>"
                f"<b>Risk:</b> {risk}<br>"
                f"<b>Reason:</b> {row.get('reasons','')}"
            )
        )

        # Beneficiary node with tooltip
        net.add_node(
            row["beneficiary_company"],
            label=row["beneficiary_company"],
            color=color,
            title=(
                f"<b>Beneficiary:</b> {row['beneficiary_company']}<br>"
                f"<b>Country:</b> {row['beneficiary_country']}<br>"
                f"<b>Risk:</b> {risk}<br>"
                f"<b>Reason:</b> {row.get('reasons','')}"
            )
        )

        # Edge with tooltip
        net.add_edge(
            row["originator_company"],
            row["beneficiary_company"],
            title=f"Transaction Risk: {risk}"
        )

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    net.save_graph(tmp_file.name)
    html_code = open(tmp_file.name, "r", encoding="utf-8").read()
    st.components.v1.html(html_code, height=420, scrolling=True)

    # Legend under the graph
    st.markdown("""
    <div style="margin-top:10px;">
        <b>Legend:</b> 
        <span style="color:green;">🟢 Low Risk</span> | 
        <span style="color:orange;">🟠 Medium Risk</span> | 
        <span style="color:red;">🔴 High Risk</span>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------
# 📋 Transactions Table
# -----------------------------
st.subheader("📋 Transactions Table")

# Rename for readability
filtered_df = filtered_df.rename(columns={
    "risk_level": "Risk Level",
    "reasons": "Reasons",
    "rationale": "Rationale",
    "transaction_id": "Transaction Id",
    "originator_company": "Originator Company",
    "originator_country": "Originator Country",
    "beneficiary_company": "Beneficiary Company",
    "beneficiary_country": "Beneficiary Country"
})

table_df = filtered_df[
    ["Risk Level", "Reasons", "Rationale", "Transaction Id",
     "Originator Company", "Originator Country",
     "Beneficiary Company", "Beneficiary Country"]
]

# Styling
css = """
<style>
.tx-table-wrap{
  max-height: 600px; overflow-y: auto; border: 1px solid #e9ecef;
  border-radius: 10px; background:#fff;
  width: 100%;   /* take full width */
  display: block;
}
table.tx-table{
  width: 100%; min-width: 1200px;  /* auto expand width */
  border-collapse: collapse; table-layout: auto;
  font-size: 14px;
}
.tx-table thead th{
  position: sticky; top: 0; z-index: 2;
  background:#fafafa; text-align:center; font-weight:700; color:#000;
  padding:10px; border-bottom:1px solid #e9ecef;
}
.tx-table thead th.head-green{ color:#15803d; }   /* green headers */
.tx-table td{
  vertical-align: top; padding:10px; border-top:1px solid #f0f0f0;
  word-wrap: break-word; white-space: normal;
}
</style>
"""

# Build HTML
html = table_df.to_html(index=False, classes="tx-table")
html = html.replace("<th>Reasons</th>",   '<th class="head-green">Reasons</th>')
html = html.replace("<th>Rationale</th>", '<th class="head-green">Rationale</th>')

# Render
components.html(css + f'<div class="tx-table-wrap">{html}</div>', height=600, scrolling=True)
