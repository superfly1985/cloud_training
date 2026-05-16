import os
import sys
import time
import socket
import json
import hashlib
import tempfile
import zipfile
import paramiko

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.environment_contract import (
    CONVERSION_IMPORT_CHECK_SNIPPET,
    TRAINING_IMPORT_CHECK_SNIPPET,
)
from deploy_logger import get_logger

EXCLUDE_DIRS = {".git", "__pycache__", "data", ".pytest_cache", "test", ".trae", "node_modules"}
EXCLUDE_FILES = {".gitignore", ".DS_Store", "Thumbs.db"}
ALLOWED_DEPLOY_TOOL_FILES = {
    "requirements-web.txt",
    "requirements-training.txt",
    "requirements-conversion.txt",
}
SERVICE_PORT = 8090
SUPERVISOR_CONF_NAME = "metaqa-cloud"
SERVICE_UNIT_NAME = "metaqa-cloud.service"
DEPLOY_STEPS = [
    "连接服务器",
    "环境预检",
    "初始化目录与环境",
    "停止旧服务",
    "上传文件",
    "安装 Web 依赖",
    "创建训练环境",
    "创建转换环境",
    "验证固定环境",
    "base瘦身与清理",
    "配置自启动",
    "启动并验证服务",
]


class DeployManager:

    def __init__(self):
        self.client = None
        self.sftp = None
        self._cancelled = False
        self._host = None
        self._port = None
        self.logger = get_logger()
        
        # 路径相关（连接后初始化）
        self.remote_home = ""
        self.base_runtime_dir = ""
        self.remote_dir = ""
        self.fixed_conda = ""
        self.fixed_base_python = ""
        self.fixed_training_python = ""
        self.fixed_conversion_python = ""
        self.deploy_state_path = ""
        
        self._deploy_context = {
            "deploy_state": None,
            "precheck": {},
            "first_bootstrap": True,
            "should_run_base_slim": True,
            "current_step_name": "",
            "step_cb": None,
        }

    def _update_paths(self, home_dir):
        """根据远程 home 目录更新所有固定路径"""
        self.remote_home = home_dir.rstrip("/")
        self.base_runtime_dir = f"{self.remote_home}/cloud-training-runtime"
        self.remote_dir = f"{self.base_runtime_dir}/MetaQA_CloudTraining"
        self.fixed_conda = f"{self.base_runtime_dir}/miniforge3/bin/conda"
        self.fixed_base_python = f"{self.base_runtime_dir}/miniforge3/bin/python"
        self.fixed_training_python = f"{self.base_runtime_dir}/miniforge3/envs/cloud-training/bin/python"
        self.fixed_conversion_python = f"{self.base_runtime_dir}/miniforge3/envs/cloud-conversion/bin/python"
        self.deploy_state_path = f"{self.remote_dir}/data/deploy_state.json"
        
        self.logger.info("INIT", f"已设置远程根目录: {self.base_runtime_dir}")

    def cancel(self):
        self._cancelled = True

    def reset_cancel(self):
        self._cancelled = False

    @property
    def cancelled(self):
        return self._cancelled

    def test_connection(self, host, port, user, password, timeout=10):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=port, username=user, password=password, timeout=timeout)
            # 顺便检查 sudo 权限
            code, out, err = self._exec(client, "sudo -n echo OK 2>/dev/null || echo NO_SUDO")
            has_sudo = out.strip() == "OK"
            client.close()
            msg = "连接成功" + (" (具备 sudo 权限)" if has_sudo else " (无 sudo 权限)")
            return True, msg
        except paramiko.AuthenticationException:
            return False, "认证失败：用户名或密码错误"
        except paramiko.SSHException as e:
            return False, f"SSH错误: {e}"
        except Exception as e:
            return False, f"连接失败: {e}"

    def connect(self, host, port, user, password, timeout=15):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host, port=port, username=user, password=password, timeout=timeout)
        
        self._user = user
        
        # 获取远程 home 目录并初始化路径
        code, out, err = self._exec(self.client, "echo $HOME")
        home_dir = out.strip() or f"/home/{user}"
        self._update_paths(home_dir)
        
        self.sftp = self.client.open_sftp()
        self._host = host
        self._port = port

    def close(self):
        if self.sftp:
            try:
                self.sftp.close()
            except:
                pass
            self.sftp = None
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        self._host = None
        self._port = None

    def run(self, cmd, timeout=120):
        return self._exec(self.client, cmd, timeout)

    def _emit_step_detail(self, detail):
        step_name = self._deploy_context.get("current_step_name") or ""
        step_cb = self._deploy_context.get("step_cb")
        if step_name and callable(step_cb):
            step_cb(step_name, "running", detail)

    def _format_elapsed(self, seconds):
        total = max(0, int(seconds))
        mins, secs = divmod(total, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def _parse_requirement_display_items(self, requirements_path):
        if not requirements_path:
            return []
        if not os.path.isabs(requirements_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.basename(base_dir) == "deploy_tool":
                base_dir = os.path.dirname(base_dir)
            requirements_path = os.path.join(base_dir, requirements_path)
        if not os.path.exists(requirements_path):
            return []

        items = []
        with open(requirements_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                items.append(line)
        return items

    def _build_requirements_heartbeat_label(self, base_label, requirement_items, heartbeat_index):
        if not requirement_items:
            return base_label
        index = max(0, min(int(heartbeat_index), len(requirement_items) - 1))
        return (
            f"{base_label}，当前依赖 {index + 1}/{len(requirement_items)}: "
            f"{requirement_items[index]}"
        )

    def _run_command_with_heartbeat(
        self,
        cmd,
        timeout=120,
        log_cb=None,
        heartbeat_label="",
        heartbeat_interval=10,
        heartbeat_label_cb=None,
    ):
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=min(timeout, 30))
        channel = stdout.channel
        start_time = time.time()
        next_heartbeat = start_time + heartbeat_interval
        heartbeat_count = 0

        while not channel.exit_status_ready():
            now = time.time()
            if now - start_time > timeout:
                try:
                    channel.close()
                except Exception:
                    pass
                raise TimeoutError(f"命令超时: {cmd}")

            if heartbeat_label and now >= next_heartbeat:
                elapsed = self._format_elapsed(now - start_time)
                current_label = heartbeat_label_cb() if callable(heartbeat_label_cb) else heartbeat_label
                msg = f"  仍在执行：{current_label}，已耗时 {elapsed}"
                if log_cb:
                    log_cb(msg)
                self.logger.info("PROGRESS", msg.strip())
                self._emit_step_detail(f"{current_label}（已耗时 {elapsed}）")
                next_heartbeat = now + heartbeat_interval
                heartbeat_count += 1

            time.sleep(1)

        code = channel.recv_exit_status()
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        return code, out, err

    def _exec(self, client, cmd, timeout=120):
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        code = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        return code, out, err

    def check_remote_env(self, log_cb=None):
        results = {}
        checks = [
            ("python", f"test -x {self.fixed_base_python} && echo {self.fixed_base_python} || echo NOT_FOUND"),
            ("python_version", f"{self.fixed_base_python} --version 2>&1 || echo NOT_FOUND"),
            ("pip", f"test -x {self.base_runtime_dir}/miniforge3/bin/pip && echo {self.base_runtime_dir}/miniforge3/bin/pip || echo NOT_FOUND"),
            ("conda", f"test -x {self.fixed_conda} && echo {self.fixed_conda} || echo NOT_FOUND"),
            ("training_python", f"test -x {self.fixed_training_python} && echo {self.fixed_training_python} || echo NOT_FOUND"),
            ("conversion_python", f"test -x {self.fixed_conversion_python} && echo {self.fixed_conversion_python} || echo NOT_FOUND"),
            ("project_dir", f"test -d {self.remote_dir} && echo EXISTS || echo NOT_FOUND"),
            ("system_libs", "dpkg -s libgl1 libglib2.0-0 >/dev/null 2>&1 && echo READY || echo MISSING"),
            ("systemd", "command -v systemctl 2>/dev/null || echo NOT_FOUND"),
            ("systemd_service", f"sudo -n test -f /etc/systemd/system/{SERVICE_UNIT_NAME} && echo EXISTS || echo NOT_FOUND"),
            ("port_8090", f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{SERVICE_PORT}/ 2>/dev/null || echo FREE"),
            ("service_running", f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{SERVICE_PORT}/ 2>/dev/null || echo NO"),
            ("disk_space", "df -h / | tail -1 | awk '{print $4}'"),
            ("memory", "free -h | grep Mem | awk '{print $2, $4}'"),
        ]
        for name, cmd in checks:
            code, out, err = self.run(cmd)
            results[name] = out
            if log_cb:
                label = {
                    "python": "Python路径",
                    "python_version": "Python版本",
                    "pip": "pip路径",
                    "conda": "Conda路径",
                    "training_python": "训练环境Python",
                    "conversion_python": "转换环境Python",
                    "project_dir": "项目目录",
                    "system_libs": "系统运行库",
                    "systemd": "systemd",
                    "systemd_service": "systemd服务",
                    "port_8090": "端口8090",
                    "service_running": "服务状态",
                    "disk_space": "磁盘剩余",
                    "memory": "内存(总/可用)",
                }.get(name, name)
                log_cb(f"  {label}: {out}")
        return results

    def _build_precheck_plan(self, env):
        python_ready = "NOT_FOUND" not in env.get("python", "")
        conda_ready = "NOT_FOUND" not in env.get("conda", "")
        training_ready = "NOT_FOUND" not in env.get("training_python", "")
        conversion_ready = "NOT_FOUND" not in env.get("conversion_python", "")
        systemd_ready = "NOT_FOUND" not in env.get("systemd", "")
        systemd_service_exists = env.get("systemd_service", "").strip() == "EXISTS"
        system_libs_ready = env.get("system_libs", "").strip() == "READY"

        # 获取本地和远端的 requirements 哈希
        local_hashes = self._get_local_requirements_hashes()
        remote_state = self._load_remote_deploy_state() or {}
        remote_hashes = remote_state.get("requirements_hashes", {})

        return {
            "need_install_miniforge": not (python_ready and conda_ready),
            "need_install_system_deps": not system_libs_ready,
            "need_install_web_requirements": local_hashes.get("web") != remote_hashes.get("web"),
            "need_create_training_env": not training_ready,
            "need_sync_training_requirements": local_hashes.get("training") != remote_hashes.get("training"),
            "need_create_conversion_env": not conversion_ready,
            "need_sync_conversion_requirements": local_hashes.get("conversion") != remote_hashes.get("conversion"),
            "need_configure_autostart": systemd_ready and not systemd_service_exists,
            "systemd_available": systemd_ready,
            "service_already_running": env.get("service_running", "").strip() in ("200", "301", "302", "304"),
            "requirements_hashes": local_hashes
        }

    def _get_local_requirements_hashes(self):
        """计算本地 requirements 文件的哈希值"""
        hashes = {}
        mapping = {
            "web": "deploy_tool/requirements-web.txt",
            "training": "deploy_tool/requirements-training.txt",
            "conversion": "deploy_tool/requirements-conversion.txt"
        }
        
        # 假设当前工作目录是项目根目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(base_dir) == "deploy_tool":
            base_dir = os.path.dirname(base_dir)

        for key, rel_path in mapping.items():
            full_path = os.path.join(base_dir, rel_path)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    hashes[key] = hashlib.md5(f.read()).hexdigest()
            else:
                hashes[key] = ""
        return hashes

    def _log_precheck_plan(self, plan, log_cb=None):
        if not log_cb:
            return
        log_cb("  预检执行计划:")
        log_cb(f"    Miniforge: {'缺失，将安装' if plan['need_install_miniforge'] else '已存在，跳过创建'}")
        log_cb(f"    系统运行库: {'缺失，将安装' if plan['need_install_system_deps'] else '已存在，跳过安装'}")
        log_cb(f"    Web依赖: {'锁文件已变更，将补齐 requirements' if plan['need_install_web_requirements'] else '锁文件未变更，跳过补齐'}")
        if plan["need_create_training_env"]:
            log_cb("    训练环境: 缺失，将创建并补齐依赖")
        else:
            log_cb(f"    训练环境: {'已存在，仅补齐依赖' if plan['need_sync_training_requirements'] else '已存在且锁文件未变更，跳过补齐'}")
        if plan["need_create_conversion_env"]:
            log_cb("    转换环境: 缺失，将创建并补齐依赖")
        else:
            log_cb(f"    转换环境: {'已存在，仅补齐依赖' if plan['need_sync_conversion_requirements'] else '已存在且锁文件未变更，跳过补齐'}")
        if not plan["systemd_available"]:
            log_cb("    自启动: 当前系统不支持 systemd，跳过配置")
        else:
            log_cb(f"    自启动: {'缺失，将配置' if plan['need_configure_autostart'] else '已存在，跳过配置'}")

    def stop_service(self, log_cb=None):
        self.logger.info("SERVICE", "=" * 60)
        self.logger.info("SERVICE", "停止旧服务开始")
        
        if log_cb:
            log_cb("停止旧服务...")

        if self._has_systemd() and self._has_systemd_service():
            code, out, err = self.run(f"sudo -n systemctl stop {SERVICE_UNIT_NAME}")
            self.logger.info("SERVICE", f"  systemctl stop exit_code={code}, output={repr((out or err).strip())}")
            if log_cb and code == 0:
                log_cb("  已停止 systemd 服务")
        
        # 检测1: fuser
        self.logger.info("SERVICE", "[检测1] 使用 fuser 检查端口占用")
        code, out, err = self.run(f"fuser {SERVICE_PORT}/tcp 2>/dev/null")
        self.logger.info("SERVICE", f"  fuser exit_code={code}, output={repr(out.strip())}")
        
        if out.strip():
            self.logger.info("SERVICE", f"  发现进程占用端口 {SERVICE_PORT}，执行 fuser -k")
            self.run(f"fuser -k {SERVICE_PORT}/tcp 2>/dev/null")
            if log_cb:
                log_cb(f"  已终止端口 {SERVICE_PORT} 上的进程")
        else:
            self.logger.info("SERVICE", "  fuser 未发现占用进程")
            
            # 检测2: lsof
            self.logger.info("SERVICE", "[检测2] 使用 lsof 检查端口占用")
            code, out, err = self.run(f"lsof -ti:{SERVICE_PORT} 2>/dev/null")
            self.logger.info("SERVICE", f"  lsof exit_code={code}, output={repr(out.strip())}")
            
            if out.strip():
                self.logger.info("SERVICE", f"  发现 {len(out.split(chr(10)))} 个进程占用端口")
                for pid in out.split("\n"):
                    pid = pid.strip()
                    if pid:
                        self.logger.info("SERVICE", f"  终止进程 PID={pid}")
                        self.run(f"kill {pid} 2>/dev/null")
                        if log_cb:
                            log_cb(f"  已终止进程 {pid}")
        
        # 检测3: ps 查找 run.py
        self.logger.info("SERVICE", "[检测3] 使用 ps 查找 run.py 进程")
        code, out, err = self.run(f"ps aux | grep 'run.py' | grep -v grep | awk '{{print $2}}'")
        self.logger.info("SERVICE", f"  ps exit_code={code}, output={repr(out.strip())}")
        
        if out.strip():
            pids = [p.strip() for p in out.split("\n") if p.strip()]
            self.logger.info("SERVICE", f"  发现 {len(pids)} 个 run.py 进程: {pids}")
            for pid in pids:
                self.logger.info("SERVICE", f"  终止 run.py 进程 PID={pid}")
                self.run(f"kill {pid} 2>/dev/null")
                if log_cb:
                    log_cb(f"  已终止 run.py 进程 {pid}")
        else:
            self.logger.info("SERVICE", "  未发现 run.py 进程")
        
        self.logger.info("SERVICE", "等待 2 秒让进程完全终止...")
        time.sleep(2)
        
        # 检测4: 验证端口是否仍被占用
        self.logger.info("SERVICE", "[检测4] 验证端口是否仍被占用")
        self.logger.info("SERVICE", f"  _host={self._host}, _port={self._port}")
        
        if self._check_port_listening(SERVICE_PORT, log_cb):
            self.logger.warn("SERVICE", "  [警告] 端口仍被占用，执行强制清理 (kill -9)")
            if log_cb:
                log_cb("  [警告] 端口仍被占用，强制清理")
            code, out, err = self.run(f"ps aux | grep 'run.py' | grep -v grep | awk '{{print $2}}'")
            self.logger.info("SERVICE", f"  强制清理前 ps output={repr(out.strip())}")
            for pid in out.split("\n"):
                pid = pid.strip()
                if pid:
                    self.logger.info("SERVICE", f"  强制终止 PID={pid}")
                    self.run(f"kill -9 {pid} 2>/dev/null")
            time.sleep(2)
            
            # 最终验证
            still_listening = self._check_port_listening(SERVICE_PORT)
            self.logger.info("SERVICE", f"  强制清理后端口状态: {'仍被占用' if still_listening else '已释放'}")
        else:
            self.logger.info("SERVICE", "  端口已释放")
            if log_cb:
                log_cb("  端口已释放")
        
        self.logger.info("SERVICE", "停止旧服务完成")
        self.logger.info("SERVICE", "=" * 60)

    def _collect_local_files(self, local_dir):
        file_list = []
        for root, dirs, files in os.walk(local_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                local_path = os.path.join(root, f)
                rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                if rel_path.startswith("deploy_tool/") and f not in ALLOWED_DEPLOY_TOOL_FILES:
                    continue
                file_list.append((rel_path, local_path))
        return sorted(file_list, key=lambda x: x[0])

    def _build_upload_archive(self, local_files):
        fd, archive_path = tempfile.mkstemp(prefix="metaqa-deploy-", suffix=".zip")
        os.close(fd)
        try:
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for rel_path, local_path in local_files:
                    archive.write(local_path, arcname=rel_path)
            return archive_path
        except Exception:
            try:
                os.remove(archive_path)
            except OSError:
                pass
            raise

    def _get_remote_upload_archive_path(self):
        stamp = f"{int(time.time())}-{os.getpid()}"
        return f"{self.remote_dir}/data/temp/deploy-upload-{stamp}.zip"

    def _cleanup_local_upload_archive(self, archive_path):
        if archive_path and os.path.exists(archive_path):
            try:
                os.remove(archive_path)
            except OSError:
                pass

    def _cleanup_remote_upload_archive(self, remote_archive_path):
        if not remote_archive_path:
            return
        try:
            self.run(f"rm -f '{remote_archive_path}'", timeout=120)
        except Exception:
            pass

    def _extract_remote_upload_archive(self, remote_archive_path):
        cmd = (
            f"mkdir -p '{self.remote_dir}' '{self.remote_dir}/data/temp' && "
            f"find '{self.remote_dir}' -mindepth 1 -maxdepth 1 ! -name data -exec rm -rf {{}} + && "
            f"{self.fixed_base_python} - <<'PY'\n"
            "import zipfile\n"
            f"archive_path = {json.dumps(remote_archive_path)}\n"
            f"target_dir = {json.dumps(self.remote_dir)}\n"
            "with zipfile.ZipFile(archive_path, 'r') as zf:\n"
            "    zf.extractall(target_dir)\n"
            "PY"
        )
        return self.run(cmd, timeout=600)

    def upload_files(self, local_dir, log_cb=None, progress_cb=None, skip_existing=True):
        local_files = self._collect_local_files(local_dir)
        total = len(local_files)

        uploaded = 0
        skipped = 0
        failed = 0
        archive_path = ""
        remote_archive_path = ""

        if log_cb:
            log_cb(f"准备全量上传，共 {total} 个文件")

        if total == 0:
            if progress_cb:
                progress_cb(0, 0, 0, 0, 0)
            if log_cb:
                log_cb("上传完成: 已上传 0, 失败 0")
            return True, uploaded, skipped, failed

        if self._cancelled:
            if log_cb:
                log_cb("[已取消] 上传中断")
            return False, uploaded, skipped, failed

        try:
            archive_path = self._build_upload_archive(local_files)
            remote_archive_path = self._get_remote_upload_archive_path()

            self.run(f"mkdir -p '{self.remote_dir}' '{self.remote_dir}/data/temp'")
            self.sftp.put(archive_path, remote_archive_path)

            if self._cancelled:
                if log_cb:
                    log_cb("[已取消] 上传中断")
                return False, uploaded, skipped, failed

            code, out, err = self._extract_remote_upload_archive(remote_archive_path)
            if code != 0:
                failed = total
                if log_cb:
                    log_cb(f"  [失败] 远端解压部署包失败: {err or out or '无输出'}")
                if progress_cb:
                    progress_cb(total, total, uploaded, skipped, failed)
                return False, uploaded, skipped, failed

            uploaded = total
            if progress_cb:
                progress_cb(total, total, uploaded, skipped, failed)
            if log_cb:
                log_cb(f"上传完成: 已上传 {uploaded}, 失败 {failed}")
            return True, uploaded, skipped, failed
        except Exception as e:
            failed = total or 1
            if log_cb:
                log_cb(f"  [失败] 上传部署包失败: {e}")
            if progress_cb:
                progress_cb(total, total, uploaded, skipped, failed)
            return False, uploaded, skipped, failed
        finally:
            self._cleanup_remote_upload_archive(remote_archive_path)
            self._cleanup_local_upload_archive(archive_path)

    def install_dependencies(self, log_cb=None):
        if log_cb:
            log_cb("安装 Web 依赖...")
        self.ensure_data_dirs()
        pip_cmd = (
            f"cd {self.remote_dir} && "
            f"{self.fixed_base_python} -m pip install -r deploy_tool/requirements-web.txt -q 2>&1"
        )
        code, out, err = self.run(pip_cmd, timeout=600)
        if code == 0:
            if log_cb:
                log_cb("  依赖安装完成")
            return True
        else:
            if log_cb:
                log_cb(f"  [警告] pip 安装返回 {code}")
                if out:
                    log_cb(f"  {out[:500]}")
            return False

    def ensure_data_dirs(self, log_cb=None):
        if log_cb:
            log_cb("创建数据目录...")
        dirs = ["datasets", "runs", "pretrained", "temp", "logs", "db"]
        for d in dirs:
            self.run(f"mkdir -p {self.remote_dir}/data/{d}")
        if log_cb:
            log_cb("  数据目录已就绪")

    def _build_systemd_service_content(self):
        return (
            "[Unit]\n"
            "Description=MetaQA Cloud Training Web Service\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={self._user}\n"
            f"WorkingDirectory={self.remote_dir}\n"
            f"ExecStart={self.fixed_base_python} run.py\n"
            "Restart=always\n"
            "RestartSec=5\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            f"Environment=CT_PORT={SERVICE_PORT}\n"
            f"StandardOutput=append:{self.remote_dir}/data/logs/server.log\n"
            f"StandardError=append:{self.remote_dir}/data/logs/server.log\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

    def _has_systemd(self):
        code, out, err = self.run("command -v systemctl >/dev/null 2>&1 && echo OK || echo NO")
        return out.strip() == "OK"

    def _has_systemd_service(self):
        code, out, err = self.run(f"sudo -n test -f /etc/systemd/system/{SERVICE_UNIT_NAME} && echo EXISTS || echo MISSING")
        return out.strip() == "EXISTS"

    def configure_autostart(self, log_cb=None):
        if log_cb:
            log_cb("配置 systemd 自启动...")

        if not self._has_systemd():
            if log_cb:
                log_cb("  当前服务器未检测到 systemd，跳过自启动配置")
            return False

        self.ensure_data_dirs()
        temp_service_path = f"{self.remote_dir}/data/temp/{SERVICE_UNIT_NAME}"
        service_content = self._build_systemd_service_content()
        escaped = service_content.replace("'", "'\\''")

        commands = [
            f"mkdir -p {self.remote_dir}/data/temp",
            f"printf '%s' '{escaped}' > {temp_service_path}",
            f"sudo -n cp {temp_service_path} /etc/systemd/system/{SERVICE_UNIT_NAME}",
            "sudo -n systemctl daemon-reload",
            f"sudo -n systemctl enable {SERVICE_UNIT_NAME}",
        ]
        for cmd in commands:
            code, out, err = self.run(cmd, timeout=120)
            if code != 0:
                if log_cb:
                    log_cb(f"  systemd 配置失败: {err or out or cmd}")
                return False

        code, out, err = self.run(f"sudo -n systemctl is-enabled {SERVICE_UNIT_NAME}")
        if code == 0 and "enabled" in (out or ""):
            if log_cb:
                log_cb("  systemd 自启动已启用")
            return True

        if log_cb:
            log_cb(f"  systemd enable 校验失败: {err or out}")
        return False

    def _check_port_listening(self, port, log_cb=None):
        """检测端口是否监听 - 使用本地 socket 连接（最可靠）"""
        import time
        start_time = time.time()
        self.logger.info("CHECK", f"_check_port_listening 开始: port={port}, _host={self._host}")
        
        # 检测: 本地 socket 连接（最可靠的方法）
        if self._host:
            self.logger.info("CHECK", "  本地 socket 连接...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)  # 3秒超时
                sock_start = time.time()
                result = sock.connect_ex((self._host, port))
                sock_elapsed = time.time() - sock_start
                sock.close()
                self.logger.info("CHECK", f"    socket.connect_ex 返回: {result} (耗时 {sock_elapsed:.2f}s)")
                if result == 0:
                    self.logger.info("CHECK", "    ✓ 端口已开放")
                    return True
                else:
                    self.logger.info("CHECK", f"    ✗ 端口未开放 (错误码: {result})")
            except socket.timeout:
                self.logger.error("CHECK", "    ✗ 连接超时")
            except Exception as e:
                self.logger.error("CHECK", f"    ✗ 异常: {type(e).__name__}: {e}")
        else:
            self.logger.warn("CHECK", "  跳过: _host 为 None")
        
        self.logger.warn("CHECK", "  端口未检测到")
        return False

    def _collect_startup_diagnostics(self):
        sections = []

        def _append_section(title, cmd):
            code, out, err = self.run(cmd)
            content = (out or err or "").strip()
            if not content:
                content = f"无输出（exit_code={code}）"
            sections.append({"title": title, "content": content})

        _append_section(
            "server.log",
            f"tail -100 {self.remote_dir}/data/logs/server.log 2>/dev/null || echo 'server.log not found'",
        )

        if self._has_systemd() and self._has_systemd_service():
            _append_section(
                "systemctl status",
                f"sudo -n systemctl status {SERVICE_UNIT_NAME} --no-pager -n 50 2>&1",
            )
            _append_section(
                "journalctl",
                f"sudo -n journalctl -u {SERVICE_UNIT_NAME} -n 80 --no-pager 2>&1",
            )

        _append_section(
            "processes",
            "ps aux | grep -E 'python|uvicorn|run.py' | grep -v grep 2>/dev/null || true",
        )
        _append_section(
            "port",
            f"ss -lntp | grep ':{SERVICE_PORT} ' 2>/dev/null || echo 'port not listening'",
        )
        return sections

    def _emit_startup_diagnostics(self, sections, log_cb=None, max_lines_per_section=40):
        for section in sections:
            title = section.get("title", "diagnostic")
            content = section.get("content", "").strip()
            self.logger.info("SERVICE", f"[诊断] {title}:\n{content}")
            if not log_cb:
                continue
            log_cb(f"  --- {title} ---")
            lines = content.splitlines() if content else ["无输出"]
            for line in lines[:max_lines_per_section]:
                log_cb(f"    {line}")
            if len(lines) > max_lines_per_section:
                log_cb(f"    ...(已截断，剩余 {len(lines) - max_lines_per_section} 行)")

    def start_service(self, log_cb=None):
        self.logger.info("SERVICE", "=" * 60)
        self.logger.info("SERVICE", "启动服务开始")
        self.logger.info("SERVICE", f"  _host={self._host}, _port={self._port}")
        self.logger.info("SERVICE", f"  SERVICE_PORT={SERVICE_PORT}")
        
        if log_cb:
            log_cb("启动服务...")

        # 检测1: 检查服务是否已在运行
        self.logger.info("SERVICE", "[检测1] 检查服务是否已在运行")
        self.logger.info("SERVICE", "  调用 _check_port_listening...")
        
        check_result = self._check_port_listening(SERVICE_PORT, log_cb)
        self.logger.info("SERVICE", f"  _check_port_listening 返回: {check_result}")
        
        if check_result:
            self.logger.info("SERVICE", "  服务已在运行，跳过启动")
            if log_cb:
                log_cb("  服务已在运行，跳过启动")
            self.logger.info("SERVICE", "启动服务完成 (跳过)")
            self.logger.info("SERVICE", "=" * 60)
            return True

        def _start_with_nohup():
            start_cmd = (
                f"cd {self.remote_dir} && "
                f"nohup {self.fixed_base_python} run.py "
                f"> {self.remote_dir}/data/logs/server.log 2>&1 &"
            )
            self.logger.info("SERVICE", f"  启动命令: {start_cmd}")
            try:
                stdin, stdout, stderr = self.client.exec_command(start_cmd, timeout=10)
                code = stdout.channel.recv_exit_status()
                self.logger.info("SERVICE", f"  启动命令已发送: exit_code={code}")
                stdout.channel.close()
                stderr.channel.close()
            except Exception as e:
                self.logger.warn("SERVICE", f"  启动命令发送异常(可忽略): {type(e).__name__}: {e}")
                self.logger.info("SERVICE", "  nohup 后台命令超时属正常现象，服务可能已在启动中")

        # 启动服务
        self.logger.info("SERVICE", "[操作] 服务未运行，执行启动命令")
        if self._has_systemd() and self._has_systemd_service():
            start_cmd = f"sudo -n systemctl restart {SERVICE_UNIT_NAME}"
            self.logger.info("SERVICE", f"  systemd 启动命令: {start_cmd}")
            code, out, err = self.run(start_cmd, timeout=30)
            self.logger.info("SERVICE", f"  systemd 启动结果: exit_code={code}, output={repr((out or err).strip())}")
            if code != 0:
                if log_cb:
                    log_cb(f"  systemd 启动失败，回退 nohup: {err or out}")
                _start_with_nohup()
            else:
                if log_cb:
                    log_cb("  已通过 systemd 启动服务")
        else:
            _start_with_nohup()

        # 等待服务启动
        max_wait = 30  # 最多30秒
        interval = 1   # 每秒检测一次
        waited = 0
        self.logger.info("SERVICE", f"[检测2] 等待服务启动 (最多 {max_wait}s, 每 {interval}s 检测一次)")
        
        while waited < max_wait:
            time.sleep(interval)
            waited += interval
            self.logger.info("SERVICE", f"  等待 {waited}s/{max_wait}s...")
            
            check_result = self._check_port_listening(SERVICE_PORT, log_cb)
            self.logger.info("SERVICE", f"  _check_port_listening 返回: {check_result}")
            
            if check_result:
                self.logger.info("SERVICE", f"  服务已启动，端口 {SERVICE_PORT}")
                if log_cb:
                    log_cb(f"  服务已启动，端口 {SERVICE_PORT}（等待 {waited}s）")
                self.logger.info("SERVICE", "启动服务完成 (成功)")
                self.logger.info("SERVICE", "=" * 60)
                return True
            
            if log_cb:
                log_cb(f"  等待服务就绪... ({waited}s/{max_wait}s)")

        # 启动失败
        self.logger.error("SERVICE", f"[失败] 等待 {max_wait}s 后服务仍未启动")
        if log_cb:
            log_cb("  [警告] 端口未监听，检查日志")

        diagnostics = self._collect_startup_diagnostics()
        self._emit_startup_diagnostics(diagnostics, log_cb)
        
        self.logger.error("SERVICE", "启动服务完成 (失败)")
        self.logger.info("SERVICE", "=" * 60)
        return False

    def verify_service(self, log_cb=None):
        if log_cb:
            log_cb("验证服务...")

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            if self._host:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((self._host, SERVICE_PORT))
                    sock.close()
                    if result == 0:
                        if log_cb:
                            log_cb(f"  TCP端口连通 - 服务正常（第 {attempt} 次尝试）")
                        return True, "connected"
                except Exception as e:
                    if log_cb:
                        log_cb(f"  第 {attempt}/{max_retries} 次验证: TCP连接失败 - {e}")
            code, out, err = self.run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{SERVICE_PORT}/ 2>/dev/null")
            if out in ("200", "301", "302", "304"):
                if log_cb:
                    log_cb(f"  HTTP {out} - 服务正常（第 {attempt} 次尝试）")
                return True, out
            if log_cb:
                log_cb(f"  第 {attempt}/{max_retries} 次验证: HTTP {out or '无响应'}")
            if attempt < max_retries:
                time.sleep(3)

        if log_cb:
            log_cb(f"  服务验证失败")
        return False, "无响应"

    def full_deploy(self, host, port, user, password, local_dir, log_cb=None, progress_cb=None, step_cb=None):
        self.reset_cancel()
        steps = [
            ("连接服务器", self._step_connect),
            ("环境预检", self._step_precheck),
            ("初始化目录与环境", self._step_bootstrap_runtime),
            ("停止旧服务", self._step_stop_service),
            ("上传文件", self._step_upload),
            ("安装 Web 依赖", self._step_install_deps),
            ("创建训练环境", self._step_prepare_training_env),
            ("创建转换环境", self._step_prepare_conversion_env),
            ("验证固定环境", self._step_verify_envs),
            ("base瘦身与清理", self._step_slim_base),
            ("配置自启动", self._step_configure_autostart),
            ("启动并验证服务", self._step_start_and_verify),
        ]

        results = {}
        for step_name, step_fn in steps:
            if self._cancelled:
                if log_cb:
                    log_cb(f"\n[已取消] 部署在 '{step_name}' 步骤中断")
                break

            if step_cb:
                step_cb(step_name, "running", f"{step_name}：开始执行")
            self._deploy_context["current_step_name"] = step_name
            self._deploy_context["step_cb"] = step_cb

            if log_cb:
                log_cb(f"\n{'='*40}")
                log_cb(f"[{step_name}]")
                log_cb(f"{'='*40}")

            try:
                success, detail = step_fn(host, port, user, password, local_dir, log_cb, progress_cb)
                results[step_name] = {"success": success, "detail": detail}
                if step_cb:
                    step_cb(step_name, "success" if success else "error", detail)
                if not success:
                    if log_cb:
                        log_cb(f"[失败] {step_name}: {detail}")
                    break
            except Exception as e:
                results[step_name] = {"success": False, "detail": str(e)}
                if step_cb:
                    step_cb(step_name, "error", str(e))
                if log_cb:
                    log_cb(f"[异常] {step_name}: {e}")
                break

        return results

    def _step_bootstrap_runtime(self, host, port, user, password, local_dir, log_cb, progress_cb):
        if log_cb:
            log_cb(f"初始化运行时目录: {self.base_runtime_dir}")
        self.run(f"mkdir -p {self.base_runtime_dir}")

        state = self._load_remote_deploy_state()
        should_slim = self._should_run_base_slim(state)
        current_step_name = self._deploy_context.get("current_step_name", "")
        step_cb = self._deploy_context.get("step_cb")
        precheck = self._deploy_context.get("precheck", {})
        
        self._deploy_context.update({
            "deploy_state": state,
            "first_bootstrap": state is None,
            "should_run_base_slim": should_slim,
            "current_step_name": current_step_name,
            "step_cb": step_cb,
            "precheck": precheck
        })
        if log_cb:
            log_cb(f"  首次部署/复位: {'是' if state is None else '否'}")
            log_cb(f"  本次需要 base 瘦身: {'是' if should_slim else '否'}")

        precheck = self._deploy_context.get("precheck", {})
        if precheck.get("need_install_miniforge", True):
            if not self._install_miniforge(log_cb):
                return False, "Miniforge 安装失败"
        elif log_cb:
            log_cb("  Miniforge 已存在，跳过安装")
            
        # 检查项目目录
        self.run(f"mkdir -p {self.remote_dir}")
        
        if precheck.get("need_install_system_deps", True):
            self._install_system_deps(log_cb)
        elif log_cb:
            log_cb("  系统运行库已满足，跳过安装")
        
        return True, "运行时环境初始化完成"

    def _install_miniforge(self, log_cb=None):
        code, out, err = self.run(f"test -x {self.fixed_conda} && echo EXISTS || echo MISSING")
        if out.strip() == "EXISTS":
            if log_cb:
                log_cb("  Miniforge 已安装")
            return True
            
        if log_cb:
            log_cb("  未发现 Miniforge，开始自动安装...")
            
        installer = "Miniforge3-Linux-x86_64.sh"
        # 使用清华源或其他镜像可能更快，但 github 官方最稳
        download_cmd = f"wget https://github.com/conda-forge/miniforge/releases/latest/download/{installer} -O /tmp/{installer}"
        install_cmd = f"bash /tmp/{installer} -b -p {self.base_runtime_dir}/miniforge3"
        
        self._emit_step_detail("下载 Miniforge")
        code, out, err = self._run_command_with_heartbeat(
            download_cmd, timeout=600, log_cb=log_cb, heartbeat_label="下载 Miniforge"
        )
        if code != 0:
            if log_cb:
                log_cb(f"  下载失败: {err or out}")
            return False
            
        self._emit_step_detail("安装 Miniforge")
        code, out, err = self._run_command_with_heartbeat(
            install_cmd, timeout=900, log_cb=log_cb, heartbeat_label="安装 Miniforge"
        )
        if code != 0:
            if log_cb:
                log_cb(f"  安装失败: {err or out}")
            return False
            
        if log_cb:
            log_cb("  Miniforge 安装成功")
        return True

    def _install_system_deps(self, log_cb=None):
        code, out, err = self.run("dpkg -s libgl1 libglib2.0-0 >/dev/null 2>&1 && echo READY || echo MISSING")
        if out.strip() == "READY":
            if log_cb:
                log_cb("  系统运行库已存在，跳过安装")
            return True

        if log_cb:
            log_cb("安装系统运行库 (sudo)...")
        # 针对新服务器，确保 libgl1 (OpenCV headless 仍需部分 glib) 等存在
        # 使用 sudo -n 避免交互式密码输入
        cmd = "sudo -n apt-get update && sudo -n apt-get install -y libgl1 libglib2.0-0"
        self._emit_step_detail("安装系统运行库")
        code, out, err = self._run_command_with_heartbeat(
            cmd, timeout=300, log_cb=log_cb, heartbeat_label="安装系统依赖"
        )
        if code != 0:
            if log_cb:
                log_cb(f"  系统依赖安装跳过或失败 (可能无 sudo 权限): {err or out}")
            # 系统依赖失败不一定导致部署失败，后续环境验证会兜底
        return True

    def _step_connect(self, host, port, user, password, local_dir, log_cb, progress_cb):
        try:
            self.connect(host, port, user, password)
            if log_cb:
                log_cb(f"  已连接 {user}@{host}:{port}")
            return True, "连接成功"
        except Exception as e:
            return False, str(e)

    def _step_precheck(self, host, port, user, password, local_dir, log_cb, progress_cb):
        env = self.check_remote_env(log_cb)
        plan = self._build_precheck_plan(env)
        self._deploy_context["precheck"] = plan
        self._log_precheck_plan(plan, log_cb)
        return True, "环境预检完成"

    def _step_stop_service(self, host, port, user, password, local_dir, log_cb, progress_cb):
        self.stop_service(log_cb)
        return True, "旧服务已停止"

    def _step_upload(self, host, port, user, password, local_dir, log_cb, progress_cb):
        success, uploaded, skipped, failed = self.upload_files(
            local_dir, log_cb, progress_cb, skip_existing=True
        )
        detail = f"已上传:{uploaded} 失败:{failed}"
        return success, detail

    def _step_install_deps(self, host, port, user, password, local_dir, log_cb, progress_cb):
        precheck = self._deploy_context.get("precheck", {})
        if not precheck.get("need_install_web_requirements", True):
            if log_cb:
                log_cb("  Web 依赖无需补齐，跳过安装")
            return True, "Web依赖已跳过"
        success = self.install_dependencies(log_cb)
        self.ensure_data_dirs(log_cb)
        return success, "Web依赖安装完成" if success else "Web依赖安装有警告"

    def _step_prepare_training_env(self, host, port, user, password, local_dir, log_cb, progress_cb):
        precheck = self._deploy_context.get("precheck", {})
        if precheck.get("need_create_training_env", True):
            success = self._create_remote_env("cloud-training", log_cb)
            if not success:
                return False, "训练环境创建失败"
        elif log_cb:
            log_cb("  训练环境已存在，跳过创建，开始补齐依赖")

        if precheck.get("need_sync_training_requirements", True):
            success = self._sync_remote_env_requirements(
                self.fixed_training_python, "deploy_tool/requirements-training.txt", "cloud-training", log_cb
            )
        else:
            if log_cb:
                log_cb("  训练环境依赖未变更，跳过同步")
            success = True
        return success, "训练环境已就绪" if success else "训练环境创建失败"

    def _step_prepare_conversion_env(self, host, port, user, password, local_dir, log_cb, progress_cb):
        precheck = self._deploy_context.get("precheck", {})
        if precheck.get("need_create_conversion_env", True):
            success = self._create_remote_env("cloud-conversion", log_cb)
            if not success:
                return False, "转换环境创建失败"
        elif log_cb:
            log_cb("  转换环境已存在，跳过创建，开始补齐依赖")

        if precheck.get("need_sync_conversion_requirements", True):
            success = self._sync_remote_env_requirements(
                self.fixed_conversion_python, "deploy_tool/requirements-conversion.txt", "cloud-conversion", log_cb
            )
        else:
            if log_cb:
                log_cb("  转换环境依赖未变更，跳过同步")
            success = True
        return success, "转换环境已就绪" if success else "转换环境创建失败"

    def _step_verify_envs(self, host, port, user, password, local_dir, log_cb, progress_cb):
        training_ok, training_detail = self._verify_remote_imports(
            self.fixed_training_python,
            TRAINING_IMPORT_CHECK_SNIPPET,
            log_cb,
            "训练环境",
        )
        conversion_ok, conversion_detail = self._verify_remote_imports(
            self.fixed_conversion_python,
            CONVERSION_IMPORT_CHECK_SNIPPET,
            log_cb,
            "转换环境",
        )
        if training_ok and conversion_ok:
            return True, "固定环境验证通过"
        if not training_ok and conversion_ok:
            return False, training_detail
        if training_ok and not conversion_ok:
            return False, conversion_detail
        return False, f"{training_detail}；{conversion_detail}"

    def _step_slim_base(self, host, port, user, password, local_dir, log_cb, progress_cb):
        if not self._deploy_context.get("should_run_base_slim", True):
            if log_cb:
                log_cb("  已存在完整 deploy_state，跳过 base 瘦身")
            self._write_remote_deploy_state(self._build_deploy_state(base_slimmed=True))
            return True, "base 瘦身已跳过"

        success = self._slim_remote_base(log_cb)
        if success:
            self._write_remote_deploy_state(self._build_deploy_state(base_slimmed=True))
            return True, "base 瘦身完成"
        return False, "base 瘦身失败"

    def _step_configure_autostart(self, host, port, user, password, local_dir, log_cb, progress_cb):
        precheck = self._deploy_context.get("precheck", {})
        if not precheck.get("systemd_available", True):
            if log_cb:
                log_cb("  当前系统不支持 systemd，跳过自启动配置")
            return True, "systemd 不可用，已跳过"
        if not precheck.get("need_configure_autostart", True):
            if log_cb:
                log_cb("  systemd 自启动已存在，跳过配置")
            return True, "systemd 自启动已存在"
        success = self.configure_autostart(log_cb)
        return success, "systemd 自启动已配置" if success else "systemd 自启动配置失败"

    def _step_start_and_verify(self, host, port, user, password, local_dir, log_cb, progress_cb):
        success = self.start_service(log_cb)
        if not success:
            return False, "服务启动异常"
        success, code = self.verify_service(log_cb)
        return success, f"HTTP {code}"

    def _load_remote_deploy_state(self):
        code, out, err = self.run(f"test -f {self.deploy_state_path} && cat {self.deploy_state_path} || echo ''")
        if code == 0 and out.strip():
            try:
                return json.loads(out)
            except Exception:
                return None
        return None

    def _write_remote_deploy_state(self, state):
        payload = json.dumps(state, ensure_ascii=False)
        escaped = payload.replace("'", "'\\''")
        self.run(f"mkdir -p {self.remote_dir}/data")
        self.run(f"printf '%s' '{escaped}' > {self.deploy_state_path}")

    def _should_run_base_slim(self, state):
        if not state:
            return True
        if not state.get("base_slimmed"):
            return True
        if not state.get("base_slimmed_at"):
            return True
        if not state.get("env_snapshot"):
            return True
        if not state.get("version_locks"):
            return True
        return False

    def _create_remote_env(self, env_name, log_cb=None):
        if log_cb:
            log_cb(f"  创建环境 {env_name}...")
            log_cb("  这是慢步骤，可能需要几分钟，请等待心跳日志持续刷新")
        self._emit_step_detail(f"创建 {env_name} conda 环境")
        code, out, err = self._run_command_with_heartbeat(
            f"{self.fixed_conda} create -y -n {env_name} python=3.10",
            timeout=1800,
            log_cb=log_cb,
            heartbeat_label=f"创建 {env_name} conda 环境",
        )
        if code != 0:
            if log_cb and err:
                log_cb(f"  {err[:300]}")
            return False
        return True

    def _sync_remote_env_requirements(self, python_path, requirements_rel_path, env_name, log_cb=None):
        if log_cb:
            log_cb(f"  安装 {env_name} 锁定依赖...")
            log_cb("  这是慢步骤，安装大包时会定期输出仍在执行的心跳")
        requirement_items = self._parse_requirement_display_items(requirements_rel_path)
        heartbeat_index = {"value": 0}
        heartbeat_label = f"安装 {env_name} 锁定依赖"

        def heartbeat_label_cb():
            label = self._build_requirements_heartbeat_label(
                heartbeat_label,
                requirement_items,
                heartbeat_index["value"],
            )
            if heartbeat_index["value"] < len(requirement_items) - 1:
                heartbeat_index["value"] += 1
            return label

        self._emit_step_detail(f"安装 {env_name} 锁定依赖")
        code, out, err = self._run_command_with_heartbeat(
            f"cd {self.remote_dir} && {python_path} -m pip install -r {requirements_rel_path}",
            timeout=3600,
            log_cb=log_cb,
            heartbeat_label=heartbeat_label,
            heartbeat_label_cb=heartbeat_label_cb,
        )
        if code != 0:
            if log_cb and (err or out):
                log_cb(f"  {(err or out)[:300]}")
            return False
        if log_cb and out:
            log_cb(f"  {out.splitlines()[-1][:300]}")
        return True

    def _ensure_remote_env(self, env_name, python_path, requirements_rel_path, log_cb=None):
        code, out, err = self.run(f"test -x {python_path} && echo EXISTS || echo MISSING")
        if out.strip() != "EXISTS":
            success = self._create_remote_env(env_name, log_cb)
            if not success:
                return False
        return self._sync_remote_env_requirements(python_path, requirements_rel_path, env_name, log_cb)

    def _verify_remote_imports(self, python_path, code_snippet, log_cb, label):
        self._emit_step_detail(f"{label}导入验证")
        code, out, err = self.run(
            f"{python_path} -c \"{code_snippet}\"",
            timeout=120,
        )
        if code == 0:
            if log_cb:
                log_cb(f"  {label}验证通过")
            return True, f"{label}验证通过"
        detail = (err or out or "无输出")[:300]
        if log_cb:
            log_cb(f"  {label}验证失败: {detail}")
        return False, f"{label}验证失败: {detail}"

    def run_remote_package_replay(self, task_id, log_cb=None):
        if not self.client:
            return False, "未连接服务器"
        task_id = str(task_id or "").strip()
        if not task_id:
            return False, "未提供任务ID"
        if log_cb:
            log_cb(f"  开始离线回放产物打包: {task_id}")
        cmd = (
            f"cd {self.remote_dir} && "
            f"{self.fixed_base_python} - <<'PY'\n"
            "from app.core.package_manager import create_package\n"
            f"pkg = create_package({task_id!r})\n"
            "print('REPLAY_OK')\n"
            "print(pkg['file_path'])\n"
            "PY"
        )
        code, out, err = self._exec(self.client, cmd, timeout=3600)
        detail = (out or err or "").strip()
        if code == 0:
            if log_cb:
                log_cb("  离线回放执行成功")
            return True, detail
        if log_cb:
            log_cb(f"  离线回放执行失败: {detail[:300]}")
        return False, detail or "离线回放执行失败"

    def _slim_remote_base(self, log_cb=None):
        if log_cb:
            log_cb("  备份 base 环境包清单...")
        self.run(f"mkdir -p {self.remote_dir}/data/logs")
        self.run(f"cd {self.remote_dir} && {self.fixed_base_python} -m pip freeze > data/logs/base-freeze-before-slim.txt")
        self.run(f"cd {self.remote_dir} && {self.fixed_base_python} -m pip list --format=freeze > data/logs/base-pip-list-before-slim.txt")

        uninstall_cmd = (
            f"{self.fixed_base_python} -m pip uninstall -y "
            "torch torchvision torchaudio ultralytics onnx tensorflow onnx2tf "
            "onnxruntime onnxruntime-gpu onnxsim ai-edge-litert sng4onnx "
            "onnx_graphsurgeon tf-keras h5py flatbuffers protobuf"
        )
        if log_cb:
            log_cb("  执行 base 瘦身...")
        self.run(uninstall_cmd, timeout=1800)

        verify_cmd = (
            f"{self.fixed_base_python} -c "
            "\"import fastapi, uvicorn, yaml, multipart, aiofiles; print('web-ok')\""
        )
        code, out, err = self.run(verify_cmd, timeout=120)
        if code != 0:
            if log_cb:
                log_cb(f"  base 校验失败: {(err or out)[:300]}")
            return False

        if log_cb:
            log_cb("  清理 pip/conda 缓存...")
        self.run(f"{self.fixed_base_python} -m pip cache purge", timeout=300)
        self.run(f"{self.fixed_conda} clean -a -y", timeout=600)
        return True

    def _build_deploy_state(self, base_slimmed):
        snapshot_name = self._snapshot_remote_envs()
        precheck = self._deploy_context.get("precheck", {})
        return {
            "schema_version": 1,
            "env_layout": "base-web__cloud-training__cloud-conversion",
            "project_bootstrapped": True,
            "base_slimmed": base_slimmed,
            "base_slimmed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if base_slimmed else "",
            "last_deploy_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "env_snapshot": snapshot_name,
            "version_locks": True,
            "requirements_hashes": precheck.get("requirements_hashes", {})
        }

    def _snapshot_remote_envs(self):
        version = self._get_local_app_version()
        snapshot_name = f"env-snapshot-{version}-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}.json"
        snapshot_path = f"{self.remote_dir}/data/logs/{snapshot_name}"
        script = (
            "import json, subprocess\n"
            "payload = {\n"
            f"  'version': {json.dumps(version)},\n"
            f"  'web_python': {json.dumps(self.fixed_base_python)},\n"
            f"  'training_python': {json.dumps(self.fixed_training_python)},\n"
            f"  'conversion_python': {json.dumps(self.fixed_conversion_python)},\n"
            "}\n"
            "for key, cmd in {\n"
            f"  'web_packages': [{json.dumps(self.fixed_base_python)}, '-m', 'pip', 'freeze'],\n"
            f"  'training_packages': [{json.dumps(self.fixed_training_python)}, '-m', 'pip', 'freeze'],\n"
            f"  'conversion_packages': [{json.dumps(self.fixed_conversion_python)}, '-m', 'pip', 'freeze'],\n"
            "}.items():\n"
            "  try:\n"
            "    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)\n"
            "    payload[key] = result.stdout.splitlines()\n"
            "  except Exception as exc:\n"
            "    payload[key] = [str(exc)]\n"
            f"open({json.dumps(snapshot_path)}, 'w', encoding='utf-8').write(json.dumps(payload, ensure_ascii=False, indent=2))\n"
        )
        self.run(f"mkdir -p {self.remote_dir}/data/logs")
        self.run(f"{self.fixed_base_python} -c \"{script}\"", timeout=300)
        return snapshot_name

    def _get_local_app_version(self):
        config_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "app_config.yaml"))
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            in_app = False
            for line in lines:
                if line.strip() == "app:":
                    in_app = True
                    continue
                if in_app and line.startswith("server:"):
                    break
                if in_app and "version:" in line:
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return "v0.1.0"
