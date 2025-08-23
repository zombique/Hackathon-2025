#!/bin/bash
set -euo pipefail

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"
LOG_FILE="run_pipeline.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Detect project and region
PROJECT=$(gcloud config get-value project)
REGION=$(gcloud config get-value compute/region)
if [[ -z "$REGION" || "$REGION" == "(unset)" ]]; then
  REGION="asia-southeast1"
fi

SERVICE_ACCOUNT="vertex-ai-sa@${PROJECT}.iam.gserviceaccount.com"

echo "✅ INFO: Using Project: $PROJECT"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Using Service Account: $SERVICE_ACCOUNT"

# Buckets (add random suffix to avoid conflicts)
SUFFIX=$(date +%s)
STAGING_BUCKET="gs://${PROJECT}-fincrime-pipeline-root-${SUFFIX}"
OUTPUT_BUCKET="gs://${PROJECT}-fincrime-outputs-${SUFFIX}"

# Create buckets if not exist
echo "✅ INFO: Creating buckets..."
gsutil mb -l "$REGION" -p "$PROJECT" "$STAGING_BUCKET" || echo "ℹ️ Bucket $STAGING_BUCKET already exists"
gsutil mb -l "$REGION" -p "$PROJECT" "$OUTPUT_BUCKET" || echo "ℹ️ Bucket $OUTPUT_BUCKET already exists"

# Upload input data
echo "✅ INFO: Uploading transactions_sample.csv to $OUTPUT_BUCKET"
gsutil cp transactions_sample.csv "$OUTPUT_BUCKET/"

INPUT_URI="${OUTPUT_BUCKET}/transactions_sample.csv"
EXPORT_URI="${OUTPUT_BUCKET}/fincrime_output/"

echo "✅ INFO: Input URI: $INPUT_URI"
echo "✅ INFO: Export URI: $EXPORT_URI"
echo "✅ INFO: Staging Bucket: $STAGING_BUCKET"

# Compile pipeline locally
echo "✅ INFO: Compiling pipeline with python3 fincrime_pipeline.py"
python3 fincrime_pipeline.py
echo "✅ INFO: Generated Vertex AI Pipeline spec at fincrime_pipeline.yaml"

# Upload required scripts and YAML so container can use them
echo "✅ INFO: Uploading pipeline spec and launcher script to staging bucket"
gsutil cp fincrime_pipeline.yaml "$STAGING_BUCKET/"
gsutil cp run_pipeline_auto.py "$STAGING_BUCKET/"

# Generate Custom Job YAML
cat > custom_job.yaml <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: n1-standard-4
    replicaCount: 1
    pythonPackageSpec:
      executorImageUri: asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest
      packageUris: []
      pythonModule: run_pipeline_auto
      args:
        --project=${PROJECT}
        --region=${REGION}
        --staging-bucket=${STAGING_BUCKET}
        --gcs-input-uri=${INPUT_URI}
        --export-uri=${EXPORT_URI}
        --model=gemini-1.5-flash
EOF

echo "✅ INFO: Generated Vertex AI Custom Job YAML at custom_job.yaml"

# Submit job
echo "✅ INFO: Submitting Custom Job to Vertex AI..."
gcloud ai custom-jobs create \
  --region="$REGION" \
  --display-name="fincrime-pipeline-job" \
  --config=custom_job.yaml \
  --project="$PROJECT" \
  --service-account="$SERVICE_ACCOUNT"
