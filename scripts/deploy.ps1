param(
    [ValidateSet("help", "auth-docker", "docker-build", "docker-push", "cloud-build", "tf-init", "tf-plan", "tf-apply", "tf-only", "deploy-all", "ib-gateway-setup")]
    [string]$Target = "help",
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$Zone = "us-central1-b",
    [string]$ArRepo = "quantum",
    [string]$ImageName = "quantum-ml",
    [string]$ImageTag = "latest",
    [string]$TfDir = "infra",
    [string]$IbVmName = "ib-gateway-vm",
    [string]$IbMachineType = "e2-standard-2",
    [string]$IbNetwork = "default",
    [string]$IbSubnetwork = "",
    [int]$IbApiPort = 4002,
    [string]$IbVmTag = "ib-gateway",
    [string]$IbFirewallRule = "allow-ibkr-api",
    [string]$IbSourceRanges = "",
    [string]$IbUsernameSecretId = "ibkr-username",
    [string]$IbPasswordSecretId = "ibkr-password",
    [string]$IbGatewayInstallerUrl = "",
    [string]$IbcZipUrl = "",
    [ValidateSet("paper", "live")]
    [string]$IbTradingMode = "paper",
    [switch]$TunnelThroughIap,
    [switch]$InstallIbSoftware,
    [switch]$ApplyTerraformAfterSetup,
    [switch]$RunCloudRunAfterSetup,
    [int]$GatewayReadyTimeoutSeconds = 600,
    [int]$ParquetMinCount = 1,
    [switch]$CreateSecretVersions,
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$script:GcloudCmd = $null

function Get-ImageUri {
    return "$Region-docker.pkg.dev/$ProjectId/$ArRepo/$ImageName`:$ImageTag"
}

function Require-ProjectId {
    if ([string]::IsNullOrWhiteSpace($ProjectId)) {
        throw "ProjectId is required. Example: .\scripts\deploy.ps1 -Target deploy-all -ProjectId my-gcp-project"
    }
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Resolve-Gcloud {
    # Prefer gcloud.cmd on Windows. Some extensionless gcloud launchers can hang in PowerShell.
    $cmd = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $all = Get-Command gcloud -All -ErrorAction SilentlyContinue
    if ($all) {
        $cmdCandidate = $all | Where-Object { $_.Source -like "*.cmd" } | Select-Object -First 1
        if ($cmdCandidate) { return $cmdCandidate.Source }
        return ($all | Select-Object -First 1).Source
    }

    $candidates = @(
        "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud",
        "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Require-GcloudReady {
    $resolved = Resolve-Gcloud
    if (-not $resolved) {
        throw "gcloud CLI not found. Add Google Cloud SDK bin to PATH, or reinstall Cloud SDK."
    }
    $script:GcloudCmd = $resolved
    & $script:GcloudCmd auth list --filter=status:ACTIVE --format="value(account)" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud is not authenticated. Run: gcloud auth login"
    }
}

function Ensure-ArtifactRepo {
    Require-GcloudReady
    $prevEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $script:GcloudCmd artifacts repositories describe "$ArRepo" `
            --project "$ProjectId" `
            --location "$Region" *> $null
        if ($LASTEXITCODE -eq 0) { return }
    }
    finally {
        $ErrorActionPreference = $prevEap
    }

    Write-Host "Artifact Registry repo '$ArRepo' not found in $Region; creating it..."
    & $script:GcloudCmd artifacts repositories create "$ArRepo" `
        --project "$ProjectId" `
        --location "$Region" `
        --repository-format docker `
        --description "Quantum ML container images"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Artifact Registry repository '$ArRepo' in $Region."
    }
}

function Ensure-GcpService {
    param([string]$ServiceName)
    Require-GcloudReady
    $prevEap = $ErrorActionPreference
    try {
        # In Windows PowerShell, gcloud may emit progress/status text on stderr
        # even when the operation succeeds. Do not fail on stderr alone.
        $ErrorActionPreference = "Continue"
        & $script:GcloudCmd services enable $ServiceName --project "$ProjectId"
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to enable service: $ServiceName"
    }
}

