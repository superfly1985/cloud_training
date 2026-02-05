# Simple package download script
$DownloadDir = ".\Environment_package"

# Create download directory
if (-not (Test-Path $DownloadDir)) {
    New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
}

Set-Location $DownloadDir

# Define packages to download
$Packages = @(
    "numpy",
    "pillow", 
    "opencv-python",
    "matplotlib",
    "pandas",
    "pyyaml",
    "scipy",
    "torchvision"
)

Write-Host "Downloading packages..." -ForegroundColor Green

$SuccessCount = 0
foreach ($package in $Packages) {
    Write-Host "Downloading $package..." -ForegroundColor Yellow
    
    try {
        python -m pip download $package --dest . --timeout 30
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Success: $package" -ForegroundColor Green
            $SuccessCount++
        } else {
            Write-Host "Failed: $package" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "Error: $package" -ForegroundColor Red
    }
    
    Start-Sleep -Seconds 1
}

# Show results
$TotalFiles = (Get-ChildItem *.whl).Count
Write-Host ""
Write-Host "Total .whl files: $TotalFiles" -ForegroundColor Green
Write-Host "Success rate: $SuccessCount/$($Packages.Count)" -ForegroundColor Green
Write-Host "Download complete!" -ForegroundColor Green