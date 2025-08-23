import functions_framework
from google.cloud import bigquery

# ------------------------
# Hardcoded configs
# ------------------------
PROJECT_ID = "sonic-totem-469814-q5"
BQ_DATASET = "transactions_dataset"
PREDICTION_TABLE = "transactions_predictions"
STAGING_TABLE = "transactions_prediction_staging"
MODEL_NAME = "transaction_validity_model"

bq_client = bigquery.Client()


# ------------------------
# Function A: Predict
# Triggered by file upload
# ------------------------
@functions_framework.cloud_event
def predict_transaction(cloud_event):
    """
    Triggered when a CSV is uploaded to prediction bucket.
    Loads file into staging table, runs ML.PREDICT,
    saves results into predictions table.
    """
    try:
        data = cloud_event.data
        bucket = data["bucket"]
        name = data["name"]

        gcs_uri = f"gs://{bucket}/{name}"
        print(f"New file uploaded: {gcs_uri}")

        staging_table_id = f"{PROJECT_ID}.{BQ_DATASET}.{STAGING_TABLE}"
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
            ],
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            write_disposition="WRITE_TRUNCATE",
        )

        load_job = bq_client.load_table_from_uri(gcs_uri, staging_table_id, job_config=job_config)
        load_job.result()
        print(f"Loaded file into staging table: {staging_table_id}")

        model_id = f"{PROJECT_ID}.{BQ_DATASET}.{MODEL_NAME}"
        prediction_table_id = f"{PROJECT_ID}.{BQ_DATASET}.{PREDICTION_TABLE}"

        predict_query = f"""
        CREATE OR REPLACE TABLE `{prediction_table_id}` AS
        SELECT
          transaction_id,
          entity_a,
          entity_b,
          sector_a,
          sector_b,
          country_a,
          country_b,
          transaction_amount,
          transaction_type,
          predicted_is_valid,
          predicted_is_valid_probs
        FROM ML.PREDICT(
          MODEL `{model_id}`,
          TABLE `{staging_table_id}`
        );
        """

        query_job = bq_client.query(predict_query)
        query_job.result()
        print(f"Predictions written to {prediction_table_id}")

        return {"status": "success", "message": f"Predictions stored in {prediction_table_id}"}

    except Exception as e:
        print(f"Error during prediction: {str(e)}")
        return {"status": "error", "message": str(e)}


