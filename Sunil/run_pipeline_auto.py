import argparse
import logging
from google.cloud import aiplatform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_pipeline(project, region, staging_bucket, gcs_input_uri, export_uri, model):
    logger.info("🚀 Launching FinCrime pipeline...")

    # Always use the custom Vertex AI service account
    service_account = f"vertex-ai-sa@{project}.iam.gserviceaccount.com"

    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline-job",
        template_path="fincrime_pipeline.yaml",
        pipeline_root=staging_bucket,
        parameter_values={
            "gcs_input_uri": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
        enable_caching=False,
        service_account=service_account,   # 👈 force correct SA
    )

    job.run(sync=True)
    logger.info("✅ Pipeline submitted successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--gcs-input-uri", required=True)
    parser.add_argument("--export-uri", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    aiplatform.init(project=args.project, location=args.region)

    run_pipeline(
        project=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
    )
