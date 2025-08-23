#!/bin/bash
set -euo pipefail

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"
LOG_FILE="run_pipeline.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# --- CONFIG ---
PROJECT_ID=$(gcloud config get-value project)
REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "asia-southeast1")
JOB_NAME="fincrime-pipeline-job-$(date +%s)"

STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root"
OUTPUT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs"

echo "✅ INFO: Using Project: $PROJECT_ID"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Job Name: $JOB_NAME"

# Ensure buckets exist
if ! gsutil ls -b "$STAGING_BUCKET" >/dev/null 2>&1; then
  echo "ℹ️ Creating staging bucket: $STAGING_BUCKET"
  gsutil mb -l "$REGION" "$STAGING_BUCKET"
else
  echo "ℹ️ Reusing existing staging bucket: $STAGING_BUCKET"
fi

if ! gsutil ls -b "$OUTPUT_BUCKET" >/dev/null 2>&1; then
  echo "ℹ️ Creating output bucket: $OUTPUT_BUCKET"
  gsutil mb -l "$REGION" "$OUTPUT_BUCKET"
else
  echo "ℹ️ Reusing existing output bucket: $OUTPUT_BUCKET"
fi

# Upload CSV if not already present
if ! gsutil ls "$OUTPUT_BUCKET/transactions_sample.csv" >/dev/null 2>&1; then
  echo "✅ Uploading transactions_sample.csv to $OUTPUT_BUCKET"
  gsutil cp transactions_sample.csv "$OUTPUT_BUCKET/"
else
  echo "ℹ️ Reusing existing transactions_sample.csv in $OUTPUT_BUCKET"
fi

# --- SUBMIT CUSTOM JOB DIRECTLY WITH LOCAL CODE ---
echo "✅ INFO: Submitting Custom Job to Vertex AI..."
gcloud ai custom-jobs create \
  --region="$REGION" \
  --display-name="$JOB_NAME" \
  --worker-pool-spec=machine-type=n1-standard-4,replica-count=1,executor-image-uri=asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest,local-package-path=.,python-module=run_pipeline_auto \
  --args="--project=$PROJECT_ID,--region=$REGION,--staging-bucket=$STAGING_BUCKET,--gcs-input-uri=$OUTPUT_BUCKET/transactions_sample.csv,--export-uri=$OUTPUT_BUCKET/fincrime_output/,--model=gemini-1.5-flash"

echo "✅ Job submitted: $JOB_NAME"
echo "👉 Track logs: gcloud ai custom-jobs stream-logs --region=$REGION $JOB_NAME"
