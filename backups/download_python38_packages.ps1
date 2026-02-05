# 下载Python 3.8兼容的包
Write-Host "开始下载Python 3.8兼容的包..." -ForegroundColor Green

# 设置目标目录
$targetDir = "Environment_package"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force
}

# 清理旧包（可选）
Write-Host "清理旧包..." -ForegroundColor Yellow
Remove-Item "$targetDir\*.whl" -Force -ErrorAction SilentlyContinue

# 定义要下载的包列表（指定Python 3.8兼容版本）
$packages = @(
    # 基础包（通用版本，兼容Python 3.8）
    "setuptools==69.5.1",  # 最后支持Python 3.8的版本
    "wheel==0.43.0",       # 兼容Python 3.8
    "typing-extensions==4.8.0",  # 兼容Python 3.8的版本
    
    # 核心依赖包
    "tqdm==4.66.4",
    "pyyaml==6.0.1",
    "requests==2.31.0",
    "urllib3==2.0.7",
    "certifi==2024.2.2",
    "charset-normalizer==3.3.2",
    "idna==3.6",
    
    # 科学计算包
    "numpy==1.24.4",       # 最后支持Python 3.8的版本
    "pillow==10.0.1",      # 兼容Python 3.8
    "opencv-python==4.8.1.78",
    
    # PyTorch（CPU版本，兼容Python 3.8）
    "torch==2.0.1+cpu",
    "torchvision==0.15.2+cpu",
    
    # Ultralytics（兼容版本）
    "ultralytics==8.0.196"
)

# 下载计数器
$successCount = 0
$totalCount = $packages.Count

Write-Host "开始下载 $totalCount 个包..." -ForegroundColor Cyan

foreach ($package in $packages) {
    Write-Host "正在下载: $package" -ForegroundColor White
    
    try {
        # 使用pip download下载包，指定Python 3.8兼容性
        $result = pip download --dest $targetDir --python-version 38 --only-binary=:all: --timeout 60 $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 成功下载: $package" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "❌ 下载失败: $package" -ForegroundColor Red
            Write-Host "错误信息: $result" -ForegroundColor Red
            
            # 尝试不指定版本下载
            Write-Host "尝试下载通用版本..." -ForegroundColor Yellow
            $packageName = $package.Split("==")[0]
            $fallbackResult = pip download --dest $targetDir --prefer-binary --timeout 60 $packageName 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ 通用版本下载成功: $packageName" -ForegroundColor Green
                $successCount++
            } else {
                Write-Host "❌ 通用版本也下载失败: $packageName" -ForegroundColor Red
            }
        }
    }
    catch {
        Write-Host "❌ 下载异常: $package - $_" -ForegroundColor Red
    }
    
    Start-Sleep -Milliseconds 500  # 短暂延迟避免过于频繁的请求
}

# 特殊处理：下载PyTorch CPU版本（如果上面失败）
Write-Host "`n尝试从PyTorch官方源下载..." -ForegroundColor Cyan
try {
    $torchResult = pip download --dest $targetDir --index-url https://download.pytorch.org/whl/cpu --timeout 120 "torch==2.0.1+cpu" "torchvision==0.15.2+cpu" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ PyTorch CPU版本下载成功" -ForegroundColor Green
    } else {
        Write-Host "⚠️ PyTorch官方源下载失败，使用默认源版本" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠️ PyTorch官方源访问异常" -ForegroundColor Yellow
}

# 统计下载结果
Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "下载完成统计:" -ForegroundColor Green
Write-Host "成功下载: $successCount/$totalCount 个包" -ForegroundColor Green

# 检查下载的文件
$downloadedFiles = Get-ChildItem "$targetDir\*.whl" | Measure-Object
Write-Host "实际下载文件数: $($downloadedFiles.Count)" -ForegroundColor Green

if ($downloadedFiles.Count -gt 0) {
    Write-Host "`n下载的包文件:" -ForegroundColor Cyan
    Get-ChildItem "$targetDir\*.whl" | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor White
    }
    
    # 生成包清单
    Get-ChildItem "$targetDir\*.whl" | Out-File "$targetDir\package_manifest_python38.txt" -Encoding UTF8
    Write-Host "`n📄 包清单已保存到: package_manifest_python38.txt" -ForegroundColor Green
} else {
    Write-Host "⚠️ 没有成功下载任何包文件" -ForegroundColor Yellow
}

Write-Host "`n✅ Python 3.8兼容包下载完成！" -ForegroundColor Green