
# FinCrime Pipeline Deployment Guide

This guide explains how to deploy and run the FinCrime Detection Pipeline on **Vertex AI Pipelines**.

---

## 1. Prerequisites
- Google Cloud project with Vertex AI enabled
- Python 3.9+
- `gcloud` CLI installed and authenticated
- Terraform installed (if using infra automation)
- Buckets already created:
  - **Transactions bucket**: holds input CSVs
  - **Artifact bucket**: stores pipeline outputs and artifacts

---

## 2. Compile the Pipeline
```bash
make compile
```
This generates `fincrime_pipeline.yaml`, the pipeline spec for Vertex AI.

---

## 3. Run the Pipeline (manual trigger)
```bash
make run PROJECT_ID=your-project REGION=us-central1 \    STAGING_BUCKET=gs://your-artifact-bucket \    INPUT_URI=gs://your-transactions-bucket/transactions_sample.csv \    EXPORT_URI=gs://your-artifact-bucket/exports
```

Outputs:
- `decisions.csv` → detailed risk flags
- `risk_summary.csv` → aggregated risk distribution
- `reason_summary.csv` → breakdown of risk reasons

All files are written to `gs://your-artifact-bucket/exports`.

---

## 4. Run the Dashboard
```bash
streamlit run dashboard.py
```
This reads the enriched `decisions.csv` and shows filters + summaries.

---

## 5. Automated Trigger (Cloud Function)
The repo includes a **Cloud Function** that triggers on every new file in your transactions bucket.

### Deploy with Terraform
```bash
make deploy PROJECT_ID=your-project REGION=us-central1
```

### Tear down
```bash
make destroy PROJECT_ID=your-project REGION=us-central1
```

---

## 6. Monitoring
- Vertex AI Console → Pipelines → Pipeline Runs
- Cloud Logging → Logs Explorer (`resource.type="cloud_function"`)

---

## 7. Next Steps
- Customize enrichment rules inside the pipeline
- Add monitoring dashboards (e.g., Data Studio / Looker Studio)
- Connect `dashboard.py` to a scheduled job if you want always-fresh views

---
