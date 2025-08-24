import os
import pickle
import numpy as np
import pandas as pd

# Define the model directory where the model.pkl file is located
# Vertex AI automatically sets this environment variable
MODEL_DIR = os.getenv('AIP_MODEL_DIR')  # fallback for local testing

model = None
kmeans = None

def load_model():
    """
    Loads the pre-trained scikit-learn model from the model directory.
    This function is called once when the container starts.
    """
    global model, kmeans
    model_path = os.path.join(MODEL_DIR, 'model.pkl')
    with open(model_path, 'rb') as f:
        assets = pickle.load(f)
        model = assets['model']  # sentence transformer model
        kmeans = assets['kmeans']  # clustering model
    print("Model loaded successfully!")

def predict(instances):
    """
    Handles prediction requests from Vertex AI.
    Args:
        instances (list): List of prediction inputs
    Returns:
        dict: Prediction results
    """
    global model, kmeans
    
    if model is None or kmeans is None:
        load_model()
    
    predictions = []
    
    for instance in instances:
        # Each instance should be [desc1, desc2]
        desc1, desc2 = instance[0], instance[1]
        
        # Embed both descriptions
        X = model.encode([desc1, desc2])
        
        # Predict cluster ID for both
        cl1, cl2 = kmeans.predict(X)
        
        # Return result
        same_cluster = bool(cl1 == cl2)
        result = {
            "same_cluster": same_cluster,
            "cluster1": int(cl1),
            "cluster2": int(cl2)
        }
        predictions.append(result)
    
    return {"predictions": predictions}

# This is required for Vertex AI custom container
def handler(request):
    """
    Entry point for Vertex AI predictions
    """
    instances = request.get('instances', [])
    return predict(instances)

if __name__ == '__main__':
    # Example usage for local testing:
    #load_model()
    #desc_a = "Crude Petroleum and Natural Gas"
    #desc_b = "Natural Gas Liquids"
    
    # Test the prediction function
    #test_instances = [[desc_a, desc_b]]
    #result = predict(test_instances)
    #print("Test result:", result)
    pass