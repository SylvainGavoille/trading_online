# GCP Daily ML Deployment (Terraform)

This Terraform stack deploys:

- A GCS bucket that stores `price_historical/`, `options_snapshot/`, `portfolio_daily/`, `ml_output/`
- Cloud Run Job(s) for daily ML execution:
  - legacy single job: `quantum-daily-ml` (when `split_jobs_enabled=false`)
  - split jobs: `quantum-daily-ml-refresh` + `quantum-daily-ml-pipeline` (when `split_jobs_enabled=true`)
- Cloud Scheduler trigger(s) for daily execution
- Service accounts and IAM for least-privilege invocation/runtime

## 1) Build and push the job image

Create a container image that includes this repository and dependencies, then push it to Artifact Registry.

Example:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/<PROJECT_ID>/quantum/quantum-ml:latest -f Dockerfile.ml-job .
docker push us-central1-docker.pkg.dev/<PROJECT_ID>/quantum/quantum-ml:latest
```

## 2) Configure Terraform variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Update at least:

- `project_id`
- `bucket_name` (must be globally unique)
- `container_image`

## 3) Deploy

```bash
terraform init
terraform plan
terraform apply
```

Or from repository root:

```bash
make deploy-all PROJECT_ID=<PROJECT_ID>
```

Make sure `infra/terraform.tfvars` uses the same `container_image` URI printed by `make help`.

On Windows PowerShell (no `make`), use:

```powershell
.\scripts\deploy.ps1 -Target help
.\scripts\deploy.ps1 -Target deploy-all -ProjectId <PROJECT_ID>
.\scripts\deploy.ps1 -Target deploy-all -ProjectId <PROJECT_ID> -AutoApprove
```

If Docker image is already available in Artifact Registry, you can skip Docker steps:

```powershell
.\scripts\deploy.ps1 -Target tf-only
```

If Docker Desktop is not running, build remotely in GCP (no local Docker required):

```powershell
.\scripts\deploy.ps1 -Target cloud-build -ProjectId <PROJECT_ID>
```

The deploy script now auto-creates the Artifact Registry repo (`quantum` by default) if missing.

## 3.1) Manual run / troubleshooting

List deployed jobs first:

```bash
gcloud run jobs list --region us-central1 --project <PROJECT_ID>
```

Run split jobs (recommended):

```bash
gcloud run jobs execute quantum-daily-ml-refresh --region us-central1 --project <PROJECT_ID> --wait
gcloud run jobs execute quantum-daily-ml-pipeline --region us-central1 --project <PROJECT_ID> --wait
```

In split mode, the pipeline job is configured to wait for a refresh completion marker
written by the refresh job before starting model training.

Run legacy single job (only when `split_jobs_enabled=false`):

```bash
gcloud run jobs execute quantum-daily-ml --region us-central1 --project <PROJECT_ID> --wait
```

## 4) Dashboard access to cloud results

Set this environment variable where Streamlit dashboard runs:

```bash
ML_RESULTS_GCS_URI=gs://<bucket-name>/ml_output
```

The modeling tab now reads local `ml_output/` first, then falls back to this GCS URI.

## Notes

- `options_snapshot/` and `portfolio_daily/` must exist in the bucket for full pipeline success.
- Cloud Run uses Application Default Credentials for GCS access.

## IBKR connectivity from Cloud Run

Cloud Run cannot run a desktop IB session directly. Use a persistent host (typically a GCE VM)
running IB Gateway/TWS, then connect from Cloud Run over network to that host.

Terraform variables now support this pattern:

- `ibkr_tws_endpoint`: private IP or DNS of your IB Gateway/TWS host
- `ibkr_port`: API port (commonly 4002 paper, 4001 live, 7497/7496 for TWS)
- `ibkr_username_secret_id`, `ibkr_password_secret_id`: Secret Manager IDs injected as env vars
- `vpc_connector_name`, `vpc_connector_cidr`, `vpc_network`: Serverless VPC Access for Cloud Run -> private VM IP reachability

Security guidance:

- Keep IB Gateway/TWS on a private subnet, not a public IP when possible.
- Restrict firewall to Cloud Run egress range/VPC connector source only.
- Store credentials only in Secret Manager (never in `terraform.tfvars` or git).
- Ensure Cloud Run uses Serverless VPC Access when `ibkr_tws_endpoint` is a private IP (10.x/172.16-31.x/192.168.x).

See runbooks:

- `scripts/deploy_ib_gateway.md` (quick deployment flow)
- `docs/IBKR_VM_DOCUMENTATION.md` (full step-by-step VM auth/troubleshooting)

Automated host bootstrap is available via `scripts/deploy.ps1 -Target ib-gateway-setup`
with `-InstallIbSoftware` and installer URLs for IB Gateway/IBC.
