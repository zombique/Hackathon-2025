"""
Cloud Function: Train ML model for transaction validity

This function is triggered manually (HTTP).
It:
1. Loads the latest training CSV from the TRAIN_BUCKET into BigQuery (with explicit schema).
2. Trains or replaces the ML model using BigQuery ML.
"""

import json
from google.cloud import bigquery, storage

# 🔧 Inline configuration
PROJECT_ID = "sonic-totem-469814-q5"           # replace with your GCP project
BQ_DATASET = "transactions_dataset"      # BigQuery dataset created by infra
TRAINING_TABLE = "transactions_training" # Training table created by infra
MODEL_NAME = "transaction_validity_model"         # Model name
TRAIN_BUCKET = "sonic-totem-469814-q5-train-data"       # GCS bucket where training CSVs are uploaded


def train_model(request):
    """
    HTTP-triggered function that:
    - Loads CSV data from TRAIN_BUCKET into BigQuery training table (schema enforced).
    - Creates/updates a BigQuery ML logistic regression model.
    """

    try:
        storage_client = storage.Client()
        bq_client = bigquery.Client()

        dataset_id = f"{PROJECT_ID}.{BQ_DATASET}"
        table_id = f"{dataset_id}.{TRAINING_TABLE}"
        model_id = f"{dataset_id}.{MODEL_NAME}"

        # --- Pick latest file from bucket if none specified ---
        request_json = request.get_json(silent=True)
        file_name = None

        if request_json and "file_name" in request_json:
            file_name = request_json["file_name"]
        else:
            blobs = list(storage_client.list_blobs(TRAIN_BUCKET))
            if not blobs:
                return (json.dumps({
                    "status": "error",
                    "message": "No files found in training bucket"
                }), 400)
            blobs.sort(key=lambda b: b.updated, reverse=True)
            file_name = blobs[0].name

        uri = f"gs://{TRAIN_BUCKET}/{file_name}"
        print(f"🚀 Using training file: {uri}")

        # --- Load CSV into BigQuery training table with explicit schema ---
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField("transaction_id", "STRING"),
                bigquery.SchemaField("entity_a", "STRING"),
                bigquery.SchemaField("entity_b", "STRING"),
                bigquery.SchemaField("sector_a", "STRING"),
                bigquery.SchemaField("sector_b", "STRING"),
                bigquery.SchemaField("country_a", "STRING"),
                bigquery.SchemaField("country_b", "STRING"),
                bigquery.SchemaField("transaction_amount", "FLOAT64"),
                bigquery.SchemaField("transaction_type", "STRING"),
                bigquery.SchemaField("is_valid", "INT64"),
            ],
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            write_disposition="WRITE_APPEND"
        )
        load_job = bq_client.load_table_from_uri(uri, table_id, job_config=job_config)
        load_job.result()
        print(f"✅ Data loaded into {table_id}")

        # --- Train ML model ---
        train_query = f"""
        CREATE OR REPLACE MODEL `{model_id}`
        OPTIONS(
                model_type='logistic_reg',
                input_label_cols=['is_valid']
        ) AS
        SELECT
            entity_a,
            entity_b,
            sector_a,
            sector_b,
            country_a,
            country_b,
            transaction_amount,
            transaction_type,
            is_valid
        FROM `{table_id}`;
        """
        bq_client.query(train_query).result()
        print(f"🎉 Model `{model_id}` trained successfully!")

        return json.dumps({"status": "success", "file": uri, "model": model_id})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return (json.dumps({"status": "error", "message": str(e)}), 500)

