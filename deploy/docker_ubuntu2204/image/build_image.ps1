param(
    [string]$ImageRepo = "cloud-training",
    [string]$ImageTag = "v2.3.0"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$imageRef = "$ImageRepo`:$ImageTag"

Write-Host "Building image: $imageRef"
docker build -t $imageRef -f "$scriptDir\Dockerfile" $scriptDir
if ($LASTEXITCODE -ne 0) {
    throw "docker build failed with exit code $LASTEXITCODE"
}

Write-Host "Running environment verify..."
docker run --rm --gpus all $imageRef python /workspace/verify_env.py
if ($LASTEXITCODE -ne 0) {
    throw "docker run verify failed with exit code $LASTEXITCODE"
}

Write-Host "Done: $imageRef"
