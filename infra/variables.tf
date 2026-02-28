variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "vpc_network" {
  type    = string
  default = "default"
}

variable "vpc_subnetwork" {
  type    = string
  default = ""
}

variable "vpc_connector_name" {
  type    = string
  default = "quantum-connector"
}

variable "vpc_connector_cidr" {
  type    = string
  default = "10.8.0.0/28"
}

variable "job_name" {
  type    = string
  default = "quantum-daily-ml"
}

variable "scheduler_job_name" {
  type    = string
  default = "quantum-daily-ml-trigger"
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
}

variable "container_image" {
  type        = string
  description = "Container image URI for the Cloud Run Job (Artifact Registry recommended)."
}

variable "ibkr_tws_endpoint" {
  type        = string
  default     = ""
  description = "Optional IB Gateway/TWS host reachable from Cloud Run (private IP or DNS). Empty disables override."
}

variable "ibkr_port" {
  type        = number
  default     = 0
  description = "Optional IB Gateway/TWS port. Set 4002/4001/7497/7496. 0 disables override."
}

variable "ibkr_username_secret_id" {
  type        = string
  default     = ""
  description = "Optional Secret Manager secret ID containing IBKR username."
}

variable "ibkr_password_secret_id" {
  type        = string
  default     = ""
  description = "Optional Secret Manager secret ID containing IBKR password."
}

variable "ibkr_username_secret_version" {
  type        = string
  default     = "latest"
  description = "Secret version for ibkr_username_secret_id."
}

variable "ibkr_password_secret_version" {
  type        = string
  default     = "latest"
  description = "Secret version for ibkr_password_secret_id."
}

variable "scheduler_cron" {
  type    = string
  default = "20 22 * * 1-5"
}

variable "scheduler_time_zone" {
  type    = string
  default = "America/New_York"
}

variable "price_refresh_days" {
  type    = number
  default = 7
}

variable "pipeline_lookback_days" {
  type    = number
  default = 365
}

variable "pipeline_horizons" {
  type    = list(number)
  default = [2, 5, 10, 21]
}

variable "pipeline_categories" {
  type    = list(string)
  default = ["long_premium", "short_premium"]
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

variable "job_timeout_seconds" {
  type    = number
  default = 7200
}

variable "job_cpu" {
  type    = string
  default = "2"
}

variable "job_memory" {
  type    = string
  default = "8Gi"
}

variable "job_max_retries" {
  type    = number
  default = 1
}
