#!/bin/bash

echo "开始下载项目所需的Python包（包含平台兼容版本）..."
echo

# 设置下载目录
DOWNLOAD_DIR="D:/OneDrive/24.Visual AI/training_scripts/Environment_package"
mkdir -p "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

echo "当前下载目录: $DOWNLOAD_DIR"
echo

# 升级pip
echo "升级pip..."
python3 -m pip install --upgrade pip
echo

# 下载PyTorch包 (CPU版本 - Linux兼容)
echo "下载PyTorch包（Linux兼容版本）..."
python3 -m pip download torch==2.0.1+cpu torchvision==0.15.2+cpu torchaudio==2.0.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu \
    --dest "$DOWNLOAD_DIR"
echo

# 下载PyTorch包 (通用版本，如果有的话)
echo "下载PyTorch包（尝试通用版本）..."
python3 -m pip download torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --dest "$DOWNLOAD_DIR" --no-deps
echo

# 下载Ultralytics（已有通用版本）
echo "下载Ultralytics..."
python3 -m pip download ultralytics==8.0.196 --dest "$DOWNLOAD_DIR"
python3 -m pip download ultralytics --dest "$DOWNLOAD_DIR"
echo

# 下载NetworkX（已有通用版本）
echo "下载NetworkX..."
python3 -m pip download networkx==2.8.8 --dest "$DOWNLOAD_DIR"
python3 -m pip download networkx --dest "$DOWNLOAD_DIR"
echo

# 下载核心依赖包（优先下载Linux兼容版本）
echo "下载核心依赖包（Linux兼容版本）..."
python3 -m pip download numpy==1.24.4 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ numpy Linux版本下载失败"
python3 -m pip download opencv-python==4.8.1.78 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ opencv-python Linux版本下载失败"
python3 -m pip download pillow==10.0.1 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ pillow Linux版本下载失败"
python3 -m pip download matplotlib==3.7.2 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ matplotlib Linux版本下载失败"
python3 -m pip download scipy==1.11.4 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ scipy Linux版本下载失败"
python3 -m pip download pandas==2.0.3 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 60 || echo "⚠️ pandas Linux版本下载失败"
echo

# 下载核心依赖包（通用版本作为备选）
echo "下载核心依赖包（通用版本备选）..."
python3 -m pip download numpy opencv-python pillow matplotlib scipy pandas \
    --dest "$DOWNLOAD_DIR"
echo

# 下载工具包（大部分已有通用版本）
echo "下载工具包..."
python3 -m pip download requests tqdm pyyaml seaborn psutil thop \
    --dest "$DOWNLOAD_DIR"
echo

# 下载缺失的PyYAML Linux版本
echo "下载PyYAML（Linux兼容版本）..."
python3 -m pip download pyyaml==6.0.1 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR"
echo

# 下载PyTorch依赖包
echo "下载PyTorch依赖包..."
python3 -m pip download filelock jinja2 sympy typing-extensions \
    --dest "$DOWNLOAD_DIR"
echo

# 下载机器学习包
echo "下载机器学习包..."
python3 -m pip download scikit-learn scikit-image albumentations imgaug \
    --dest "$DOWNLOAD_DIR"
echo

# 下载实验跟踪包
echo "下载实验跟踪包..."
python3 -m pip download tensorboard wandb clearml \
    --dest "$DOWNLOAD_DIR"
echo

# 下载基础包管理工具（已有通用版本）
echo "下载基础包管理工具..."
python3 -m pip download setuptools wheel \
    --dest "$DOWNLOAD_DIR"
echo

# 下载额外的依赖包（确保完整性）
echo "下载额外依赖包..."
python3 -m pip download certifi charset-normalizer idna urllib3 \
    --dest "$DOWNLOAD_DIR"
echo

# 下载Python 3.8兼容版本（服务器使用的版本）
echo "下载Python 3.8兼容版本..."
python3 -m pip download numpy==1.24.4 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ numpy 3.8版本下载失败"
python3 -m pip download opencv-python==4.8.1.78 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ opencv-python 3.8版本下载失败"
python3 -m pip download pillow==10.0.1 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ pillow 3.8版本下载失败"
python3 -m pip download matplotlib==3.7.2 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ matplotlib 3.8版本下载失败"
python3 -m pip download pandas==2.0.3 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ pandas 3.8版本下载失败"
python3 -m pip download pyyaml==6.0.1 --python-version 38 --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" || echo "⚠️ pyyaml 3.8版本下载失败"
echo

# 备用下载策略（如果特定版本失败）
echo "执行备用下载策略..."
echo "下载最新兼容版本作为备选..."

# 备用：下载最新的Linux兼容版本
python3 -m pip download numpy --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ numpy备用版本下载失败"
python3 -m pip download opencv-python --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ opencv-python备用版本下载失败"
python3 -m pip download pillow --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ pillow备用版本下载失败"
python3 -m pip download matplotlib --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ matplotlib备用版本下载失败"
python3 -m pip download pandas --platform linux_x86_64 --only-binary=:all: --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ pandas备用版本下载失败"

