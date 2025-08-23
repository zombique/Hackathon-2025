#!/bin/bash

# ==============================
# Run FinCrime Pipeline on Vertex AI
# ==============================

set -euo pipefail

# ---- User Inputs ----
PROJECT_ID=$(gcloud config get-value project)
REGION=$(gcloud config get-value compute/region || echo "us-central1")
STAGING_BUCKET="gs://$PROJECT_ID-fincrime-artifacts"
INPUT_URI="$1"   # e.g., gs://your-bucket/transactions.csv
EXPORT_URI="$2"  # e.g., gs://your-bucket/output
MODEL="gemini-1.5-flash"

# ---- Ensure bucket exists ----
echo "Checking if bucket exists: $STAGING_BUCKET"
if ! gsutil ls -b "$STAGING_BUCKET" >/dev/null 2>&1; then
  echo "Bucket not found. Creating: $STAGING_BUCKET"
  gsutil mb -l "$REGION" "$STAGING_BUCKET"
fi

# ---- Compile pipeline ----
echo "Compiling pipeline..."
python3 fincrime_pipeline.py

# ---- Run pipeline ----
echo "Running pipeline on Vertex AI..."
python3 run_pipeline.py \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --staging-bucket "$STAGING_BUCKET" \
  --input-uri "$INPUT_URI" \
  --export-uri "$EXPORT_URI" \
  --pipeline-spec fincrime_pipeline.yaml \
  --model "$MODEL"

echo "✅ Pipeline submitted! Monitor in Vertex AI Console (Project: $PROJECT_ID, Region: $REGION)"
