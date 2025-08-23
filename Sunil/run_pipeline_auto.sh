#!/bin/bash
set -e

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"

# --- CONFIG ---
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
REGION=$(gcloud config get-value ai/region 2>/dev/null || echo "")
if [[ -z "$REGION" ]]; then
  REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "")
fi
if [[ -z "$REGION" ]]; then
  REGION="asia-southeast1"   # ✅ fallback
fi
JOB_NAME="fincrime-pipeline-job-$(date +%s)"

STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root"
OUTPUT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs"

echo "✅ INFO: Using Project: $PROJECT_ID"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Job Name: $JOB_NAME"

# --- BUCKETS ---
if gsutil ls -b "$STAGING_BUCKET" >/dev/null 2>&1; then
  echo "ℹ️ Reusing existing staging bucket: $STAGING_BUCKET"
else
  echo "✅ INFO: Creating staging bucket: $STAGING_BUCKET"
  gsutil mb -l "$REGION" "$STAGING_BUCKET"
fi

if gsutil ls -b "$OUTPUT_BUCKET" >/dev/null 2>&1; then
  echo "ℹ️ Reusing existing output bucket: $OUTPUT_BUCKET"
else
  echo "✅ INFO: Creating output bucket: $OUTPUT_BUCKET"
  gsutil mb -l "$REGION" "$OUTPUT_BUCKET"
fi

# --- INPUT FILE ---
if gsutil ls "$OUTPUT_BUCKET/transactions_sample.csv" >/dev/null 2>&1; then
  echo "ℹ️ Reusing existing transactions_sample.csv in $OUTPUT_BUCKET"
else
  echo "✅ INFO: Uploading transactions_sample.csv"
  gsutil cp transactions_sample.csv "$OUTPUT_BUCKET/"
fi

# --- PACKAGE CODE ---
echo "✅ INFO: Packaging pipeline code..."
rm -f fincrime_code.tar.gz
tar -czf fincrime_code.tar.gz run_pipeline_auto.py fincrime_pipeline.py fincrime_pipeline.yaml requirements.txt

echo "✅ INFO: Uploading package to $STAGING_BUCKET/code/"
gsutil cp fincrime_code.tar.gz "$STAGING_BUCKET/code/"

# --- SUBMIT CUSTOM JOB ---
echo "✅ INFO: Submitting Custom Job to Vertex AI..."

JOB_ID=$(gcloud ai custom-jobs create \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$JOB_NAME" \
  --format="value(name)" \
  --python-package-uris="$STAGING_BUCKET/code/fincrime_code.tar.gz" \
  --worker-pool-spec=machine-type=n1-standard-4,executor-image-uri=us-docker.pkg.dev/vertex-ai/training/python:3.10,python-module=run_pipeline_auto,requirements=requirements.txt \
  --args="--project=$PROJECT_ID","--region=$REGION","--staging-bucket=$STAGING_BUCKET","--gcs-input-uri=$OUTPUT_BUCKET/transactions_sample.csv","--export-uri=$OUTPUT_BUCKET/fincrime_output/","--model=gemini-1.5-flash")

echo "✅ INFO: Custom Job submitted: $JOB_ID"
echo "📡 Streaming logs... (Ctrl+C to stop)"

# --- STREAM LOGS ---
gcloud ai custom-jobs stream-logs "$JOB_ID" --project="$PROJECT_ID" --region="$REGION"
