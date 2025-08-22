import os
from google.cloud import aiplatform

def trigger_pipeline(event, context):
    project_id = os.environ["PROJECT_ID"]
    region     = os.environ.get("REGION", "us-central1")
    staging    = os.environ["STAGING_BUCKET"]
    export_uri = os.environ["EXPORT_URI"]
    model      = os.environ.get("MODEL", "gemini-1.5-flash")

    bucket = event.get("bucket")
    name   = event.get("name")
    if not bucket or not name:
        print("Invalid event structure")
        return

    # Only process CSV or Parquet
    if not (name.endswith(".csv") or name.endswith(".parquet")):
        print(f"Skipping non-supported object: {name}")
        return

    input_uri = f"gs://{bucket}/{name}"
    print(f"Launching pipeline for {input_uri}")

    aiplatform.init(project=project_id, location=region, staging_bucket=staging)

    job = aiplatform.PipelineJob(
        display_name="fincrime-auto-csv",
        pipeline_root=f"gs://{staging}/pipeline-root",
        pipeline_spec="fincrime_pipeline.yaml",
        parameter_values={
            "project": project_id,
            "location": region,
            "gcs_input_uri": input_uri,
            "gcs_export_uri": export_uri,
        },
    )
    job.run(sync=False)