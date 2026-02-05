#!/bin/bash

echo "快速下载最关键的包（避免卡住）..."
echo

# 设置下载目录
DOWNLOAD_DIR="D:/OneDrive/24.Visual AI/training_scripts/Environment_package"
mkdir -p "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

echo "当前下载目录: $DOWNLOAD_DIR"
echo

# 设置超时时间
TIMEOUT=30

echo "=========================================="
echo "下载最关键的Linux兼容包"
echo "=========================================="

# 只下载最关键的包，避免卡住
echo "1. 下载numpy（Linux版本）..."
python3 -m pip download numpy==1.24.4 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ numpy下载失败"

echo "2. 下载pillow（Linux版本）..."
python3 -m pip download pillow==10.0.1 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ pillow下载失败"

echo "3. 下载opencv-python（Linux版本）..."
python3 -m pip download opencv-python==4.8.1.78 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ opencv-python下载失败"

echo "4. 下载matplotlib（Linux版本）..."
python3 -m pip download matplotlib==3.7.2 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ matplotlib下载失败"

echo "5. 下载pandas（Linux版本）..."
python3 -m pip download pandas==2.0.3 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ pandas下载失败"

echo "6. 下载pyyaml（Linux版本）..."
python3 -m pip download pyyaml==6.0.1 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ pyyaml下载失败"

echo ""
echo "=========================================="
echo "下载通用包（备选方案）"
echo "=========================================="

echo "7. 下载通用版本作为备选..."
python3 -m pip download numpy pillow opencv-python matplotlib pandas pyyaml --dest "$DOWNLOAD_DIR" --timeout $TIMEOUT || echo "❌ 通用版本下载失败"

echo ""
echo "=========================================="
echo "检查下载结果"
echo "=========================================="

# 检查关键包
CRITICAL_PACKAGES=("numpy" "pillow" "opencv" "matplotlib" "pandas" "pyyaml")
SUCCESS_COUNT=0

for package in "${CRITICAL_PACKAGES[@]}"; do
    if ls "$DOWNLOAD_DIR"/*${package}* >/dev/null 2>&1; then
        echo "✅ $package: 已下载"
        ((SUCCESS_COUNT++))
    else
        echo "❌ $package: 缺失"
    fi
done

echo ""
echo "下载成功率: $SUCCESS_COUNT/${#CRITICAL_PACKAGES[@]} 个关键包"

# 统计文件
TOTAL_FILES=$(ls "$DOWNLOAD_DIR"/*.whl 2>/dev/null | wc -l)
echo "📦 总计下载: $TOTAL_FILES 个.whl文件"

if [ $SUCCESS_COUNT -ge 4 ]; then
    echo "✅ 下载成功！已获得足够的关键包"
else
    echo "⚠️ 下载不完整，建议检查网络连接后重试"
fi

echo ""
echo "=========================================="
echo "使用说明"
echo "=========================================="
echo "1. 这些Linux兼容包可以解决服务器安装问题"
echo "2. 上传Environment_package目录到服务器"
echo "3. GUI会自动选择合适的包版本"
echo ""
echo "如需下载更多包，请运行: bash manual_download_commands.sh"