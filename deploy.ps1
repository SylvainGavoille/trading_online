param(
    [string]$ProjectId  = "sylvain-488510",
    [string]$Region     = "us-central1",
    [string]$ArRepo     = "quantum",
    [string]$ImageName  = "quantum-ml",
    [string]$ImageTag   = "latest",
    [string]$TfDir      = "infra",
    [switch]$BuildOnly,
    [switch]$TfOnly
)

$ErrorActionPreference = "Stop"

$ImageUri = "$Region-docker.pkg.dev/$ProjectId/$ArRepo/$ImageName`:$ImageTag"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }

if (-not $TfOnly) {
    Step "Building image on Cloud Build (no local Docker needed)"
    $WinDir = (Get-Location).Path
    $WslDir = bash -c "wslpath '$($WinDir -replace '\\\\', '/')'"
    bash -c "cd '$WslDir' && CLOUDSDK_CONFIG=/mnt/c/Users/sylva/AppData/Roaming/gcloud gcloud builds submit --project $ProjectId --config cloudbuild.yaml --substitutions _IMAGE_URI=$ImageUri ."
    if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed" }
    Ok "Built & pushed: $ImageUri"
}

if (-not $BuildOnly) {
    Step "Terraform init"
    terraform "-chdir=$TfDir" init
    if ($LASTEXITCODE -ne 0) { throw "terraform init failed" }

    Step "Terraform apply"
    terraform "-chdir=$TfDir" apply
    if ($LASTEXITCODE -ne 0) { throw "terraform apply failed" }
}

Write-Host "`nDeployment complete." -ForegroundColor Green
Write-Host "Image: $ImageUri"
