#!/bin/bash
set -euo pipefail

echo "🚀 Starting FinCrime Pipeline end-to-end on Vertex AI"
LOG_FILE="run_pipeline.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "📝 Logging to $LOG_FILE"

# 🔹 Project + Region
PROJECT_ID=$(gcloud config get-value project)
REGION=$(gcloud config get-value ai/region || echo "asia-southeast1")
SERVICE_ACCOUNT="vertex-ai-sa@$PROJECT_ID.iam.gserviceaccount.com"

echo "✅ INFO: Using Project: $PROJECT_ID"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Using Service Account: $SERVICE_ACCOUNT"

# 🔹 Buckets
STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root-$(date +%s)"
OUTPUT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs-$(date +%s)"

echo "✅ INFO: Creating staging bucket: $STAGING_BUCKET"
gsutil mb -l "$REGION" "$STAGING_BUCKET" || echo "ℹ️ Bucket may already exist"

echo "✅ INFO: Creating output bucket: $OUTPUT_BUCKET"
gsutil mb -l "$REGION" "$OUTPUT_BUCKET" || echo "ℹ️ Bucket may already exist"

# 🔹 Upload sample CSV
INPUT_CSV="transactions_sample.csv"
echo "✅ INFO: Uploading $INPUT_CSV to $OUTPUT_BUCKET"
gsutil cp "$INPUT_CSV" "$OUTPUT_BUCKET/"

INPUT_URI="$OUTPUT_BUCKET/$INPUT_CSV"
EXPORT_URI="$OUTPUT_BUCKET/fincrime_output/"

echo "✅ INFO: Input URI: $INPUT_URI"
echo "✅ INFO: Export URI: $EXPORT_URI"
echo "✅ INFO: Staging Bucket: $STAGING_BUCKET"

# 🔹 Compile pipeline
echo "✅ INFO: Compiling pipeline with python3 fincrime_pipeline.py"
python3 fincrime_pipeline.py

# 🔹 Upload runner + pipeline spec to staging bucket
gsutil cp run_pipeline_auto.py "$STAGING_BUCKET/"
gsutil cp fincrime_pipeline.yaml "$STAGING_BUCKET/"

# 🔹 Submit as Custom Job
echo "✅ INFO: Generating Vertex AI Custom Job YAML at custom_job.yaml"

cat > custom_job.yaml <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: n1-standard-4
    replicaCount: 1
    containerSpec:
      imageUri: asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest
      command:
        - python3
        - run_pipeline_auto.py
      args:
        - --project=$PROJECT_ID
        - --region=$REGION
        - --staging-bucket=$STAGING_BUCKET
        - --gcs-input-uri=$INPUT_URI
        - --export-uri=$EXPORT_URI
        - --model=gemini-1.5-flash
        - --service-account=$SERVICE_ACCOUNT
    pythonPackageSpec:
      executorImageUri: asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest
EOF

echo "✅ INFO: Submitting Custom Job to Vertex AI..."
gcloud ai custom-jobs create \
  --region="$REGION" \
  --display-name="fincrime-pipeline-job" \
  --config=custom_job.yaml
