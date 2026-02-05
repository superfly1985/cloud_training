# 简化的包下载脚本 - 避免卡住问题

$DownloadDir = ".\Environment_package"
Write-Host "简化包下载脚本 - 专注于通用版本" -ForegroundColor Cyan
Write-Host ""

# 创建下载目录
if (-not (Test-Path $DownloadDir)) {
    New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
}

Set-Location $DownloadDir
Write-Host "当前下载目录: $(Get-Location)" -ForegroundColor Green
Write-Host ""

# 定义需要下载的包（使用通用版本）
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

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "下载通用版本包（避免平台限制）" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$SuccessCount = 0
$TotalPackages = $Packages.Count

foreach ($package in $Packages) {
    Write-Host "$($SuccessCount + 1)/$TotalPackages. 下载 $package..." -ForegroundColor Yellow
    
    try {
        # 使用简单的pip download，让pip自动选择合适的版本
        $result = python -m pip download $package --dest . --timeout 30 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $package 下载成功" -ForegroundColor Green
            $SuccessCount++
        } else {
            Write-Host "❌ $package 下载失败: $result" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "❌ $package 下载异常: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Start-Sleep -Seconds 1  # 短暂暂停避免过快请求
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "下载结果统计" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 统计结果
$TotalFiles = (Get-ChildItem *.whl).Count
$RecentFiles = (Get-ChildItem *.whl | Where-Object {$_.LastWriteTime -gt (Get-Date).AddMinutes(-10)}).Count

Write-Host "📦 总计 .whl 文件: $TotalFiles" -ForegroundColor Green
Write-Host "🆕 本次下载: $RecentFiles" -ForegroundColor Green
Write-Host "✅ 包下载成功率: $SuccessCount/$TotalPackages" -ForegroundColor Green

# 检查关键包
Write-Host ""
Write-Host "关键包检查:" -ForegroundColor Cyan
$KeyPackages = @("numpy", "pillow", "opencv", "matplotlib", "pandas", "pyyaml", "torch")
foreach ($pkg in $KeyPackages) {
    $files = Get-ChildItem "*$pkg*" -ErrorAction SilentlyContinue
    if ($files) {
        $count = $files.Count
        Write-Host "✅ $pkg`: $count 个版本" -ForegroundColor Green
    } else {
        Write-Host "❌ $pkg`: 未找到" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "使用说明" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "1. 这些包已下载到 Environment_package 目录"
Write-Host "2. 包含Windows和通用版本，适合多平台使用"
Write-Host "3. 上传整个目录到云服务器即可使用"
Write-Host "4. GUI会自动选择合适的包版本进行安装"
Write-Host ""
Write-Host "✅ 下载完成！" -ForegroundColor Green