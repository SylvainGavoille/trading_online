# IBKR VM Documentation (Step by Step)

This guide documents the full setup to run IB Gateway on GCP VM and connect Cloud Run to IBKR API for historical data downloads.

## 1) Preconditions

- GCP project: `sylvain-488510`
- VM target zone: `us-central1-b`
- VM name: `ib-gateway-vm`
- IB API port: `4002` (paper)
- Cloud Run Job: `quantum-daily-ml`
- Bucket: `quantum-ml-bucket`

Use the `us-central1-b` VM only if multiple VMs with the same name exist.
If you previously created `ib-gateway-vm` in another zone (for example `us-central1-a`), avoid using it for commands and consider deleting it.

## 2) One-command infrastructure + software setup

Run from repo root:

```powershell
.\scripts\deploy.ps1 -Target ib-gateway-setup -ProjectId sylvain-488510 -Region us-central1 -Zone us-central1-b -IbVmName ib-gateway-vm -IbApiPort 4002 -IbSourceRanges 10.8.0.0/28 -InstallIbSoftware -TunnelThroughIap -ApplyTerraformAfterSetup -RunCloudRunAfterSetup -AutoApprove
```

What this does:

- Ensures VM exists
- Ensures VM scopes + Secret Manager IAM
- Ensures firewall for IB API
- Ensures secrets exist
- Installs Java + IB Gateway + IBC + systemd
- Optionally applies Terraform
- Optionally runs Cloud Run job and checks parquet output

## 3) Required firewall rule for noVNC over IAP

Create once:

```powershell
gcloud compute firewall-rules create allow-iap-novnc --project=sylvain-488510 --network=default --direction=INGRESS --action=ALLOW --rules=tcp:6080 --source-ranges=35.235.240.0/20 --target-tags=ib-gateway
```

Optional troubleshooting rule for direct IAP tunnel to IB API port:

```powershell
gcloud compute firewall-rules create allow-iap-ibkr --project=sylvain-488510 --network=default --direction=INGRESS --action=ALLOW --rules=tcp:4002 --source-ranges=35.235.240.0/20 --target-tags=ib-gateway
```

## 4) Open temporary GUI session for first IBKR authentication

This is required when logs show `exit code=1100` and `full authentication will be required`.

### 4.1 SSH to VM

```powershell
gcloud compute ssh ib-gateway-vm --project=sylvain-488510 --zone=us-central1-b --tunnel-through-iap
```

### 4.2 Install GUI helpers (once)

```bash
sudo apt-get update
sudo apt-get install -y x11vnc novnc websockify xvfb xterm
```

### 4.3 Start X + VNC + noVNC

```bash
pkill -f websockify || true
pkill -f x11vnc || true
pkill -f Xvfb || true

Xvfb :1 -screen 0 1280x1024x24 -ac >/tmp/xvfb.log 2>&1 &
sleep 2
x11vnc -display :1 -forever -shared -nopw -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
sleep 2
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/websockify.log 2>&1 &
sleep 2
sudo ss -lntp | egrep '(:5900|:6080)'
```

Expected: `LISTEN` on `5900` and `6080`.

### 4.4 Start local IAP tunnel on your PC

Keep this terminal open:

```powershell
gcloud compute start-iap-tunnel ib-gateway-vm 6080 --local-host-port=127.0.0.1:6080 --project=sylvain-488510 --zone=us-central1-b
```

Open in browser:

- `http://127.0.0.1:6080/vnc.html`

### 4.5 Launch IB Gateway in GUI and complete auth

On VM shell:

```bash
sudo systemctl stop ibgateway
export DISPLAY=:1
xvfb-run -a /opt/ibc/scripts/ibcstart.sh 1044 --gateway --tws-path=/opt --tws-settings-path=/opt/ibc-data --ibc-path=/opt/ibc --ibc-ini=/opt/ibc/config.ini --mode=paper
```

In noVNC window:

- Login IBKR
- Complete 2FA
- Trust/remember device when prompted
- Accept API/security prompts
- In API settings, disable localhost-only and keep trusted IPs open for connector traffic.

## 5) Validate IB Gateway service/API after auth

Restart service and check:

```bash
sudo systemctl start ibgateway
sleep 20
systemctl is-active ibgateway
sudo ss -lntp '( sport = :4002 )'
```

Expected:

- `active`
- `LISTEN ... :4002 ... java`

Validate persisted API settings:

```bash
sudo grep -n "^\[IBGateway\]\|^TrustedIPs\|^LocalServerPort\|^ApiOnly" /opt/ibgateway/jts.ini
sudo grep -n "^\[IBGateway\]\|^TrustedIPs\|^LocalServerPort\|^ApiOnly" /opt/ibc-data/jts.ini
```

