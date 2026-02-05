#!/bin/bash
# Linux/Mac自动下载脚本

echo "开始下载Python包..."
mkdir -p packages
cd packages

# 基础依赖包
echo "下载基础依赖包..."
pip download --no-deps setuptools==75.6.0
pip download --no-deps wheel==0.45.1
pip download --no-deps typing-extensions==4.8.0

# PyYAML源码包
echo "下载PyYAML源码包..."
pip download --no-binary=:all: --no-deps pyyaml==6.0.2

# 其他依赖
echo "下载其他依赖包..."
pip download --no-deps tqdm==4.67.1
pip download --no-deps requests==2.32.4
pip download --no-deps urllib3==2.2.3
pip download --no-deps certifi==2024.8.30
pip download --no-deps charset-normalizer==3.4.0
pip download --no-deps idna==3.10

# 科学计算包（Linux版本）
echo "下载科学计算包..."
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps numpy==1.24.4
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps pillow==10.4.0
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps opencv-python==4.10.0.84

# PyTorch CPU版本
echo "下载PyTorch CPU版本..."
pip download --find-links https://download.pytorch.org/whl/cpu --no-deps torch==2.4.1+cpu
pip download --find-links https://download.pytorch.org/whl/cpu --no-deps torchvision==0.19.1+cpu

# Ultralytics
echo "下载Ultralytics..."
pip download --no-deps ultralytics==8.0.196

echo "下载完成！"
echo "文件列表："
ls -la
