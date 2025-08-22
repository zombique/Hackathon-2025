terraform {
  required_providers { google = { source = "hashicorp/google", version = ">= 5.13" } }
}
provider "google" { project = var.project_id, region = var.region }

# Enable core services
resource "google_project_service" "services" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "cloudfunctions.googleapis.com",
    "artifactregistry.googleapis.com"
  ])
  project = var.project_id
  service = each.key
  disable_on_destroy = false
}

# Upload function source zip to existing artifact bucket
resource "google_storage_bucket_object" "function_zip" {
  name   = var.function_zip_object
  bucket = var.artifact_bucket
  source = "${path.module}/../function_src.zip"
  depends_on = [google_project_service.services]
}

# Cloud Function 2nd gen (Event-driven on GCS finalize)
resource "google_cloudfunctions2_function" "trigger" {
  name     = "fincrime-trigger"
  project  = var.project_id
  location = var.region

  build_config {
    runtime     = "python310"
    entry_point = "trigger_pipeline"
    source {
      storage_source {
        bucket = var.artifact_bucket
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    environment_variables = {
      PROJECT_ID     = var.project_id
      REGION         = var.region
      STAGING_BUCKET = var.artifact_bucket
      EXPORT_URI     = "gs://${var.artifact_bucket}/exports"
      MODEL          = var.model
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.storage.object.v1.finalized"
    resource       = var.transactions_bucket
  }
  depends_on = [google_project_service.services]
}

# Grant function SA roles to call Vertex AI and write to artifact bucket
data "google_cloudfunctions2_function" "fn" {
  name     = google_cloudfunctions2_function.trigger.name
  location = var.region
  depends_on = [google_cloudfunctions2_function.trigger]
}

resource "google_project_iam_member" "fn_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${data.google_cloudfunctions2_function.fn.service_config[0].service_account_email}"
}

resource "google_storage_bucket_iam_member" "fn_storage_admin" {
  bucket = var.artifact_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_cloudfunctions2_function.fn.service_config[0].service_account_email}"
}