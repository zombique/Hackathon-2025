# ML Pipeline

This repository contains a modular machine learning pipeline with separate functions for training, prediction, cleanup, and suspicious activity detection.

## Folder Structure

ml_pipeline/
├─ config.py # Global configuration settings
├─ cleanup/ # Scripts for cleaning data/resources
│ └─ cleanup.py
├─ infra/ # Infrastructure scripts/utilities
│ └─ infra.py
├─ predict_function/ # Prediction function scripts
│ ├─ main.py
│ └─ requirements.txt
├─ suspicious_function/ # Function to detect suspicious cases
│ ├─ main.py
│ └─ requirements.txt
├─ train_function/ # Model training scripts
│ ├─ main.py
│ ├─ requirements.txt
│ └─ pycache/
├─ pycache/ # Python bytecode cache (auto-generated)

###commands to deploy infra & functions
## move to root folder(ml_pipeline)

##create infra
python -m infra.infra

# deploy train cloud function
gcloud functions deploy train-model \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point train_model \
  --region us-central1 \
  --source train_function

# deploy predict cloud function
gcloud functions deploy predict-transaction \
  --runtime python310 \
  --trigger-resource sonic-totem-469814-q5-predict-data \
  --trigger-event google.storage.object.finalize \
  --entry-point predict_transaction \
  --region us-central1 \
  --source predict_function


# deploy  cloud function to show suspicious transactions
gcloud functions deploy suspicious-transactions \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point suspicious_transactions\
  --region us-central1 \
  --source suspicious_function


## cloud function URLS
train: https://us-central1-sonic-totem-469814-q5.cloudfunctions.net/train-model
predict: https://us-central1-sonic-totem-469814-q5.cloudfunctions.net/predict-transaction (runs automatic)
view: https://us-central1-sonic-totem-469814-q5.cloudfunctions.net/suspicious-transactions

##clean up script
python cleanup/cleanup.py