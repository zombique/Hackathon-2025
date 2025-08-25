#!/bin/bash

# ==============================
# Run FinCrime Pipeline on Vertex AI
# ==============================

set -euo pipefail

# Default model if not provided
MODEL="${MODEL:-gemini-2.5-flash-lite}"

LOG_FILE="run_pipeline.log"
exec > >(tee -i $LOG_FILE) 2>&1

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"
echo "📝 Logging to $LOG_FILE"

log_info()  { echo "✅ INFO: $1"; }
log_error() { echo "❌ ERROR: $1"; exit 1; }

# ==================================================
# 1. Get GCP Project & Region
# ==================================================
if [ -z "${PROJECT_ID:-}" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
  if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "(unset)" ]; then
    log_error "PROJECT_ID is not set! Run: gcloud config set project YOUR_PROJECT_ID"
  fi
fi

if [ -z "${REGION:-}" ]; then
  ZONE=$(curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/zone" || true)
  if [ -n "$ZONE" ]; then
    ZONE=${ZONE##*/}
    REGION=${ZONE%-*}
  else
    REGION="us-central1"
    log_info "Defaulting REGION=$REGION"
  fi
fi

SERVICE_ACCOUNT="vertex-ai-sa@$PROJECT_ID.iam.gserviceaccount.com"

log_info "Using Project: $PROJECT_ID"
log_info "Using Region: $REGION"
log_info "Using Service Account: $SERVICE_ACCOUNT"

# ==================================================
# 2. Buckets (unique per run)
# ==================================================
UNIQUE_ID=$(date +%s)
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root-${UNIQUE_ID}"
EXPORT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs-${UNIQUE_ID}"

for BUCKET in "$STAGING_BUCKET" "$EXPORT_BUCKET"; do
  if ! gsutil ls -b "$BUCKET" >/dev/null 2>&1; then
    log_info "Creating GCS bucket: $BUCKET"
    gsutil mb -l "$REGION" "$BUCKET"
  else
    log_info "Bucket already exists: $BUCKET"
  fi
done

# ==================================================
# 3. Upload CSV + Python scripts + requirements.txt
# ==================================================
LOCAL_FILE="transactions_sample.csv"
if [ -f "$LOCAL_FILE" ]; then
  gsutil cp "$LOCAL_FILE" "$EXPORT_BUCKET/"
else
  log_error "transactions_sample.csv not found locally!"
fi

for SCRIPT in run_pipeline.py fincrime_pipeline.py; do
  if [ -f "$SCRIPT" ]; then
    log_info "Uploading $SCRIPT to $STAGING_BUCKET"
    gsutil cp "$SCRIPT" "$STAGING_BUCKET/"
  else
    log_error "$SCRIPT not found locally!"
  fi
  
done

INPUT_URI="$EXPORT_BUCKET/transactions_sample.csv"
EXPORT_URI="$EXPORT_BUCKET/fincrime_output/"

log_info "Input URI: $INPUT_URI"
log_info "Export URI: $EXPORT_URI"
log_info "Staging Bucket: $STAGING_BUCKET"

# ==================================================
# 4. Compile pipeline locally
# ==================================================
if [ -f fincrime_pipeline.py ]; then
  python3 fincrime_pipeline.py || log_error "Pipeline compilation failed!"
else
  log_error "fincrime_pipeline.py not found!"
fi

if [ -f fincrime_pipeline.yaml ]; then
  log_info "Uploading fincrime_pipeline.yaml to $STAGING_BUCKET"
  gsutil cp fincrime_pipeline.yaml "$STAGING_BUCKET/"
else
  log_error "fincrime_pipeline.yaml not found after compilation!"
fi

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

# ==================================================
# 5. Stream logs from the latest Custom Job
# ==================================================
echo "📡 Fetching latest Vertex AI Custom Job ID..."
JOB_ID=$(gcloud ai custom-jobs list \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --sort-by=createTime \
  --limit=1 \
  --format="value(name)")

if [ -n "$JOB_ID" ]; then
  echo "📑 Streaming logs for Job ID: $JOB_ID"
  gcloud ai custom-jobs stream-logs "$JOB_ID" \
    --region="$REGION" \
    --project="$PROJECT_ID"
else
  echo "❌ ERROR: Could not fetch Job ID!"
fi
