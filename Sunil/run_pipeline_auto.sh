#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION=$(gcloud config get-value compute/region || echo "asia-southeast1")

STAGING_BUCKET="gs://${PROJECT_ID}-fincrime-pipeline-root-$(date +%s)"
OUTPUT_BUCKET="gs://${PROJECT_ID}-fincrime-outputs-$(date +%s)"

echo "✅ INFO: Using Project: $PROJECT_ID"
echo "✅ INFO: Using Region: $REGION"
echo "✅ INFO: Staging Bucket: $STAGING_BUCKET"
echo "✅ INFO: Output Bucket: $OUTPUT_BUCKET"

# Create buckets
gsutil mb -l $REGION $STAGING_BUCKET || echo "ℹ️ Bucket exists"
gsutil mb -l $REGION $OUTPUT_BUCKET || echo "ℹ️ Bucket exists"

# Upload pipeline + runner + requirements
gsutil cp fincrime_pipeline.yaml $STAGING_BUCKET/
gsutil cp run_pipeline_auto.py $STAGING_BUCKET/
gsutil cp requirements.txt $STAGING_BUCKET/

# Submit Vertex AI Custom Job
gcloud ai custom-jobs create \
  --region=$REGION \
  --display-name=fincrime-pipeline-job \
  --python-package-uris=$STAGING_BUCKET/requirements.txt \
  --worker-pool-spec=machine-type=n1-standard-4,replica-count=1,executor-image-uri=asia-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest,local-package-path=run_pipeline_auto.py \
  --args="--project=$PROJECT_ID,--region=$REGION,--staging-bucket=$STAGING_BUCKET,--gcs-input-uri=$OUTPUT_BUCKET/transactions_sample.csv,--export-uri=$OUTPUT_BUCKET/fincrime_output/,--model=gemini-1.5-flash"
