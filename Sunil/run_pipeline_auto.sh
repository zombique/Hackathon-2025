#!/bin/bash
set -euo pipefail

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
# 2. Buckets
# ==================================================
UNIQUE_ID=$(date +%s)
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root-${UNIQUE_ID}"
EXPORT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs-${UNIQUE_ID}"

cleanup() {
  log_info "Cleaning up staging bucket..."
  gsutil -m rm -r "$STAGING_BUCKET" || true
  log_info "Cleanup completed."
}
trap cleanup EXIT

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

if [ -f "run_pipeline_auto.py" ]; then
  log_info "Uploading run_pipeline_auto.py to $STAGING_BUCKET"
  gsutil cp "run_pipeline_auto.py" "$STAGING_BUCKET/"
else
  log_error "run_pipeline_auto.py not found locally!"
fi

# Always regenerate fixed requirements.txt before upload
cat > requirements.txt <<EOF
python-json-logger==2.0.7
kfp==2.14.2
google-cloud-storage==2.19.0
google-cloud-aiplatform==1.110.0
pandas==2.3.2
protobuf==3.20.3
EOF

log_info "Uploading corrected requirements.txt to $STAGING_BUCKET"
gsutil cp "requirements.txt" "$STAGING_BUCKET/"

INPUT_URI="$EXPORT_BUCKET/transactions_sample.csv"
EXPORT_URI="$EXPORT_BUCKET/fincrime_output/"

log_info "Input URI: $INPUT_URI"
log_info "Export URI: $EXPORT_URI"
log_info "Staging Bucket: $STAGING_BUCKET"

# ==================================================
# 4. Compile pipeline
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

# ==================================================
# 5. Create Custom Job YAML
# ==================================================
CUSTOM_JOB_YAML="custom_job.yaml"

cat > $CUSTOM_JOB_YAML <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: n1-standard-4
    replicaCount: 1
    containerSpec:
      imageUri: ${REGION%%-*}-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest
      command:
        - bash
        - -c
        - |
          echo "Installing dependencies..." && \
          python3 -m pip install --upgrade pip setuptools wheel && \
          gsutil cp $STAGING_BUCKET/requirements.txt . && \
          pip install --no-cache-dir --use-pep517 -r requirements.txt && \
          pip uninstall -y google-cloud-datastore || true && \
          rm -f \$(python3 -c "import site; print(site.getsitepackages()[0])")/sitecustomize.py || true && \
          echo "Downloading pipeline files from $STAGING_BUCKET" && \
          gsutil cp $STAGING_BUCKET/run_pipeline_auto.py . && \
          gsutil cp $STAGING_BUCKET/fincrime_pipeline.yaml . && \
          python3 run_pipeline_auto.py \
            --project=$PROJECT_ID \
            --region=$REGION \
            --staging-bucket=$STAGING_BUCKET \
            --gcs-input-uri=$INPUT_URI \
            --export-uri=$EXPORT_URI \
            --model=gemini-1.5-flash
EOF

log_info "Generated Vertex AI Custom Job YAML at $CUSTOM_JOB_YAML"

# ==================================================
# 6. Submit Custom Job
# ==================================================
log_info "Submitting Custom Job to Vertex AI..."
gcloud ai custom-jobs create \
  --region=$REGION \
  --display-name="fincrime-pipeline-job" \
  --service-account=$SERVICE_ACCOUNT \
  --config=$CUSTOM_JOB_YAML
