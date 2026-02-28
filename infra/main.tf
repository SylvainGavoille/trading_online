provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  mount_path = "/mnt/quantum"
}

resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com"
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "ml_data" {
  name                        = var.bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.services]
}

resource "google_service_account" "runtime" {
  account_id   = var.runtime_service_account_id
  display_name = "Quantum ML pipeline runtime"
  description  = "Runs the daily Cloud Run Job for ML refresh and pipeline."

  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "runtime_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_service_account" "scheduler" {
  account_id   = var.scheduler_service_account_id
  display_name = "Quantum ML scheduler invoker"
  description  = "Invokes Cloud Run Job runs on schedule."

  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "scheduler_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_service_account_iam_member" "scheduler_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_vpc_access_connector" "serverless" {
  name          = var.vpc_connector_name
  project       = var.project_id
  region        = var.region
  network       = var.vpc_network
  ip_cidr_range = var.vpc_connector_cidr

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_job" "daily_ml" {
  provider = google-beta
  name     = var.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "${var.job_timeout_seconds}s"
      max_retries     = var.job_max_retries

      vpc_access {
        connector = google_vpc_access_connector.serverless.id
        egress    = "PRIVATE_RANGES_ONLY"
      }

      volumes {
        name = "ml-data"
        gcs {
          bucket    = google_storage_bucket.ml_data.name
          read_only = false
        }
      }

      containers {
        image   = var.container_image
        command = ["uv", "run", "python", "src/ml/gcp_daily_job.py"]
        args = [
          "--price_root", "${local.mount_path}/price_historical",
          "--options_root", "${local.mount_path}/options_snapshot",
          "--portfolio_root", "${local.mount_path}/portfolio_daily",
          "--out_dir", "${local.mount_path}/ml_output",
          "--price_days", tostring(var.price_refresh_days),
          "--lookback_days", tostring(var.pipeline_lookback_days),
          "--topk", tostring(var.pipeline_topk),
          "--min_train_days", tostring(var.pipeline_min_train_days),
          "--test_days", tostring(var.pipeline_test_days),
          "--step_days", tostring(var.pipeline_step_days),
          "--horizons", join(",", [for h in var.pipeline_horizons : tostring(h)]),
          "--categories", join(",", var.pipeline_categories),
          "--allow_missing_symbol_db"
        ]

        dynamic "env" {
          for_each = var.ibkr_tws_endpoint != "" ? [var.ibkr_tws_endpoint] : []
          content {
            name  = "IBKR_TWS_ENDPOINT"
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.ibkr_port > 0 ? [var.ibkr_port] : []
          content {
            name  = "IBKR_PORT"
            value = tostring(env.value)
          }
        }

        dynamic "env" {
          for_each = var.ibkr_username_secret_id != "" ? [var.ibkr_username_secret_id] : []
          content {
            name = "IBKR_USERNAME"
            value_source {
              secret_key_ref {
                secret  = env.value
                version = var.ibkr_username_secret_version
              }
            }
          }
        }

        dynamic "env" {
          for_each = var.ibkr_password_secret_id != "" ? [var.ibkr_password_secret_id] : []
          content {
            name = "IBKR_PASSWORD"
            value_source {
              secret_key_ref {
                secret  = env.value
                version = var.ibkr_password_secret_version
              }
            }
          }
        }

        env {
          name  = "IBKR_SQLITE_PATH"
          value = "${local.mount_path}/ibkr_us.sqlite"
        }

        resources {
          limits = {
            cpu    = var.job_cpu
            memory = var.job_memory
          }
        }

        volume_mounts {
          name       = "ml-data"
          mount_path = local.mount_path
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.runtime_storage_admin,
    google_project_iam_member.runtime_secret_accessor,
    google_vpc_access_connector.serverless,
    google_project_service.services
  ]
}

resource "google_cloud_scheduler_job" "daily_trigger" {
  name        = var.scheduler_job_name
  description = "Daily trigger for Quantum ML Cloud Run job"
  schedule    = var.scheduler_cron
  time_zone   = var.scheduler_time_zone
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_ml.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job.daily_ml,
    google_project_iam_member.scheduler_run_developer,
    google_service_account_iam_member.scheduler_act_as_runtime
  ]
}
