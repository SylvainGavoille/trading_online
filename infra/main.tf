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
    "vpcaccess.googleapis.com",
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

resource "google_cloud_run_v2_job" "daily_ml" {
  provider = google-beta
  count    = var.split_jobs_enabled ? 0 : 1
  name     = var.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "${var.job_timeout_seconds}s"
      max_retries     = var.job_max_retries

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
          "--price_backfill_days", tostring(var.price_backfill_days),
          "--lookback_days", tostring(var.pipeline_lookback_days),
          "--topk", tostring(var.pipeline_topk),
          "--min_train_days", tostring(var.pipeline_min_train_days),
          "--test_days", tostring(var.pipeline_test_days),
          "--step_days", tostring(var.pipeline_step_days),
          "--horizons", join(",", [for h in var.pipeline_horizons : tostring(h)]),
          "--categories", join(",", var.pipeline_categories),
          "--pipeline_horizons", join(",", [for h in var.pipeline_horizons : tostring(h)]),
          "--pipeline_categories", join(",", var.pipeline_categories),
          "--pipeline_lgbm_jobs", tostring(var.pipeline_lgbm_jobs),
          "--pipeline_max_minutes", tostring(var.pipeline_run_max_minutes),
          "--mode", "full",
          "--allow_missing_symbol_db"
        ]

        env {
          name  = "IBKR_SQLITE_PATH"
          value = "${local.mount_path}/ibkr_us.sqlite"
        }
        env {
          name  = "GCS_MOUNT_PATH"
          value = local.mount_path
        }
        env {
          name  = "GCS_DATA_URI"
          value = "gs://${var.bucket_name}"
        }
        env {
          name  = "SKIP_PRICE_REFRESH"
          value = var.skip_price_refresh ? "true" : "false"
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
    google_project_service.services
  ]
}

resource "google_cloud_run_v2_job" "daily_ml_refresh" {
  provider = google-beta
  count    = var.split_jobs_enabled ? 1 : 0
  name     = var.refresh_job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "${var.refresh_job_timeout_seconds}s"
      max_retries     = var.job_max_retries

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
          "--price_backfill_days", tostring(var.price_backfill_days),
          "--lookback_days", tostring(var.pipeline_lookback_days),
          "--topk", tostring(var.pipeline_topk),
          "--min_train_days", tostring(var.pipeline_min_train_days),
          "--test_days", tostring(var.pipeline_test_days),
          "--step_days", tostring(var.pipeline_step_days),
          "--horizons", join(",", [for h in var.pipeline_horizons : tostring(h)]),
          "--categories", join(",", var.pipeline_categories),
          "--mode", "refresh_only",
          "--allow_missing_symbol_db"
        ]

        env {
          name  = "IBKR_SQLITE_PATH"
          value = "${local.mount_path}/ibkr_us.sqlite"
        }
        env {
          name  = "GCS_MOUNT_PATH"
          value = local.mount_path
        }
        env {
          name  = "GCS_DATA_URI"
          value = "gs://${var.bucket_name}"
        }
        env {
          name  = "SKIP_PRICE_REFRESH"
          value = var.skip_price_refresh ? "true" : "false"
        }

        resources {
          limits = {
            cpu    = var.refresh_job_cpu
            memory = var.refresh_job_memory
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
    google_project_service.services
  ]
}

resource "google_cloud_run_v2_job" "daily_ml_pipeline" {
  provider = google-beta
  count    = var.split_jobs_enabled ? 1 : 0
  name     = var.pipeline_job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "${var.pipeline_job_timeout_seconds}s"
      max_retries     = var.job_max_retries

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
          "--price_backfill_days", tostring(var.price_backfill_days),
          "--lookback_days", tostring(var.pipeline_lookback_days),
          "--topk", tostring(var.pipeline_topk),
          "--min_train_days", tostring(var.pipeline_min_train_days),
          "--test_days", tostring(var.pipeline_test_days),
          "--step_days", tostring(var.pipeline_step_days),
          "--pipeline_horizons", join(",", [for h in var.pipeline_horizons : tostring(h)]),
          "--pipeline_categories", join(",", var.pipeline_categories),
          "--pipeline_lgbm_jobs", tostring(var.pipeline_lgbm_jobs),
          "--pipeline_max_minutes", tostring(var.pipeline_run_max_minutes),
          "--wait_for_refresh",
          "--mode", "pipeline_only",
          "--allow_missing_symbol_db"
        ]

        env {
          name  = "IBKR_SQLITE_PATH"
          value = "${local.mount_path}/ibkr_us.sqlite"
        }
        env {
          name  = "GCS_MOUNT_PATH"
          value = local.mount_path
        }
        env {
          name  = "GCS_DATA_URI"
          value = "gs://${var.bucket_name}"
        }
        env {
          name  = "SKIP_PRICE_REFRESH"
          value = var.skip_price_refresh ? "true" : "false"
        }

        resources {
          limits = {
            cpu    = var.pipeline_job_cpu
            memory = var.pipeline_job_memory
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
    google_project_service.services
  ]
}

resource "google_cloud_scheduler_job" "daily_trigger" {
  count       = var.split_jobs_enabled ? 0 : 1
  name        = var.scheduler_job_name
  description = "Daily trigger for Quantum ML Cloud Run job"
  schedule    = var.scheduler_cron
  time_zone   = var.scheduler_time_zone
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_ml[0].name}:run"

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

resource "google_cloud_scheduler_job" "daily_refresh_trigger" {
  count       = var.split_jobs_enabled ? 1 : 0
  name        = var.refresh_scheduler_job_name
  description = "Daily trigger for refresh-only Cloud Run job"
  schedule    = var.refresh_scheduler_cron
  time_zone   = var.scheduler_time_zone
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_ml_refresh[0].name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job.daily_ml_refresh,
    google_project_iam_member.scheduler_run_developer,
    google_service_account_iam_member.scheduler_act_as_runtime
  ]
}

resource "google_cloud_scheduler_job" "daily_pipeline_trigger" {
  count       = var.split_jobs_enabled ? 1 : 0
  name        = var.pipeline_scheduler_job_name
  description = "Daily trigger for pipeline-only Cloud Run job"
  schedule    = var.pipeline_scheduler_cron
  time_zone   = var.scheduler_time_zone
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_ml_pipeline[0].name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job.daily_ml_pipeline,
    google_project_iam_member.scheduler_run_developer,
    google_service_account_iam_member.scheduler_act_as_runtime
  ]
}
