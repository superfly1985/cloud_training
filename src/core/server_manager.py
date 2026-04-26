import os
import posixpath
import shlex
import stat
import paramiko
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from scp import SCPClient


class ServerManager:
    """服务器管理模块"""

    # 增加连接池相关的配置
    _MAX_UPLOAD_WORKERS = 8 # 降低并发数，避免 SSH 通道过多导致崩溃

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.ssh_client = None
        self.python_cmd = "python3" # 默认 Python 解释器
        self._lock = threading.Lock() # 增加锁用于线程安全

    @property
    def is_connected(self):
        return self._is_connected()

    def _is_connected(self):
        if not self.ssh_client:
            return False
        transport = self.ssh_client.get_transport()
        return bool(transport and transport.is_active())

    def ensure_connected(self):
        """确保连接可用"""
        if self._is_connected():
            return True, "已连接"
        return self.connect()

    def connect(self):
        """连接服务器"""
        try:
            server_config = self.config_manager.server_config
            self.disconnect()
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=server_config["hostname"],
                port=int(server_config["port"]),
                username=server_config["username"],
                password=server_config["password"],
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
            )
            self.ssh_client.exec_command('echo "Connection test successful"', timeout=10)
            return True, "连接成功"
        except paramiko.AuthenticationException as e:
            self.disconnect()
            return False, f"认证失败: 用户名或密码错误 - {str(e)}"
        except paramiko.SSHException as e:
            self.disconnect()
            return False, f"SSH连接错误: {str(e)}"
        except Exception as e:
            self.disconnect()
            return False, f"连接失败: {str(e)}"

    def disconnect(self):
        """断开连接"""
        try:
            if self.ssh_client:
                self.ssh_client.close()
        finally:
            self.ssh_client = None

    def execute_command(self, command, timeout=120):
        """执行命令，返回(success, output_or_error)"""
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg
        try:
            _, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error = stderr.read().decode("utf-8", errors="ignore").strip()
            if exit_code != 0:
                return False, error or output or f"命令执行失败，退出码: {exit_code}"
            return True, output
        except Exception as e:
            return False, str(e)

    def execute_command_stream(self, command):
        """执行命令并以生成器形式流式返回输出"""
        ok, msg = self.ensure_connected()
        if not ok:
            yield False, msg
            return

        try:
            # 开启 get_pty=True 可以让远程进程实时刷新缓冲区（如 tqdm 进度条）
            stdin, stdout, stderr = self.ssh_client.exec_command(command, get_pty=True)
            
            # 实时读取 stdout
            while True:
                line = stdout.readline()
                if not line:
                    break
                yield True, line.rstrip()
            
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                yield False, f"命令执行结束，退出码: {exit_status}"
            else:
                yield True, "Done"
        except Exception as e:
            yield False, f"执行流式命令失败: {str(e)}"

    def get_sftp(self):
        """获取 SFTP 客户端"""
        ok, msg = self.ensure_connected()
        if not ok:
            return None
        return self.ssh_client.open_sftp()

    def _quote_remote(self, value):
        return shlex.quote(str(value))

    def ensure_remote_dir(self, remote_dir):
        """确保远程目录存在"""
        remote_dir = str(remote_dir).strip()
        if not remote_dir:
            return False, "远程目录为空"
        cmd = f"mkdir -p {self._quote_remote(remote_dir)}"
        return self.execute_command(cmd)

    def remote_path_exists(self, remote_path):
        cmd = f"test -e {self._quote_remote(remote_path)} && echo yes || echo no"
        success, output = self.execute_command(cmd)
        return success and output.strip() == "yes"

    def list_remote_dir(self, remote_dir):
        """列出远程目录内容"""
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg, []
        try:
            sftp = self.ssh_client.open_sftp()
            items = []
            for entry in sftp.listdir_attr(remote_dir):
                items.append(
                    {
                        "name": entry.filename,
                        "is_dir": stat.S_ISDIR(entry.st_mode),
                        "size": entry.st_size,
                        "mtime": entry.st_mtime,
                    }
                )
            sftp.close()
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return True, "获取成功", items
        except Exception as e:
            return False, str(e), []

    def remove_remote_path(self, remote_path):
        """删除远程文件或目录（递归）"""
        cmd = f"rm -rf {self._quote_remote(remote_path)}"
        return self.execute_command(cmd)

    def upload_file(self, local_path, remote_path):
        """上传单文件"""
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg
        try:
            remote_parent = posixpath.dirname(remote_path)
            if remote_parent:
                self.ensure_remote_dir(remote_parent)
            sftp = self.ssh_client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True, "上传成功"
        except Exception as e:
            return False, str(e)

    def download_file(self, remote_path, local_path):
        """下载单文件"""
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg
        try:
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            sftp = self.ssh_client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return True, "下载成功"
        except Exception as e:
            return False, str(e)

    def upload_dir(self, local_dir, remote_dir, progress_callback=None, log_callback=None):
        """递归上传目录 - 增强版（跳过相同文件 + 并发优化）"""
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg
        local_dir = os.path.abspath(local_dir)
        if not os.path.isdir(local_dir):
            return False, "本地目录不存在"
        
        try:
            # 1. 扫描本地文件
            files_to_check = []
            for root, _, names in os.walk(local_dir):
                for name in names:
                    local_path = os.path.join(root, name)
                    rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                    files_to_check.append((local_path, rel_path))
            
            total_local = len(files_to_check)
            if total_local == 0:
                return True, "目录为空，无需上传"

            if log_callback:
                log_callback(f"本地共有 {total_local} 个文件，正在检查云端差异...")

            # 2. 获取远端文件信息（秒传/跳过逻辑）
            # 我们通过一次 ls -lR 命令获取所有文件的 md5 或 大小/时间（这里简化为大小/名称检查）
            # 也可以使用原版中的 fingerprint 逻辑，但这里我们做一个通用的
            remote_files_map = {}
            # 尝试列出远程目录所有文件
            success, output = self.execute_command(f"find {self._quote_remote(remote_dir)} -type f -printf '%P:%s\n' 2>/dev/null")
            if success and output:
                for line in output.splitlines():
                    if ":" in line:
                        r_rel, r_size = line.rsplit(":", 1)
                        remote_files_map[r_rel] = int(r_size)

            # 3. 过滤需要上传的文件
            files_to_upload = []
            skip_count = 0
            for l_path, rel in files_to_check:
                l_size = os.path.getsize(l_path)
                if rel in remote_files_map and remote_files_map[rel] == l_size:
                    skip_count += 1
                else:
                    files_to_upload.append((l_path, rel))

            total_upload = len(files_to_upload)
            if log_callback:
                log_callback(f"跳过已存在文件: {skip_count}，实际需上传: {total_upload}")

            if total_upload == 0:
                return True, f"所有文件已同步 (共 {total_local} 个文件)"

            self.ensure_remote_dir(remote_dir)

            # 4. 预创建所有需要的远程子目录
            subdirs = set()
            for _, rel in files_to_upload:
                remote_parent = posixpath.dirname(posixpath.join(remote_dir, rel))
                if remote_parent:
                    subdirs.add(remote_parent)
            
            for sd in sorted(list(subdirs)):
                self.ensure_remote_dir(sd)

            # 5. 并发上传
            uploaded_count = 0
            # 记录失败列表
            fail_list = []

            # 动态调整并发数
            max_workers = self._MAX_UPLOAD_WORKERS
            if total_upload < 10:
                max_workers = min(max_workers, 3)
            
            if log_callback:
                log_callback(f"启动并发上传线程: {max_workers}")

            def upload_worker(local_file_path, rel_path):
                remote_file_path = posixpath.join(remote_dir, rel_path)
                retry = 3 # 增加重试次数
                while retry >= 0:
                    try:
                        # 使用锁确保重连时的线程安全
                        with self._lock:
                            transport = self.ssh_client.get_transport()
                            if not transport or not transport.is_active():
                                self.connect()
                                transport = self.ssh_client.get_transport()

                        if not transport:
                            raise Exception("无法建立 SSH 连接")

                        with SCPClient(transport, socket_timeout=60.0) as scp: # 增加超时时间
                            scp.put(local_file_path, remote_file_path)
                        return True, None, rel_path
                    except Exception as e:
                        if retry == 0:
                            return False, str(e), rel_path
                        retry -= 1
                        import time
                        time.sleep(2) # 增加重试间隔

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(upload_worker, lp, rp): rp for lp, rp in files_to_upload}
                for future in as_completed(futures):
                    success, err, rel = future.result()
                    uploaded_count += 1
                    if progress_callback:
                        # 进度条显示相对于总本地文件的进度
                        progress_callback(uploaded_count + skip_count, total_local, rel)
                    if not success:
                        fail_list.append((rel, err))
                        if log_callback:
                            log_callback(f"上传失败 ({rel}): {err}")

            if fail_list:
                return False, f"部分文件上传失败: {len(fail_list)} 个"

            return True, f"上传完成，共 {total_local} 个文件 (新传 {total_upload}, 跳过 {skip_count})"
        except Exception as e:
            return False, str(e)

    def get_system_info(self):
        """获取服务器基本硬件信息"""
        info = {
            "hostname": "未知",
            "os": "未知",
            "cpu": "未知",
            "gpu": "未知",
            "memory": "未知",
            "disk": "未知",
        }
        commands = {
            "hostname": "hostname",
            "os": 'cat /etc/os-release | grep PRETTY_NAME | cut -d "=" -f 2 | tr -d \'"\'',
            "cpu": 'lscpu | grep "Model name" | cut -d ":" -f 2',
            "gpu": "nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1",
            "memory": "free -h | grep Mem | awk '{print $2}'",
            "disk": "df -h / | tail -1 | awk '{print $2}'",
        }
        try:
            for key, cmd in commands.items():
                success, output = self.execute_command(cmd, timeout=30)
                if success and output:
                    info[key] = output.strip()
            if info["gpu"] == "未知":
                info["gpu"] = "无"
            return True, "获取成功", info
        except Exception as e:
            return False, f"获取系统信息失败: {str(e)}", info

    def check_server_status(self):
        """检查服务器状态"""
        success, _ = self.execute_command("uname -a", timeout=20)
        return (True, "服务器正常") if success else (False, "服务器异常")
