"""
app.py
-------
A simple proof-of-concept Streamlit app to check if financial transactions 
between two companies are legitimate or suspicious based on industry similarity,
transaction patterns, high-risk countries, and ownership information.

Author: [Your Name]
Date: [Date]
"""

import pandas as pd
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer, util

# -----------------------
# Load Data
# -----------------------
# For demo purposes, we use local CSVs. In production, replace with BigQuery queries.
transactions_df = pd.read_csv("transactions_sample.csv")
registry_df = pd.read_csv("registry_sample.csv")

# -----------------------
# Load Embedding Model
# -----------------------
# SentenceTransformer converts text (e.g., industry descriptions) into vector embeddings.
# Embeddings allow us to measure semantic similarity between two descriptions.
model = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------
# Helper: Compute Industry Similarity
# -----------------------
def compute_similarity(desc1: str, desc2: str) -> float:
    """
    Compute semantic similarity between two industry descriptions using embeddings.
    
    Args:
        desc1 (str): Industry description for the originator company.
        desc2 (str): Industry description for the beneficiary company.
        
    Returns:
        float: Cosine similarity score between 0.0 and 1.0.
    """
    emb1 = model.encode(desc1, convert_to_tensor=True)
    emb2 = model.encode(desc2, convert_to_tensor=True)
    similarity = util.cos_sim(emb1, emb2).item()
    return similarity

# -----------------------
# Risk Assessment Function
# -----------------------
def assess_transaction(row: pd.Series) -> pd.Series:
    """
    Assigns a risk score to a transaction and decides if it is suspicious.

    Risk factors considered:
    1. Industry similarity (low similarity = higher risk)
    2. Known suspicious patterns (layering, structuring)
    3. High-risk countries
    4. Same ownership between companies

    Args:
        row (pd.Series): A single transaction record from transactions_df.

    Returns:
        pd.Series: similarity score, risk score, and decision label ("Legit" or "Suspicious").
    """
    # Lookup industry descriptions based on SIC codes
    originator_desc = registry_df.loc[registry_df["SIC_code"] == row["originator_SIC"], "SIC_desc"].values[0]
    beneficiary_desc = registry_df.loc[registry_df["SIC_code"] == row["beneficiary_SIC"], "SIC_desc"].values[0]

    # 1. Industry similarity
    similarity = compute_similarity(originator_desc, beneficiary_desc)

    # Risk score starts at 0
    score = 0

    # Low industry similarity increases risk
    if similarity < 0.7:
        score += 1

    # Suspicious transaction patterns
    if row["pattern"] in ["layering", "structuring"]:
        score += 2

    # High-risk countries
    if row["beneficiary_country"] in ["Iran", "North Korea", "Syria"]:
        score += 3

    # Same ownership
    if row["originator_company"] == row["beneficiary_company"]:
        score += 1

    # Decide based on score threshold (>= 3 means suspicious)
    suspicious = score >= 3

    return pd.Series({
        "similarity": round(similarity, 2),
        "risk_score": score,
        "decision": "Suspicious" if suspicious else "Legit"
    })

# -----------------------
# Streamlit UI
# -----------------------
st.title("💳 Transaction Legitimacy Checker")
st.markdown("This app uses **AI embeddings** to check if two companies should be doing business.")

# Apply risk assessment to all transactions
results_df = transactions_df.apply(assess_transaction, axis=1)

# Merge results with original data
final_df = pd.concat([transactions_df, results_df], axis=1)

# Show data in the app
st.subheader("📊 All Transactions")
st.dataframe(final_df)

# Summary metrics
total_txns = len(final_df)
suspicious_count = (final_df["decision"] == "Suspicious").sum()

st.metric("Total Transactions", total_txns)
st.metric("Suspicious Transactions", suspicious_count)

# Filter suspicious transactions
st.subheader("🚨 Suspicious Transactions")
st.dataframe(final_df[final_df["decision"] == "Suspicious"])
