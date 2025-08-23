import os
import sys
import subprocess
from google.cloud import storage

def sync_from_gcs():
    """Download latest code + pipeline files from GCS bucket before running."""
    project_id = os.environ.get("PROJECT_ID") or sys.argv[sys.argv.index("--project")+1]
    staging_bucket = os.environ.get("STAGING_BUCKET") or sys.argv[sys.argv.index("--staging-bucket")+1]

    bucket_name = staging_bucket.replace("gs://", "").split("/")[0]
    prefix = "code/"

    print(f"✅ INFO: Syncing latest code from {staging_bucket}/{prefix} ...")
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    blobs = bucket.list_blobs(prefix=prefix)
    for blob in blobs:
        filename = blob.name.split("/")[-1]
        if filename:
            print(f"⬇️ Downloading {filename}")
            blob.download_to_filename(filename)

# run sync before pipeline execution
sync_from_gcs()

# --- continue with normal pipeline runner ---
from google.cloud import aiplatform

def run_pipeline(project, region, staging_bucket, gcs_input_uri, export_uri, model):
    job = aiplatform.PipelineJob(
        display_name="fincrime-pipeline",
        template_path="fincrime_pipeline.yaml",
        pipeline_root=staging_bucket,
        parameter_values={
            "gcs_input_uri": gcs_input_uri,
            "export_uri": export_uri,
            "model": model,
        },
    )
    job.run(sync=True)

if __name__ == "__main__":
    args = {k.split("=")[0].lstrip("--"): k.split("=")[1] for k in sys.argv[1:]}
    run_pipeline(
        project=args["project"],
        region=args["region"],
        staging_bucket=args["staging-bucket"],
        gcs_input_uri=args["gcs-input-uri"],
        export_uri=args["export-uri"],
        model=args["model"],
    )
