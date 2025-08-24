import pandas as pd
import random
import uuid
from faker import Faker

fake = Faker()

# --- Reference data ---
countries = [
    ("US", "USD"), ("GB", "GBP"), ("DE", "EUR"),
    ("IN", "INR"), ("AE", "AED"), ("NG", "NGN"),
    ("RU", "RUB"), ("CN", "CNY"), ("BR", "BRL")
]

# High-risk countries (for AML)
high_risk_countries = ["NG", "RU", "CN"]

# Sample SIC/NACE codes
sic_codes = {
    "0111": "Wheat Farming",
    "6021": "National Commercial Banks",
    "7372": "Software Development",
    "7999": "Tourism Services",
    "5122": "Drugs and Sundries",
    "1311": "Oil & Gas Extraction",
    "6211": "Security Brokers"
}

# Generate synthetic transactions
def generate_transaction(label=None):
    txn_id = str(uuid.uuid4())
    amount = round(random.uniform(50, 100000), 2)
    txn_date = fake.date_time_this_year()

    origin_country, origin_ccy = random.choice(countries)
    bene_country, bene_ccy = random.choice(countries)

    origin_sic = random.choice(list(sic_codes.keys()))
    bene_sic = random.choice(list(sic_codes.keys()))

    txn = {
        "transaction_id": txn_id,
        "transaction_date": txn_date,
        "amount": amount,
        "currency": origin_ccy,
        "originator_account": fake.iban(),
        "originator_name": fake.company(),
        "originator_country": origin_country,
        "originator_sic": origin_sic,
        "beneficiary_account": fake.iban(),
        "beneficiary_name": fake.company(),
        "beneficiary_country": bene_country,
        "beneficiary_sic": bene_sic,
        "channel": random.choice(["SWIFT", "SEPA", "RTGS", "NEFT"]),
        "is_sanctioned": 0,
        "label": label if label is not None else 0  # default: non-suspicious
    }
    return txn

# --- Suspicious pattern injectors ---
def generate_suspicious_transactions(n=200):
    txns = []
    for _ in range(n):
        txn = generate_transaction(label=1)

        pattern = random.choice(["layering", "structuring", "high_risk_corridor"])

        if pattern == "layering":
            txn["amount"] = round(random.uniform(5000, 15000), 2)
            txn["channel"] = "SWIFT"

        elif pattern == "structuring":
            txn["amount"] = random.choice([9500, 9700, 9900])  # under reporting threshold
            txn["originator_account"] = txn["beneficiary_account"]  # same account used

        elif pattern == "high_risk_corridor":
            txn["originator_country"] = random.choice(high_risk_countries)
            txn["beneficiary_country"] = "US"

        # Add some sanctioned parties
        if random.random() < 0.1:
            txn["is_sanctioned"] = 1

        txns.append(txn)
    return txns

# --- Generate dataset ---
normal_txns = [generate_transaction(label=0) for _ in range(1800)]
suspicious_txns = generate_suspicious_transactions(400)

df = pd.DataFrame(normal_txns + suspicious_txns)

# Save for BigQuery upload
df.to_csv("transactions_enriched.csv", index=False)
print("✅ transactions_enriched.csv generated with", len(df), "rows")
