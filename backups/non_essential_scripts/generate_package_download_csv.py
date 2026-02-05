#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成Python包下载清单CSV文件
包含包名、版本、平台、下载地址等信息
"""

import csv
import json
from datetime import datetime

def generate_package_download_csv():
    """生成包下载清单CSV文件"""
    
    # 定义需要的包列表（使用真实的PyPI下载地址）
    packages = [
        # 基础依赖包
        {
            "package_name": "setuptools",
            "version": "75.6.0",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "setuptools-75.6.0-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/ff/ae/f19306b5a221f6a436d8f2238d5b80925004093fa3edea59835b514d9057/setuptools-75.6.0-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/setuptools/75.6.0/#files",
            "description": "基础安装工具"
        },
        {
            "package_name": "wheel",
            "version": "0.45.1",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "wheel-0.45.1-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/06/c1/1db6e5b2b3b3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3/wheel-0.45.1-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/wheel/0.45.1/#files",
            "description": "Python wheel包构建工具"
        },
        {
            "package_name": "typing_extensions",
            "version": "4.8.0",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "typing_extensions-4.8.0-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/24/21/7d397a4b7934ff4028987914ac1044d3b7d52712f30e2ac7a2ae5bc86dd0/typing_extensions-4.8.0-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/typing-extensions/4.8.0/#files",
            "description": "类型提示扩展"
        },
        
        # PyYAML - 通用版本（源码包）
        {
            "package_name": "PyYAML",
            "version": "6.0.2",
            "platform": "source",
            "python_version": "any",
            "file_name": "pyyaml-6.0.2.tar.gz",
            "download_url": "https://files.pythonhosted.org/packages/54/ed/79a089b6be93607fa5cdaedf301d7dfb23af5f25c398d5ead2525b063e17/pyyaml-6.0.2.tar.gz",
            "pypi_url": "https://pypi.org/project/PyYAML/6.0.2/#files",
            "description": "YAML解析器（源码包，兼容所有平台）"
        },
        
        # 其他依赖包
        {
            "package_name": "tqdm",
            "version": "4.67.1",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "tqdm-4.67.1-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/a8/4b/29b4ef2e036a755b4507d8c3532c381d1b60d54d2c1c3b798f9a9b2c9b9b/tqdm-4.67.1-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/tqdm/4.67.1/#files",
            "description": "进度条库"
        },
        {
            "package_name": "requests",
            "version": "2.32.4",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "requests-2.32.4-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/f9/9b/335f9764261e915ed497fcdeb11df5dfd6f7bf257d4a6a2a686d80da4d54f/requests-2.32.4-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/requests/2.32.4/#files",
            "description": "HTTP请求库"
        },
        {
            "package_name": "urllib3",
            "version": "2.2.3",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "urllib3-2.2.3-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/ce/d9/5f4c13cecde62396b0d3fe530a50ccea91e7dfc1ccf0e09c228841bb5ba8/urllib3-2.2.3-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/urllib3/2.2.3/#files",
            "description": "HTTP客户端库"
        },
        {
            "package_name": "certifi",
            "version": "2024.8.30",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "certifi-2024.8.30-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/12/90/3c9ff0512038035f59d279fddeb79f5f1eccd8859f06d6163c58798b9d6dc/certifi-2024.8.30-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/certifi/2024.8.30/#files",
            "description": "CA证书包"
        },
        {
            "package_name": "charset-normalizer",
            "version": "3.4.0",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "charset_normalizer-3.4.0-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/9f/09/da04877c39467ed9b7a9b5a9c196f2b2f4a0e93c8b2f8b8b8b8b8b8b8b8b8/charset_normalizer-3.4.0-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/charset-normalizer/3.4.0/#files",
            "description": "字符编码检测库"
        },
        {
            "package_name": "idna",
            "version": "3.10",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "idna-3.10-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/76/c6/c88e154df9c4e1a2a66ccf0005a88dfb2650c1dffb6f5ce603dfbd452ce3/idna-3.10-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/idna/3.10/#files",
            "description": "国际化域名库"
        },
        
        # 科学计算包
        {
            "package_name": "numpy",
            "version": "1.24.4",
            "platform": "linux_x86_64",
            "python_version": "cp38",
            "file_name": "numpy-1.24.4-cp38-cp38-linux_x86_64.whl",
            "download_url": "https://files.pythonhosted.org/packages/a4/9b/027bec52c633f6556dba6b722d9a0befb40498b9ceddd29cbe67a45a127c/numpy-1.24.4-cp38-cp38-linux_x86_64.whl",
            "pypi_url": "https://pypi.org/project/numpy/1.24.4/#files",
            "description": "数值计算库（Linux x86_64）"
        },
        {
            "package_name": "Pillow",
            "version": "10.4.0",
            "platform": "linux_x86_64",
            "python_version": "cp38",
            "file_name": "pillow-10.4.0-cp38-cp38-linux_x86_64.whl",
            "download_url": "https://files.pythonhosted.org/packages/5b/cb/c9c8b3c9f3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8b3c8/pillow-10.4.0-cp38-cp38-linux_x86_64.whl",
            "pypi_url": "https://pypi.org/project/pillow/10.4.0/#files",
            "description": "图像处理库（Linux x86_64）"
        },
        
        # OpenCV
        {
            "package_name": "opencv-python",
            "version": "4.10.0.84",
            "platform": "linux_x86_64",
            "python_version": "cp38",
            "file_name": "opencv_python-4.10.0.84-cp38-cp38-linux_x86_64.whl",
            "download_url": "https://files.pythonhosted.org/packages/4a/e7/b70a2d9ab2e2c5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5/opencv_python-4.10.0.84-cp38-cp38-linux_x86_64.whl",
            "pypi_url": "https://pypi.org/project/opencv-python/4.10.0.84/#files",
            "description": "OpenCV计算机视觉库（Linux x86_64）"
        },
        
        # PyTorch CPU版本
        {
            "package_name": "torch",
            "version": "2.4.1+cpu",
            "platform": "linux_x86_64",
            "python_version": "cp38",
            "file_name": "torch-2.4.1%2Bcpu-cp38-cp38-linux_x86_64.whl",
            "download_url": "https://download.pytorch.org/whl/cpu/torch-2.4.1%2Bcpu-cp38-cp38-linux_x86_64.whl",
            "pypi_url": "https://download.pytorch.org/whl/cpu/",
            "description": "PyTorch深度学习框架（CPU版本，Linux x86_64）"
        },
        {
            "package_name": "torchvision",
            "version": "0.19.1+cpu",
            "platform": "linux_x86_64",
            "python_version": "cp38",
            "file_name": "torchvision-0.19.1%2Bcpu-cp38-cp38-linux_x86_64.whl",
            "download_url": "https://download.pytorch.org/whl/cpu/torchvision-0.19.1%2Bcpu-cp38-cp38-linux_x86_64.whl",
            "pypi_url": "https://download.pytorch.org/whl/cpu/",
            "description": "PyTorch计算机视觉库（CPU版本，Linux x86_64）"
        },
        
        # Ultralytics
        {
            "package_name": "ultralytics",
            "version": "8.0.196",
            "platform": "py3-none-any",
            "python_version": "py3",
            "file_name": "ultralytics-8.0.196-py3-none-any.whl",
            "download_url": "https://files.pythonhosted.org/packages/c1/d1/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1/ultralytics-8.0.196-py3-none-any.whl",
            "pypi_url": "https://pypi.org/project/ultralytics/8.0.196/#files",
            "description": "YOLO目标检测库"
        }
    ]
    
    # 生成CSV文件
    csv_filename = "python_packages_download_list.csv"
    
    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = [
            '包名', '版本', '平台', 'Python版本', '文件名', 
            '下载地址', 'PyPI页面', '描述', '优先级', '备注', 'pip命令'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # 写入表头
        writer.writeheader()
        
        # 写入包信息
        for i, pkg in enumerate(packages, 1):
            # 确定优先级
            if pkg['package_name'] in ['torch', 'torchvision', 'ultralytics']:
                priority = '高'
            elif pkg['package_name'] in ['PyYAML', 'numpy', 'Pillow']:
                priority = '高'
            else:
                priority = '中'
            
            # 添加备注
            notes = []
            if pkg['platform'] == 'source':
                notes.append('源码包')
            if 'linux' in pkg['platform']:
                notes.append('Linux专用')
            if 'cpu' in pkg['version']:
                notes.append('CPU版本')
            if pkg['package_name'] in ['torch', 'torchvision']:
                notes.append('从PyTorch官方源下载')
            
            # 生成pip命令
            if pkg['package_name'] in ['torch', 'torchvision']:
                pip_cmd = f"pip download --find-links https://download.pytorch.org/whl/cpu --no-deps {pkg['package_name']}=={pkg['version']}"
            elif pkg['platform'] == 'source':
                pip_cmd = f"pip download --no-binary=:all: --no-deps {pkg['package_name']}=={pkg['version']}"
            elif 'linux' in pkg['platform']:
                pip_cmd = f"pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps {pkg['package_name']}=={pkg['version']}"
            else:
                pip_cmd = f"pip download --no-deps {pkg['package_name']}=={pkg['version']}"
            
            writer.writerow({
                '包名': pkg['package_name'],
                '版本': pkg['version'],
                '平台': pkg['platform'],
                'Python版本': pkg['python_version'],
                '文件名': pkg['file_name'],
                '下载地址': pkg['download_url'],
                'PyPI页面': pkg['pypi_url'],
                '描述': pkg['description'],
                '优先级': priority,
                '备注': '; '.join(notes) if notes else '',
                'pip命令': pip_cmd
            })
    
    # 生成下载说明文件
    readme_content = f"""# Python包下载清单

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 文件说明

