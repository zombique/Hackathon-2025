import argparse
from google.cloud import aiplatform
from kfp.v2 import compiler
import os

import fincrime_pipeline  # 🔑 make sure fincrime_pipeline.py is uploaded alongside this script

def run_pipeline(project, region, staging_bucket, gcs_input_uri, export_uri, model):
    aiplatform.init(project=project, location=region, staging_bucket=staging_bucket)

    # --- Compile pipeline inline ---
    compiled_path = "fincrime_pipeline.yaml"
    print("🛠 Compiling pipeline...")
    compiler.Compiler().compile(
        pipeline_func=fincrime_pipeline.fincrime_pipeline,
        package_path=compiled_path,
    )

    # Upload compiled YAML to staging bucket
    gcs_yaml_path = f"{staging_bucket}/code/{compiled_path}"
    print(f"📤 Uploading {compiled_path} to {gcs_yaml_path} ...")
    os.system(f"gsutil cp {compiled_path} {gcs_yaml_path}")

    # --- Submit pipeline job ---
    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline",
        template_path=gcs_yaml_path,
        pipeline_root=staging_bucket,
        parameter_values={
            "input_csv": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
    )

    print("🚀 Launching FinCrime pipeline...")
    job.run(sync=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--gcs-input-uri", required=True)
    parser.add_argument("--export-uri", required=True)
    parser.add_argument("--model", required=True)

    args = parser.parse_args()

    run_pipeline(
        project=args.project,
        region=args.region,
        staging_bucket=args.staging_bucket,
        gcs_input_uri=args.gcs_input_uri,
        export_uri=args.export_uri,
        model=args.model,
    )