Recommended values:

- `ApiOnly=true`
- `LocalServerPort=4002`
- `TrustedIPs=` (blank)

From your PC:

```powershell
gcloud compute ssh ib-gateway-vm --project=sylvain-488510 --zone=us-central1-b --tunnel-through-iap --command "systemctl is-active ibgateway; sudo ss -lntp '( sport = :4002 )'"
```

## 6) Ensure Cloud Run has symbol DB path

Already wired in Terraform:

- `IBKR_SQLITE_PATH=/mnt/quantum/ibkr_us.sqlite`

Upload DB once from repo root:

```powershell
gcloud storage cp .\ibkr_us.sqlite gs://quantum-ml-bucket/ibkr_us.sqlite --project=sylvain-488510
```

Apply Terraform:

```powershell
.\scripts\deploy.ps1 -Target tf-only -ProjectId sylvain-488510 -AutoApprove
```

Verify Cloud Run networking and env:

```powershell
gcloud run jobs describe quantum-daily-ml --region us-central1 --project sylvain-488510 --format=yaml
```

Confirm these fields exist:

- `run.googleapis.com/vpc-access-connector: quantum-connector`
- `run.googleapis.com/vpc-access-egress: private-ranges-only`
- `IBKR_TWS_ENDPOINT=10.128.0.3`
- `IBKR_PORT=4002`
- `IBKR_SQLITE_PATH=/mnt/quantum/ibkr_us.sqlite`

## 7) Run Cloud Run job and verify output

```powershell
gcloud run jobs execute quantum-daily-ml --region us-central1 --project sylvain-488510 --wait
```

Check parquet download:

```powershell
gcloud storage ls -r gs://quantum-ml-bucket/price_historical/**/*.parquet --project=sylvain-488510
```

Check options snapshots:

```powershell
gcloud storage ls -r gs://quantum-ml-bucket/options_snapshot/**/*.parquet --project=sylvain-488510
```

Check ML output:

```powershell
gcloud storage ls gs://quantum-ml-bucket/ml_output/ --project=sylvain-488510
```

Check logs:

```powershell
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=quantum-daily-ml" --project=sylvain-488510 --limit=200 --format="value(textPayload)"
```

## 8) Common failures and fixes

### A) `ACCESS_TOKEN_SCOPE_INSUFFICIENT` on VM secret access

Fix via deploy script (`Ensure VM Secret Manager access`) or manually set VM scopes to `cloud-platform` and grant `roles/secretmanager.secretAccessor`.

### B) `ZONE_RESOURCE_POOL_EXHAUSTED`

Switch zone (for example from `us-central1-a` to `us-central1-b`) and update `ibkr_tws_endpoint` in `infra/terraform.tfvars`.

### C) `libgomp.so.1` missing in Cloud Run

Ensure `Dockerfile.ml-job` installs `libgomp1`, rebuild image, rerun job.

### D) No parquet files found

Ensure:

- IB Gateway is truly listening on `4002`
- `ibkr_us.sqlite` exists at `gs://quantum-ml-bucket/ibkr_us.sqlite`
- Cloud Run env has `IBKR_SQLITE_PATH=/mnt/quantum/ibkr_us.sqlite`

### E) IAP noVNC tunnel fails with `failed to connect to backend`

Check:

- VM has process listening on `6080`
- Firewall rule `allow-iap-novnc` exists for source `35.235.240.0/20`
- VM tag includes `ib-gateway`

### F) Cloud Run shows `Failed to establish connection` to IBKR

Checklist:

- VM is `active` and `:4002` is listening
- Cloud Run job has VPC connector annotations (`quantum-connector`, `private-ranges-only`)
- IB Gateway API does not restrict to localhost
- `TrustedIPs` is not locked to `127.0.0.1`
- `options_snapshot` generation is attempted before pipeline (job now auto-attempts collection)

Note: local IAP tunnel errors (`4010`) are not the definitive signal for Cloud Run private networking success. The definitive test is Cloud Run execution + parquet creation in `options_snapshot/`.

## 9) Security actions

- Rotate IBKR password if it was ever exposed in logs/terminal history.
- Update secrets:
  - `ibkr-username`
  - `ibkr-password`
- Avoid passing password in process args.

## 10) Final success criteria

- `ibgateway` systemd service stays `active`
- VM port `4002` is `LISTEN`
- Cloud Run job completes successfully
- Parquet files exist under `price_historical/`
- Parquet files exist under `options_snapshot/`
- ML artifacts exist under `ml_output/`