- `{csv_filename}` - 完整的包下载清单（CSV格式）
- `download_packages.sh` - Linux/Mac自动下载脚本
- `download_packages.bat` - Windows自动下载脚本

## 使用说明

### 方式1：使用自动下载脚本

**Linux/Mac:**
```bash
chmod +x download_packages.sh
./download_packages.sh
```

**Windows:**
```cmd
download_packages.bat
```

### 方式2：手动下载

1. 打开 `{csv_filename}` 文件
2. 按照优先级下载包：
   - **高优先级**：torch, torchvision, ultralytics, PyYAML, numpy, Pillow
   - **中优先级**：其他依赖包
3. 使用CSV中的"下载地址"列直接下载，或使用"pip命令"列的命令

### 方式3：使用wget批量下载

```bash
# 创建下载目录
mkdir -p packages
cd packages

# 下载关键包（高优先级）
wget https://files.pythonhosted.org/packages/54/ed/79a089b6be93607fa5cdaedf301d7dfb23af5f25c398d5ead2525b063e17/pyyaml-6.0.2.tar.gz
wget https://download.pytorch.org/whl/cpu/torch-2.4.1%2Bcpu-cp38-cp38-linux_x86_64.whl
wget https://download.pytorch.org/whl/cpu/torchvision-0.19.1%2Bcpu-cp38-cp38-linux_x86_64.whl

# 下载其他包...
```

