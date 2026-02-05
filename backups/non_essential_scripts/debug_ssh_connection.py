#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH连接诊断工具
用于测试和诊断SSH连接问题
"""

import paramiko
import socket
import time
from datetime import datetime

def test_ssh_connection():
    """测试SSH连接的详细诊断"""
    
    # 连接参数
    hostname = "152.136.245.138"
    port = 22
    username = "root"
    password = "vonzeus01"
    
    print("="*60)
    print("SSH连接诊断工具")
    print("="*60)
    print(f"目标服务器: {hostname}:{port}")
    print(f"用户名: {username}")
    print(f"密码: {'*' * len(password)}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 步骤1: 测试网络连通性
    print("\n🔍 步骤1: 测试网络连通性...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            print(f"✅ 网络连通性正常 - 端口 {port} 可达")
        else:
            print(f"❌ 网络连接失败 - 端口 {port} 不可达")
            print("   可能原因:")
            print("   - 服务器IP地址错误")
            print("   - 防火墙阻止连接")
            print("   - SSH服务未启动")
            return False
            
    except Exception as e:
        print(f"❌ 网络测试异常: {e}")
        return False
    
    # 步骤2: 测试SSH协议握手
    print("\n🔍 步骤2: 测试SSH协议握手...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试连接但不认证
        transport = paramiko.Transport((hostname, port))
        transport.connect()
        
        print(f"✅ SSH协议握手成功")
        print(f"   服务器版本: {transport.remote_version}")
        
        # 获取支持的认证方式
        try:
            auth_result = transport.auth_none(username)
            print(f"   支持的认证方式: {auth_result}")
        except paramiko.BadAuthenticationType as e:
            print(f"   支持的认证方式: {e.allowed_types}")
        
        transport.close()
        
    except Exception as e:
        print(f"❌ SSH协议握手失败: {e}")
        return False
    
    # 步骤3: 测试用户名密码认证
    print("\n🔍 步骤3: 测试用户名密码认证...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试密码认证
        ssh.connect(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            timeout=30,
            allow_agent=False,
            look_for_keys=False
        )
        
        print("✅ 密码认证成功!")
        
        # 测试执行命令
        stdin, stdout, stderr = ssh.exec_command('whoami')
        result = stdout.read().decode().strip()
        print(f"✅ 命令执行成功: whoami = {result}")
        
        # 测试系统信息
        stdin, stdout, stderr = ssh.exec_command('uname -a')
        system_info = stdout.read().decode().strip()
        print(f"✅ 系统信息: {system_info}")
        
        ssh.close()
        print("\n🎉 SSH连接测试完全成功!")
        return True
        
    except paramiko.AuthenticationException as e:
        print(f"❌ 认证失败: {e}")
        print("\n💡 可能的解决方案:")
        print("   1. 检查用户名是否正确 (当前: root)")
        print("   2. 检查密码是否正确")
        print("   3. 确认服务器是否允许root用户SSH登录")
        print("   4. 检查服务器SSH配置 (/etc/ssh/sshd_config):")
        print("      - PermitRootLogin yes")
        print("      - PasswordAuthentication yes")
        return False
        
    except paramiko.SSHException as e:
        print(f"❌ SSH连接错误: {e}")
        return False
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False

def test_alternative_methods():
    """测试其他连接方式"""
    print("\n🔍 步骤4: 测试其他连接方式...")
    
    hostname = "152.136.245.138"
    port = 22
    
    # 测试其他常用用户名
    alternative_users = ['ubuntu', 'admin', 'user', 'centos']
    
    for user in alternative_users:
        print(f"\n   尝试用户名: {user}")
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=hostname,
                port=port,
                username=user,
                password="vonzeus01",
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            
            print(f"   ✅ 用户名 {user} 认证成功!")
            ssh.close()
            return user
            
        except:
            print(f"   ❌ 用户名 {user} 认证失败")
            continue
    
    return None

def main():
    """主函数"""
    success = test_ssh_connection()
    
    if not success:
        alternative_user = test_alternative_methods()
        if alternative_user:
            print(f"\n✅ 找到可用的用户名: {alternative_user}")
        else:
            print("\n❌ 所有测试都失败了")
            print("\n🔧 建议的排查步骤:")
            print("1. 联系服务器管理员确认:")
            print("   - 服务器IP地址是否正确")
            print("   - SSH服务是否正常运行")
            print("   - 用户名和密码是否正确")
            print("2. 检查网络连接:")
            print("   - 是否有防火墙阻止")
            print("   - 是否需要VPN连接")
            print("3. 尝试其他SSH客户端:")
            print("   - PuTTY")
            print("   - Windows Terminal")
            print("   - VS Code Remote SSH")

if __name__ == "__main__":
    main()