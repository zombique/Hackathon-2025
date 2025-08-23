#!/usr/bin/env python3
import argparse
import sys
from google.cloud import aiplatform

def parse_args():
    parser = argparse.ArgumentParser(description="Run FinCrime pipeline on Vertex AI")
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--region", required=True, help="GCP Region")
    parser.add_argument("--staging-bucket", required=True, help="Staging GCS bucket")
    parser.add_argument("--gcs-input-uri", required=True, help="Input CSV file (GCS path)")
    parser.add_argument("--export-uri", required=True, help="Export location in GCS")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Model to use")
    return parser.parse_args()

def run_pipeline(args):
    print("🚀 [run_pipeline_auto.py] Starting FinCrime Pipeline")
    print(f"   ✅ Project: {args.project}")
    print(f"   ✅ Region: {args.region}")
    print(f"   ✅ Staging Bucket: {args.staging_bucket}")
    print(f"   ✅ Input CSV: {args.gcs_input_uri}")
    print(f"   ✅ Output Path: {args.export_uri}")
    print(f"   ✅ Model: {args.model}")
    sys.stdout.flush()

    aiplatform.init(project=args.project, location=args.region, staging_bucket=args.staging_bucket)

    job = aiplatform.PipelineJob(
        display_name="fincrime_pipeline",
        template_path=f"{args.staging_bucket}/code/fincrime_pipeline.yaml",
        parameter_values={
            "gcs_input_uri": args.gcs_input_uri,
            "export_uri": args.export_uri,
            "model": args.model,
        },
    )

    print("📡 Submitting pipeline job to Vertex AI...")
    job.run(sync=True)
    print("🎉 Pipeline completed successfully!")

if __name__ == "__main__":
    args = parse_args()
    run_pipeline(args)
