import os
import posixpath
import shlex
import stat
import tarfile
import tempfile
import hashlib
from datetime import datetime
import paramiko
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
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

    def upload_dir(self, local_dir, remote_dir, progress_callback=None, log_callback=None, stop_callback=None):
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

            # 动态调整并发数（可被配置覆盖）
            upload_cfg = self.config_manager.config.get("upload", {}) if self.config_manager else {}
            max_workers_cfg = int(upload_cfg.get("max_workers", self._MAX_UPLOAD_WORKERS) or self._MAX_UPLOAD_WORKERS)
            max_workers_cfg = max(1, min(max_workers_cfg, 32))
            retry_times = int(upload_cfg.get("retry_times", 3) or 3)
            retry_times = max(0, min(retry_times, 10))
            max_workers = max_workers_cfg
            if total_upload < 10:
                max_workers = min(max_workers, 3)
            
            if log_callback:
                log_callback(f"启动并发上传线程: {max_workers}")

            def upload_worker(local_file_path, rel_path):
                remote_file_path = posixpath.join(remote_dir, rel_path)
                if stop_callback and stop_callback():
                    return False, "上传已停止", rel_path
                retry = retry_times
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
                        time.sleep(2)
                        if stop_callback and stop_callback():
                            return False, "上传已停止", rel_path

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                pending = {executor.submit(upload_worker, lp, rp) for lp, rp in files_to_upload}
                while pending:
                    if stop_callback and stop_callback():
                        for f in pending:
                            f.cancel()
                        return False, f"上传已停止（已完成 {uploaded_count + skip_count}/{total_local}）"

                    done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                    if not done:
                        continue

                    for future in done:
                        success, err, rel = future.result()
                        uploaded_count += 1
                        if progress_callback:
                            # 进度条显示相对于总本地文件的进度
                            progress_callback(uploaded_count + skip_count, total_local, rel)
                        if not success:
                            # 主动停止不计为失败
                            if "已停止" in str(err):
                                continue
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

    def upload_package(self, local_dir, remote_dir, progress_callback=None, log_callback=None, stop_callback=None, strategy_change_callback=None):
        """
        多包分片打包上传目录到远端（支持断点续传）
        流程：
        1. 扫描文件并计算总大小 + 生成数据集指纹
        2. 根据线程数映射分包数
        3. 将文件均匀分配到各包
        4. 并发创建各包的 tar.gz（稳定包名，基于指纹）
        5. 并发上传各包（检查远程是否已有，有则跳过）
        6. 顺序解压各包（检查解压标记，有则跳过）
        7. 清理临时文件和标记文件
        """
        ok, msg = self.ensure_connected()
        if not ok:
            return False, msg

        local_dir = os.path.abspath(local_dir)
        if not os.path.isdir(local_dir):
            return False, "本地目录不存在"

        try:
            # 1. 扫描本地文件并统计大小
            if log_callback:
                log_callback("正在扫描本地文件...")

            files_to_package = []
            total_size = 0
            file_hashes = []
            for root, _, names in os.walk(local_dir):
                for name in names:
                    local_path = os.path.join(root, name)
                    try:
                        file_size = os.path.getsize(local_path)
                        rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                        files_to_package.append((local_path, rel_path, file_size))
                        total_size += file_size
                        file_hashes.append(f"{rel_path}:{file_size}")
                    except Exception:
                        continue

            total_files = len(files_to_package)
            if total_files == 0:
                return True, "目录为空，无需上传"

            if log_callback:
                log_callback(f"共有 {total_files} 个文件 (总计 {total_size / 1024 / 1024:.2f} MB)")

            # 生成数据集指纹（用于稳定包名，支持断点续传）
            fingerprint_raw = f"{local_dir}|{total_files}|{total_size}|{'|'.join(sorted(file_hashes[:100]))}"
            dataset_fingerprint = hashlib.md5(fingerprint_raw.encode()).hexdigest()[:12]

            # 2. 获取线程数配置，决定分包数量
            upload_cfg = self.config_manager.config.get("upload", {}) if self.config_manager else {}
            max_workers = int(upload_cfg.get("max_workers", self._MAX_UPLOAD_WORKERS) or self._MAX_UPLOAD_WORKERS)
            num_packages = self._map_workers_to_packages(max_workers)

            if log_callback:
                log_callback(f"使用 {num_packages} 个分包上传（线程数: {max_workers}，指纹: {dataset_fingerprint}）")

            # 3. 按大小均匀分配文件到各包
            packages = self._distribute_files_to_packages(files_to_package, num_packages)

            if log_callback:
                for idx, pkg in enumerate(packages):
                    pkg_size = sum(f[2] for f in pkg)
                    log_callback(f"  包 {idx + 1}/{num_packages}: {len(pkg)} 个文件 ({pkg_size / 1024 / 1024:.2f} MB)")

            # 4. 检查远程已上传的包（断点续传 + 策略变化检测）
            sftp = self.ssh_client.open_sftp()
            remote_existing = {}
            remote_done_markers = set()
            old_fingerprint = None
            
            try:
                for item in sftp.listdir_attr(remote_dir):
                    name = item.filename
                    if name.startswith("dataset_") and "_pkg" in name:
                        if name.endswith(".tar.gz"):
                            remote_existing[name] = item.st_size
                            parts = name.split("_")
                            if len(parts) >= 2:
                                fp = parts[1]
                                if old_fingerprint is None or old_fingerprint == fp:
                                    old_fingerprint = fp
                        elif name.endswith(".done"):
                            pkg_num = name.replace(".done", "").split("_pkg")[-1]
                            remote_done_markers.add(int(pkg_num))
                            parts = name.split("_")
                            if len(parts) >= 2:
                                fp = parts[1]
                                if old_fingerprint is None or old_fingerprint == fp:
                                    old_fingerprint = fp
            except Exception:
                pass
            
            try:
                sftp.close()
            except Exception:
                pass
            
            remote_existing_for_current = {
                k: v for k, v in remote_existing.items() 
                if k.startswith(f"dataset_{dataset_fingerprint}_pkg")
            }
            
            strategy_changed = False
            if old_fingerprint and old_fingerprint != dataset_fingerprint:
                strategy_changed = True
                strategy_info = {
                    'old_fingerprint': old_fingerprint,
                    'new_fingerprint': dataset_fingerprint,
                    'old_packages': len([n for n in remote_existing.keys() if old_fingerprint in n and n.endswith(".tar.gz")]),
                    'new_packages': num_packages,
                }
                if strategy_change_callback:
                    should_continue = strategy_change_callback(strategy_info)
                    if not should_continue:
                        return False, "用户取消上传（分包策略变化）"
            
            if strategy_changed:
                cleanup_old_cmd = (
                    f"cd {self._quote_remote(remote_dir)} && "
                    f"rm -f dataset_{old_fingerprint}_pkg*.tar.gz dataset_{old_fingerprint}_pkg*.done"
                )
                self.execute_command(cleanup_old_cmd, timeout=30)
                remote_existing_for_current = {}
                remote_done_markers = set()
                if log_callback:
                    log_callback(f"已清理旧分包（指纹 {old_fingerprint}），开始全新上传")

            # 5. 并发创建各包的 tar.gz
            if log_callback:
                log_callback("正在创建压缩包...")

            temp_dir = tempfile.gettempdir()

            package_paths = []
            package_info = []

            def create_package_worker(pkg_idx, pkg_files):
                """创建单个包的压缩文件"""
                if stop_callback and stop_callback():
                    return None

                archive_name = f"dataset_{dataset_fingerprint}_pkg{pkg_idx + 1}.tar.gz"
                archive_path = os.path.join(temp_dir, archive_name)

                with tarfile.open(archive_path, "w:gz") as tar:
                    for local_path, rel_path, file_size in pkg_files:
                        tar.add(local_path, arcname=rel_path)

                return (pkg_idx, archive_path, os.path.getsize(archive_path))

            with ThreadPoolExecutor(max_workers=num_packages) as executor:
                futures = [executor.submit(create_package_worker, idx, pkg) for idx, pkg in enumerate(packages)]
                for future in futures:
                    result = future.result()
                    if result:
                        package_paths.append(result)
                        package_info.append({
                            'index': result[0],
                            'path': result[1],
                            'size': result[2]
                        })

            package_paths.sort(key=lambda x: x[0])  # 按索引排序

            if log_callback:
                total_package_size = sum(p[2] for p in package_paths)
                log_callback(f"所有压缩包创建完成 (总计 {total_package_size / 1024 / 1024:.2f} MB)")

            # 6. 确保远程目录存在
            self.ensure_remote_dir(remote_dir)

            # 7. 并发上传各包（断点续传：检查远程是否已有）
            uploaded_bytes = 0
            total_bytes = total_package_size
            skipped_packages = []

            def upload_single_package(pkg_info):
                """上传单个包（支持断点续传）"""
                if stop_callback and stop_callback():
                    return False, "已停止", pkg_info['index']

                pkg_idx = pkg_info['index']
                archive_path = pkg_info['path']
                archive_size = pkg_info['size']
                archive_name = os.path.basename(archive_path)
                remote_archive = posixpath.join(remote_dir, archive_name)

                # 断点续传：检查远程是否已有同名同大小包
                if archive_name in remote_existing and remote_existing[archive_name] == archive_size:
                    if log_callback:
                        log_callback(f"包 {pkg_idx + 1} 已存在且大小匹配，跳过上传")
                    return True, "skipped", pkg_idx

                try:
                    # 使用 SFTP 上传（支持进度回调）
                    with self._lock:
                        transport = self.ssh_client.get_transport()
                        if not transport or not transport.is_active():
                            self.connect()
                            transport = self.ssh_client.get_transport()
                        sftp = self.ssh_client.open_sftp()

                    # 进度回调函数（paramiko SFTP 格式：callback(bytes_so_far, bytes_total)）
                    last_reported = [0]  # 使用列表以便在嵌套函数中修改

                    def sftp_progress(bytes_so_far, bytes_total):
                        if progress_callback:
                            # 计算增量并更新总进度
                            delta = bytes_so_far - last_reported[0]
                            last_reported[0] = bytes_so_far
                            if delta > 0:
                                nonlocal uploaded_bytes
                                uploaded_bytes += delta
                                progress_callback(
                                    uploaded_bytes,
                                    total_bytes,
                                    f"上传中 ({pkg_idx + 1}/{num_packages}) - {archive_name}"
                                )

                    # 确保远程目录存在
                    remote_parent = posixpath.dirname(remote_archive)
                    if remote_parent:
                        try:
                            sftp.stat(remote_parent)
                        except FileNotFoundError:
                            sftp.makedirs(remote_parent)

                    # 上传文件
                    sftp.put(archive_path, remote_archive, callback=sftp_progress)
                    sftp.close()

                    # 确保进度达到100%
                    if progress_callback and uploaded_bytes < total_bytes:
                        progress_callback(total_bytes, total_bytes, f"上传完成 - {archive_name}")

                    return True, None, pkg_idx
                except Exception as e:
                    return False, str(e), pkg_idx

            if log_callback:
                log_callback("正在上传压缩包...")

            # 并发上传所有包
            with ThreadPoolExecutor(max_workers=num_packages) as executor:
                futures = [executor.submit(upload_single_package, pkg) for pkg in package_info]
                results = [f.result() for f in futures]

            # 检查上传结果
            failed_packages = []
            for success, err, pkg_idx in results:
                if not success:
                    failed_packages.append((pkg_idx, err))

            if failed_packages:
                for pkg_idx, err in failed_packages:
                    if log_callback:
                        log_callback(f"包 {pkg_idx + 1} 上传失败: {err}")
                return False, f"{len(failed_packages)} 个包上传失败"

            if log_callback:
                log_callback("所有压缩包上传完成，正在解压...")

            # 8. 顺序解压各包（断点续传：检查解压标记）
            for pkg_idx, archive_path, _ in package_paths:
                archive_name = os.path.basename(archive_path)
                done_marker = f"dataset_{dataset_fingerprint}_pkg{pkg_idx + 1}.done"

                # 断点续传：检查是否已有解压标记
                if (pkg_idx + 1) in remote_done_markers:
                    if log_callback:
                        log_callback(f"包 {pkg_idx + 1}/{num_packages} 已解压，跳过")
                    # 清理本地包
                    if os.path.exists(archive_path):
                        os.remove(archive_path)
                    continue

                # 解压并写入标记
                extract_cmd = (
                    f"cd {self._quote_remote(remote_dir)} && "
                    f"tar -xzf {archive_name} && "
                    f"touch {done_marker} && "
                    f"rm {archive_name}"
                )
                success, output = self.execute_command(extract_cmd, timeout=600)

                if not success:
                    if log_callback:
                        log_callback(f"包 {pkg_idx + 1} 解压失败: {output}")
                    return False, f"解压失败: {output}"

                # 清理本地上传后的包
                if os.path.exists(archive_path):
                    os.remove(archive_path)

                if log_callback:
                    log_callback(f"包 {pkg_idx + 1}/{num_packages} 解压完成")

            # 9. 最终清理标记文件和残留压缩包
            cleanup_cmd = (
                f"cd {self._quote_remote(remote_dir)} && "
                f"rm -f dataset_{dataset_fingerprint}_pkg*.done dataset_{dataset_fingerprint}_pkg*.tar.gz"
            )
            self.execute_command(cleanup_cmd, timeout=30)

            if log_callback:
                log_callback("所有包解压完成，清理完毕")

            return True, f"打包上传完成，共 {total_files} 个文件 (分 {num_packages} 包)"

        except Exception as e:
            return False, str(e)

    def _map_workers_to_packages(self, workers):
        """
        将线程数映射为分包数量
        映射规则：线程数 = 分包数
        """
        return max(1, workers)

    def _distribute_files_to_packages(self, files, num_packages):
        """
        将文件均匀分配到各包（按大小平衡）
        使用贪心算法，尽量保证各包总大小相近
        """
        if num_packages == 1:
            return [files]

        # 初始化各包
        packages = [[] for _ in range(num_packages)]
        package_sizes = [0] * num_packages

        # 按文件大小降序排序，优先分配大文件
        sorted_files = sorted(files, key=lambda x: x[2], reverse=True)

        # 贪心分配：将文件分配到当前最小的包
        for file_info in sorted_files:
            min_idx = package_sizes.index(min(package_sizes))
            packages[min_idx].append(file_info)
            package_sizes[min_idx] += file_info[2]

        return packages


    def check_server_status(self):
        """检查服务器状态"""
        success, _ = self.execute_command("uname -a", timeout=20)
        return (True, "服务器正常") if success else (False, "服务器异常")
