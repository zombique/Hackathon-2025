"""
Infrastructure setup script for ML Transaction Pipeline.
"""

import sys, os
from google.cloud import storage, bigquery

# Add project root to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def create_bucket(bucket_name, location="US-CENTRAL1"):
    client = storage.Client()
    try:
        bucket = client.create_bucket(bucket_name, location=location)
        print(f"✅ Bucket {bucket_name} created.")
    except Exception as e:
        if "You already own this bucket" in str(e) or "Conflict" in str(e):
            print(f"⚠️ Bucket {bucket_name} already exists, skipping...")
        else:
            raise

def create_dataset(dataset_id):
    client = bigquery.Client()
    dataset_ref = bigquery.Dataset(dataset_id)
    dataset_ref.location = config.REGION
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"✅ Dataset {dataset_id} ready.")

def create_training_table(dataset_id, table_name):
    client = bigquery.Client()
    schema = [
        bigquery.SchemaField("transaction_id", "STRING"),
        bigquery.SchemaField("entity_a", "STRING"),
        bigquery.SchemaField("entity_b", "STRING"),
        bigquery.SchemaField("sector_a", "STRING"),
        bigquery.SchemaField("sector_b", "STRING"),
        bigquery.SchemaField("country_a", "STRING"),
        bigquery.SchemaField("country_b", "STRING"),
        bigquery.SchemaField("transaction_amount", "FLOAT"),
        bigquery.SchemaField("transaction_type", "STRING"),
        bigquery.SchemaField("is_valid", "INTEGER"),
    ]
    table_id = f"{dataset_id}.{table_name}"
    client.create_table(bigquery.Table(table_id, schema=schema), exists_ok=True)
    print(f"✅ Training table {table_id} ready.")

def create_prediction_table(dataset_id, table_name):
    client = bigquery.Client()
    schema = [
        bigquery.SchemaField("transaction_id", "STRING"),
        bigquery.SchemaField("entity_a", "STRING"),
        bigquery.SchemaField("entity_b", "STRING"),
        bigquery.SchemaField("sector_a", "STRING"),
        bigquery.SchemaField("sector_b", "STRING"),
        bigquery.SchemaField("predicted_is_valid", "BOOL"),
        bigquery.SchemaField("predicted_probability", "FLOAT", mode="NULLABLE"),
    ]
    table_id = f"{dataset_id}.{table_name}"
    client.create_table(bigquery.Table(table_id, schema=schema), exists_ok=True)
    print(f"✅ Prediction table {table_id} ready.")

if __name__ == "__main__":
    print("🚀 Starting infrastructure setup...")
    create_bucket(config.TRAIN_BUCKET)
    create_bucket(config.PREDICT_BUCKET)
    dataset_id = f"{config.PROJECT_ID}.{config.BQ_DATASET}"
    create_dataset(dataset_id)
    create_training_table(dataset_id, config.TRAINING_TABLE)
    create_prediction_table(dataset_id, config.PREDICTION_TABLE)
    print("🎉 Infrastructure setup complete.")