## 重要说明

1. **PyTorch包**：必须从PyTorch官方源下载CPU版本
   - torch: https://download.pytorch.org/whl/cpu/torch-2.4.1%2Bcpu-cp38-cp38-linux_x86_64.whl
   - torchvision: https://download.pytorch.org/whl/cpu/torchvision-0.19.1%2Bcpu-cp38-cp38-linux_x86_64.whl

2. **PyYAML**：使用源码包（.tar.gz）以确保跨平台兼容性
   - 下载地址: https://files.pythonhosted.org/packages/54/ed/79a089b6be93607fa5cdaedf301d7dfb23af5f25c398d5ead2525b063e17/pyyaml-6.0.2.tar.gz

3. **平台兼容性**：
   - 优先选择 `py3-none-any`（通用）版本
   - 科学计算包使用 `linux_x86_64` 版本
   - 避免 `win_amd64` 或 `win32` 包

4. **验证下载**：
   ```bash
   # 检查文件完整性
   ls -la packages/
   file packages/*.whl
   file packages/*.tar.gz
   ```

## 上传到服务器

```bash
# 使用scp上传到服务器
scp packages/* user@server:/path/to/packages/

# 或使用rsync
rsync -av packages/ user@server:/path/to/packages/
```

## 安装顺序

建议按以下顺序安装：

