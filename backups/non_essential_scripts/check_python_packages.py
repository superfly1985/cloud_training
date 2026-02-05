#!/usr/bin/env python3
import paramiko
import json
import os

def run_ssh_command(ssh, command):
    """执行SSH命令"""
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        return {'success': True, 'output': output, 'error': error}
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}

def main():
    # 加载配置
    config_file = "cloud_training_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            server_config = config.get('server', {})
    else:
        print("❌ 配置文件不存在")
        return

    try:
        # 建立SSH连接
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            server_config['hostname'], 
            port=server_config['port'], 
            username=server_config['username'], 
            password=server_config['password']
        )
        print("✅ SSH连接成功")
        
        print("=" * 60)
        print("🔍 Python包详细检查:")
        
        # 检查pip list
        result = run_ssh_command(ssh, 'pip3 list')
        if result['success']:
            print("已安装的Python包:")
            lines = result['output'].split('\n')
            for line in lines[:40]:  # 显示前40个包
                if line.strip() and not line.startswith('Package') and not line.startswith('---'):
                    print(f"  {line}")
        else:
            print(f"❌ pip3 list 失败: {result['error']}")
        
        print("\n🔍 检查特定目录的Python包:")
        
        # 检查系统Python包目录
        dirs_to_check = [
            '/usr/lib/python3.8/dist-packages/',
            '/usr/local/lib/python3.8/dist-packages/',
            '/root/.local/lib/python3.8/site-packages/'
        ]
        
        for dir_path in dirs_to_check:
            print(f"\n检查目录: {dir_path}")
            result = run_ssh_command(ssh, f'ls -la {dir_path} 2>/dev/null | head -20')
            if result['success'] and result['output'].strip():
                print("目录内容:")
                for line in result['output'].split('\n'):
                    if line.strip():
                        print(f"  {line}")
            else:
                print("  目录不存在或为空")
        
        print("\n🔍 搜索torch和ultralytics相关文件:")
        
        # 搜索torch相关文件
        search_commands = [
            ('搜索torch', 'find /usr -name "*torch*" 2>/dev/null | head -10'),
            ('搜索ultralytics', 'find /usr -name "*ultralytics*" 2>/dev/null | head -10'),
            ('搜索pip缓存', 'find /root/.cache/pip -name "*torch*" 2>/dev/null | head -5'),
            ('检查pip安装历史', 'grep -i torch /var/log/dpkg.log 2>/dev/null | tail -5')
        ]
        
        for desc, cmd in search_commands:
            result = run_ssh_command(ssh, cmd)
            if result['success'] and result['output'].strip():
                print(f"\n{desc}:")
                for line in result['output'].split('\n'):
                    if line.strip():
                        print(f"  {line}")
        
        print("\n🔍 检查Python导入路径:")
        result = run_ssh_command(ssh, 'python3 -c "import sys; print(\'\\n\'.join(sys.path))"')
        if result['success']:
            print("Python模块搜索路径:")
            for line in result['output'].split('\n'):
                if line.strip():
                    print(f"  {line}")
        
        ssh.close()
        print("\n" + "=" * 60)
        print("✅ Python包检查完成")
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")

if __name__ == "__main__":
    main()