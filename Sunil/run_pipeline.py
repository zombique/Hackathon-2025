#!/usr/bin/env python3
from google.cloud import aiplatform
import argparse

def run_pipeline(project_id: str,
                 region: str,
                 staging_bucket: str,
                 input_uri: str,
                 export_uri: str,
                 pipeline_spec: str = "fincrime_pipeline.yaml",
                 model: str = "gemini-1.5-flash"):
    aiplatform.init(project=project_id,
                    location=region,
                    staging_bucket=staging_bucket)

    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline-run",
        template_path=pipeline_spec,
        pipeline_root=f"{staging_bucket}/pipeline-root",
        parameter_values={
            "project": project_id,
            "location": region,
            "gcs_input_uri": input_uri,
            "gcs_export_uri": export_uri,
            "model": model,
        },
    )

    print(f"Submitting pipeline job: {job._display_name}")  # internal field, safe before run()
    job.run(sync=False)
    print(f"Pipeline job started. ID: {job.job_id}")

    print(f"Pipeline submitted successfully! Track it in Vertex AI Console under project '{project_id}', region '{region}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FinCrime pipeline on Vertex AI")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-central1", help="Vertex AI region")
    parser.add_argument("--staging-bucket", required=True, help="Artifact/staging bucket (gs://...)")
    parser.add_argument("--input-uri", required=True, help="Input CSV/Parquet in GCS (gs://...)")
    parser.add_argument("--export-uri", required=True, help="Output folder in GCS (gs://...)")
    parser.add_argument("--pipeline-spec", default="fincrime_pipeline.yaml", help="Path to compiled pipeline YAML")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Generative model to use (e.g., gemini-1.5-pro)")

    args = parser.parse_args()
    run_pipeline(
        project_id=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        input_uri=args.input_uri,
        export_uri=args.export_uri,
        pipeline_spec=args.pipeline_spec,
        model=args.model,
    )
