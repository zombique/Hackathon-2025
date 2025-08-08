import os
import pandas as pd

# Build relative paths
base_dir = os.path.dirname(__file__)  # directory where main.py lives
data_dir = os.path.join(base_dir, "..", "data")
output_dir = os.path.join(base_dir, "..", "output")

# Load CSVs
transactions_df = pd.read_csv(os.path.join(data_dir, "validatable_transactions.csv"))
companies_df = pd.read_csv(os.path.join(data_dir, "fake_company_sic_nace_dataset.csv"))
industry_df = pd.read_csv(os.path.join(data_dir, "sample_sic_nace_codes.csv"))

print(transactions_df.head())
print(companies_df.head())

# --- Merge originator and beneficiary industries ---
companies = companies_df.rename(columns={"company_name": "Originator_Name"})
trxn = transactions_df.merge(companies, on="Originator_Name", how="left") \
                 .rename(columns={"sic_nace_code": "originator_sic", "industry": "originator_industry"})

companies = companies.rename(columns={"Originator_Name": "Beneficiary_Name"})
trxn = trxn.merge(companies, on="Beneficiary_Name", how="left") \
       .rename(columns={"sic_nace_code": "beneficiary_sic", "industry": "beneficiary_industry"})

# --- Rule-based matching logic ---
ALLOWED_RELATIONS = {
    "Semiconductor Manufacturing": ["Metal Product Manufacturing", "Chemical Manufacturing"],
    "Chemical Manufacturing": ["Hospital Activities", "Semiconductor Manufacturing"],
    "Metal Product Manufacturing": ["Machinery Repair", "Semiconductor Manufacturing"],
    "Hospital Activities": ["Chemical Manufacturing"],
    "Beverage Production": ["Wheat Farming"],
    "Machinery Repair": ["Metal Product Manufacturing"],
    "Wheat Farming": ["Beverage Production"],
    "Motor Vehicle Wholesale": ["Semiconductor Manufacturing", "Machinery Repair"],
    "Business Consulting": ["Semiconductor Manufacturing", "Chemical Manufacturing"],
    "Advertising Agencies": ["Business Consulting"],
    "Cleaning Services": ["Hospital Activities", "Business Consulting"]
}
# Extend as needed or create a JASON file.

def validate_match(ind1, ind2):
    if pd.isna(ind1) or pd.isna(ind2):
        return "Unknown"
    elif ind2 in ALLOWED_RELATIONS.get(ind1, []):
        return "Valid"
    else:
        return "Mismatch"

trxn["match_verdict"] = trxn.apply(
    lambda row: validate_match(row["originator_industry"], row["beneficiary_industry"]),
    axis=1
)

# --- Save result ---
trxn.to_csv(os.path.join(output_dir, "validated_transactions.csv"), index=False)
print("Done! Output saved to validated_transactions.csv")
