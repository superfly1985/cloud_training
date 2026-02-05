#!/bin/bash

# 快速检查当前Environment_package目录中的包状态
# 用于确定还需要下载哪些包

PACKAGE_DIR="../Environment_package"

echo "=========================================="
echo "检查当前包状态"
echo "=========================================="
echo "包目录: $PACKAGE_DIR"
echo ""

# 检查目录是否存在
if [ ! -d "$PACKAGE_DIR" ]; then
    echo "❌ 包目录不存在: $PACKAGE_DIR"
    exit 1
fi

# 定义需要检查的关键包
declare -A REQUIRED_PACKAGES=(
    ["torch"]="PyTorch深度学习框架"
    ["torchvision"]="PyTorch视觉库"
    ["ultralytics"]="YOLO模型库"
    ["numpy"]="数值计算库"
    ["opencv"]="计算机视觉库"
    ["pillow"]="图像处理库"
    ["matplotlib"]="绘图库"
    ["pandas"]="数据分析库"
    ["pyyaml"]="YAML解析库"
    ["tqdm"]="进度条库"
    ["requests"]="HTTP请求库"
    ["urllib3"]="URL处理库"
    ["typing_extensions"]="类型扩展库"
    ["networkx"]="网络分析库"
    ["scipy"]="科学计算库"
)

echo "检查关键包状态..."
echo "----------------------------------------"

MISSING_PACKAGES=()
WINDOWS_ONLY_PACKAGES=()
HAS_UNIVERSAL_PACKAGES=()

for package in "${!REQUIRED_PACKAGES[@]}"; do
    description="${REQUIRED_PACKAGES[$package]}"
    
    # 检查是否有任何版本的包
    if ls "$PACKAGE_DIR"/*${package}* >/dev/null 2>&1; then
        # 检查是否有通用版本
        if ls "$PACKAGE_DIR"/*${package}*py3-none-any* >/dev/null 2>&1 || ls "$PACKAGE_DIR"/*${package}*py2.py3-none-any* >/dev/null 2>&1; then
            echo "✅ $package: 有通用版本 ($description)"
            HAS_UNIVERSAL_PACKAGES+=("$package")
        # 检查是否只有Windows版本
        elif ls "$PACKAGE_DIR"/*${package}*win_amd64* >/dev/null 2>&1; then
            echo "⚠️ $package: 仅Windows版本 ($description)"
            WINDOWS_ONLY_PACKAGES+=("$package")
        # 检查是否有Linux版本
        elif ls "$PACKAGE_DIR"/*${package}*linux* >/dev/null 2>&1; then
            echo "✅ $package: 有Linux版本 ($description)"
            HAS_UNIVERSAL_PACKAGES+=("$package")
        else
            echo "🔍 $package: 有其他版本 ($description)"
            HAS_UNIVERSAL_PACKAGES+=("$package")
        fi
    else
        echo "❌ $package: 完全缺失 ($description)"
        MISSING_PACKAGES+=("$package")
    fi
done

echo ""
echo "=========================================="
echo "统计结果"
echo "=========================================="

# 统计文件数量
TOTAL_WHL=$(ls "$PACKAGE_DIR"/*.whl 2>/dev/null | wc -l)
TOTAL_TAR=$(ls "$PACKAGE_DIR"/*.tar.gz 2>/dev/null | wc -l)
UNIVERSAL_WHL=$(ls "$PACKAGE_DIR"/*py3-none-any*.whl "$PACKAGE_DIR"/*py2.py3-none-any*.whl 2>/dev/null | wc -l)
WINDOWS_WHL=$(ls "$PACKAGE_DIR"/*win_amd64*.whl 2>/dev/null | wc -l)
LINUX_WHL=$(ls "$PACKAGE_DIR"/*linux*.whl 2>/dev/null | wc -l)

echo "📦 总文件数: $((TOTAL_WHL + TOTAL_TAR))"
echo "🔧 .whl文件: $TOTAL_WHL"
echo "📁 .tar.gz文件: $TOTAL_TAR"
echo "🌐 通用包: $UNIVERSAL_WHL"
echo "🪟 Windows包: $WINDOWS_WHL"
echo "🐧 Linux包: $LINUX_WHL"

echo ""
echo "包状态分析:"
echo "✅ 有通用/Linux版本: ${#HAS_UNIVERSAL_PACKAGES[@]} 个"
echo "⚠️ 仅Windows版本: ${#WINDOWS_ONLY_PACKAGES[@]} 个"
echo "❌ 完全缺失: ${#MISSING_PACKAGES[@]} 个"

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "完全缺失的包:"
    for package in "${MISSING_PACKAGES[@]}"; do
        echo "  - $package"
    done
fi

if [ ${#WINDOWS_ONLY_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "仅有Windows版本的包:"
    for package in "${WINDOWS_ONLY_PACKAGES[@]}"; do
        echo "  - $package"
    done
fi

echo ""
echo "=========================================="
echo "建议操作"
echo "=========================================="

if [ ${#MISSING_PACKAGES[@]} -gt 0 ] || [ ${#WINDOWS_ONLY_PACKAGES[@]} -gt 0 ]; then
    echo "🔄 建议运行 manual_download_commands.sh 来下载缺失的包"
    echo ""
    echo "需要下载的包类型:"
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo "  📥 完全缺失: ${MISSING_PACKAGES[*]}"
    fi
    
    if [ ${#WINDOWS_ONLY_PACKAGES[@]} -gt 0 ]; then
        echo "  🔄 需要Linux版本: ${WINDOWS_ONLY_PACKAGES[*]}"
    fi
else
    echo "✅ 所有关键包都已准备就绪!"
    echo "可以直接使用现有的包进行云训练"
fi

echo ""
echo "运行下载脚本: ./manual_download_commands.sh"
echo "检查GUI兼容性: python cloud_training_gui.py"