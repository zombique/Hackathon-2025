import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

# Build relative paths
base_dir = os.path.dirname(__file__)  # directory where main.py lives
data_dir = os.path.join(base_dir, "..", "data")
output_dir = os.path.join(base_dir, "..", "output")
ml_train_data_dir = os.path.join(base_dir, "..", "training_data")

# Load CSVs
transactions_df = pd.read_csv(os.path.join(data_dir, "validatable_transactions.csv"))
companies_df = pd.read_csv(os.path.join(data_dir, "fake_company_sic_nace_dataset.csv"))
industry_df = pd.read_csv(os.path.join(data_dir, "sample_sic_nace_codes.csv"))

print(transactions_df.head())
print(companies_df.head())

# Load your processed transaction data
df_train_model = pd.read_csv(os.path.join(output_dir, "validated_transactions.csv"))
# Combine industry fields as a single input string
df_train_model["combined_industries"] = df_train_model["originator_industry"] + " <-> " + df_train_model["beneficiary_industry"]

# Split data
X = df_train_model["combined_industries"]
y = df_train_model["match_verdict"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Define pipeline: TF-IDF + Logistic Regression
pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', LogisticRegression(max_iter=1000))
])

# Train model
pipeline.fit(X_train, y_train)

# Save model if needed
joblib.dump(pipeline, os.path.join(ml_train_data_dir,"industry_match_model.pkl"))

# Load model
model = joblib.load(os.path.join(ml_train_data_dir,"industry_match_model.pkl"))    

# --- Merge originator and beneficiary industries ---
companies = companies_df.rename(columns={"company_name": "Originator_Name"})
trxn = transactions_df.merge(companies, on="Originator_Name", how="left") \
                 .rename(columns={"sic_nace_code": "originator_sic", "industry": "originator_industry"})

companies = companies.rename(columns={"Originator_Name": "Beneficiary_Name"})
trxn = trxn.merge(companies, on="Beneficiary_Name", how="left") \
       .rename(columns={"sic_nace_code": "beneficiary_sic", "industry": "beneficiary_industry"})

# Predict
trxn["ml_verdict"] = model.predict(trxn["originator_industry"] + " <-> " + trxn["beneficiary_industry"])

# --- Save result ---
trxn.to_csv(os.path.join(output_dir, "validated_transactions.csv"), index=False)
print("Done! Output saved to validated_transactions.csv")
