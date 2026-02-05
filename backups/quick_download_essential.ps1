# 快速下载最关键的包（PowerShell版本）

$DownloadDir = ".\Environment_package"
$Timeout = 30

Write-Host "快速下载最关键的包（避免卡住）..." -ForegroundColor Cyan
Write-Host ""

# 创建下载目录
if (-not (Test-Path $DownloadDir)) {
    New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
}

Set-Location $DownloadDir
Write-Host "当前下载目录: $(Get-Location)" -ForegroundColor Green
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "下载最关键的Linux兼容包" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 定义关键包
$CriticalPackages = @{
    "numpy" = "numpy==1.24.4"
    "pillow" = "pillow==10.0.1"
    "opencv-python" = "opencv-python==4.8.1.78"
    "matplotlib" = "matplotlib==3.7.2"
    "pandas" = "pandas==2.0.3"
    "pyyaml" = "pyyaml==6.0.1"
}

$SuccessCount = 0
$TotalPackages = $CriticalPackages.Count

foreach ($package in $CriticalPackages.GetEnumerator()) {
    $packageName = $package.Key
    $packageSpec = $package.Value
    
    Write-Host "$($SuccessCount + 1). 下载 $packageName（Linux版本）..." -ForegroundColor Yellow
    
    try {
        $process = Start-Process -FilePath "python" -ArgumentList @(
            "-m", "pip", "download", $packageSpec,
            "--platform", "linux_x86_64",
            "--only-binary=:all:",
            "--dest", ".",
            "--timeout", $Timeout
        ) -Wait -PassThru -NoNewWindow -RedirectStandardError "error.log"
        
        if ($process.ExitCode -eq 0) {
            Write-Host "✅ $packageName 下载成功" -ForegroundColor Green
            $SuccessCount++
        } else {
            Write-Host "❌ $packageName 下载失败" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "❌ $packageName 下载异常: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "下载通用包（备选方案）" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "下载通用版本作为备选..." -ForegroundColor Yellow
try {
    $process = Start-Process -FilePath "python" -ArgumentList @(
        "-m", "pip", "download",
        "numpy", "pillow", "opencv-python", "matplotlib", "pandas", "pyyaml",
        "--dest", ".",
        "--timeout", $Timeout
    ) -Wait -PassThru -NoNewWindow -RedirectStandardError "error_universal.log"
    
    if ($process.ExitCode -eq 0) {
        Write-Host "✅ 通用版本下载成功" -ForegroundColor Green
    } else {
        Write-Host "❌ 通用版本下载失败" -ForegroundColor Red
    }
}
catch {
    Write-Host "❌ 通用版本下载异常: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "检查下载结果" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 检查关键包
$CheckPackages = @("numpy", "pillow", "opencv", "matplotlib", "pandas", "pyyaml")
$FoundCount = 0

foreach ($package in $CheckPackages) {
    $files = Get-ChildItem -Name "*$package*" -ErrorAction SilentlyContinue
    if ($files) {
        Write-Host "✅ $package`: 已下载" -ForegroundColor Green
        $FoundCount++
    } else {
        Write-Host "❌ $package`: 缺失" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "下载成功率: $FoundCount/$($CheckPackages.Count) 个关键包" -ForegroundColor $(if ($FoundCount -ge 4) { "Green" } else { "Yellow" })

# 统计文件
$WhlFiles = Get-ChildItem -Name "*.whl" -ErrorAction SilentlyContinue
$TotalFiles = if ($WhlFiles) { $WhlFiles.Count } else { 0 }
Write-Host "📦 总计下载: $TotalFiles 个.whl文件"

if ($FoundCount -ge 4) {
    Write-Host "✅ 下载成功！已获得足够的关键包" -ForegroundColor Green
} else {
    Write-Host "⚠️ 下载不完整，建议检查网络连接后重试" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "使用说明" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "1. 这些Linux兼容包可以解决服务器安装问题"
Write-Host "2. 上传Environment_package目录到服务器"
Write-Host "3. GUI会自动选择合适的包版本"
Write-Host ""
Write-Host "如需下载更多包，请运行: bash manual_download_commands.sh"

# 清理错误日志
if (Test-Path "error.log") { Remove-Item "error.log" -Force }
if (Test-Path "error_universal.log") { Remove-Item "error_universal.log" -Force }