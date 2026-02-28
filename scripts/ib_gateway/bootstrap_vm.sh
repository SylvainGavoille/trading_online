#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bootstrap_vm.sh
  --project <gcp-project-id>
  --username-secret <secret-id>
  --password-secret <secret-id>
  --api-port <port>
  --gateway-url <ib-gateway-installer-url>
  --ibc-zip-url <ibc-zip-url>
  [--trading-mode paper|live]

Example:
  sudo ./bootstrap_vm.sh \
    --project my-project \
    --username-secret ibkr-username \
    --password-secret ibkr-password \
    --api-port 4002 \
    --gateway-url https://example/ibgateway-latest-standalone-linux-x64.sh \
    --ibc-zip-url https://example/IBCLinux-latest.zip \
    --trading-mode paper
EOF
}

PROJECT=""
USERNAME_SECRET=""
PASSWORD_SECRET=""
API_PORT=""
GATEWAY_URL=""
IBC_ZIP_URL=""
TRADING_MODE="paper"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="${2:-}"; shift 2 ;;
    --username-secret) USERNAME_SECRET="${2:-}"; shift 2 ;;
    --password-secret) PASSWORD_SECRET="${2:-}"; shift 2 ;;
    --api-port) API_PORT="${2:-}"; shift 2 ;;
    --gateway-url) GATEWAY_URL="${2:-}"; shift 2 ;;
    --ibc-zip-url) IBC_ZIP_URL="${2:-}"; shift 2 ;;
    --trading-mode) TRADING_MODE="${2:-paper}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$PROJECT" || -z "$USERNAME_SECRET" || -z "$PASSWORD_SECRET" || -z "$API_PORT" || -z "$GATEWAY_URL" || -z "$IBC_ZIP_URL" ]]; then
  echo "[ERROR] Missing required arguments."
  usage
  exit 1
fi

if [[ "$TRADING_MODE" != "paper" && "$TRADING_MODE" != "live" ]]; then
  echo "[ERROR] trading-mode must be 'paper' or 'live'."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y openjdk-17-jre-headless xvfb unzip wget curl jq socat

sudo mkdir -p /opt/ibgateway /opt/ibc /opt/ibc-data /var/log/ibgateway
sudo chown -R "$USER":"$USER" /opt/ibgateway /opt/ibc /opt/ibc-data

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

echo "[INFO] Downloading IB Gateway installer..."
wget -q -O "$tmp_dir/ibgateway-installer.sh" "$GATEWAY_URL"
chmod +x "$tmp_dir/ibgateway-installer.sh"

echo "[INFO] Installing IB Gateway to /opt/ibgateway..."
"$tmp_dir/ibgateway-installer.sh" -q -dir /opt/ibgateway || true

echo "[INFO] Downloading IBC..."
wget -q -O "$tmp_dir/ibc.zip" "$IBC_ZIP_URL"
unzip -oq "$tmp_dir/ibc.zip" -d /opt/ibc

# Some unzip paths drop execute bits; enforce executable permissions for scripts.
chmod +x /opt/ibc/scripts/*.sh 2>/dev/null || true
chmod +x /opt/ibc/*.sh 2>/dev/null || true

if [[ ! -f /opt/ibc/scripts/ibcstart.sh ]]; then
  echo "[ERROR] IBC install failed: /opt/ibc/scripts/ibcstart.sh not found."
  exit 1
fi

sudo tee /etc/default/ibgateway >/dev/null <<EOF
GCP_PROJECT="$PROJECT"
IBKR_USERNAME_SECRET_ID="$USERNAME_SECRET"
IBKR_PASSWORD_SECRET_ID="$PASSWORD_SECRET"
IBKR_API_PORT="$API_PORT"
# Internal Gateway socket port kept on localhost; public-facing port is proxied.
IBKR_GATEWAY_LOCAL_PORT="$((API_PORT + 1))"
IBKR_TRADING_MODE="$TRADING_MODE"
EOF

sudo tee /usr/local/bin/ibgateway-start.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

source /etc/default/ibgateway

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud command not found; cannot fetch secrets"
  exit 1
fi

TWS_USERID="$(gcloud secrets versions access latest --secret="$IBKR_USERNAME_SECRET_ID" --project="$GCP_PROJECT" | tr -d '\r')"
TWS_PASSWORD="$(gcloud secrets versions access latest --secret="$IBKR_PASSWORD_SECRET_ID" --project="$GCP_PROJECT" | tr -d '\r')"

if [[ -z "$TWS_USERID" || -z "$TWS_PASSWORD" ]]; then
  echo "IBKR credentials are empty from Secret Manager."
  exit 1
fi

mkdir -p /opt/ibc-data

cat > /opt/ibc/config.ini <<CFG
[Logon]
IbLoginId=$TWS_USERID
IbPassword=$TWS_PASSWORD
TradingMode=${IBKR_TRADING_MODE}

[Config]
IbDir=/opt/ibgateway
OverrideTwsApiPort=${IBKR_GATEWAY_LOCAL_PORT}
AcceptIncomingConnectionAction=accept
# Keep default localhost-only API on Gateway and expose remote access through
# a controlled TCP proxy service on $IBKR_API_PORT.
TrustedTwsApiClientIPs=127.0.0.1
ReadOnlyApi=yes
StoreSettingsOnServer=no
CFG

chmod 600 /opt/ibc/config.ini
export IBC_INI=/opt/ibc/config.ini
export TWS_SETTINGS_PATH=/opt/ibc-data

GATEWAY_VERSION="$(ls /opt/ibgateway/IB\ Gateway*.desktop 2>/dev/null | sed -E 's/.*IB Gateway ([0-9]+)\.([0-9]+).*/\1\2/' | head -n1)"
if [[ -z "$GATEWAY_VERSION" ]]; then
  GATEWAY_VERSION="1044"
