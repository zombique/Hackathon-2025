# ==========================================================
# Vertex AI FinCrime Pipeline - CSV-in / CSV-out
# With Optional Enrichment Columns for Richer Context
# ==========================================================

import kfp
from kfp import dsl
from kfp.dsl import (Dataset, Input, Output, component, pipeline)

# -------------------------
# Component 1: Extract Transactions from GCS
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def extract_transactions(gcs_input_uri: str, output: Output[Dataset]):
    import pandas as pd

    df = pd.read_csv(gcs_input_uri) if gcs_input_uri.endswith(".csv") else pd.read_parquet(gcs_input_uri)

    required_cols = [
        "transaction_id", "originator_company", "originator_country", "beneficiary_company", 
        "beneficiary_country","amount", "currency", "date", 
        "originator_id", "originator_desc", "beneficiary_id", "beneficiary_desc","prediction"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # ✅ Keep required + optional if present
    optional_cols = [
        "purpose","industry","transaction_type","channel",
        "customer_segment","relationship_length","product"
    ]
    keep_cols = required_cols + [c for c in optional_cols if c in df.columns]
    df = df[keep_cols]

    df.to_parquet(output.path, index=False)


# -------------------------
# Component 2: Build Prompts for Gemini
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow"],
)
def build_prompts(transactions: Input[Dataset], output: Output[Dataset]):
    import pandas as pd

    df = pd.read_parquet(transactions.path)
    prompts = []
    for _, row in df.iterrows():
        context_parts = []
        for col in df.columns:
            if col not in ["transaction_id"]:
                context_parts.append(f"{col}: {row[col]}")
        context = ", ".join(context_parts)

        prompt = f"""
        You are a FinCrime risk assistant. Given a transaction, decide if the transaction makes sense

        Transaction Details: {context}
        
        Return ONLY strict JSON with fields:
        - risk_level (LOW | MEDIUM | HIGH)
        - reasons (one or two lines of consolidated text)

        Consider:
        - Sanctioned or high-risk regions
        - Industry or customer profile mismatches
        - Unusual amounts relative to segment/industry
        - Cross-border and high-value red flags
        - Channel-specific risk factors
        - Transaction type anomalies
        """
        prompts.append({"transaction_id": row["transaction_id"], "prompt": prompt})

    pd.DataFrame(prompts).to_parquet(output.path, index=False)


# -------------------------
# Component 3: LLM Scoring with Gemini
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","google-cloud-aiplatform","google-generativeai"],
)
def llm_score(prompts: Input[Dataset], output: Output[Dataset], project: str, location: str, model: str):
    import pandas as pd, json

    from vertexai.generative_models import GenerativeModel
    import vertexai

    vertexai.init(project=project, location=location)
    model = genai.GenerativeModel("gemini-2.5-flash")

    df = pd.read_parquet(prompts.path)
    results = []

    for _, row in df.iterrows():
        resp = model.generate_content(row["prompt"])
        try:
            parsed = json.loads(resp.candidates[0].content.parts[0].text)
        except Exception:
            parsed = {"risk_level": "UNKNOWN", "reasons": ["parse_error"], "suggested_actions": []}
        parsed["transaction_id"] = row["transaction_id"]
        results.append(parsed)

    pd.DataFrame(results).to_parquet(output.path, index=False)


# -------------------------
# Component 4: Persist Outputs to GCS
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def persist_outputs(results: Input[Dataset], gcs_export_uri: str):
    import pandas as pd

    df = pd.read_parquet(results.path)
    out_csv = gcs_export_uri.rstrip("/") + "/decisions.csv"
    df.to_csv(out_csv, index=False)


# -------------------------
# Component 5: Generate Dashboard CSVs
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def generate_dashboard(results: Input[Dataset], gcs_export_uri: str):
    import pandas as pd
    df = pd.read_parquet(results.path)

    summary = df.groupby("risk_level").size().reset_index(name="count")
    summary.to_csv(gcs_export_uri.rstrip("/") + "/risk_summary.csv", index=False)

    exploded = df.explode("reasons")
    reason_counts = exploded.groupby("reasons").size().reset_index(name="count").sort_values("count", ascending=False)
    reason_counts.to_csv(gcs_export_uri.rstrip("/") + "/reason_summary.csv", index=False)


# -------------------------
# Pipeline Definition
# -------------------------
@dsl.pipeline(
    name="fincrime-risk-pipeline",
    pipeline_root="gs://your-artifact-bucket/pipeline-root"
)
def pipeline(project: str, location: str, gcs_input_uri: str, gcs_export_uri: str, model: str):
    raw = extract_transactions(gcs_input_uri=gcs_input_uri)
    prompts = build_prompts(transactions=raw.outputs["output"])
    scored = llm_score(prompts=prompts.outputs["output"], project=project, location=location, model=model)
    persist_outputs(results=scored.outputs["output"], gcs_export_uri=gcs_export_uri)
    generate_dashboard(results=scored.outputs["output"], gcs_export_uri=gcs_export_uri)


# -------------------------
# Compile Entry Point
# -------------------------
if __name__ == "__main__":
    kfp.compiler.Compiler().compile(
        pipeline_func=pipeline,
        package_path="fincrime_pipeline.yaml"
    )