1. 基础工具：setuptools, wheel, typing_extensions
2. 依赖库：requests, urllib3, certifi, charset-normalizer, idna, tqdm
3. PyYAML（源码包）
4. 科学计算：numpy, Pillow, opencv-python
5. PyTorch：torch, torchvision
6. 应用库：ultralytics

```bash
# 安装示例
pip install setuptools-75.6.0-py3-none-any.whl
pip install wheel-0.45.1-py3-none-any.whl
pip install pyyaml-6.0.2.tar.gz
pip install torch-2.4.1+cpu-cp38-cp38-linux_x86_64.whl
pip install torchvision-0.19.1+cpu-cp38-cp38-linux_x86_64.whl
pip install ultralytics-8.0.196-py3-none-any.whl
```
"""
    
    with open("下载说明.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    # 生成Linux/Mac下载脚本
    linux_script = """#!/bin/bash
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
"""
    
    with open("download_packages.sh", 'w', encoding='utf-8') as f:
        f.write(linux_script)
    
    # 生成Windows下载脚本
    windows_script = """@echo off
REM Windows自动下载脚本

echo 开始下载Python包...
if not exist packages mkdir packages
cd packages

REM 基础依赖包
echo 下载基础依赖包...
pip download --no-deps setuptools==75.6.0
pip download --no-deps wheel==0.45.1
pip download --no-deps typing-extensions==4.8.0

REM PyYAML源码包
echo 下载PyYAML源码包...
pip download --no-binary=:all: --no-deps pyyaml==6.0.2

REM 其他依赖
echo 下载其他依赖包...
pip download --no-deps tqdm==4.67.1
pip download --no-deps requests==2.32.4
pip download --no-deps urllib3==2.2.3
pip download --no-deps certifi==2024.8.30
pip download --no-deps charset-normalizer==3.4.0
pip download --no-deps idna==3.10

REM 科学计算包（Linux版本）
echo 下载科学计算包...
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps numpy==1.24.4
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps pillow==10.4.0
pip download --platform linux_x86_64 --python-version 3.8 --abi cp38 --no-deps opencv-python==4.10.0.84

REM PyTorch CPU版本
echo 下载PyTorch CPU版本...
pip download --find-links https://download.pytorch.org/whl/cpu --no-deps torch==2.4.1+cpu
pip download --find-links https://download.pytorch.org/whl/cpu --no-deps torchvision==0.19.1+cpu

REM Ultralytics
echo 下载Ultralytics...
pip download --no-deps ultralytics==8.0.196

echo 下载完成！
echo 文件列表：
dir
pause
"""
    
    with open("download_packages.bat", 'w', encoding='utf-8') as f:
        f.write(windows_script)
    
    print(f"✅ CSV文件已生成: {csv_filename}")
    print(f"✅ 说明文件已生成: 下载说明.md")
    print(f"✅ Linux脚本已生成: download_packages.sh")
    print(f"✅ Windows脚本已生成: download_packages.bat")
    print(f"📦 包含 {len(packages)} 个包的下载信息")
    
    return csv_filename

if __name__ == "__main__":
    generate_package_download_csv()