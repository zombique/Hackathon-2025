#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
: "${ARTIFACT_BUCKET:?Set ARTIFACT_BUCKET (existing)}"
: "${TRANSACTIONS_BUCKET:?Set TRANSACTIONS_BUCKET (existing)}"
MODEL="${MODEL:-gemini-1.5-flash}"

echo "Installing local tools..."
pip -q install -U kfp google-cloud-aiplatform vertexai pandas pyarrow gcsfs >/dev/null

echo "Compiling pipeline spec..."
python3 fincrime_pipeline.py  # produces fincrime_pipeline.yaml

echo "Packaging Cloud Function source..."
rm -f function_src.zip
mkdir -p build/trigger_pipeline
cp -f trigger_pipeline/main.py build/trigger_pipeline/
cp -f trigger_pipeline/requirements.txt build/trigger_pipeline/
cp -f fincrime_pipeline.yaml build/trigger_pipeline/
pushd build >/dev/null
zip -qr ../function_src.zip trigger_pipeline
popd >/dev/null

echo "Writing terraform.tfvars..."
cat > infra/terraform.tfvars <<EOF
project_id = "${PROJECT_ID}"
region = "${REGION}"
artifact_bucket = "${ARTIFACT_BUCKET}"
transactions_bucket = "${TRANSACTIONS_BUCKET}"
function_zip_object = "function_src.zip"
model = "${MODEL}"
EOF

echo "Deploying Terraform..."
pushd infra >/dev/null
terraform init -upgrade
terraform apply -auto-approve
popd >/dev/null

echo "Done. Upload a CSV to gs://${TRANSACTIONS_BUCKET} to trigger the pipeline."