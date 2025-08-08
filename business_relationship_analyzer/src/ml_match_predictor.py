import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
import joblib

# --- Config ---
DATA_FILE = os.path.join("..", "output", "validated_transactions.csv")
MODEL_OUTPUT_PATH = os.path.join("..", "output", "industry_match_model.pkl")
PREDICTION_OUTPUT_PATH = os.path.join("..", "output", "ml_validated_transactions.csv")


def load_and_prepare_data(data_file):
    print("[INFO] Loading data...")
    df = pd.read_csv(data_file)

    # Drop missing industry info
    df = df.dropna(subset=["originator_industry", "beneficiary_industry", "match_verdict"])

    # Combine industries into a single feature
    df["combined_industries"] = df["originator_industry"] + " <-> " + df["beneficiary_industry"]
    return df


def train_model(df):
    print("[INFO] Training model...")
    X = df["combined_industries"]
    y = df["match_verdict"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    # Simple pipeline: TF-IDF + Logistic Regression
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer()),
        ('clf', LogisticRegression(max_iter=1000))
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    print("\n[INFO] Model performance on test data:")
    print(classification_report(y_test, y_pred))

    return pipeline


def apply_model(model, df):
    print("[INFO] Applying model to all transactions...")
    df["ml_verdict"] = model.predict(df["combined_industries"])
    return df


def save_outputs(model, df):
    print("[INFO] Saving model and predictions...")
    joblib.dump(model, MODEL_OUTPUT_PATH)
    df.to_csv(PREDICTION_OUTPUT_PATH, index=False)
    print(f"[INFO] Model saved to: {MODEL_OUTPUT_PATH}")
    print(f"[INFO] Predictions saved to: {PREDICTION_OUTPUT_PATH}")


def main():
    df = load_and_prepare_data(DATA_FILE)
    model = train_model(df)
    df_with_preds = apply_model(model, df)
    save_outputs(model, df_with_preds)


if __name__ == "__main__":
    main()
