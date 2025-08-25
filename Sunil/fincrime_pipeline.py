# ==========================================================
# Vertex AI FinCrime Pipeline - CSV-in / CSV-out
# With Color-Coded Logging for Easier Debugging
# ==========================================================

import kfp
from kfp import dsl
from kfp.dsl import (Dataset, Input, Output, component, pipeline)

# -------------------------
# Helper for ANSI colors
# -------------------------
def get_colors():
    return {
        "RED": "\033[91m",
        "GREEN": "\033[92m",
        "YELLOW": "\033[93m",
        "RESET": "\033[0m"
    }

# -------------------------
# Component 1: Extract Transactions from GCS
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def extract_transactions(gcs_input_uri: str, output: Output[Dataset]):
    import pandas as pd, logging
    colors = get_colors()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info(f"{colors['YELLOW']}🚀 Starting Extract Transactions{colors['RESET']}")

    df = pd.read_csv(gcs_input_uri) if gcs_input_uri.endswith(".csv") else pd.read_parquet(gcs_input_uri)

    required_cols = [
        "transaction_id", "originator_company", "originator_country", "beneficiary_company", 
        "beneficiary_country","amount", "currency", "date", 
        "originator_id", "originator_desc", "beneficiary_id", "beneficiary_desc","prediction"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logging.error(f"{colors['RED']}❌ Missing required columns: {missing}{colors['RESET']}")
        raise ValueError(f"Missing required columns: {missing}")

    optional_cols = [
        "purpose","industry","transaction_type","channel",
        "customer_segment","relationship_length","product"
    ]
    keep_cols = required_cols + [c for c in optional_cols if c in df.columns]
    df = df[keep_cols]

    df.to_parquet(output.path, index=False)
    logging.info(f"{colors['GREEN']}✅ Extract step completed successfully, rows={len(df)}{colors['RESET']}")

# -------------------------
# Component 2: Build Prompts
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow"],
)
def build_prompts(transactions: Input[Dataset], output: Output[Dataset]):
    import pandas as pd, logging
    colors = get_colors()
    logging.basicConfig(level=logging.INFO)
    logging.info(f"{colors['YELLOW']}🚀 Starting Build Prompts{colors['RESET']}")

    df = pd.read_parquet(transactions.path)
    prompts = []
    for _, row in df.iterrows():
        context_parts = [f"{col}: {row[col]}" for col in df.columns if col != "transaction_id"]
        context = ", ".join(context_parts)
        prompt = f"""
You are a FinCrime risk assistant. Given a transaction, decide if the transaction makes sense.

Transaction Details:
{context}

Return ONLY a strict JSON object with this schema:

{{
  "risk_level": "LOW | MEDIUM | HIGH",
  "reasons": "<one or two lines of consolidated text>"
}}

Do not include any text outside the JSON.

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
    logging.info(f"{colors['GREEN']}✅ Build Prompts completed, prompts={len(prompts)}{colors['RESET']}")

# -------------------------
# Component 3: LLM Scoring
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","google-cloud-aiplatform","google-generativeai"],
)
def llm_score(prompts: Input[Dataset], output: Output[Dataset], project: str, location: str, model: str):
    import pandas as pd, json, logging
    import vertexai
    from vertexai.generative_models import GenerativeModel

    colors = get_colors()
    logging.basicConfig(level=logging.INFO)
    logging.info(f"{colors['YELLOW']}🚀 Starting LLM Scoring{colors['RESET']}")

    vertexai.init(project=project, location=location)
    model_instance = GenerativeModel(model)

    df = pd.read_parquet(prompts.path)
    results = []

    for _, row in df.iterrows():
        try:
            resp = model_instance.generate_content(
                row["prompt"],
                generation_config={"response_mime_type": "application/json"}
            )

            if resp.candidates and resp.candidates[0].content.parts:
                raw_text = resp.candidates[0].content.parts[0].text.strip()
                logging.info(f"{colors['YELLOW']}🔎 Raw model output for tx {row['transaction_id']}: {raw_text}{colors['RESET']}")
                parsed = json.loads(raw_text)
            else:
                raise ValueError("Empty response from model")

            if isinstance(parsed.get("reasons"), list):
                parsed["reasons"] = " ".join(parsed["reasons"])

        except Exception as e:
            logging.warning(f"{colors['RED']}⚠️ Parse error for transaction {row['transaction_id']}: {str(e)}{colors['RESET']}")
            parsed = {
                "risk_level": "UNKNOWN",
                "reasons": f"parse_error: {str(e)}"
            }

        parsed["transaction_id"] = row["transaction_id"]
        results.append(parsed)

    pd.DataFrame(results).to_parquet(output.path, index=False)
    logging.info(f"{colors['GREEN']}✅ LLM Scoring completed, rows={len(results)}{colors['RESET']}")

# -------------------------
# Component 4: Persist Outputs
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def persist_outputs(results: Input[Dataset], gcs_export_uri: str):
    import pandas as pd, logging
    colors = get_colors()
    logging.basicConfig(level=logging.INFO)
    logging.info(f"{colors['YELLOW']}🚀 Starting Persist Outputs{colors['RESET']}")

    df = pd.read_parquet(results.path)
    out_csv = gcs_export_uri.rstrip("/") + "/decisions.csv"
    df.to_csv(out_csv, index=False)
    logging.info(f"{colors['GREEN']}✅ Outputs saved to {out_csv}{colors['RESET']}")

# -------------------------
# Component 5: Dashboard
# -------------------------
@component(
    base_image="python:3.10",
    packages_to_install=["pandas==2.2.2","pyarrow","gcsfs"],
)
def generate_dashboard(results: Input[Dataset], gcs_export_uri: str):
    import pandas as pd, logging
    colors = get_colors()
    logging.basicConfig(level=logging.INFO)
    logging.info(f"{colors['YELLOW']}🚀 Starting Dashboard Generation{colors['RESET']}")

    df = pd.read_parquet(results.path)

    summary = df.groupby("risk_level").size().reset_index(name="count")
    summary.to_csv(gcs_export_uri.rstrip("/") + "/risk_summary.csv", index=False)
    logging.info(f"{colors['GREEN']}✅ risk_summary.csv generated{colors['RESET']}")

    reason_counts = (
        df.groupby("reasons")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    reason_counts.to_csv(gcs_export_uri.rstrip("/") + "/reason_summary.csv", index=False)
    logging.info(f"{colors['GREEN']}✅ reason_summary.csv generated{colors['RESET']}")

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

if __name__ == "__main__":
    kfp.compiler.Compiler().compile(
        pipeline_func=pipeline,
        package_path="fincrime_pipeline.yaml"
    )