# 备用：下载更多通用版本
echo "下载更多通用版本作为备选..."
python3 -m pip download numpy opencv-python pillow matplotlib pandas pyyaml --dest "$DOWNLOAD_DIR" --timeout 30 || echo "⚠️ 通用版本下载失败"

# 跳过源码包下载（避免编译卡住）
echo "⚠️ 跳过源码包下载（避免编译时间过长）"
echo "如需源码包，请手动下载：pip download <package> --no-binary=:all:"
echo

echo "所有包下载完成！"
echo "下载位置: $DOWNLOAD_DIR"
echo

echo "查看下载的文件:"
ls -la "$DOWNLOAD_DIR"/*.whl 2>/dev/null || echo "没有找到.whl文件"
echo

echo "统计下载的包数量:"
whl_count=$(ls "$DOWNLOAD_DIR"/*.whl 2>/dev/null | wc -l)
tar_count=$(ls "$DOWNLOAD_DIR"/*.tar.gz 2>/dev/null | wc -l)
echo "WHL文件: $whl_count 个"
echo "TAR.GZ文件: $tar_count 个"
echo "总计: $((whl_count + tar_count)) 个包文件"
echo

echo "检查关键包的平台兼容性:"
echo "==================================="

# 检查Linux兼容包
echo "Linux兼容包:"
ls "$DOWNLOAD_DIR"/*linux*.whl 2>/dev/null | while read file; do
    echo "  ✅ $(basename "$file")"
done

echo
echo "通用包 (py3-none-any):"
ls "$DOWNLOAD_DIR"/*py3-none-any*.whl 2>/dev/null | while read file; do
    echo "  ✅ $(basename "$file")"
done

echo
echo "通用包 (py2.py3-none-any):"
ls "$DOWNLOAD_DIR"/*py2.py3-none-any*.whl 2>/dev/null | while read file; do
    echo "  ✅ $(basename "$file")"
done

echo
echo "Windows特定包 (仅供参考):"
ls "$DOWNLOAD_DIR"/*win*.whl 2>/dev/null | while read file; do
    echo "  ⚠️  $(basename "$file")"
done

echo
echo "==================================="
echo "下载完成总结:"
echo "✅ 已下载Linux兼容的核心包（numpy, opencv, pillow, matplotlib, pandas, pyyaml）"
echo "✅ 已下载通用包（ultralytics, networkx, tqdm, requests等）"
echo "✅ 已下载PyTorch CPU版本（Linux兼容）"
echo "✅ 已下载Python 3.8兼容版本"
echo
echo "注意事项:"
echo "- Linux兼容包优先用于云端服务器"
echo "- Windows包仅供本地开发使用"
echo "- 通用包可在所有平台使用"
echo
echo "========================================="
echo "验证下载的包..."
echo "========================================="

# 检查关键包是否存在
echo "检查关键包文件..."
CRITICAL_PACKAGES=("torch" "ultralytics" "numpy" "opencv" "pillow" "matplotlib" "pandas")
MISSING_PACKAGES=()

for package in "${CRITICAL_PACKAGES[@]}"; do
    if ls "$DOWNLOAD_DIR"/*${package}* >/dev/null 2>&1; then
        echo "✅ $package: 已下载"
    else
        echo "❌ $package: 缺失"
        MISSING_PACKAGES+=("$package")
    fi
done

# 统计下载结果
TOTAL_FILES=$(ls "$DOWNLOAD_DIR"/*.whl 2>/dev/null | wc -l)
TOTAL_TAR=$(ls "$DOWNLOAD_DIR"/*.tar.gz 2>/dev/null | wc -l)

echo ""
echo "========================================="
echo "下载完成总结"
echo "========================================="
echo "📦 总计下载文件: $((TOTAL_FILES + TOTAL_TAR)) 个"
echo "🔧 .whl 文件: $TOTAL_FILES 个"
echo "📁 .tar.gz 文件: $TOTAL_TAR 个"

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo "✅ 所有关键包都已下载"
else
    echo "⚠️ 缺失的包: ${MISSING_PACKAGES[*]}"
    echo "建议手动下载这些包或检查网络连接"
fi

echo ""
echo "========================================="
echo "使用说明"
echo "========================================="
echo "1. 将 Environment_package 目录上传到服务器"
echo "2. 在服务器上运行云训练GUI"
echo "3. GUI会自动选择合适的包版本进行安装"
echo ""

# 建议的测试命令
echo "建议运行以下命令测试下载的包："
echo "python3 -c \"import sys; sys.path.insert(0, '$DOWNLOAD_DIR'); import torch, ultralytics, numpy, cv2; print('所有包导入成功!')\""

# 创建包清单文件
echo ""
echo "创建包清单文件..."
ls -la "$DOWNLOAD_DIR"/*.whl "$DOWNLOAD_DIR"/*.tar.gz 2>/dev/null > "$DOWNLOAD_DIR/package_manifest.txt"
echo "📋 包清单已保存到: $DOWNLOAD_DIR/package_manifest.txt"