import argparse
import os
from google.cloud import aiplatform

def run_pipeline(project, region, staging_bucket, gcs_input_uri, export_uri, model):
    print("🚀 Launching FinCrime pipeline...")

    # GCS paths for pipeline + runner script
    pipeline_path = os.path.join(staging_bucket, "fincrime_pipeline.yaml")

    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline",
        template_path=pipeline_path,
        pipeline_root=staging_bucket,
        parameter_values={
            "gcs_input_uri": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
        project=project,
        location=region,
    )

    job.run(sync=True)
    print("✅ Pipeline execution completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--gcs-input-uri", required=True)
    parser.add_argument("--export-uri", required=True)
    parser.add_argument("--model", default="gemini-1.5-flash")
    args = parser.parse_args()

    # Ensure staging bucket is a proper GCS path
    if not args.staging_bucket.startswith("gs://"):
        args.staging_bucket = f"gs://{args.staging_bucket}"

    run_pipeline(
        project=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
    )
