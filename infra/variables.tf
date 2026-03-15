variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "job_name" {
  type    = string
  default = "quantum-daily-ml"
}

variable "scheduler_job_name" {
  type    = string
  default = "quantum-daily-ml-trigger"
}

variable "split_jobs_enabled" {
  type    = bool
  default = false
}

variable "skip_price_refresh" {
  type        = bool
  default     = true
  description = "Set to true to skip Yahoo Finance price download (use when Cloud Run IP is rate-limited)."
}

variable "refresh_job_name" {
  type    = string
  default = "quantum-daily-ml-refresh"
}

variable "pipeline_job_name" {
  type    = string
  default = "quantum-daily-ml-pipeline"
}

variable "refresh_scheduler_job_name" {
  type    = string
  default = "quantum-daily-ml-refresh-trigger"
}

variable "pipeline_scheduler_job_name" {
  type    = string
  default = "quantum-daily-ml-pipeline-trigger"
}

variable "runtime_service_account_id" {
  type    = string
  default = "quantum-ml-runner"
}

variable "scheduler_service_account_id" {
  type    = string
  default = "quantum-ml-scheduler"
}

variable "bucket_name" {
  type        = string
  description = "Global-unique GCS bucket name for pipeline data and outputs."

  validation {
    condition     = trimspace(var.bucket_name) != "" && !startswith(var.bucket_name, "your-unique-")
    error_message = "bucket_name must be set to a real GCS bucket name, not the example placeholder."
  }
}

variable "container_image" {
  type        = string
  description = "Container image URI for the Cloud Run Job (Artifact Registry recommended)."
}

variable "scheduler_cron" {
  type    = string
  default = "20 22 * * 1-5"
}

variable "scheduler_time_zone" {
  type    = string
  default = "America/New_York"
}

variable "refresh_scheduler_cron" {
  type    = string
  default = "20 22 * * 1-5"
}

variable "pipeline_scheduler_cron" {
  type    = string
  default = "50 22 * * 1-5"
}

variable "price_refresh_days" {
  type    = number
  default = 7
}

variable "price_backfill_days" {
  type    = number
  default = 365
}

variable "pipeline_lookback_days" {
  type    = number
  default = 365
}

variable "pipeline_horizons" {
  type    = list(number)
  default = [5, 10]
}

variable "pipeline_categories" {
  type    = list(string)
  default = ["long_premium"]
}

variable "pipeline_topk" {
  type    = number
  default = 3
}

variable "pipeline_min_train_days" {
  type    = number
  default = 80
}

variable "pipeline_test_days" {
  type    = number
  default = 20
}

variable "pipeline_step_days" {
  type    = number
  default = 20
}

variable "pipeline_run_max_minutes" {
  type    = number
  default = 45
}

variable "pipeline_lgbm_jobs" {
  type    = number
  default = 1
}

variable "job_timeout_seconds" {
  type    = number
  default = 7200
}

variable "refresh_job_timeout_seconds" {
  type    = number
  default = 5400
}

variable "pipeline_job_timeout_seconds" {
  type    = number
  default = 10800
}

variable "job_cpu" {
  type    = string
  default = "2"
}

variable "job_memory" {
  type    = string
  default = "8Gi"
}

variable "refresh_job_cpu" {
  type    = string
  default = "2"
}

variable "refresh_job_memory" {
  type    = string
  default = "8Gi"
}

variable "pipeline_job_cpu" {
  type    = string
  default = "4"
}

variable "pipeline_job_memory" {
  type    = string
  default = "16Gi"
}

variable "job_max_retries" {
  type    = number
  default = 1
}
