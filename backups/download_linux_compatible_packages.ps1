# 下载Linux兼容的Python包脚本
# 优先选择通用包（py3-none-any），避免Windows特定包

Write-Host "开始下载Linux兼容的Python包..." -ForegroundColor Green

# 清理旧包
$packageDir = ".\packages"
if (Test-Path $packageDir) {
    Write-Host "清理旧包目录..." -ForegroundColor Yellow
    Remove-Item $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $packageDir -Force | Out-Null

# 包列表 - 使用更灵活的版本策略
$packages = @(
    # 基础依赖 - 不指定具体版本，让pip选择最佳版本
    "setuptools",
    "wheel", 
    "typing-extensions",
    
    # PyYAML - 尝试不同版本
    "pyyaml",
    
    # 其他依赖
    "tqdm",
    "requests",
    "urllib3",
    "certifi",
    "charset-normalizer",
    "idna",
    
    # 科学计算包
    "numpy",
    "pillow",
    
    # OpenCV
    "opencv-python",
    
    # Ultralytics
    "ultralytics"
)

# PyTorch包单独处理
$torchPackages = @(
    "torch",
    "torchvision"
)

$downloadedPackages = @()
$failedPackages = @()

# 下载普通包
foreach ($package in $packages) {
    Write-Host "下载 $package ..." -ForegroundColor Cyan
    
    try {
        # 策略1: 尝试下载通用包
        Write-Host "  尝试通用版本..." -ForegroundColor Yellow
        $result = pip download --dest $packageDir --prefer-binary --platform any --no-deps $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ 通用版本下载成功" -ForegroundColor Green
            $downloadedPackages += $package
            continue
        }
        
        # 策略2: 尝试Linux版本
        Write-Host "  尝试Linux版本..." -ForegroundColor Yellow
        $result = pip download --dest $packageDir --prefer-binary --platform linux_x86_64 --no-deps $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Linux版本下载成功" -ForegroundColor Green
            $downloadedPackages += $package
            continue
        }
        
        # 策略3: 下载源码包
        Write-Host "  尝试源码包..." -ForegroundColor Yellow
        $result = pip download --dest $packageDir --no-binary=:all: --no-deps $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ 源码包下载成功" -ForegroundColor Green
            $downloadedPackages += $package
        } else {
            Write-Host "  ✗ 所有策略都失败: $result" -ForegroundColor Red
            $failedPackages += $package
        }
    }
    catch {
        Write-Host "  ✗ 下载异常: $($_.Exception.Message)" -ForegroundColor Red
        $failedPackages += $package
    }
}

# 下载PyTorch包（CPU版本）
foreach ($package in $torchPackages) {
    Write-Host "下载 $package (CPU版本)..." -ForegroundColor Cyan
    
    try {
        # 策略1: 从PyTorch官方源下载CPU版本
        Write-Host "  尝试PyTorch官方CPU版本..." -ForegroundColor Yellow
        $result = pip download --dest $packageDir --find-links https://download.pytorch.org/whl/cpu --no-deps $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ PyTorch CPU版本下载成功" -ForegroundColor Green
            $downloadedPackages += $package
            continue
        }
        
        # 策略2: 下载通用版本
        Write-Host "  尝试通用版本..." -ForegroundColor Yellow
        $result = pip download --dest $packageDir --prefer-binary --platform any --no-deps $package 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ 通用版本下载成功" -ForegroundColor Green
            $downloadedPackages += $package
        } else {
            Write-Host "  ✗ 下载失败: $result" -ForegroundColor Red
            $failedPackages += $package
        }
    }
    catch {
        Write-Host "  ✗ 下载异常: $($_.Exception.Message)" -ForegroundColor Red
        $failedPackages += $package
    }
}

# 统计结果
Write-Host "`n下载完成!" -ForegroundColor Green
Write-Host "成功下载: $($downloadedPackages.Count) 个包" -ForegroundColor Green
Write-Host "下载失败: $($failedPackages.Count) 个包" -ForegroundColor Red

if ($failedPackages.Count -gt 0) {
    Write-Host "`n失败的包:" -ForegroundColor Red
    $failedPackages | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

# 生成包清单
$manifestFile = "package_manifest_linux.txt"
Write-Host "`n生成包清单: $manifestFile" -ForegroundColor Cyan

$manifest = @()
$manifest += "# Linux兼容包清单 - $(Get-Date)"
$manifest += "# 总计: $($downloadedPackages.Count) 个包"
$manifest += ""

Get-ChildItem $packageDir -Filter "*" | Sort-Object Name | ForEach-Object {
    $manifest += $_.Name
}

$manifest | Out-File -FilePath $manifestFile -Encoding UTF8
Write-Host "包清单已保存到: $manifestFile" -ForegroundColor Green

# 检查关键包
Write-Host "`n检查关键包..." -ForegroundColor Cyan
$keyPackages = @("pyyaml", "torch", "torchvision", "ultralytics")
foreach ($key in $keyPackages) {
    $found = Get-ChildItem $packageDir -Filter "*$key*" | Select-Object -First 1
    if ($found) {
        Write-Host "  ✓ $key : $($found.Name)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $key : 未找到" -ForegroundColor Red
    }
}

# 检查是否有Windows特定包
Write-Host "`n检查Windows特定包..." -ForegroundColor Cyan
$winPackages = Get-ChildItem $packageDir -Filter "*win_amd64*" -ErrorAction SilentlyContinue
if ($winPackages) {
    Write-Host "  ⚠️ 发现Windows特定包:" -ForegroundColor Yellow
    $winPackages | ForEach-Object { Write-Host "    - $($_.Name)" -ForegroundColor Yellow }
} else {
    Write-Host "  ✓ 没有Windows特定包" -ForegroundColor Green
}

Write-Host "`n脚本执行完成!" -ForegroundColor Green