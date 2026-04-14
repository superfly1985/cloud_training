#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器2深度检查 - 全盘扫描PyTorch和其他训练环境
"""

import paramiko
import json
import sys

HOST = "43.133.224.112"
PORT = 22
USERNAME = "root"
PASSWORD = "Vonzeus01"

def run_command(ssh, cmd, timeout=120):
    """执行命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

def main():
    output_lines = []
    
    def log(msg):
        try:
            print(msg)
        except:
            print(msg.encode('utf-8', errors='ignore').decode('utf-8'))
        output_lines.append(msg)
    
    log("="*80)
    log("服务器2深度环境扫描")
    log(f"服务器: {HOST}")
    log("="*80)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        log("\n连接服务器...")
        ssh.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=15)
        log("[OK] 连接成功\n")
        
        # 1. 全盘查找Python解释器
        log("-"*80)
        log("【全盘Python解释器扫描】")
        log("-"*80)
        out, err = run_command(ssh, 'find / -name "python*" -type f -executable 2>/dev/null | head -30')
        log(out if out else "未找到")
        
        # 2. 查找conda环境
        log("\n-"*80)
        log("【Conda环境检查】")
        log("-"*80)
        
        # 检查conda命令
        out, err = run_command(ssh, 'which conda && conda --version')
        log(f"Conda: {out if out else '未找到'}")
        
        # 列出所有conda环境
        out, err = run_command(ssh, 'conda env list 2>/dev/null || echo "无法获取conda环境列表"')
        log(f"\nConda环境列表:\n{out}")
        
        # 3. 深度检查miniforge3
        log("\n-"*80)
        log("【Miniforge3深度检查】")
        log("-"*80)
        
        out, err = run_command(ssh, 'ls -la /root/miniforge3/bin/python* 2>/dev/null')
        log(f"Python解释器:\n{out}")
        
        out, err = run_command(ssh, 'ls -la /root/miniforge3/lib/python3.10/site-packages/ 2>/dev/null | grep -E "torch|ultralytics|yaml|cv2"')
        log(f"\n关键包目录:\n{out if out else '未找到相关包'}")
        
        # 4. 检查pip安装的包
        log("\n-"*80)
        log("【Miniforge3 pip包列表】")
        log("-"*80)
        out, err = run_command(ssh, '/root/miniforge3/bin/python3 -m pip list 2>/dev/null')
        log(out if out else "无法获取")
        
        # 5. 尝试导入torch的不同方式
        log("\n-"*80)
        log("【PyTorch导入测试】")
        log("-"*80)
        
        test_commands = [
            ('torch导入', 'import torch; print(f"PyTorch: {torch.__version__}"); print(f"CUDA: {torch.cuda.is_available()}")'),
            ('Python路径', 'import sys; print(f"Python: {sys.executable}"); print(f"路径数: {len(sys.path)}")'),
            ('site-packages', 'import site; print(f"Site-packages: {site.getsitepackages()}")'),
        ]
        
        for name, cmd in test_commands:
            log(f"\n测试 [{name}]:")
            out, err = run_command(ssh, f'/root/miniforge3/bin/python3 -c "{cmd}" 2>&1')
            log(f"输出: {out if out else '无输出'}")
            if err:
                log(f"错误: {err[:200]}")
        
        # 6. 查找torch安装位置
        log("\n-"*80)
        log("【全盘查找torch安装】")
        log("-"*80)
        
        out, err = run_command(ssh, 'find / -name "torch" -type d 2>/dev/null | head -10')
        log(f"Torch目录:\n{out if out else '未找到'}")
        
        out, err = run_command(ssh, 'find / -name "__init__.py" -path "*/torch/*" 2>/dev/null | head -5')
        log(f"\nTorch __init__.py:\n{out if out else '未找到'}")
        
        # 7. 检查PYTHONPATH
        log("\n-"*80)
        log("【环境变量检查】")
        log("-"*80)
        
        out, err = run_command(ssh, 'echo $PYTHONPATH')
        log(f"PYTHONPATH: {out if out else '未设置'}")
        
        out, err = run_command(ssh, 'echo $PATH')
        log(f"PATH前5个: {':'.join(out.split(':')[:5])}")
        
        # 8. 检查site-packages的所有包
        log("\n-"*80)
        log("【Site-packages完整列表(前100个)】")
        log("-"*80)
        
        out, err = run_command(ssh, 'ls /root/miniforge3/lib/python3.10/site-packages/ 2>/dev/null | head -100')
        log(out if out else "无法获取")
        
        # 9. 检查是否有其他Python环境
        log("\n-"*80)
        log("【其他Python环境】")
        log("-"*80)
        
        out, err = run_command(ssh, 'ls -la /opt/ 2>/dev/null | grep -E "python|conda"')
        log(f"/opt/目录: {out if out else '无'}")
        
        out, err = run_command(ssh, 'ls -la /usr/local/lib/ 2>/dev/null | grep python')
        log(f"/usr/local/lib: {out if out else '无'}")
        
        # 10. 检查pip缓存和安装记录
        log("\n-"*80)
        log("【Pip安装历史】")
        log("-"*80)
        
        out, err = run_command(ssh, 'ls -la /root/.cache/pip/wheels 2>/dev/null | head -10')
        log(f"Pip缓存:\n{out if out else '无缓存'}")
        
        ssh.close()
        log("\n" + "="*80)
        log("检查完成")
        log("="*80)
        
        # 保存到文件
        with open('server2_check_result.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print("\n结果已保存到 server2_check_result.txt")
        
    except Exception as e:
        log(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