function Test-GcloudDescribe {
    param([ScriptBlock]$Action)
    $prevEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Action *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
}

function Ensure-Secret {
    param([string]$SecretId)
    $exists = Test-GcloudDescribe -Action {
        & $script:GcloudCmd secrets describe "$SecretId" --project "$ProjectId"
    }
    if (-not $exists) {
        Write-Host "Creating secret: $SecretId"
        & $script:GcloudCmd secrets create "$SecretId" --replication-policy="automatic" --project "$ProjectId"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create secret: $SecretId"
        }
    } else {
        Write-Host "Secret exists: $SecretId"
    }
}

function Ensure-ComputeInstance {
    $exists = Test-GcloudDescribe -Action {
        & $script:GcloudCmd compute instances describe "$IbVmName" --zone "$Zone" --project "$ProjectId"
    }
    if ($exists) {
        Write-Host "VM exists: $IbVmName"
        return
    }

    Write-Host "Creating VM: $IbVmName"
    $args = @(
        "compute", "instances", "create", "$IbVmName",
        "--project", "$ProjectId",
        "--zone", "$Zone",
        "--machine-type", "$IbMachineType",
        "--network", "$IbNetwork",
        "--tags", "$IbVmTag",
        "--scopes", "cloud-platform"
    )
    if (-not [string]::IsNullOrWhiteSpace($IbSubnetwork)) {
        $args += @("--subnet", "$IbSubnetwork")
    }
    & $script:GcloudCmd @args
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create VM: $IbVmName"
    }
}

function Get-ProjectNumber {
    $pn = (& $script:GcloudCmd projects describe "$ProjectId" --format "value(projectNumber)" 2>$null).Trim()
    if ([string]::IsNullOrWhiteSpace($pn)) {
        throw "Unable to resolve project number for $ProjectId"
    }
    return $pn
}

function Get-InstanceServiceAccount {
    $sa = (& $script:GcloudCmd compute instances describe "$IbVmName" `
        --zone "$Zone" `
        --project "$ProjectId" `
        --format "value(serviceAccounts[0].email)" 2>$null).Trim()
    return $sa
}

function Get-InstanceScopes {
    $scopes = (& $script:GcloudCmd compute instances describe "$IbVmName" `
        --zone "$Zone" `
        --project "$ProjectId" `
        --format "value(serviceAccounts[0].scopes.join(','))" 2>$null).Trim()
    return $scopes
}

function Ensure-InstanceSecretAccess {
    $sa = Get-InstanceServiceAccount
    if ([string]::IsNullOrWhiteSpace($sa)) {
        $pn = Get-ProjectNumber
        $sa = "$pn-compute@developer.gserviceaccount.com"
    }

    $scopes = Get-InstanceScopes
    $needsScopeFix = ($scopes -notmatch "cloud-platform")

    if ($needsScopeFix) {
        Write-Host "Updating VM service account scopes to cloud-platform (requires stop/start)..."
        & $script:GcloudCmd compute instances stop "$IbVmName" --zone "$Zone" --project "$ProjectId"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to stop VM before scope update."
        }

        & $script:GcloudCmd compute instances set-service-account "$IbVmName" `
            --zone "$Zone" `
            --project "$ProjectId" `
            --service-account "$sa" `
            --scopes "https://www.googleapis.com/auth/cloud-platform"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update VM service account/scopes."
        }

        & $script:GcloudCmd compute instances start "$IbVmName" --zone "$Zone" --project "$ProjectId"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to restart VM after scope update."
        }
    }
    else {
        Write-Host "VM scopes already include cloud-platform."
    }

    $prevEap = $ErrorActionPreference
    try {
        # gcloud can print success/progress on stderr; rely on exit code instead.
        $ErrorActionPreference = "Continue"
        & $script:GcloudCmd projects add-iam-policy-binding "$ProjectId" `
            --member "serviceAccount:$sa" `
            --role "roles/secretmanager.secretAccessor" `
            --quiet
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to grant roles/secretmanager.secretAccessor to VM service account $sa"
    }

    Write-Host "VM service account ready for Secret Manager: $sa"
}

function Get-GatewayStatus {
    $sshArgs = @(
        "compute", "ssh", "$IbVmName",
        "--zone", "$Zone",
        "--project", "$ProjectId",
        "--command", "systemctl is-active ibgateway; sudo ss -lnt '( sport = :$IbApiPort )' | tail -n +2"
    )
    if ($TunnelThroughIap) {
        $sshArgs += "--tunnel-through-iap"
    }
    $out = & $script:GcloudCmd @sshArgs 2>$null
    return ($out -join "`n")
}

