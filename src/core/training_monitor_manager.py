import csv
import io
import os
from datetime import datetime


class TrainingMonitorManager:
    """训练监控数据管理：远程 results.csv 获取与 Loss 序列解析"""

    def __init__(self, server_manager):
        self.server_manager = server_manager
        self._session_dataset_path = ""
        self._session_model_name = ""
        self._session_start_ts = None
        self._locked_results_path = ""

    def start_session(self, remote_dataset_path, model_name, start_ts=None):
        """启动一次训练监控会话，锁定数据源范围，避免读取历史训练结果。"""
        self._session_dataset_path = (remote_dataset_path or "").strip() or "/root/yolo_dataset"
        self._session_model_name = (model_name or "").strip()
        try:
            self._session_start_ts = float(start_ts) if start_ts is not None else None
        except Exception:
            self._session_start_ts = None
        self._locked_results_path = ""

    def end_session(self):
        self._session_dataset_path = ""
        self._session_model_name = ""
        self._session_start_ts = None
        self._locked_results_path = ""

    def _parse_loss_csv(self, csv_content):
        if not csv_content or not csv_content.strip():
            return None

        reader = csv.reader(io.StringIO(csv_content.strip()))
        rows = []
        for row in reader:
            clean = [str(c).strip() for c in row]
            if any(clean):
                rows.append(clean)
        if len(rows) <= 1:
            return None

        headers = [str(h).strip().lower() for h in rows[0]]

        def find_col(candidates, contains=None):
            for idx, key in enumerate(headers):
                if key in candidates:
                    return idx
            if contains:
                for idx, key in enumerate(headers):
                    if contains in key:
                        return idx
            return None

        epoch_idx = find_col(["epoch"])
        box_idx = find_col(["train/box_loss", "box_loss"], contains="box_loss")
        cls_idx = find_col(["train/cls_loss", "cls_loss"], contains="cls_loss")
        dfl_idx = find_col(["train/dfl_loss", "dfl_loss"], contains="dfl_loss")

        if epoch_idx is None:
            return None
        if box_idx is None and cls_idx is None and dfl_idx is None:
            return None

        def parse_float(row, col_idx):
            if col_idx is None:
                return float("nan")
            try:
                return float(str(row[col_idx]).strip())
            except Exception:
                return float("nan")

        epochs, box_loss, cls_loss, dfl_loss = [], [], [], []
        for row in rows[1:]:
            if len(row) < len(headers):
                row.extend([""] * (len(headers) - len(row)))
            try:
                ep = int(float(row[epoch_idx]))
            except Exception:
                continue
            epochs.append(ep)
            box_loss.append(parse_float(row, box_idx))
            cls_loss.append(parse_float(row, cls_idx))
            dfl_loss.append(parse_float(row, dfl_idx))

        if not epochs:
            return None

        return {
            "epochs": epochs,
            "box_loss": box_loss,
            "cls_loss": cls_loss,
            "dfl_loss": dfl_loss,
        }

    def _build_preferred_results_path(self, dataset_path, model_name):
        if not model_name:
            return ""
        return f"{dataset_path}/runs/train/{model_name}/results.csv"

    def _get_remote_mtime(self, remote_file):
        if not remote_file:
            return None
        ok, output = self.server_manager.execute_command(f"stat -c %Y '{remote_file}' 2>/dev/null")
        if not ok or not output:
            return None
        try:
            return float(str(output).strip().splitlines()[-1])
        except Exception:
            return None

    def _is_fresh_enough(self, mtime):
        if self._session_start_ts is None:
            return True
        if mtime is None:
            return False
        # 允许少量时钟偏差
        return mtime >= (self._session_start_ts - 2.0)

    def _read_and_parse(self, results_path):
        ok, content = self.server_manager.execute_command(f"cat '{results_path}' 2>/dev/null")
        if not ok or not content or not content.strip():
            return None
        parsed = self._parse_loss_csv(content)
        if not parsed:
            return None
        parsed["raw_csv"] = content
        parsed["source_path"] = results_path
        return parsed

    def get_loss_series_by_results_path(self, results_path):
        """按指定 results.csv 路径读取 Loss 序列。"""
        path = (results_path or "").strip()
        if not path:
            return None
        return self._read_and_parse(path)

    def _find_latest_results(self, dataset_path):
        find_cmd = (
            f"find '{dataset_path}/runs' -name 'results.csv' "
            "-printf '%T@ %p\\n' 2>/dev/null | sort -nr | head -n 1"
        )
        ok_f, latest_line = self.server_manager.execute_command(find_cmd)
        if not ok_f or not latest_line or not latest_line.strip():
            return None, None
        line = latest_line.strip().splitlines()[-1].strip()
        parts = line.split(" ", 1)
        if len(parts) != 2:
            return None, None
        ts_text, path = parts[0].strip(), parts[1].strip()
        try:
            mtime = float(ts_text)
        except Exception:
            mtime = None
        return path, mtime

    def list_history_runs(self, remote_dataset_path=None, limit=200):
        """列出历史训练 results.csv（按更新时间倒序）。"""
        dataset_path = (remote_dataset_path or self._session_dataset_path or "").strip() or "/root/yolo_dataset"
        try:
            max_count = max(1, int(limit))
        except Exception:
            max_count = 200

        # 优化搜索：先在指定数据集目录下找，如果没有，尝试在当前连接的根目录或常用位置找
        # 使用更稳健的 find 命令，支持多种 YOLO 目录结构
        search_paths = [dataset_path, ".", "~"]
        unique_paths = []
        for p in search_paths:
            if p and p not in unique_paths:
                unique_paths.append(p)
        
        path_args = " ".join([f"'{p}/runs'" for p in unique_paths])
        
        # 尝试搜索所有可能的 runs 目录下的 results.csv
        cmd = (
            f"find {path_args} -name 'results.csv' "
            "-printf '%T@|%h|%p\\n' 2>/dev/null | sort -t'|' -nr -k1,1 "
            f"| head -n {max_count}"
        )
        ok, output = self.server_manager.execute_command(cmd)
        if not ok or not output or not output.strip():
            return []

        rows = []
        for line in str(output).splitlines():
            text = str(line).strip()
            if not text:
                continue
            parts = text.split("|", 2)
            if len(parts) != 3:
                continue
            ts_text, run_dir, results_path = parts[0].strip(), parts[1].strip(), parts[2].strip()
            try:
                mtime = float(ts_text)
            except Exception:
                mtime = None
            if mtime is not None:
                time_text = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_text = "--"
            rows.append(
                {
                    "run_name": os.path.basename(run_dir) or run_dir,
                    "run_dir": run_dir,
                    "results_path": results_path,
                    "mtime": mtime,
                    "mtime_text": time_text,
                }
            )
        return rows

    def get_loss_series(self, remote_dataset_path=None, model_name=None):
        """读取并解析 Loss 序列，返回结构化数据和原始CSV内容"""
        dataset_path = (remote_dataset_path or self._session_dataset_path or "").strip() or "/root/yolo_dataset"
        model = (model_name or self._session_model_name or "").strip()
        results_path = self._build_preferred_results_path(dataset_path, model)

        # 0) 会话锁定路径优先（防止不同 run 切换导致“跳回旧曲线”）
        if self._locked_results_path:
            parsed_locked = self._read_and_parse(self._locked_results_path)
            if parsed_locked:
                return parsed_locked

        # 1) 优先读取推导路径
        if results_path:
            preferred_mtime = self._get_remote_mtime(results_path)
            if self._is_fresh_enough(preferred_mtime):
                parsed = self._read_and_parse(results_path)
            else:
                parsed = None
            if parsed:
                self._locked_results_path = results_path
                return parsed

        # 2) 回退：搜索最新 results.csv
        latest, latest_mtime = self._find_latest_results(dataset_path)
        if latest and self._is_fresh_enough(latest_mtime):
            parsed = self._read_and_parse(latest)
            if parsed:
                self._locked_results_path = latest
                return parsed

        return None
