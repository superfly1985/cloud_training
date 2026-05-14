import os
import yaml
import time
import json
import shlex
from datetime import datetime


class ModelManager:
    """模型下载与转换管理"""

    def __init__(self, config_manager, server_manager):
        self.config_manager = config_manager
        self.server_manager = server_manager

    def _remote_base(self):
        return self.config_manager.dataset_config.get("remote_path", "/root/yolo_dataset")

    def _candidate_search_roots(self):
        base = self._remote_base().rstrip("/")
        roots = [
            "/root/runs",
            "/root/runs/train",
            f"{base}/runs",
            f"{base}/runs/train",
        ]
        unique = []
        seen = set()
        for r in roots:
            rr = str(r).strip()
            if not rr or rr in seen:
                continue
            seen.add(rr)
            unique.append(rr)
        return unique

    def _model_profile(self, model_name):
        import re
        name = str(model_name).lower()
        match = re.search(r'yolov\d+([a-z])', name)
        scale = match.group(1) if match else 's'
        if scale in ['c', 'b']:
            scale = 'm'
        if scale == 'e':
            scale = 'l'
        if scale not in ['n', 's', 'm', 'l', 'x']:
            scale = 's'
        return scale

    def _format_bytes_text(self, size_bytes):
        value = float(max(0, size_bytes))
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        while value >= 1024 and idx < len(units) - 1:
            value /= 1024.0
            idx += 1
        return f"{value:.1f}{units[idx]}"

    def query_all_models(self):
        """仅扫描训练产物目录，快速查询服务器模型文件。"""
        model_info = []
        search_roots = self._candidate_search_roots()
        if not search_roots:
            return model_info

        roots_cmd = " ".join(self._quote(p) for p in search_roots)
        # 仅扫描 runs 训练产物目录，限制深度并优先匹配常见产物扩展名
        cmd = (
            f"for d in {roots_cmd}; do "
            "if [ -d \"$d\" ]; then "
            "find \"$d\" -maxdepth 6 -type f \\( "
            "-name '*.pt' -o -name '*.onnx' -o -name '*.tflite' -o -name '*.zip' "
            "\\) -printf '%T@|%s|%p\\n' 2>/dev/null; "
            "fi; "
            "done | sort -t'|' -k1,1nr"
        )

        success, output = self.server_manager.execute_command(cmd)
        if not success or not output:
            return model_info

        sftp = self.server_manager.get_sftp()
        args_cache = {}

        try:
            for line in output.splitlines():
                line = line.strip()
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 2)
                if len(parts) != 3:
                    continue
                mtime_text, size_text, file_path = parts
                
                try:
                    mtime = float(mtime_text)
                except Exception:
                    mtime = 0.0
                try:
                    size_bytes = int(float(size_text))
                except Exception:
                    size_bytes = 0
                    
                parent_dir = os.path.dirname(file_path)
                if os.path.basename(parent_dir) == 'weights':
                    run_root = os.path.dirname(parent_dir)
                else:
                    run_root = parent_dir

                run_dir = os.path.basename(run_root.rstrip('/')) or '-'
                args_path = f"{run_root}/args.yaml"
                args_data = args_cache.get(run_root)
                if args_data is None:
                    args_data = {}
                    if sftp:
                        try:
                            with sftp.open(args_path, 'r') as rf:
                                raw = rf.read()
                            if isinstance(raw, bytes):
                                raw = raw.decode('utf-8', errors='ignore')
                            parsed = yaml.safe_load(raw) or {}
                            if isinstance(parsed, dict):
                                args_data = parsed
                        except Exception:
                            args_data = {}
                    args_cache[run_root] = args_data
                
                image_size = args_data.get('imgsz', args_data.get('img_size', '-'))
                base_model_raw = args_data.get('model', '-')
                base_model_name = os.path.basename(str(base_model_raw)) if base_model_raw not in (None, '') else '-'
                model_scale = self._model_profile(base_model_name).upper() if base_model_name != '-' else '-'
                base_model_display = f"{base_model_name} ({model_scale})" if base_model_name != '-' else '-'
                ext = os.path.splitext(file_path)[1].lower()
                
                model_info.append({
                    'name': os.path.basename(file_path) or 'best.pt',
                    'path': file_path,
                    'ext': ext,
                    'size': self._format_bytes_text(size_bytes),
                    'size_bytes': size_bytes,
                    'date': datetime.fromtimestamp(max(0.0, mtime)).strftime("%Y-%m-%d %H:%M:%S"),
                    'mtime': mtime,
                    'run_dir': run_dir,
                    'image_size': image_size,
                    'base_model': base_model_display,
                    'base_model_name': base_model_name,
                    'model_scale': model_scale,
                    'epochs': args_data.get('epochs', '-'),
                    'batch': args_data.get('batch', '-'),
                    'lr0': args_data.get('lr0', args_data.get('lr', '-')),
                    'patience': args_data.get('patience', '-'),
                    'optimizer': args_data.get('optimizer', '-')
                })
            
            model_info.sort(key=lambda x: float(x.get('mtime') or 0.0), reverse=True)
            return model_info
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass

    def remove_models(self, remote_paths):
        """批量删除模型文件。"""
        paths = [p for p in (remote_paths or []) if str(p).strip()]
        if not paths:
            return False, "未提供可删除文件"
        quoted = " ".join(self._quote(p) for p in paths)
        cmd = f"rm -f {quoted}"
        ok, out = self.server_manager.execute_command(cmd, timeout=120)
        if not ok:
            return False, out or "删除失败"
        return True, f"已删除 {len(paths)} 个文件"

    def find_latest_best_model(self):
        base = self._remote_base()
        # 同时搜索 /root/runs 和 数据集目录下的 runs
        cmd = (
            f"find /root/runs {base}/runs -type f -name best.pt 2>/dev/null "
            f"| xargs -r ls -t | head -n 1"
        )
        success, out = self.server_manager.execute_command(cmd, timeout=40)
        if not success or not out.strip():
            return False, "未找到 best.pt", ""
        return True, "找到模型", out.strip()

    def download_latest_best_model(self, local_dir):
        ok, msg, remote_model = self.find_latest_best_model()
        if not ok:
            return False, msg, ""
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"best_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt")
        success, out = self.server_manager.download_file(remote_model, local_path)
        if not success:
            return False, out, ""
        return True, f"下载完成: {local_path}", local_path

    def _quote(self, text):
        return shlex.quote(str(text))

    def _extract_json_between_markers(self, text, begin, end):
        data = str(text or "")
        s = data.find(begin)
        e = data.find(end, s + len(begin)) if s != -1 else -1
        if s == -1 or e == -1:
            return None
        body = data[s + len(begin):e].strip()
        if not body:
            return None
        try:
            return json.loads(body)
        except Exception:
            return None

    def _discover_tflite_outputs(self, python_cmd, remote_model):
        discover_script = (
            "import os, glob, json\n"
            f"best_pt = {remote_model!r}\n"
            "model_stem = os.path.splitext(os.path.basename(best_pt))[0]\n"
            "out_dir = os.path.dirname(best_pt) or '/root'\n"
            "saved_model_dir = os.path.splitext(best_pt)[0] + '_saved_model'\n"
            "files = sorted(glob.glob(os.path.join(saved_model_dir, '*.tflite')))\n"
            "files = [f for f in files if model_stem in os.path.basename(f)]\n"
            "if not files:\n"
            "    files = sorted(glob.glob(os.path.join(out_dir, '*_saved_model', '*.tflite')))\n"
            "    files = [f for f in files if model_stem in os.path.basename(f)]\n"
            "result = {'tflite': '', 'tflite_fp32': '', 'tflite_fp16': ''}\n"
            "for fp in files:\n"
            "    low = os.path.basename(fp).lower()\n"
            "    if 'float16' in low and not result['tflite_fp16']:\n"
            "        result['tflite_fp16'] = fp\n"
            "    elif not result['tflite_fp32']:\n"
            "        result['tflite_fp32'] = fp\n"
            "if result['tflite_fp32']:\n"
            "    result['tflite'] = result['tflite_fp32']\n"
            "print(json.dumps(result, ensure_ascii=False))\n"
        )
        cmd = f"{python_cmd} - <<'PY'\n{discover_script}PY"
        ok, out = self.server_manager.execute_command(cmd, timeout=50)
        if not ok or not out:
            return {}
        line = out.strip().splitlines()[-1]
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return {}

    def _ensure_canonical_tflite_name(self, python_cmd, remote_model, tflite_path):
        """将导出的 tflite 统一落在原模型目录，且与原模型同名仅改扩展名（保留 fp32/fp16 标记）。"""
        if not tflite_path:
            return False, ""
        normalize_script = (
            "import os, shutil, json\n"
            f"src = {tflite_path!r}\n"
            f"model_path = {remote_model!r}\n"
            "src_name = os.path.basename(src)\n"
            "suffix = ''\n"
            "if '_fp32.tflite' in src_name:\n"
            "    suffix = '_fp32'\n"
            "elif '_fp16.tflite' in src_name:\n"
            "    suffix = '_fp16'\n"
            "dst = os.path.splitext(model_path)[0] + suffix + '.tflite'\n"
            "ret = {'ok': False, 'path': dst, 'error': ''}\n"
            "try:\n"
            "    if not os.path.isfile(src):\n"
            "        raise FileNotFoundError(f'未找到导出文件: {src}')\n"
            "    if os.path.abspath(src) != os.path.abspath(dst):\n"
            "        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)\n"
            "        shutil.copy2(src, dst)\n"
            "    ret['ok'] = True\n"
            "except Exception as e:\n"
            "    ret['error'] = str(e)\n"
            "print(json.dumps(ret, ensure_ascii=False))\n"
        )
        cmd = f"{python_cmd} - <<'PY'\n{normalize_script}PY"
        ok, out = self.server_manager.execute_command(cmd, timeout=60)
        if not ok or not out.strip():
            return False, ""
        try:
            obj = json.loads(out.strip().splitlines()[-1])
        except Exception:
            return False, ""
        if isinstance(obj, dict) and obj.get("ok"):
            return True, str(obj.get("path", "")).strip()
        return False, ""

    def convert_remote_model_to_tflite(self, remote_model, python_cmd, log_callback=None, tflite_format="fp32"):
        def _log(msg):
            if callable(log_callback):
                log_callback(msg)

        if not python_cmd:
            return False, "未指定可用的转换Python解释器"

        imgsz = int(self.config_manager.training_config.get("image_size", 640) or 640)
        quoted_model = self._quote(remote_model)
        remote_base = self._remote_base()
        model_dir = os.path.dirname(remote_model) or "/root"
        primary_data_yaml = f"{remote_base}/dataset.yaml"

        find_yaml_script = (
            "import os, yaml, json\n"
            f"model_dir = {model_dir!r}\n"
            f"primary = {primary_data_yaml!r}\n"
            "result = {'path': primary}\n"
            "def has_nc_names(fp):\n"
            "    try:\n"
            "        with open(fp, 'r', encoding='utf-8') as f:\n"
            "            d = yaml.safe_load(f) or {}\n"
            "            return 'nc' in d and 'names' in d\n"
            "    except:\n"
            "        return False\n"
            "if os.path.isfile(primary) and has_nc_names(primary):\n"
            "    result['path'] = primary\n"
            "else:\n"
            "    for f in sorted(os.listdir(model_dir)):\n"
            "        if f.endswith('.yaml') or f.endswith('.yml'):\n"
            "            fp = os.path.join(model_dir, f)\n"
            "            if has_nc_names(fp):\n"
            "                result['path'] = fp\n"
            "                break\n"
            "print('__YAML_FIND_RESULT__')\n"
            "print(json.dumps(result))\n"
            "print('__YAML_FIND_RESULT_END__')\n"
        )
        find_yaml_cmd = f"{python_cmd} - <<'PY'\n{find_yaml_script}PY"
        ok_find, out_find = self.server_manager.execute_command(find_yaml_cmd, timeout=15)
        data_yaml_path = primary_data_yaml
        if ok_find:
            import json as _json
            marker_start = "__YAML_FIND_RESULT__"
            marker_end = "__YAML_FIND_RESULT_END__"
            if marker_start in out_find and marker_end in out_find:
                try:
                    json_str = out_find.split(marker_start, 1)[1].split(marker_end, 1)[0].strip()
                    find_result = _json.loads(json_str)
                    if find_result.get("path"):
                        data_yaml_path = find_result["path"]
                except Exception:
                    pass

        # 1) 转换前门禁：文件存在 + ultralytics + YOLO 导入
        preflight_script = (
            "import os, json\n"
            f"best_pt = {remote_model!r}\n"
            "result = {'ok': False, 'error': '', 'ultralytics_version': ''}\n"
            "try:\n"
            "    if not os.path.isfile(best_pt):\n"
            "        raise FileNotFoundError(f'best.pt不存在: {best_pt}')\n"
            "    import ultralytics\n"
            "    from ultralytics import YOLO\n"
            "    _ = YOLO\n"
            "    result['ok'] = True\n"
            "    result['ultralytics_version'] = getattr(ultralytics, '__version__', 'unknown')\n"
            "except Exception as e:\n"
            "    result['error'] = str(e)\n"
            "print('__TFLITE_PREFLIGHT_JSON_BEGIN__')\n"
            "print(json.dumps(result, ensure_ascii=False))\n"
            "print('__TFLITE_PREFLIGHT_JSON_END__')\n"
        )
        preflight_cmd = f"{python_cmd} - <<'PY'\n{preflight_script}PY"
        ok_pre, out_pre = self.server_manager.execute_command(preflight_cmd, timeout=40)
        pre_obj = self._extract_json_between_markers(
            out_pre, "__TFLITE_PREFLIGHT_JSON_BEGIN__", "__TFLITE_PREFLIGHT_JSON_END__"
        )
        if (not ok_pre) or (not isinstance(pre_obj, dict)) or (not pre_obj.get("ok")):
            detail = ""
            if isinstance(pre_obj, dict):
                detail = str(pre_obj.get("error", "")).strip()
            if not detail:
                detail = str(out_pre or "").strip()[-400:] or "门禁检查未通过"
            return False, f"转换前检查失败: {detail}"
        _log(f"转换门禁通过: ultralytics {pre_obj.get('ultralytics_version', 'unknown')}")

        # 2) 主路径：一次导出生成 fp16+fp32，清理中间产物
        native_script = (
            "import glob, json, os, traceback\n"
            "from ultralytics import YOLO\n"
            "import ultralytics\n"
            f"best_pt = {remote_model!r}\n"
            f"imgsz = {imgsz}\n"
            f"data_yaml = {data_yaml_path!r}\n"
            "result = {'status':'failed','error_msg':'','outputs':{},'logs':{'ultralytics_version':getattr(ultralytics,'__version__','unknown')}}\n"
            "try:\n"
            "    model = YOLO(best_pt)\n"
            "    model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=True, nms=True, data=data_yaml)\n"
            "    model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=False, nms=True, data=data_yaml)\n"
            "    model_stem = os.path.splitext(os.path.basename(best_pt))[0]\n"
            "    out_dir = os.path.dirname(best_pt) or '/root'\n"
            "    saved_model_dir = os.path.splitext(best_pt)[0] + '_saved_model'\n"
            "    fp32_file = ''\n"
            "    fp16_file = ''\n"
            "    for fp in sorted(glob.glob(os.path.join(saved_model_dir, '*.tflite'))):\n"
            "        bn = os.path.basename(fp)\n"
            "        if 'float32' in bn and model_stem in bn:\n"
            "            fp32_file = fp\n"
            "        elif 'float16' in bn and model_stem in bn:\n"
            "            fp16_file = fp\n"
            "    if not fp32_file:\n"
            "        for fp in sorted(glob.glob(os.path.join(saved_model_dir, '*.tflite'))):\n"
            "            if model_stem in os.path.basename(fp) and 'float16' not in os.path.basename(fp):\n"
            "                fp32_file = fp\n"
            "                break\n"
            "    if fp32_file:\n"
            "        new_fp32 = fp32_file.replace('.tflite', '_fp32.tflite') if not fp32_file.endswith('_fp32.tflite') else fp32_file\n"
            "        if fp32_file != new_fp32 and os.path.exists(fp32_file):\n"
            "            os.rename(fp32_file, new_fp32)\n"
            "            fp32_file = new_fp32\n"
            "    if fp16_file:\n"
            "        new_fp16 = fp16_file.replace('.tflite', '_fp16.tflite') if not fp16_file.endswith('_fp16.tflite') else fp16_file\n"
            "        if fp16_file != new_fp16 and os.path.exists(fp16_file):\n"
            "            os.rename(fp16_file, new_fp16)\n"
            "            fp16_file = new_fp16\n"
            "    onnx_file = os.path.splitext(best_pt)[0] + '.onnx'\n"
            "    if os.path.isfile(onnx_file):\n"
            "        os.remove(onnx_file)\n"
            "    other_tflites = []\n"
            "    for fp in glob.glob(os.path.join(saved_model_dir, '*.tflite')):\n"
            "        bn = os.path.basename(fp)\n"
            "        if fp != fp32_file and fp != fp16_file:\n"
            "            other_tflites.append(fp)\n"
            "    for fp in other_tflites:\n"
            "        try:\n"
            "            os.remove(fp)\n"
            "        except:\n"
            "            pass\n"
            "    result['outputs']['tflite_fp32'] = fp32_file\n"
            "    result['outputs']['tflite_fp16'] = fp16_file\n"
            "    result['outputs']['tflite'] = fp32_file\n"
            "    result['outputs']['cleaned_onnx'] = onnx_file\n"
            "    result['outputs']['cleaned_other'] = len(other_tflites)\n"
            "    result['status'] = 'success'\n"
            "except Exception as e:\n"
            "    result['error_msg'] = str(e)\n"
            "    result['logs']['traceback'] = traceback.format_exc()[-3000:]\n"
            "print('__TFLITE_RESULT_JSON_BEGIN__')\n"
            "print(json.dumps(result, ensure_ascii=False))\n"
            "print('__TFLITE_RESULT_JSON_END__')\n"
        )
        native_cmd = f"{python_cmd} - <<'PY'\n{native_script}PY"
        ok_native, out_native = self.server_manager.execute_command(native_cmd, timeout=3600)
        native_obj = self._extract_json_between_markers(
            out_native, "__TFLITE_RESULT_JSON_BEGIN__", "__TFLITE_RESULT_JSON_END__"
        )
        if ok_native and isinstance(native_obj, dict) and native_obj.get("status") == "success":
            outputs = native_obj.get("outputs", {}) or {}
            fp32 = outputs.get("tflite_fp32") or outputs.get("tflite")
            fp16 = outputs.get("tflite_fp16")
            model_dir_clean = os.path.dirname(remote_model) or "/root"
            clean_cmd = f"cd {self._quote(model_dir_clean)} && rm -f *.tflite 2>/dev/null || true"
            self.server_manager.execute_command(clean_cmd, timeout=10)
            msg = f"转换成功: fp32={fp32}" if fp32 else "转换成功"
            if fp16:
                msg += f" | fp16={fp16}"
            cleaned = outputs.get("cleaned_other", 0)
            if cleaned:
                msg += f" (清理{cleaned}个多余文件)"
            return True, msg

        # 3) 回退链：python -m ultralytics export
        _log("主转换路径失败，尝试回退: python -m ultralytics export")
        cmd_m = f"{python_cmd} -m ultralytics export model={quoted_model} format=tflite imgsz={imgsz} int8=False nms=True data={data_yaml_path}"
        ok_m, out_m = self.server_manager.execute_command(cmd_m, timeout=3600)
        discovered_m = self._discover_tflite_outputs(python_cmd, remote_model)
        if ok_m and discovered_m.get("tflite"):
            fp32 = discovered_m.get("tflite_fp32") or discovered_m.get("tflite")
            fp16 = discovered_m.get("tflite_fp16")
            model_dir_clean = os.path.dirname(remote_model) or "/root"
            clean_cmd = f"cd {self._quote(model_dir_clean)} && rm -f *.tflite 2>/dev/null || true"
            self.server_manager.execute_command(clean_cmd, timeout=10)
            msg = f"回退转换成功: fp32={fp32}" if fp32 else "回退转换成功"
            if fp16:
                msg += f" | fp16={fp16}"
            return True, msg

        # 4) 回退链：yolo export
        _log("继续回退: yolo export")
        cmd_yolo = f"yolo export model={quoted_model} format=tflite imgsz={imgsz} int8=False nms=True data={data_yaml_path}"
        ok_yolo, out_yolo = self.server_manager.execute_command(cmd_yolo, timeout=3600)
        discovered_yolo = self._discover_tflite_outputs(python_cmd, remote_model)
        if ok_yolo and discovered_yolo.get("tflite"):
            fp32 = discovered_yolo.get("tflite_fp32") or discovered_yolo.get("tflite")
            fp16 = discovered_yolo.get("tflite_fp16")
            model_dir_clean = os.path.dirname(remote_model) or "/root"
            clean_cmd = f"cd {self._quote(model_dir_clean)} && rm -f *.tflite 2>/dev/null || true"
            self.server_manager.execute_command(clean_cmd, timeout=10)
            msg = f"CLI回退成功: fp32={fp32}" if fp32 else "CLI回退成功"
            if fp16:
                msg += f" | fp16={fp16}"
            return True, msg

        native_err = ""
        if isinstance(native_obj, dict):
            native_err = str(native_obj.get("error_msg", "")).strip()
        if not native_err:
            native_err = str(out_native or "").strip()[-500:]
        m_err = str(out_m or "").strip()[-300:]
        y_err = str(out_yolo or "").strip()[-300:]
        return False, (
            f"转换失败。主路径: {native_err or '未知错误'} | "
            f"回退1: {m_err or '失败'} | 回退2: {y_err or '失败'}"
        )

    def convert_latest_best_to_tflite(self, python_cmd=None, log_callback=None):
        ok, msg, remote_model = self.find_latest_best_model()
        if not ok:
            return False, msg
        return self.convert_remote_model_to_tflite(remote_model, python_cmd, log_callback=log_callback)
