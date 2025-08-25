import os
import pandas as pd
import pickle
import numpy as np
from google.cloud import storage
from tempfile import NamedTemporaryFile

# Initialize GCS client
storage_client = storage.Client()

# Buckets and model info
MODEL_BUCKET = "rc-hackathon-model"
MODEL_FILE = "TransactionAnalysis_mlp.pkl"
OUTPUT_BUCKET = "rc-hackathon-model"  # bucket must exist
OUTPUT_FOLDER = "output"  # folder inside the bucket

def preprocess_features(df):
    """
    Compute features expected by the model:
    - amount_log: log-transformed amount
    - same_industry: flag if originator_id == beneficiary_id
    """
    print("Preprocessing features...")
    
    if 'amount' in df.columns:
        df['amount_log'] = np.log1p(df['amount'])
        print("Created 'amount_log'")
    else:
        raise KeyError("'amount' column is missing in CSV")
    
    if 'originator_id' in df.columns and 'beneficiary_id' in df.columns:
        df['same_industry'] = (df['originator_id'] == df['beneficiary_id']).astype(int)
        print("Created 'same_industry'")
    else:
        raise KeyError("'originator_id' or 'beneficiary_id' column is missing in CSV")
    
    return df

def predict_transaction(data, model):
    """
    Automatically select features based on the model.
    """
    print("Selecting features for prediction...")
    
    if hasattr(model, 'feature_names_in_'):
        features = list(model.feature_names_in_)
        print(f"Model expects features: {features}")
    else:
        # fallback: all numeric columns
        features = data.select_dtypes(include=['number']).columns.tolist()
        print(f"Model feature_names_in_ missing. Using numeric columns: {features}")
    
    X = data[features]
    data['prediction'] = model.predict(X)
    print("Prediction complete")
    return data

def load_model_from_gcs(bucket_name, model_file):
    print(f"Loading model from gs://{bucket_name}/{model_file}")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(model_file)
    
    with NamedTemporaryFile() as temp_file:
        blob.download_to_filename(temp_file.name)
        model = pickle.load(open(temp_file.name, 'rb'))
    
    print("Model loaded successfully")
    return model

def process_transaction_file(event, context):
    """
    Triggered by a change to a GCS bucket.
    """
    file_name = event['name']
    bucket_name = event['bucket']

    if bucket_name != "rc-hackathon-txn":
        print(f"Ignoring file from bucket {bucket_name}")
        return

    print(f"Processing file: {file_name} from bucket: {bucket_name}")
    
    # Download uploaded transaction file
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    with NamedTemporaryFile() as temp_file:
        blob.download_to_filename(temp_file.name)
        df = pd.read_csv(temp_file.name)
        print(f"Downloaded file, shape: {df.shape}")
    
    # Preprocess features (adds amount_log & same_industry)
    df = preprocess_features(df)
    
    # Load model
    model = load_model_from_gcs(MODEL_BUCKET, MODEL_FILE)
    
    # Predict
    df_pred = predict_transaction(df, model)
    
    # Remove engineering-only columns from output
    drop_cols = ['amount_log', 'same_industry']
    df_pred = df_pred.drop(columns=[c for c in drop_cols if c in df_pred.columns])
    
    # Ensure transaction_id is included (if present in input)
    if 'transaction_id' in df.columns:
        keep_cols = ['transaction_id'] + [c for c in df_pred.columns if c != 'transaction_id']
        df_pred = df_pred[keep_cols]
    
    # Save result to output bucket
    output_blob_name = f"{OUTPUT_FOLDER}/predicted_{file_name}"  # include folder in blob path
    output_bucket = storage_client.bucket(OUTPUT_BUCKET)
    output_blob = output_bucket.blob(output_blob_name)
    
    with NamedTemporaryFile() as temp_output:
        df_pred.to_csv(temp_output.name, index=False)
        output_blob.upload_from_filename(temp_output.name)
    
    print(f"Predicted file saved to gs://{OUTPUT_BUCKET}/{output_blob_name}")
