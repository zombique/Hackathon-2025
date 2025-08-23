"""
Shared configuration for ML pipeline
"""

# Project and region
PROJECT_ID = "sonic-totem-469814-q5"
REGION = "us-central1"

# GCS Buckets
TRAIN_BUCKET = "sonic-totem-469814-q5-train-data"
PREDICT_BUCKET = "sonic-totem-469814-q5-predict-data"

# BigQuery
BQ_DATASET = "transactions_dataset"
TRAINING_TABLE = "transactions_training"
PREDICTION_TABLE = "transactions_predictions"
MODEL_NAME = "transaction_validity_model"
