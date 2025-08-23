import os
import subprocess
from google.cloud import aiplatform

def install_requirements_from_gcs(bucket_uri: str):
    """
    Download requirements.txt from GCS and install it.
    """
    req_path = "/tmp/requirements.txt"
    try:
        print(f"✅ Downloading requirements.txt from {bucket_uri}")
        subprocess.run(
            ["gsutil", "cp", f"{bucket_uri}/code/requirements.txt", req_path],
            check=True
        )
        print("✅ Installing dependencies from requirements.txt")
        subprocess.run(
            ["pip", "install", "--no-cache-dir", "-r", req_path],
            check=True
        )
    except Exception as e:
        print(f"⚠️ Skipping requirements install (error: {e})")

def run_pipeline(project: str, region: str, staging_bucket: str,
                 gcs_input_uri: str, export_uri: str, model: str):

    print("🚀 Launching FinCrime pipeline...")

    # Define pipeline job
    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline",
        template_path="fincrime_pipeline.yaml",
        pipeline_root=staging_bucket,
        parameter_values={
            "project": project,
            "region": region,
            "gcs_input_uri": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
    )

    job.run(sync=True)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--gcs-input-uri", required=True)
    parser.add_argument("--export-uri", required=True)
    parser.add_argument("--model", required=True)

    args = parser.parse_args()

    # ✅ Install requirements before running pipeline
    install_requirements_from_gcs(args.staging_bucket)

    # ✅ Initialize Vertex AI
    aiplatform.init(project=args.project, location=args.region, staging_bucket=args.staging_bucket)

    # ✅ Run pipeline
    run_pipeline(
        project=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
    )
