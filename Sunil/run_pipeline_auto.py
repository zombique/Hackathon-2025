import subprocess
import sys
import argparse
from google.cloud import aiplatform

def install_deps():
    """Install required Python dependencies inside the Vertex AI container."""
    pkgs = [
        "kfp==2.5.0",
        "google-cloud-aiplatform==1.43.0",
        "protobuf==3.20.3",
        "python-json-logger==2.0.7",
        "pandas==2.3.2"
    ]
    for pkg in pkgs:
        print(f"📦 Installing {pkg} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])

def run_pipeline(project, region, staging_bucket, gcs_input_uri, export_uri, model, service_account):
    """Submit a pipeline job to Vertex AI."""
    aiplatform.init(project=project, location=region, staging_bucket=staging_bucket)

    job = aiplatform.PipelineJob(
        display_name="fincrime_pipeline",
        template_path="fincrime_pipeline.yaml",
        pipeline_root=staging_bucket,
        parameter_values={
            "gcs_input_uri": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
    )

    print("🚀 Launching FinCrime pipeline...")
    job.submit(service_account=service_account)
    job.wait()

if __name__ == "__main__":
    install_deps()

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--gcs-input-uri", required=True)
    parser.add_argument("--export-uri", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--service-account", required=True)

    args = parser.parse_args()

    run_pipeline(
        project=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
        service_account=args.service_account,
    )
