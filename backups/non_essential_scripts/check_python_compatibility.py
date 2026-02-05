#!/usr/bin/env python3
"""
检查Environment_package目录中包的Python版本兼容性
"""

import os
import zipfile
import json
import re
from pathlib import Path

def extract_metadata_from_wheel(wheel_path):
    """从wheel文件中提取元数据"""
    try:
        with zipfile.ZipFile(wheel_path, 'r') as wheel:
            # 查找METADATA文件
            metadata_files = [f for f in wheel.namelist() if f.endswith('METADATA') or f.endswith('PKG-INFO')]
            if not metadata_files:
                return None
            
            metadata_content = wheel.read(metadata_files[0]).decode('utf-8')
            return metadata_content
    except Exception as e:
        print(f"❌ 无法读取 {wheel_path}: {e}")
        return None

def parse_python_requires(metadata_content):
    """解析Python版本要求"""
    if not metadata_content:
        return None
    
    # 查找Requires-Python字段
    for line in metadata_content.split('\n'):
        if line.startswith('Requires-Python:'):
            return line.split(':', 1)[1].strip()
    
    return None

def check_python_38_compatibility(requires_python):
    """检查是否与Python 3.8兼容"""
    if not requires_python:
        return True  # 没有指定要求，假设兼容
    
    # 移除空格
    requires_python = requires_python.replace(' ', '')
    
    # 常见的不兼容模式
    incompatible_patterns = [
        r'>=3\.9',  # 要求3.9+
        r'>3\.8',   # 要求大于3.8
        r'>=3\.10', # 要求3.10+
        r'>=3\.11', # 要求3.11+
        r'>=3\.12', # 要求3.12+
    ]
    
    for pattern in incompatible_patterns:
        if re.search(pattern, requires_python):
            return False
    
    return True

def main():
    """主函数"""
    package_dir = Path("Environment_package")
    
    if not package_dir.exists():
        print("❌ Environment_package目录不存在")
        return
    
    print("🔍 检查Python 3.8兼容性...")
    print("=" * 60)
    
    compatible_packages = []
    incompatible_packages = []
    unknown_packages = []
    
    wheel_files = list(package_dir.glob("*.whl"))
    
    for wheel_file in wheel_files:
        print(f"\n📦 检查: {wheel_file.name}")
        
        metadata = extract_metadata_from_wheel(wheel_file)
        python_requires = parse_python_requires(metadata)
        
        if python_requires:
            print(f"   Python要求: {python_requires}")
            if check_python_38_compatibility(python_requires):
                print("   ✅ 与Python 3.8兼容")
                compatible_packages.append(wheel_file.name)
            else:
                print("   ❌ 与Python 3.8不兼容")
                incompatible_packages.append((wheel_file.name, python_requires))
        else:
            print("   ⚠️  未指定Python版本要求")
            unknown_packages.append(wheel_file.name)
    
    # 统计结果
    print("\n" + "=" * 60)
    print("📊 兼容性统计:")
    print(f"   总包数: {len(wheel_files)}")
    print(f"   ✅ 兼容包: {len(compatible_packages)}")
    print(f"   ❌ 不兼容包: {len(incompatible_packages)}")
    print(f"   ⚠️  未知包: {len(unknown_packages)}")
    
    if incompatible_packages:
        print("\n❌ 不兼容的包:")
        for pkg_name, requires in incompatible_packages:
            print(f"   - {pkg_name} (要求: {requires})")
    
    if unknown_packages:
        print("\n⚠️  未指定Python版本要求的包:")
        for pkg_name in unknown_packages:
            print(f"   - {pkg_name}")
    
    # 生成兼容性报告
    report = {
        "total_packages": len(wheel_files),
        "compatible_packages": compatible_packages,
        "incompatible_packages": [{"name": name, "requires": req} for name, req in incompatible_packages],
        "unknown_packages": unknown_packages,
        "python_version": "3.8.10"
    }
    
    with open("python_compatibility_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 详细报告已保存到: python_compatibility_report.json")

if __name__ == "__main__":
    main()