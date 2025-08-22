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
    REGION="asia-southeast1" # default primary region
    log_info "No metadata zone found, defaulting REGION=$REGION"
  fi
fi

FALLBACK_REGION="us-central1" # always has more capacity
SERVICE_ACCOUNT="vertex-ai-sa@$PROJECT_ID.iam.gserviceaccount.com"

log_info "Using Project: $PROJECT_ID"
log_info "Using Primary Region: $REGION"
log_info "Fallback Region: $FALLBACK_REGION"
log_info "Using Service Account: $SERVICE_ACCOUNT"

# ==================================================
# 2. Create unique bucket names
# ==================================================
UNIQUE_ID=$(date +%s)
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root-${UNIQUE_ID}"
EXPORT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs-${UNIQUE_ID}"

log_info "Staging Bucket will be: $STAGING_BUCKET"
log_info "Export Bucket will be: $EXPORT_BUCKET"

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

generate_job_yaml() {
cat > $CUSTOM_JOB_YAML <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: n1-standard-4
    replicaCount: 1
    containerSpec:
      imageUri: ${1}-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest
      command: ["python3", "run_pipeline_auto.py"]
      args:
        - --project=$PROJECT_ID
        - --region=$2
        - --staging-bucket=$STAGING_BUCKET
        - --gcs-input-uri=$INPUT_URI
        - --export-uri=$EXPORT_URI
        - --model=gemini-1.5-flash
EOF
}

# ==================================================
# 6. Submit Job (with fallback region support)
# ==================================================
submit_job() {
  local region=$1
  local repo=$2
  generate_job_yaml "$repo" "$region"

  log_info "Generated Vertex AI Custom Job YAML for region=$region"
  log_info "Submitting Custom Job to Vertex AI in $region..."

  JOB_ID=$(gcloud ai custom-jobs create \
    --region=$region \
    --display-name="fincrime-pipeline-job" \
    --service-account=$SERVICE_ACCOUNT \
    --config=$CUSTOM_JOB_YAML \
    --format="value(name)" || echo "")

  if [ -z "$JOB_ID" ]; then
    log_error "Failed to submit job in $region"
  fi

  echo "$JOB_ID"
}

# Try primary region first
JOB_ID=$(submit_job "$REGION" "${REGION%%-*}")
log_info "Submitted Job: $JOB_ID"

# Wait briefly and check status
sleep 60
STATUS=$(gcloud ai custom-jobs describe "$JOB_ID" --region=$REGION --format="value(state)" || echo "UNKNOWN")

if [ "$STATUS" == "PENDING" ]; then
  log_info "Job stuck in PENDING in $REGION. Retrying in fallback region $FALLBACK_REGION..."
  JOB_ID=$(submit_job "$FALLBACK_REGION" "us")
  log_info "Fallback Job Submitted: $JOB_ID"
fi

log_info "Monitor with: gcloud ai custom-jobs stream-logs $JOB_ID --region=$REGION"
