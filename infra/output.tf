output "project_id" { value = var.project_id }
output "region" { value = var.region }

output "runtime_service_account_email" {
  value       = google_service_account.runtime.email
  description = "Service account used by the Cloud Run Job."
}

output "scheduler_service_account_email" {
  value       = google_service_account.scheduler.email
  description = "Service account used by Cloud Scheduler to invoke the job."
}

output "data_bucket_name" {
  value       = google_storage_bucket.ml_data.name
  description = "Bucket containing price/options/portfolio/ml_output data."
}

output "cloud_run_job_name" {
  value       = try(google_cloud_run_v2_job.daily_ml[0].name, null)
  description = "Legacy full daily ML Cloud Run Job (null when split mode enabled)."
}

output "scheduler_job_name" {
  value       = try(google_cloud_scheduler_job.daily_trigger[0].name, null)
  description = "Legacy scheduler trigger job (null when split mode enabled)."
}

output "refresh_cloud_run_job_name" {
  value       = try(google_cloud_run_v2_job.daily_ml_refresh[0].name, null)
  description = "Refresh-only Cloud Run Job (split mode)."
}

output "pipeline_cloud_run_job_name" {
  value       = try(google_cloud_run_v2_job.daily_ml_pipeline[0].name, null)
  description = "Pipeline-only Cloud Run Job (split mode)."
}

output "refresh_scheduler_job_name" {
  value       = try(google_cloud_scheduler_job.daily_refresh_trigger[0].name, null)
  description = "Refresh scheduler trigger (split mode)."
}

output "pipeline_scheduler_job_name" {
  value       = try(google_cloud_scheduler_job.daily_pipeline_trigger[0].name, null)
  description = "Pipeline scheduler trigger (split mode)."
}

output "dashboard_results_gcs_uri" {
  value       = "gs://${google_storage_bucket.ml_data.name}/ml_output"
  description = "Set ML_RESULTS_GCS_URI to this value in your dashboard environment."
}