fi

# IBC expects Linux gateway layout: <tws-path>/ibgateway/<version>/jars
mkdir -p /opt/ibgateway
ln -sfn /opt/ibgateway "/opt/ibgateway/${GATEWAY_VERSION}"

# Ensure Gateway API is reachable from remote clients (firewall still restricts ingress).
# Gateway reads settings from --tws-settings-path (/opt/ibc-data), but keeping both
# jts.ini files aligned avoids drift after updates/reinstalls.
set_jts_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf "%s=%s\n" "$key" "$value" >> "$file"
  fi
}

for JTS_INI in /opt/ibgateway/jts.ini /opt/ibc-data/jts.ini; do
  touch "$JTS_INI"
  grep -q "^\[IBGateway\]" "$JTS_INI" || printf "\n[IBGateway]\n" >> "$JTS_INI"
  set_jts_key "$JTS_INI" "ApiOnly" "true"
  set_jts_key "$JTS_INI" "LocalServerPort" "${IBKR_GATEWAY_LOCAL_PORT}"
  set_jts_key "$JTS_INI" "TrustedIPs" "127.0.0.1"
done

exec xvfb-run -a /opt/ibc/scripts/ibcstart.sh "$GATEWAY_VERSION" --gateway \
  --tws-path=/opt \
  --tws-settings-path=/opt/ibc-data \
  --ibc-path=/opt/ibc \
  --ibc-ini=/opt/ibc/config.ini \
  --mode="$IBKR_TRADING_MODE"
EOF
sudo chmod +x /usr/local/bin/ibgateway-start.sh

sudo tee /usr/local/bin/ibgateway-proxy-start.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

source /etc/default/ibgateway

exec /usr/bin/socat \
  "TCP-LISTEN:${IBKR_API_PORT},bind=0.0.0.0,reuseaddr,fork" \
  "TCP:127.0.0.1:${IBKR_GATEWAY_LOCAL_PORT}"
EOF
sudo chmod +x /usr/local/bin/ibgateway-proxy-start.sh

sudo tee /etc/systemd/system/ibgateway.service >/dev/null <<'EOF'
[Unit]
Description=IB Gateway via IBC
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=/etc/default/ibgateway
ExecStart=/usr/local/bin/ibgateway-start.sh
Restart=always
RestartSec=15
StandardOutput=append:/var/log/ibgateway/ibgateway.log
StandardError=append:/var/log/ibgateway/ibgateway.log

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/ibgateway-proxy.service >/dev/null <<'EOF'
[Unit]
Description=IB Gateway TCP proxy (remote clients -> localhost API)
After=network-online.target ibgateway.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/default/ibgateway
ExecStart=/usr/local/bin/ibgateway-proxy-start.sh
Restart=always
RestartSec=2
StandardOutput=append:/var/log/ibgateway/ibgateway.log
StandardError=append:/var/log/ibgateway/ibgateway.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ibgateway.service
sudo systemctl enable ibgateway-proxy.service
sudo systemctl restart ibgateway.service
sudo systemctl restart ibgateway-proxy.service
sleep 3
sudo systemctl --no-pager --full status ibgateway.service || true
sudo systemctl --no-pager --full status ibgateway-proxy.service || true

echo "[DONE] IB Gateway bootstrap completed."
