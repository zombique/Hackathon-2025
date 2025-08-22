#!/usr/bin/env python3
"""
Run FinCrime Pipeline on Vertex AI Pipelines
"""

import argparse
import subprocess
from google.cloud import aiplatform


def compile_pipeline():
    """Compile the pipeline definition into YAML."""
    subprocess.run(
        [
            "python",
            "-m",
            "kfp.v2.compiler",
            "--py",
            "fincrime_pipeline.py",
            "--output",
            "fincrime_pipeline.yaml",
        ],
        check=True,
    )


def run_pipeline(project, location, staging_bucket, gcs_input_uri, export_uri, model):
    """Submit pipeline run to Vertex AI Pipelines."""

    aiplatform.init(project=project, location=location)

    job = aiplatform.PipelineJob(
        display_name="fincrime-risk-pipeline",
        template_path="fincrime_pipeline.yaml",
        pipeline_root=staging_bucket,
        parameter_values={
            "project": project,
            "location": location,
            "gcs_input_uri": gcs_input_uri,
            "gcs_export_uri": export_uri,
            "model": model,
        },
    )

    job.run(sync=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--project", required=True, help="Google Cloud Project ID")
    parser.add_argument("--region", required=True, help="Vertex AI region, e.g. us-central1")
    parser.add_argument("--staging-bucket", required=True, help="GCS bucket for pipeline artifacts (gs://...)")
    parser.add_argument("--gcs-input-uri", required=True, help="Input CSV/Parquet file in GCS (gs://...)")
    parser.add_argument("--export-uri", required=True, help="Export GCS path for outputs (gs://...)")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Gemini model version")

    args = parser.parse_args()

    print("✅ Compiling pipeline...")
    compile_pipeline()

    print("🚀 Submitting pipeline job...")
    run_pipeline(
        project=args.project,
        location=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
    )
