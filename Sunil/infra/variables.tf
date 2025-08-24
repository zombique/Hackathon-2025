variable "project_id" { type = string }
variable "region"     { type = string  default = "us-central1" }
variable "artifact_bucket"  { type = string  description = "Existing bucket used for artifacts and exports" }
variable "transactions_bucket" { type = string description = "Existing bucket that receives incoming CSVs" }
variable "function_zip_object" { type = string default = "function_src.zip" }
variable "model" { type = string default = "gemini-1.5-flash" }