#!/bin/bash
set -e

# Detect Project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo "❌ ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

# Try to detect region automatically
REGION=$(gcloud config get-value compute/region 2>/dev/null)

# If not set, try default Compute Engine zone -> region
if [ -z "$REGION" ]; then
  ZONE=$(gcloud config get-value compute/zone 2>/dev/null)
  if [ -n "$ZONE" ]; then
    REGION=$(echo "$ZONE" | sed 's/-[a-z]$//')
  fi
fi

# If still not set, fallback to asia-southeast1
if [ -z "$REGION" ]; then
  REGION="asia-southeast1"
fi

# Fixed (reusable) bucket names
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root"
OUTPUT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs"

echo "✅ INFO: Using Project: $PROJECT_ID"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Staging Bucket: $STAGING_BUCKET"
echo "✅ INFO: Output Bucket: $OUTPUT_BUCKET"

# Create buckets only if missing
if ! gsutil ls "$STAGING_BUCKET" >/dev/null 2>&1; then
  gsutil mb -l "$REGION" "$STAGING_BUCKET"
else
  echo "ℹ️ Reusing existing bucket: $STAGING_BUCKET"
fi

if ! gsutil ls "$OUTPUT_BUCKET" >/dev/null 2>&1; then
  gsutil mb -l "$REGION" "$OUTPUT_BUCKET"
else
  echo "ℹ️ Reusing existing bucket: $OUTPUT_BUCKET"
fi

# Upload pipeline + runner + requirements
gsutil cp fincrime_pipeline.yaml "$STAGING_BUCKET"/
gsutil cp run_pipeline_auto.py "$STAGING_BUCKET"/
gsutil cp requirements.txt "$STAGING_BUCKET"/

# Upload sample CSV if not already present
if ! gsutil ls "$OUTPUT_BUCKET/transactions_sample.csv" >/dev/null 2>&1; then
  gsutil cp transactions_sample.csv "$OUTPUT_BUCKET"/
else
  echo "ℹ️ Reusing existing input CSV in $OUTPUT_BUCKET"
fi

# Submit Vertex AI Custom Job
gcloud ai custom-jobs create \
  --region="$REGION" \
  --display-name=fincrime-pipeline-job \
  --worker-pool-spec=machine-type=n1-standard-4,replica-count=1,executor-image-uri=asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest \
  --args="--project=$PROJECT_ID,--region=$REGION,--staging-bucket=$STAGING_BUCKET,--gcs-input-uri=$OUTPUT_BUCKET/transactions_sample.csv,--export-uri=$OUTPUT_BUCKET/fincrime_output/,--model=gemini-1.5-flash"
