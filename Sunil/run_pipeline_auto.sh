#!/bin/bash
set -euo pipefail

LOG_FILE="run_pipeline.log"
exec > >(tee -i $LOG_FILE) 2>&1

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"
echo "📝 Logging to $LOG_FILE"

log_info()  { echo "✅ INFO: $1"; }
log_error() { echo "❌ ERROR: $1"; exit 1; }

# ==================================================
# 1. Dynamically fetch GCP Project & Region
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
    REGION="us-central1" # default fallback
    log_info "No metadata zone found, defaulting REGION=$REGION"
  fi
fi

SERVICE_ACCOUNT="vertex-ai-sa@$PROJECT_ID.iam.gserviceaccount.com"

log_info "Using Project: $PROJECT_ID"
log_info "Using Region: $REGION"
log_info "Using Service Account: $SERVICE_ACCOUNT"

# ==================================================
# 2. Create buckets if not exist
# ==================================================
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root"
EXPORT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs"

for BUCKET in "$STAGING_BUCKET" "$EXPORT_BUCKET"; do
  if ! gsutil ls -b "$BUCKET" >/dev/null 2>&1; then
    log_info "Creating GCS bucket: $BUCKET"
    gsutil mb -l "$REGION" "$BUCKET" || log_error "Failed to create bucket $BUCKET"
  else
    log_info "Bucket already exists: $BUCKET"
  fi
done

# ==================================================
# 3. Upload sample CSV to GCS
# ==================================================
LOCAL_FILE="transactions_sample.csv"
if [ -f "$LOCAL_FILE" ]; then
  log_info "Uploading $LOCAL_FILE to $EXPORT_BUCKET"
  gsutil cp "$LOCAL_FILE" "$EXPORT_BUCKET/" || log_error "Failed to upload $LOCAL_FILE"
else
  log_error "transactions_sample.csv not found in local folder!"
fi

INPUT_URI="$EXPORT_BUCKET/transactions_sample.csv"
EXPORT_URI="$EXPORT_BUCKET/fincrime_output/"

log_info "Input URI: $INPUT_URI"
log_info "Export URI: $EXPORT_URI"
log_info "Staging Bucket: $STAGING_BUCKET"

# ==================================================
# 4. Compile pipeline
# ==================================================
if [ -f fincrime_pipeline.py ]; then
  log_info "Compiling pipeline with python3 fincrime_pipeline.py"
  if ! python3 fincrime_pipeline.py; then
    log_error "Pipeline compilation failed!"
  fi
else
  log_error "fincrime_pipeline.py not found!"
fi

# ==================================================
# 5. Create Vertex AI Custom Job YAML dynamically
# ==================================================
CUSTOM_JOB_YAML="custom_job.yaml"

cat > $CUSTOM_JOB_YAML <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: n1-standard-4
    replicaCount: 1
    containerSpec:
      imageUri: gcr.io/cloud-aiplatform/training/tf-cpu.2-5:latest
      command: ["python3", "run_pipeline_auto.py"]
      args:
        - --project=$PROJECT_ID
        - --region=$REGION
        - --staging-bucket=$STAGING_BUCKET
        - --gcs-input-uri=$INPUT_URI
        - --export-uri=$EXPORT_URI
        - --model=gemini-1.5-flash
EOF

log_info "Generated Vertex AI Custom Job YAML at $CUSTOM_JOB_YAML"

# ==================================================
# 6. Submit Custom Job to Vertex AI
# ==================================================
log_info "Submitting Custom Job to Vertex AI..."
if gcloud ai custom-jobs create \
  --region=$REGION \
  --display-name="fincrime-pipeline-job" \
  --service-account=$SERVICE_ACCOUNT \
  --config=$CUSTOM_JOB_YAML; then
  log_info "Vertex AI Custom Job submitted successfully!"
else
  log_error "Failed to submit Custom Job to Vertex AI"
fi
