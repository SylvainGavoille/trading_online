# Deploy IB Gateway for Cloud Run Access

This runbook is aligned with the current deployment flow used in this repo (VM in `us-central1-b`, automated bootstrap from `deploy.ps1`, and Cloud Run over VPC connector).

## 1) Architecture

- Cloud Run Job: `quantum-daily-ml`
- GCE VM: `ib-gateway-vm` running IB Gateway + IBC + systemd
- Connectivity: Cloud Run (Serverless VPC Access) -> VM private IP (`10.128.0.3`) port `4002`
- Secrets: Secret Manager (`ibkr-username`, `ibkr-password`)

## 2) One-command setup (infra + VM bootstrap)

Run from repository root:

```powershell
.\scripts\deploy.ps1 -Target ib-gateway-setup -ProjectId sylvain-488510 -Region us-central1 -Zone us-central1-b -IbVmName ib-gateway-vm -IbApiPort 4002 -IbSourceRanges 10.8.0.0/28 -InstallIbSoftware -TunnelThroughIap -ApplyTerraformAfterSetup -RunCloudRunAfterSetup -AutoApprove
```

What it does:

- Enables required APIs
- Ensures VM + firewall + Secret Manager secrets
- Ensures VM scopes/IAM for Secret Manager access
- Installs Java + IB Gateway + IBC + `ibgateway.service`
- Applies Terraform and can execute Cloud Run job

If you need to create/rotate secrets interactively in the same command, add:

```powershell
-CreateSecretVersions
```

## 3) Mandatory manual step: first interactive IBKR authentication

Username/password in secrets are not always sufficient. A first interactive login + trust/2FA is usually required.

Use the detailed step-by-step guide:

- [IBKR_VM_DOCUMENTATION.md](../docs/IBKR_VM_DOCUMENTATION.md)

In short:

1. Open temporary GUI on VM (Xvfb + x11vnc + noVNC).
2. Login to Gateway interactively.
3. Complete 2FA and trust the device.
4. Confirm API settings (`ApiOnly`, port `4002`, localhost-only disabled).

## 4) VM-side checks

```powershell
gcloud compute ssh ib-gateway-vm --project=sylvain-488510 --zone=us-central1-b --tunnel-through-iap --command "systemctl is-active ibgateway; sudo ss -lntp '( sport = :4002 )'"
```

Expected:

- `active`
- `LISTEN ... :4002 ... java`

## 5) Cloud Run checks

Verify Job configuration:

```powershell
gcloud run jobs describe quantum-daily-ml --region us-central1 --project sylvain-488510 --format=yaml
```

Confirm:

- annotation `run.googleapis.com/vpc-access-connector: quantum-connector`
- annotation `run.googleapis.com/vpc-access-egress: private-ranges-only`
- env `IBKR_TWS_ENDPOINT=10.128.0.3`
- env `IBKR_PORT=4002`
- env `IBKR_SQLITE_PATH=/mnt/quantum/ibkr_us.sqlite`

## 6) Run and validate outputs

```powershell
gcloud run jobs execute quantum-daily-ml --region us-central1 --project sylvain-488510 --wait
```

Check generated artifacts:

```powershell
gcloud storage ls -r gs://quantum-ml-bucket/price_historical/**/*.parquet --project=sylvain-488510
gcloud storage ls -r gs://quantum-ml-bucket/options_snapshot/**/*.parquet --project=sylvain-488510
gcloud storage ls gs://quantum-ml-bucket/ml_output/ --project=sylvain-488510
```

## 7) Common issues

- `exit code=1100` / `full authentication will be required`:
  - interactive login has not been fully completed/trusted.
- `Failed to establish connection` from Cloud Run:
  - check VM service active/listening, Cloud Run VPC connector config, and API settings.
- `No files found ... options_snapshot/**/*.parquet`:
  - IB connection failed during options snapshot collection.

## 8) Security notes

- Rotate IBKR credentials if ever exposed.
- Keep credentials only in Secret Manager.
- Avoid passing password in shell arguments.