function Wait-GatewayReady {
    param([int]$TimeoutSeconds = 600)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $status = Get-GatewayStatus
        $active = ($status -match "(?m)^active\s*$")
        $listening = ($status -match "(?m)\bLISTEN\b")

        if ($active -and $listening) {
            Write-Host "IB Gateway is ready (service active + port $IbApiPort listening)."
            return $true
        }

        Write-Host "Waiting for IB Gateway readiness... (active=$active, listening=$listening)"
        Start-Sleep -Seconds 10
    } while ((Get-Date) -lt $deadline)

    Write-Warning "IB Gateway not ready within $TimeoutSeconds seconds."
    Write-Warning "Likely first-time IBKR interactive auth/2FA is still required."
    return $false
}

function Invoke-CloudRunAndCheckParquet {
    & $script:GcloudCmd run jobs execute "$env:JOB_NAME" `
        --region "$Region" `
        --project "$ProjectId" `
        --wait
    if ($LASTEXITCODE -ne 0) {
        throw "Cloud Run job execution failed."
    }

    $parquetLines = & $script:GcloudCmd storage ls -r "gs://quantum-ml-bucket/price_historical/**/*.parquet" --project "$ProjectId" 2>$null
    $count = @($parquetLines).Count
    Write-Host "price_historical parquet count: $count"
    if ($count -lt $ParquetMinCount) {
        throw "Parquet count ($count) is below expected minimum ($ParquetMinCount)."
    }
}

function Resolve-IbGatewayInstallerUrl {
    if (-not [string]::IsNullOrWhiteSpace($IbGatewayInstallerUrl)) {
        return $IbGatewayInstallerUrl
    }
    return "https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh"
}

function Resolve-IbcZipUrl {
    if (-not [string]::IsNullOrWhiteSpace($IbcZipUrl)) {
        return $IbcZipUrl
    }

    try {
        $release = Invoke-RestMethod "https://api.github.com/repos/IbcAlpha/IBC/releases/latest"
        $asset = $release.assets |
            Where-Object { $_.name -match "^IBCLinux.*\.zip$" } |
            Select-Object -First 1

        if ($asset -and $asset.browser_download_url) {
            return $asset.browser_download_url
        }
    }
    catch {
        # handled below with explicit error
    }

    throw "Unable to auto-resolve IBC Linux ZIP URL from GitHub. Pass -IbcZipUrl explicitly."
}

function Invoke-IbBootstrap {
    $resolvedIbGatewayInstallerUrl = Resolve-IbGatewayInstallerUrl
    $resolvedIbcZipUrl = Resolve-IbcZipUrl

    $bootstrapLocal = "scripts/ib_gateway/bootstrap_vm.sh"
    if (-not (Test-Path $bootstrapLocal)) {
        throw "Bootstrap script not found: $bootstrapLocal"
    }

    $remoteBootstrap = "/tmp/bootstrap_vm.sh"

    Write-Host "Copying bootstrap script to VM..."
    $scpArgs = @(
        "compute", "scp", "$bootstrapLocal", "$IbVmName`:$remoteBootstrap",
        "--zone", "$Zone",
        "--project", "$ProjectId"
    )
    if ($TunnelThroughIap) {
        $scpArgs += "--tunnel-through-iap"
    }
    & $script:GcloudCmd @scpArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy bootstrap script to VM."
    }

    $remoteCmd = "chmod +x $remoteBootstrap && " +
        "sudo $remoteBootstrap " +
        "--project '$ProjectId' " +
        "--username-secret '$IbUsernameSecretId' " +
        "--password-secret '$IbPasswordSecretId' " +
        "--api-port '$IbApiPort' " +
        "--gateway-url '$resolvedIbGatewayInstallerUrl' " +
        "--ibc-zip-url '$resolvedIbcZipUrl' " +
        "--trading-mode '$IbTradingMode'"

    Write-Host "Using IB Gateway installer URL: $resolvedIbGatewayInstallerUrl"
    Write-Host "Using IBC ZIP URL: $resolvedIbcZipUrl"

    Write-Host "Running bootstrap on VM (this can take several minutes)..."
    $sshArgs = @(
        "compute", "ssh", "$IbVmName",
        "--zone", "$Zone",
        "--project", "$ProjectId",
        "--command", "$remoteCmd"
    )
    if ($TunnelThroughIap) {
        $sshArgs += "--tunnel-through-iap"
    }
    & $script:GcloudCmd @sshArgs
    if ($LASTEXITCODE -ne 0) {
        throw "IB Gateway bootstrap failed on VM."
    }
}

