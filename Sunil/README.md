# Vertex AI FinCrime — CSV → Gemini → CSV

## Contents
- `fincrime_pipeline.py` — Vertex AI Pipelines definition (CSV in/out + dashboard CSVs)
- `dashboard.py` — Streamlit dashboard for the generated CSVs
- `requirements.txt`

## Usage

### Compile the pipeline spec
```bash
pip install -r requirements.txt
python fincrime_pipeline.py
```

### Run the pipeline in Vertex AI
Upload your input file to GCS and launch a PipelineJob using the compiled `fincrime_pipeline.yaml`.
Parameters needed:
- `project`: your GCP project ID
- `location`: e.g. `us-central1`
- `gcs_input_uri`: `gs://<bucket>/path/transactions.csv`
- `gcs_export_uri`: `gs://<artifact-bucket>/exports`

### Streamlit dashboard
Copy the exported CSVs locally (or mount the bucket) then run:
```bash
streamlit run dashboard.py
```

### Input CSV required columns
- transaction_id, originator_name, beneficiary_name, amount, currency, value_date,
  originator_country, beneficiary_country, purpose

Optional columns (auto-used if present): industry, transaction_type, channel,
customer_segment, relationship_length, product.