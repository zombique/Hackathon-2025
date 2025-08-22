
PROJECT_ID ?= your-project-id
REGION ?= us-central1
STAGING_BUCKET ?= gs://your-artifact-bucket
INPUT_URI ?= gs://your-transactions-bucket/transactions_sample.csv
EXPORT_URI ?= gs://your-artifact-bucket/exports

compile:
	python3 fincrime_pipeline.py

run:
	python3 run_pipeline.py \	  --project $(PROJECT_ID) \	  --region $(REGION) \	  --staging-bucket $(STAGING_BUCKET) \	  --input-uri $(INPUT_URI) \	  --export-uri $(EXPORT_URI)

deploy:
	cd infra && terraform init && terraform apply -auto-approve

destroy:
	cd infra && terraform destroy -auto-approve
