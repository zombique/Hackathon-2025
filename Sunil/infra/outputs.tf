output "artifact_bucket" { value = var.artifact_bucket }
output "transactions_bucket" { value = var.transactions_bucket }
output "function_service_account" { value = data.google_cloudfunctions2_function.fn.service_config[0].service_account_email }