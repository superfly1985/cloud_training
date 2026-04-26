import os
import time

class EnvironmentManager:
    """服务器环境检查与修复 - 深度复刻原版逻辑"""

    def __init__(self, server_manager):
        self.server_manager = server_manager

    @property
    def resolved_python(self):
        return self.server_manager.python_cmd

    @resolved_python.setter
    def resolved_python(self, value):
        self.server_manager.python_cmd = value

    def get_python_cmd_with_fallback(self, log_callback=None):
        """
        深度复刻原版：获取可用的Python命令（支持多路径探测和PIP校验）
        """
        def _log(msg):
            if log_callback:
                log_callback(msg)

        python_candidates = self._default_python_candidates()
        for cmd in python_candidates:
            ok, resolved, _, pip_ok = self._probe_python_basic(cmd)
            if ok and pip_ok:
                self.resolved_python = resolved
                return resolved
        _log("✗ 未找到可用Python解释器（缺少pip或不可执行）")
        return None

    def _default_python_candidates(self):
        return [
            "/root/miniforge3/bin/python3",
            "/root/miniconda3/bin/python3",
            "/root/anaconda3/bin/python3",
            "/opt/conda/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
            "python3",
            "python",
        ]

    def _probe_python_basic(self, cmd):
        """基础探测：可执行 + 版本 + pip 可用。"""
        probe_script = (
            'import sys, subprocess; '
            'print(sys.executable); '
            'print(str(sys.version_info.major)+\".\"+str(sys.version_info.minor)); '
            'rc=subprocess.call([sys.executable, \"-m\", \"pip\", \"--version\"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); '
            'print(\"PIP_OK\" if rc==0 else \"PIP_MISSING\")'
        )
        ok, out = self.server_manager.execute_command(f'{cmd} -c \'{probe_script}\' 2>/dev/null', timeout=15)
        if not ok or not out:
            return False, "", "", False
        lines = out.strip().splitlines()
        if len(lines) < 3:
            return False, "", "", False
        resolved = lines[0].strip() or str(cmd).strip()
        py_ver = lines[1].strip()
        pip_ok = lines[-1].strip() == "PIP_OK"
        return True, resolved, py_ver, pip_ok

    def _probe_ultralytics_ready(self, python_cmd):
        """探测转换门禁：ultralytics 与 YOLO 导入。"""
        check_script = (
            "import json\n"
            "res={'ok': False, 'ultralytics_version':'', 'error':''}\n"
            "try:\n"
            "    import ultralytics\n"
            "    from ultralytics import YOLO\n"
            "    _ = YOLO\n"
            "    res['ok'] = True\n"
            "    res['ultralytics_version'] = getattr(ultralytics, '__version__', 'unknown')\n"
            "except Exception as e:\n"
            "    res['error'] = str(e)\n"
            "print(json.dumps(res, ensure_ascii=False))\n"
        )
        cmd = f"{python_cmd} - <<'PY'\n{check_script}PY"
        ok, out = self.server_manager.execute_command(cmd, timeout=25)
        if not ok:
            return False, "", (out or "").strip()
        text = (out or "").strip().splitlines()[-1] if out else ""
        if not text:
            return False, "", "探测输出为空"
        try:
            import json
            obj = json.loads(text)
        except Exception:
            return False, "", f"探测输出不可解析: {text[:120]}"
        if obj.get("ok"):
            return True, str(obj.get("ultralytics_version", "")).strip(), ""
        return False, "", str(obj.get("error", "")).strip() or "ultralytics/YOLO 导入失败"

    def get_export_python_cmd(self, preferred_cmd="", log_callback=None):
        """
        获取可用于 TFLite 转换的 Python（独立于训练环境）：
        1) 优先配置中的 convert.python_export_cmd；
        2) 再遍历常见解释器，要求通过 ultralytics + YOLO 导入门禁。
        """
        def _log(msg):
            if log_callback:
                log_callback(msg)

        candidates = []
        preferred = str(preferred_cmd or "").strip()
        if preferred:
            candidates.append(preferred)
        for c in self._default_python_candidates():
            if c not in candidates:
                candidates.append(c)

        for cmd in candidates:
            ok_basic, resolved, py_ver, pip_ok = self._probe_python_basic(cmd)
            if not ok_basic:
                continue
            if not pip_ok:
                continue
            ok_ultra, ultra_ver, ultra_err = self._probe_ultralytics_ready(resolved)
            if ok_ultra:
                _log(f"✓ 转换环境: {resolved} | Python {py_ver} | ultralytics {ultra_ver}")
                return resolved, ultra_ver
            _log(f"⚠ 跳过解释器 {resolved}: {ultra_err or 'ultralytics不可用'}")

        return "", ""

    def _get_env_spec(self):
        """训练环境规则源：检查、修复、训练前门禁复用"""
        return {
            "system_packages": ["libgl1-mesa-glx", "libglib2.0-0", "libusb-1.0-0"],
            "python_packages": [
                {"name": "pyyaml", "pip": "pyyaml", "import_cmd": 'import yaml; print("OK")'},
                {"name": "numpy", "pip": "numpy==1.26.4", "import_cmd": "import numpy; print(numpy.__version__)", "min_ver": "1.26.0", "max_ver": "2.0.0"},
                {"name": "cv2", "pip": "opencv-python==4.7.0.72", "import_cmd": "import cv2; print(cv2.__version__)"},
                {"name": "PIL", "pip": "pillow", "import_cmd": "from PIL import Image; print(Image.__version__)"},
                {"name": "torch", "pip": "torch", "import_cmd": "import torch; print(torch.__version__)"},
                {"name": "ultralytics", "pip": "ultralytics", "import_cmd": "import ultralytics; print(ultralytics.__version__)"},
                {"name": "matplotlib", "pip": "matplotlib", "import_cmd": "import matplotlib; print(matplotlib.__version__)"},
                {"name": "onnx", "pip": "onnx==1.16.1", "import_cmd": "import onnx; print(onnx.__version__)", "exact_ver": "1.16.1"},
                {"name": "onnxsim", "pip": "onnxsim", "import_cmd": "import onnxsim; print(onnxsim.__version__)"},
                {"name": "onnxruntime", "pip": "onnxruntime-gpu", "import_cmd": "import onnxruntime as ort; print(ort.__version__)"},
                {"name": "flatbuffers", "pip": "flatbuffers", "import_cmd": "import flatbuffers; print(getattr(flatbuffers, '__version__', 'OK'))"},
                {"name": "protobuf", "pip": "protobuf>=5,<6", "import_cmd": "from google.protobuf import __version__ as v; print(v)", "min_ver": "5.0.0", "max_ver": "6.0.0"},
                {"name": "h5py", "pip": "h5py", "import_cmd": "import h5py; print(h5py.__version__)"},
            ],
            "system_libs": [
                {"name": "libGL.so.1", "check_cmd": "ldconfig -p | grep libGL.so.1", "hint": "OpenCV需要", "fix_pkg": "libgl1-mesa-glx"},
            ],
        }

    def _is_benign_import_stderr_line(self, line):
        t = (line or "").strip()
        if not t: return True
        lower = t.lower()
        benign_prefixes = ["i tensorflow/", "w0000", "e0000", "warning:", "all log messages"]
        if any(lower.startswith(p) for p in benign_prefixes): return True
        benign_contains = ["onednn custom operations", "unable to register", "binary is optimized"]
        return any(x in lower for x in benign_contains)

    def _is_benign_apt_line(self, line):
        """深度复刻原版：过滤 apt 安装过程中的非致命警告"""
        t = (line or "").strip().lower()
        if not t: return True
        # 常见非致命提示：容器/精简系统缺少 apt-utils 时会出现
        if "debconf: delaying package configuration, since apt-utils is not installed" in t:
            return True
        if t.startswith("debconf:"):
            return True
        if "warning" in t:
            return True
        if "focusing on" in t:
            return True
        # 忽略一些进度或状态信息
        if "reading package lists" in t or "building dependency tree" in t or "reading state information" in t:
            return True
        return False

    def _execute_apt_install(self, apt_pkg_str, log_callback=None):
        """
        统一执行 apt 安装逻辑，支持 sudo 探测和良性错误过滤
        """
        def _log(msg):
            if log_callback: log_callback(msg)

        # 1. 检测是否需要 sudo
        ok_whoami, whoami = self.server_manager.execute_command("whoami")
        is_root = (ok_whoami and whoami.strip() == "root")
        
        sudo_prefix = ""
        if not is_root:
            ok_sudo, _ = self.server_manager.execute_command("command -v sudo")
            if ok_sudo:
                sudo_prefix = "sudo "
        
        # 2. 构建命令
        # 深度复刻：apt-get update -qq && apt-get install -y ... -qq
        cmd = f"{sudo_prefix}apt-get update -qq && {sudo_prefix}apt-get install -y {apt_pkg_str} -qq"
        
        # 3. 执行
        ok, out = self.server_manager.execute_command(cmd, timeout=300)
        
        if not ok:
            # 过滤错误信息
            lines = out.splitlines()
            fatal_lines = [ln for ln in lines if not self._is_benign_apt_line(ln)]
            if not fatal_lines:
                # 如果没有致命错误行，尝试验证安装是否真的失败
                _log(f"  ⚠ apt 执行返回非零，但未发现致命错误，正在校验...")
                return True, out
            return False, "\n".join(fatal_lines)
        
        return True, out

    def _first_import_error_line(self, text):
        lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
        if not lines: return "无详细错误信息"
        for ln in lines:
            if any(k in ln for k in ["ImportError:", "ModuleNotFoundError:", "OSError:", "RuntimeError:", "Exception:"]):
                return ln[:220]
        for ln in lines:
            if not self._is_benign_import_stderr_line(ln) and not (ln.startswith("Traceback") or ln.startswith("File ")):
                return ln[:220]
        return lines[-1][:220]

    def _ver_tuple(self, version_text):
        nums = []
        for seg in str(version_text or "").split("."):
            seg = "".join(ch for ch in seg if ch.isdigit())
            if not seg: break
            nums.append(int(seg))
        return tuple(nums[:3] or [0])

    def _version_reason(self, current, spec):
        cur = str(current or "").strip()
        if not cur: return "无法读取版本"
        if spec.get("exact_ver") and cur != spec["exact_ver"]:
            return f"版本不匹配({cur})，需 =={spec['exact_ver']}"
        cur_t = self._ver_tuple(cur)
        if spec.get("min_ver") and cur_t < self._ver_tuple(spec["min_ver"]):
            return f"版本过低({cur})，需 >={spec['min_ver']}"
        if spec.get("max_ver") and cur_t >= self._ver_tuple(spec["max_ver"]):
            return f"版本过高({cur})，需 <{spec['max_ver']}"
        return ""

    def check_environment(self, log_callback=None):
        """执行环境检查 - 深度复刻原版显示格式"""
        def _log(msg):
            if log_callback: log_callback(msg)

        spec = self._get_env_spec()
        missing = []
        versions = {}

        # 1. 探测 Python 解释器
        python_cmd = self.get_python_cmd_with_fallback(log_callback=None)
        if not python_cmd:
            _log("✗ 未找到可用的Python环境（或缺少pip模块）")
            # 即使没找到，也记录一个默认的用于后续尝试修复
            python_cmd = "python3"
        else:
            _log(f"✓ Python命令: {python_cmd}")
        
        self.resolved_python = python_cmd

        # 2. 检查 Python 版本
        ok, py_out = self.server_manager.execute_command(f"{python_cmd} --version", timeout=30)
        py_ver = py_out.strip() if ok else "unknown"
        versions["python"] = py_ver
        _log(f"✓ Python版本: {py_ver}")

        # 3. 检查 Python 包
        for pkg in spec["python_packages"]:
            is_optional = bool(pkg.get("optional"))
            escaped_cmd = pkg["import_cmd"].replace('"', '\\"')
            cmd = f"{python_cmd} -c \"{escaped_cmd}\""
            ok, out = self.server_manager.execute_command(cmd, timeout=30)
            
            if not ok:
                reason = self._first_import_error_line(out)
                if is_optional:
                    versions[pkg["name"]] = f"OPTIONAL_FAIL:{reason[:60]}"
                    _log(f"  ⚠ {pkg['name']}: 可选依赖不可用（{reason}）")
                else:
                    missing.append({"type": "python", "name": pkg["name"], "reason": reason, "pip": pkg["pip"]})
                    _log(f"  ❌ {pkg['name']}: 未安装/不可用（{reason}）")
                continue

            cur_ver = out.splitlines()[0].strip() if out else "OK"
            versions[pkg["name"]] = cur_ver
            ver_reason = self._version_reason(cur_ver, pkg)
            if ver_reason:
                missing.append({"type": "python", "name": pkg["name"], "reason": ver_reason, "pip": pkg["pip"]})
                _log(f"  ❌ {pkg['name']}: {ver_reason}")
            else:
                _log(f"  ✅ {pkg['name']}: {cur_ver}")

        # 3. 检查系统库
        _log("检查系统库...")
        for lib in spec["system_libs"]:
            ok, out = self.server_manager.execute_command(lib["check_cmd"], timeout=20)
            if ok and out.strip():
                versions[lib["name"]] = "OK"
                _log(f"  ✅ {lib['name']}: 已安装")
            else:
                versions[lib["name"]] = "MISSING"
                reason = f"未安装（{lib['hint']}）"
                missing.append({"type": "system", "name": lib["name"], "reason": reason, "pip": lib["fix_pkg"]})
                _log(f"  ❌ {lib['name']}: {reason}")

        fingerprint_items = [f"{k}={versions[k]}" for k in sorted(versions.keys())]
        return {
            "missing": missing,
            "versions": versions,
            "fingerprint": "|".join(fingerprint_items),
            "errors": [f"{m['name']}: {m['reason']}" for m in missing]
        }

    def fix_environment(self, log_callback=None):
        """修复环境 - 深度复刻原版安装与反馈逻辑"""
        def _log(msg):
            if log_callback: log_callback(msg)

        spec = self._get_env_spec()
        python_cmd = self.resolved_python

        # 1. 首先执行一次检查以获取缺失列表
        _log("正在获取环境差异清单...")
        check_res = self.check_environment(log_callback=None) # 静默检查
        
        # 即使 check_res 没报错，如果 resolved_python 没 pip，也要修
        # 检查 pip 是否可用
        pip_check_cmd = f"{python_cmd} -m pip --version"
        ok_pip, _ = self.server_manager.execute_command(pip_check_cmd, timeout=15)
        
        if not check_res["missing"] and ok_pip:
            _log("✓ 当前环境已通过统一检查，无需修复")
            return True, []

        # 2. 尝试修复 pip (如果缺失)
        if not ok_pip:
            _log(f"⚠ {python_cmd} 缺少 pip 模块，尝试安装...")
            # 使用统一的 apt 安装逻辑
            ok_apt, out_apt = self._execute_apt_install("python3-pip", log_callback=_log)
            
            if not ok_apt:
                # 尝试使用 ensurepip
                _log("  ⚠ apt 安装失败，尝试使用 ensurepip...")
                ensure_cmd = f"{python_cmd} -m ensurepip --upgrade"
                ok_ensure, out_ensure = self.server_manager.execute_command(ensure_cmd, timeout=60)
                if not ok_ensure:
                    _log(f"❌ 无法安装 pip: {out_ensure}")
                    return False, [{"command": "install_pip", "success": False, "output": out_ensure}]
            _log("✓ pip 模块安装/修复完成")

        missing_system_pkgs = []
        missing_python_names = set()
        for item in check_res["missing"]:
            if item.get("type") == "system" and item.get("pip"):
                missing_system_pkgs.append(item["pip"])
            elif item.get("type") == "python":
                missing_python_names.add(item.get("name"))

        # 3. 安装系统库
        system_pkg_list = [p for p in spec["system_packages"] if p in missing_system_pkgs]
        if system_pkg_list:
            system_pkg_str = " ".join(system_pkg_list)
            _log(f"安装系统库: {system_pkg_str}")
            ok, out = self._execute_apt_install(system_pkg_str, log_callback=_log)
            if not ok:
                _log(f"❌ 系统库安装失败: {out[:200]}")
                return False, [{"command": "system_libs", "success": False, "output": out}]
            _log("✓ 系统库安装完成")
        else:
            _log("✓ 系统库均已满足，跳过安装")

        # 4. 安装 Python 包
        required_python_packages = [item for item in spec["python_packages"] if (not item.get("optional")) and item.get("name") in missing_python_names]
        packages_to_install = [item["pip"] for item in required_python_packages]
        
        if packages_to_install:
            _log(f"按统一检查结果修复Python依赖，共 {len(packages_to_install)} 项")
            for pkg in packages_to_install:
                _log(f"安装 {pkg}...")
                cmd = f"{python_cmd} -m pip install \"{pkg}\" -q"
                ok, out = self.server_manager.execute_command(cmd, timeout=300)
                if not ok:
                    # 复检是否真的不可用（原版逻辑）
                    _log(f"  ⚠ {pkg} 安装可能有冲突，正在复检...")
                    # 再次尝试导入
                    check_pkg = [p for p in spec["python_packages"] if p["pip"] == pkg][0]
                    escaped_check = check_pkg["import_cmd"].replace('"', '\\"')
                    ok_re, _ = self.server_manager.execute_command(f"{python_cmd} -c \"{escaped_check}\"", timeout=15)
                    if ok_re:
                        _log(f"  ✓ {pkg} 导入校验通过，忽略安装警告")
                        continue
                    
                    _log(f"❌ {pkg} 安装失败: {out[:100]}")
                    return False, [{"command": pkg, "success": False, "output": out}]
                _log(f"✓ {pkg} 安装完成")
        else:
            _log("✓ Python依赖均已满足，跳过安装")

        # 4. 最后复检
        _log("正在执行修复后复检...")
        final_check = self.check_environment(log_callback=None)
        if final_check["missing"]:
            _log(f"❌ 修复后复检仍失败: {len(final_check['missing'])} 项缺失")
            return False, []
            
        return True, []
