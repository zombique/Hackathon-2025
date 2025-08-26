# Business Sense Engine (Industry Match Validator)

A lightweight rules-first engine that validates whether two companies should reasonably be doing business together based on their SIC/NACE industry codes. It ingests transactions, enriches parties with industry data, applies a configurable relationship policy, and emits a verdict (Valid / Mismatch / Unknown) for each transaction.

> Perfect for AML/compliance triage, analyst assist, and data quality checks. Start simple with rules; plug in AI/ML later.

## ✨ **Key Features**

* **Transaction enrichment:** Joins originator/beneficiary to a fake company registry with sic_nace_code and industry.

* **Configurable policy:** Rule-map of which industries may transact (e.g., Semiconductor Manufacturing ↔ Chemical Manufacturing).

* **Deterministic output:** Valid, Mismatch, or Unknown per transaction with full columns for auditing.

* **Extensible:** Designed to add RAG, LLM scoring, and ML models without changing the core flow.

# 🧠 **Why this exists**

Compliance teams often rely on manual judgement to decide whether a payer/payee pairing is sensible. This project automates the first pass: _Is the relationship consistent with expected industry behavior?_ That signal reduces noise and speeds investigations.

# 🗂️ **Repository Structure**
```
business_sense_engine/
├─ data/
│  ├─ validatable_transactions.csv           # Sample transactions (originator/beneficiary + amounts)
│  ├─ fake_company_sic_nace_dataset.csv      # Fake registry: company_name → sic_nace_code, industry
│  └─ sample_sic_nace_codes.csv              # (Optional) Code → industry mapping
├─ output/
│  └─ validated_transactions.csv             # Results are written here
├─ src/
│  ├─ main.py                                # Entry point: loads, merges, validates, writes output
│  └─ rules.json                             # (Optional) Externalized ALLOWED_RELATIONS map
└─ README.md
```
> If `rules.json` isn’t present, `main.py` falls back to the built‑in `ALLOWED_RELATIONS` dictionary.

## 🚀 Getting Started

### **Prerequisites**

* Python 3.9+

* `pip` and (recommended) `venv`

### Setup

```bash
# From repo root
cd business_sense_engine

# 1) Create & activate a virtual environment
python -m venv .venv
# Windows
. .venv/Scripts/activate
# macOS/Linux
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt  # if present
# or minimal:
pip install pandas
```
### Run

```python src/main.py```

This will read the CSVs from `data/`, join the industries, apply the rules, and save `output/validated_transactions.csv`.

## 🧩 How it works (core logic)

1. Load data
   - `validatable_transactions.csv` with columns: `Originator_Name, Originator_SIC, Beneficiary_Name, Beneficiary_SIC, Amount, Currency, Transaction ID`
   - `fake_company_sic_nace_dataset.csv` with columns: `company_name, sic_nace_code, industry`
   - `sample_sic_nace_codes.csv` (optional reference)

2. Enrich: Left-join companies to transactions twice (for originator and beneficiary) to add `originator_industry` and `beneficiary_industry`.

3. Validate: For each row, evaluate `ALLOWED_RELATIONS`:

   - If either industry is missing → `Unknown`

   - If `(originator_industry → beneficiary_industry)` allowed → `Valid`

   - Otherwise → `Mismatch`

4. Write: Save the enriched file with `match_verdict`.

Example rule map (excerpt)
```json
{
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
```
Place as `src/rules.json` to override the defaults.

## 🧪 Sample input → output

**Input (transactions):** `data/validatable_transactions.csv` 
**Output (enriched):** `output/validated_transactions.csv` with extra columns:

   - `originator_sic`, `originator_industry`, `beneficiary_sic`, `beneficiary_industry`, `match_verdict`

> Tip: Filter `Mismatch` and `Unknown` in Excel/BI/Dashboard to show potential red flags.

## 🔌 Adding AI/ML (roadmap)

- **LLM Scoring (RAG):** Build a knowledge base of industry relationships from public sources; use an LLM to score plausibility → new column llm_score (0–1) + rationale.

- **Anomaly Model:** Train a simple classifier on historical labeled outcomes to predict sensible_vs_not. Start with Logistic Regression/XGBoost; graduate to Graph ML.

- **Feedback Loop:** Analysts correct verdicts in UI → captured as labels → nightly retrain → improved precision.

See `docs/ai_plan.md` (to be added) for step-by-step integration.

## ⚙️ Configuration

- `DATA_DIR` / `OUTPUT_DIR` can be adjusted in `src/main.py`.

- Replace sample CSVs with your own, keeping header names consistent.

- Externalize rules to `src/rules.json` for non-code updates.

## 🛡️ Security & Privacy

- The included datasets are **fake/synthetic**. Do **not** commit real customer data.

- If adapting to real data, ensure masking, access controls, and audit logging per your policy.

## 🤝 Contributing

1. Fork the repo

2. Create a branch: `git checkout -b feature/my-improvement`

3. Commit: `git commit -m "feat: add my improvement"`

4. Push & open a PR

For issues/ideas, open a GitHub Issue.

## 📄 License (TBD)

MIT (or your preferred license). Add a `LICENSE `file if not present.

## 📸 Screenshots (TBD)

Add screenshots of the dashboard, sample output, and the PPT visuals (Impact & Benefits) in `/docs/images` and embed them here.

## 🧭 Credits

Built during `Hackathon 2025` by the _**Daemon Mode**_ team.

