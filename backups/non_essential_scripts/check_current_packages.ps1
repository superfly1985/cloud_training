# 快速检查当前Environment_package目录中的包状态
# PowerShell版本

$PackageDir = ".\Environment_package"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "检查当前包状态" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "包目录: $PackageDir"
Write-Host ""

# 检查目录是否存在
if (-not (Test-Path $PackageDir)) {
    Write-Host "❌ 包目录不存在: $PackageDir" -ForegroundColor Red
    exit 1
}

# 定义需要检查的关键包
$RequiredPackages = @{
    "torch" = "PyTorch深度学习框架"
    "torchvision" = "PyTorch视觉库"
    "ultralytics" = "YOLO模型库"
    "numpy" = "数值计算库"
    "opencv" = "计算机视觉库"
    "pillow" = "图像处理库"
    "matplotlib" = "绘图库"
    "pandas" = "数据分析库"
    "pyyaml" = "YAML解析库"
    "tqdm" = "进度条库"
    "requests" = "HTTP请求库"
    "urllib3" = "URL处理库"
    "typing_extensions" = "类型扩展库"
    "networkx" = "网络分析库"
    "scipy" = "科学计算库"
}

Write-Host "检查关键包状态..." -ForegroundColor Yellow
Write-Host "----------------------------------------"

$MissingPackages = @()
$WindowsOnlyPackages = @()
$HasUniversalPackages = @()

foreach ($package in $RequiredPackages.Keys) {
    $description = $RequiredPackages[$package]
    
    # 检查是否有任何版本的包
    $packageFiles = Get-ChildItem -Path $PackageDir -Name "*$package*" -ErrorAction SilentlyContinue
    
    if ($packageFiles) {
        # 检查是否有通用版本
        $universalFiles = Get-ChildItem -Path $PackageDir -Name "*$package*py3-none-any*" -ErrorAction SilentlyContinue
        $py2py3Files = Get-ChildItem -Path $PackageDir -Name "*$package*py2.py3-none-any*" -ErrorAction SilentlyContinue
        
        if ($universalFiles -or $py2py3Files) {
            Write-Host "✅ $package`: 有通用版本 ($description)" -ForegroundColor Green
            $HasUniversalPackages += $package
        }
        # 检查是否只有Windows版本
        elseif (Get-ChildItem -Path $PackageDir -Name "*$package*win_amd64*" -ErrorAction SilentlyContinue) {
            Write-Host "⚠️ $package`: 仅Windows版本 ($description)" -ForegroundColor Yellow
            $WindowsOnlyPackages += $package
        }
        # 检查是否有Linux版本
        elseif (Get-ChildItem -Path $PackageDir -Name "*$package*linux*" -ErrorAction SilentlyContinue) {
            Write-Host "✅ $package`: 有Linux版本 ($description)" -ForegroundColor Green
            $HasUniversalPackages += $package
        }
        else {
            Write-Host "🔍 $package`: 有其他版本 ($description)" -ForegroundColor Cyan
            $HasUniversalPackages += $package
        }
    }
    else {
        Write-Host "❌ $package`: 完全缺失 ($description)" -ForegroundColor Red
        $MissingPackages += $package
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "统计结果" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 统计文件数量
$WhlFiles = Get-ChildItem -Path $PackageDir -Name "*.whl" -ErrorAction SilentlyContinue
$TarFiles = Get-ChildItem -Path $PackageDir -Name "*.tar.gz" -ErrorAction SilentlyContinue
$UniversalWhl = Get-ChildItem -Path $PackageDir -Name "*py3-none-any*.whl", "*py2.py3-none-any*.whl" -ErrorAction SilentlyContinue
$WindowsWhl = Get-ChildItem -Path $PackageDir -Name "*win_amd64*.whl" -ErrorAction SilentlyContinue
$LinuxWhl = Get-ChildItem -Path $PackageDir -Name "*linux*.whl" -ErrorAction SilentlyContinue

$TotalWhl = if ($WhlFiles) { $WhlFiles.Count } else { 0 }
$TotalTar = if ($TarFiles) { $TarFiles.Count } else { 0 }
$UniversalCount = if ($UniversalWhl) { $UniversalWhl.Count } else { 0 }
$WindowsCount = if ($WindowsWhl) { $WindowsWhl.Count } else { 0 }
$LinuxCount = if ($LinuxWhl) { $LinuxWhl.Count } else { 0 }

Write-Host "📦 总文件数: $($TotalWhl + $TotalTar)"
Write-Host "🔧 .whl文件: $TotalWhl"
Write-Host "📁 .tar.gz文件: $TotalTar"
Write-Host "🌐 通用包: $UniversalCount"
Write-Host "🪟 Windows包: $WindowsCount"
Write-Host "🐧 Linux包: $LinuxCount"

Write-Host ""
Write-Host "包状态分析:"
Write-Host "✅ 有通用/Linux版本: $($HasUniversalPackages.Count) 个" -ForegroundColor Green
Write-Host "⚠️ 仅Windows版本: $($WindowsOnlyPackages.Count) 个" -ForegroundColor Yellow
Write-Host "❌ 完全缺失: $($MissingPackages.Count) 个" -ForegroundColor Red

if ($MissingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "完全缺失的包:" -ForegroundColor Red
    foreach ($package in $MissingPackages) {
        Write-Host "  - $package"
    }
}

if ($WindowsOnlyPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "仅有Windows版本的包:" -ForegroundColor Yellow
    foreach ($package in $WindowsOnlyPackages) {
        Write-Host "  - $package"
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "建议操作" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if ($MissingPackages.Count -gt 0 -or $WindowsOnlyPackages.Count -gt 0) {
    Write-Host "🔄 建议运行 manual_download_commands.sh 来下载缺失的包" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "需要下载的包类型:"
    
    if ($MissingPackages.Count -gt 0) {
        Write-Host "  📥 完全缺失: $($MissingPackages -join ', ')" -ForegroundColor Red
    }
    
    if ($WindowsOnlyPackages.Count -gt 0) {
        Write-Host "  🔄 需要Linux版本: $($WindowsOnlyPackages -join ', ')" -ForegroundColor Yellow
    }
}
else {
    Write-Host "✅ 所有关键包都已准备就绪!" -ForegroundColor Green
    Write-Host "可以直接使用现有的包进行云训练"
}

Write-Host ""
Write-Host "运行下载脚本: bash manual_download_commands.sh"
Write-Host "检查GUI兼容性: python cloud_training_gui.py"