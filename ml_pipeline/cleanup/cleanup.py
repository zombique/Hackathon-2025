"""
reset_infra.py

This script cleans up all GCP resources related to the ML pipeline:
1. Deletes Cloud Functions (train-model, predict-transaction, suspicious-transactions).
2. Deletes GCS Buckets (train & predict).
3. Deletes BigQuery dataset (transactions_dataset).

Run this manually in Cloud Shell or locally with authenticated gcloud SDK.
"""

import subprocess

# Project and resource names
PROJECT_ID = "sonic-totem-469814-q5"
REGION = "us-central1"
DATASET = "transactions_dataset"

# Buckets
BUCKETS = [
    "sonic-totem-469814-q5-train-data",
    "sonic-totem-469814-q5-predict-data"
]

# Cloud Functions
FUNCTIONS = [
    "train-model",
    "predict-transaction",
    "suspicious-transactions"
]


def run_cmd(cmd):
    """Run a shell command and print output."""
    print(f"\n👉 Running: {cmd}")
    try:
        subprocess.run(cmd, check=True, shell=True)
        print("✅ Success")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Command failed: {e}")


def delete_functions():
    """Delete Cloud Functions."""
    for fn in FUNCTIONS:
        cmd = f"gcloud functions delete {fn} --region={REGION} --quiet --project={PROJECT_ID}"
        run_cmd(cmd)


def delete_buckets():
    """Delete GCS Buckets."""
    for bucket in BUCKETS:
        cmd = f"gsutil rm -r gs://{bucket}"
        run_cmd(cmd)


def delete_bq_dataset():
    """Delete BigQuery Dataset and everything inside."""
    cmd = f"bq rm -r -f -d {PROJECT_ID}:{DATASET}"
    run_cmd(cmd)


if __name__ == "__main__":
    print("⚠️ WARNING: This will permanently delete all ML pipeline resources.")
    delete_functions()
    delete_buckets()
    delete_bq_dataset()
    print("\n✅ Reset complete! All resources cleaned up.")