function Ensure-FirewallRule {
    if ([string]::IsNullOrWhiteSpace($IbSourceRanges)) {
        throw "IbSourceRanges is required for ib-gateway-setup. Example: -IbSourceRanges 10.8.0.0/28"
    }

    $exists = Test-GcloudDescribe -Action {
        & $script:GcloudCmd compute firewall-rules describe "$IbFirewallRule" --project "$ProjectId"
    }
    if ($exists) {
        Write-Host "Firewall rule exists: $IbFirewallRule"
        return
    }

    Write-Host "Creating firewall rule: $IbFirewallRule"
    & $script:GcloudCmd compute firewall-rules create "$IbFirewallRule" `
        --project "$ProjectId" `
        --network "$IbNetwork" `
        --direction INGRESS `
        --action ALLOW `
        --rules "tcp:$IbApiPort" `
        --source-ranges "$IbSourceRanges" `
        --target-tags "$IbVmTag"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create firewall rule: $IbFirewallRule"
    }
}

function Convert-SecureStringToPlainText {
    param([Security.SecureString]$Value)
    if (-not $Value) { return "" }
    $bstr = [IntPtr]::Zero
    try {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Invoke-Step {
    param([ScriptBlock]$Action, [string]$Label)
    Write-Host "==> $Label"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Label (exit code $LASTEXITCODE)"
    }
}

function Require-DockerDaemon {
    try {
        docker info *> $null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        return $true
    }
    catch {
        return $false
    }
}

switch ($Target) {
    "help" {
        Write-Host "Targets:"
        Write-Host "  .\scripts\deploy.ps1 -Target help"
        Write-Host "  .\scripts\deploy.ps1 -Target docker-build -ProjectId <id>"
        Write-Host "  .\scripts\deploy.ps1 -Target docker-push -ProjectId <id>"
        Write-Host "  .\scripts\deploy.ps1 -Target cloud-build -ProjectId <id>"
        Write-Host "  .\scripts\deploy.ps1 -Target tf-init"
        Write-Host "  .\scripts\deploy.ps1 -Target tf-plan"
        Write-Host "  .\scripts\deploy.ps1 -Target tf-apply [-AutoApprove]"
        Write-Host "  .\scripts\deploy.ps1 -Target tf-only"
        Write-Host "  .\scripts\deploy.ps1 -Target deploy-all -ProjectId <id> [-AutoApprove]"
        Write-Host "  .\scripts\deploy.ps1 -Target ib-gateway-setup -ProjectId <id> -IbSourceRanges <cidr>"
        Write-Host "      Optional install: -InstallIbSoftware [-IbGatewayInstallerUrl <url>] [-IbcZipUrl <url>] [-IbTradingMode paper|live] [-TunnelThroughIap]"
        Write-Host "      Optional end-to-end: -ApplyTerraformAfterSetup -RunCloudRunAfterSetup"
        Write-Host ""
        if ([string]::IsNullOrWhiteSpace($ProjectId)) {
            Write-Host "Resolved image URI: <set -ProjectId first>"
        } else {
            Write-Host "Resolved image URI: $(Get-ImageUri)"
        }
    }
    "auth-docker" {
        Require-ProjectId
        Require-GcloudReady
        Ensure-ArtifactRepo
        & $script:GcloudCmd auth configure-docker "$Region-docker.pkg.dev" -q
    }
    "docker-build" {
        Require-ProjectId
        if (-not (Require-DockerDaemon)) { throw "Docker daemon is not available. Start Docker Desktop, then retry, or use -Target cloud-build." }
        $img = Get-ImageUri
        docker build -t $img -f Dockerfile.ml-job .
        if ($LASTEXITCODE -ne 0) { throw "Docker build failed (exit code $LASTEXITCODE)" }
        Write-Host "Built: $img"
    }
    "docker-push" {
        Require-ProjectId
        if (-not (Require-DockerDaemon)) { throw "Docker daemon is not available. Start Docker Desktop, then retry, or use -Target cloud-build." }
        $img = Get-ImageUri
        docker push $img
        if ($LASTEXITCODE -ne 0) { throw "Docker push failed (exit code $LASTEXITCODE)" }
        Write-Host "Pushed: $img"
    }
    "cloud-build" {
        Require-ProjectId
        Require-GcloudReady
        Ensure-ArtifactRepo
        $img = Get-ImageUri
        & $script:GcloudCmd builds submit `
            --project "$ProjectId" `
            --config cloudbuild.ml-job.yaml `
            --substitutions "_IMAGE_URI=$img" `
            .
        if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed (exit code $LASTEXITCODE)" }
        Write-Host "Built and pushed via Cloud Build: $img"
    }
    "tf-init" {
        terraform -chdir="$TfDir" init
    }
    "tf-plan" {
        terraform -chdir="$TfDir" plan
    }
    "tf-apply" {
        if ($AutoApprove) {
            terraform -chdir="$TfDir" apply -auto-approve
        }
        else {
            terraform -chdir="$TfDir" apply
        }
    }
    "tf-only" {
        Invoke-Step -Label "Terraform init" -Action { terraform -chdir="$TfDir" init }
        if ($AutoApprove) {
            Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply -auto-approve }
        }
        else {
            Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply }
        }
        Write-Host "Terraform deployment complete."
    }
    "deploy-all" {
        Require-ProjectId
        Require-GcloudReady
        Ensure-ArtifactRepo
        $img = Get-ImageUri
        if (Require-DockerDaemon) {
            Invoke-Step -Label "Configure Docker auth" -Action { & $script:GcloudCmd auth configure-docker "$Region-docker.pkg.dev" -q }
            Invoke-Step -Label "Build image" -Action { docker build -t $img -f Dockerfile.ml-job . }
            Invoke-Step -Label "Push image" -Action { docker push $img }
        }
        else {
            Write-Host "Docker daemon not available; using Cloud Build instead."
            Invoke-Step -Label "Build+push image via Cloud Build" -Action {
                & $script:GcloudCmd builds submit `
                    --project "$ProjectId" `
                    --config cloudbuild.ml-job.yaml `
                    --substitutions "_IMAGE_URI=$img" `
                    .
            }
        }
        Invoke-Step -Label "Terraform init" -Action { terraform -chdir="$TfDir" init }
        if ($AutoApprove) {
            Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply -auto-approve }
        }
        else {
            Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply }
        }
        Write-Host "Deployment complete."
        Write-Host "Ensure $TfDir/terraform.tfvars has container_image=$img"
    }
    "ib-gateway-setup" {
        Require-ProjectId
        Require-GcloudReady
        $env:JOB_NAME = "quantum-daily-ml"

        Invoke-Step -Label "Enable Compute Engine API" -Action { Ensure-GcpService -ServiceName "compute.googleapis.com" }
        Invoke-Step -Label "Enable Secret Manager API" -Action { Ensure-GcpService -ServiceName "secretmanager.googleapis.com" }
        Invoke-Step -Label "Ensure IB Gateway VM" -Action { Ensure-ComputeInstance }
        Invoke-Step -Label "Ensure VM Secret Manager access (scopes + IAM)" -Action { Ensure-InstanceSecretAccess }
        Invoke-Step -Label "Ensure IB API firewall rule" -Action { Ensure-FirewallRule }
        Invoke-Step -Label "Ensure IBKR username/password secrets" -Action {
            Ensure-Secret -SecretId "$IbUsernameSecretId"
            Ensure-Secret -SecretId "$IbPasswordSecretId"
        }

        if ($CreateSecretVersions) {
            Write-Host "Enter IBKR username (input hidden)"
            $u = Read-Host -AsSecureString
            Write-Host "Enter IBKR password (input hidden)"
            $p = Read-Host -AsSecureString

            $uPlain = Convert-SecureStringToPlainText -Value $u
            $pPlain = Convert-SecureStringToPlainText -Value $p

            if ([string]::IsNullOrWhiteSpace($uPlain)) {
                throw "IBKR username is empty. Re-run and enter a non-empty value."
            }
            if ([string]::IsNullOrWhiteSpace($pPlain)) {
                throw "IBKR password is empty. Re-run and enter a non-empty value."
            }

            $tmpU = Join-Path $env:TEMP "ibkr-username.txt"
            $tmpP = Join-Path $env:TEMP "ibkr-password.txt"
            Set-Content -Path $tmpU -Value $uPlain -NoNewline
            Set-Content -Path $tmpP -Value $pPlain -NoNewline

            try {
                Invoke-Step -Label "Add username secret version" -Action {
                    & $script:GcloudCmd secrets versions add "$IbUsernameSecretId" --project "$ProjectId" --data-file "$tmpU"
                }
                Invoke-Step -Label "Add password secret version" -Action {
                    & $script:GcloudCmd secrets versions add "$IbPasswordSecretId" --project "$ProjectId" --data-file "$tmpP"
                }
            }
            finally {
                Remove-Item -Path $tmpU -Force -ErrorAction SilentlyContinue
                Remove-Item -Path $tmpP -Force -ErrorAction SilentlyContinue
            }
        }

        if ($InstallIbSoftware) {
            Invoke-Step -Label "Install Java + IB Gateway + IBC + systemd on VM" -Action { Invoke-IbBootstrap }
            Wait-GatewayReady -TimeoutSeconds $GatewayReadyTimeoutSeconds | Out-Null
        }

        if ($ApplyTerraformAfterSetup) {
            Invoke-Step -Label "Terraform init" -Action { terraform -chdir="$TfDir" init }
            if ($AutoApprove) {
                Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply -auto-approve }
            }
            else {
                Invoke-Step -Label "Terraform apply" -Action { terraform -chdir="$TfDir" apply }
            }
        }

        if ($RunCloudRunAfterSetup) {
            if (-not $ApplyTerraformAfterSetup) {
                Write-Warning "RunCloudRunAfterSetup enabled without ApplyTerraformAfterSetup; using current deployed config."
            }
            Invoke-Step -Label "Execute Cloud Run job + verify parquet" -Action { Invoke-CloudRunAndCheckParquet }
        }

        Write-Host ""
        Write-Host "IB Gateway base infrastructure is ready."
        Write-Host "Next actions:"
        Write-Host "1) If first login is pending, complete interactive IBKR auth (2FA/trust device) on VM."
        Write-Host "2) Verify services: ibgateway active, ibgateway-proxy active, and port $IbApiPort listening."
        Write-Host "3) Set infra/terraform.tfvars: ibkr_tws_endpoint, ibkr_port, ibkr_username_secret_id, ibkr_password_secret_id."
        Write-Host "4) Run .\scripts\deploy.ps1 -Target tf-only -ProjectId $ProjectId"
    }
}
