import json
import os
import re
import threading
import time


class TrainingLogManager:
    """训练日志管理：实时提炼、折叠压缩、原始归档。"""

    def __init__(self, archive_dir="logs"):
        self.archive_dir = archive_dir
        self._lock = threading.Lock()
        self._raw_fp = None
        self._raw_path = ""
        self._session_id = ""
        self._detail_index = 0
        self._details = {}
        self._last_norm_line = None
        self._repeat_count = 0
        self._last_emit_time = {}
        self._recent_emit = {}
        self._epoch_header_seen = False
        self._line_max_len = 420
        self._throttle_seconds = 1.0
        self._dedupe_window_seconds = 1.5
        self._ansi_escape_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
        self._compact_space_re = re.compile(r"\s+")
        self._throttle_patterns = [
            re.compile(r"^\s*\d+/\d+\s"),        # batch 进度
            re.compile(r"^\s*Epoch\s+\d+"),      # epoch 明细
            re.compile(r".*it/s.*"),             # 速度统计
            re.compile(r".*GPU_mem.*"),          # ultralytics 表头/行
        ]

    def start_session(self, model_name="train"):
        with self._lock:
            self.close_session()
            safe_name = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fa5]+", "_", str(model_name or "train")).strip("_")
            if not safe_name:
                safe_name = "train"
            ts = time.strftime("%Y%m%d_%H%M%S")
            self._session_id = f"{safe_name}_{ts}"
            os.makedirs(self.archive_dir, exist_ok=True)
            self._raw_path = os.path.join(self.archive_dir, f"training_raw_{self._session_id}.log")
            self._raw_fp = open(self._raw_path, "a", encoding="utf-8")
            self._raw_fp.write(f"===== TRAIN SESSION {self._session_id} =====\n")
            self._raw_fp.flush()
            self._detail_index = 0
            self._details = {}
            self._last_norm_line = None
            self._repeat_count = 0
            self._last_emit_time = {}
            self._recent_emit = {}
            self._epoch_header_seen = False
            return self._raw_path

    def close_session(self):
        if self._raw_fp:
            try:
                self._raw_fp.flush()
                self._raw_fp.close()
            except Exception:
                pass
        self._raw_fp = None

    def get_raw_log_path(self):
        return self._raw_path

    def process_line(self, line):
        """输入原始日志行，返回可显示的提炼后日志列表。"""
        out = []
        raw_text = str(line).rstrip("\n")

        with self._lock:
            self._append_raw(raw_text)
            for text in self._normalize_chunks(raw_text):
                if not text:
                    continue

                # 优先处理重复行折叠（先刷折叠，再继续处理当前行）
                out.extend(self._handle_repeat(text))

                # JSON 瘦身（尤其是转换类超长输出）
                slim = self._slim_json_like(text)
                if slim:
                    for s in slim:
                        if self._should_emit(s):
                            out.append(s)
                    continue

                # 结构化提炼（训练/验证摘要）
                structured = self._extract_compact_training_line(text)
                if structured:
                    if self._should_emit(structured):
                        out.append(structured)
                    continue

                # 跳过终端重绘类无效内容（表头去重、进度条细节）
                if self._is_noisy_terminal_line(text):
                    continue

                # 高频日志节流
                if self._should_throttle(text):
                    continue

                # 长行截断与详情引用
                compact = self._truncate_with_detail(text)
                if self._should_emit(compact):
                    out.append(compact)
            return out

    def flush(self):
        """结束前刷出重复折叠计数。"""
        with self._lock:
            if self._repeat_count > 0 and self._last_norm_line:
                msg = f"[折叠] 上一条重复 {self._repeat_count} 次"
                self._repeat_count = 0
                return [msg]
            return []

    def _append_raw(self, text):
        if self._raw_fp:
            try:
                self._raw_fp.write(text + "\n")
                self._raw_fp.flush()
            except Exception:
                pass

    def _handle_repeat(self, text):
        norm = re.sub(r"\s+", " ", text.strip())
        if not norm:
            return []
        if self._last_norm_line is None:
            self._last_norm_line = norm
            return []
        if norm == self._last_norm_line:
            self._repeat_count += 1
            return []
        out = []
        if self._repeat_count > 0:
            out.append(f"[折叠] 上一条重复 {self._repeat_count} 次")
            self._repeat_count = 0
        self._last_norm_line = norm
        return out

    def _normalize_chunks(self, text):
        # 清理 ANSI 控制符与终端清行符
        s = text.replace("\x1b[K", "")
        s = self._ansi_escape_re.sub("", s)
        s = s.replace("\u2500", " ").replace("\u2501", " ")
        s = s.replace("\t", " ")

        # 对 \r 重绘输出仅保留最后有效段
        if "\r" in s:
            parts = [p.strip() for p in s.split("\r") if p.strip()]
            s = parts[-1] if parts else ""

        # 有时一行里会出现重复拼接，尝试去重一半
        s = self._dedupe_line_halves(s.strip())
        if not s:
            return []

        # 拆分多行后逐行处理
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        return lines

    def _dedupe_line_halves(self, text):
        tokens = text.split()
        if len(tokens) >= 8 and len(tokens) % 2 == 0:
            half = len(tokens) // 2
            if tokens[:half] == tokens[half:]:
                return " ".join(tokens[:half])
        return text

    def _should_throttle(self, text):
        now = time.time()
        for p in self._throttle_patterns:
            if p.match(text):
                key = p.pattern
                last_t = self._last_emit_time.get(key, 0)
                if now - last_t < self._throttle_seconds:
                    return True
                self._last_emit_time[key] = now
                return False
        return False

    def _should_emit(self, text):
        norm = self._compact_space_re.sub(" ", text.strip())
        if not norm:
            return False
        now = time.time()
        last = self._recent_emit.get(norm, 0.0)
        self._recent_emit[norm] = now
        # 清理旧记录，避免字典无限增长
        if len(self._recent_emit) > 300:
            cutoff = now - 15.0
            self._recent_emit = {k: v for k, v in self._recent_emit.items() if v >= cutoff}
        return (now - last) > self._dedupe_window_seconds

    def _is_noisy_terminal_line(self, text):
        line = text.strip()
        if not line:
            return True
        # 重复表头仅显示一次
        if "Epoch" in line and "GPU_mem" in line and "box_loss" in line:
            if self._epoch_header_seen:
                return True
            self._epoch_header_seen = True
            return False
        # 仅进度条/绘制符号的短线信息
        if re.search(r"\d+/\d+.*it/s", line) and "box_loss" not in line:
            return True
        return False

    def _extract_compact_training_line(self, text):
        line = self._compact_space_re.sub(" ", text.strip())
        if not line:
            return None

        # train 行（如: 7/60 3.71G 1.792 2.453 1.187 16 640: 100% 2/2 6.1it/s 0.3s）
        train_re = re.compile(
            r"^\s*(\d+/\d+)\s+([0-9.]+G)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+(\d+)\s+(\d+):.*?(?:(\d+)\s*/\s*(\d+))?"
        )
        m = train_re.search(line)
        if m:
            ep, gpu, box, cls, dfl, inst, size, b_cur, b_total = m.groups()
            batch_part = f" | batch {b_cur}/{b_total}" if b_cur and b_total else ""
            return f"[训练] Epoch {ep} | GPU {gpu} | box {box} cls {cls} dfl {dfl} | inst {inst} | img {size}{batch_part}"

        # val 行（如: all 12 12 0.00306 0.917 0.506 0.179）
        val_re = re.compile(
            r"^\s*all\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$"
        )
        v = val_re.search(line)
        if v:
            imgs, inst, p, r, map50, map95 = v.groups()
            return f"[验证] all imgs={imgs} inst={inst} | P={p} R={r} mAP50={map50} mAP50-95={map95}"

        return None

    def _slim_json_like(self, text):
        stripped = text.strip()
        json_obj = None

        # 场景1：整行是 JSON
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                json_obj = json.loads(stripped)
            except Exception:
                json_obj = None

        # 场景2：前缀 + JSON，如 "转换输出: {...}"
        if json_obj is None and "{" in stripped and "}" in stripped:
            prefix, _, possible = stripped.partition("{")
            possible_json = "{" + possible
            try:
                json_obj = json.loads(possible_json)
                stripped = prefix.strip()
            except Exception:
                json_obj = None

        if not isinstance(json_obj, dict):
            return None

        status = str(json_obj.get("status", "")).strip()
        error_code = str(json_obj.get("error_code", "")).strip()
        error_msg = str(json_obj.get("error_msg", "")).strip()
        outputs = json_obj.get("outputs", {})
        out_keys = list(outputs.keys()) if isinstance(outputs, dict) else []

        # logs 字段可能极长，折叠为详情
        logs_payload = json_obj.get("logs")
        detail_tag = ""
        if logs_payload:
            detail_id = self._store_detail(logs_payload)
            detail_tag = f" [详情#{detail_id}]"

        summary = []
        title = stripped if stripped else "结构化输出"
        if status:
            summary.append(f"{title}: status={status}")
        if error_code:
            summary[-1] = summary[-1] + f", code={error_code}" if summary else f"{title}: code={error_code}"
        if error_msg:
            summary.append(f"错误信息: {error_msg}")
        if out_keys:
            summary.append("产物: " + ", ".join(map(str, out_keys)))
        if detail_tag:
            summary.append(f"详细日志已折叠{detail_tag}")

        if not summary:
            summary = [self._truncate_with_detail(text)]
        return summary

    def _truncate_with_detail(self, text):
        if len(text) <= self._line_max_len:
            return text
        detail_id = self._store_detail(text)
        head = text[:220]
        tail = text[-120:]
        omitted = len(text) - 340
        return f"{head} ...[省略{omitted}字符]... {tail} [详情#{detail_id}]"

    def _store_detail(self, payload):
        self._detail_index += 1
        idx = self._detail_index
        try:
            if isinstance(payload, (dict, list)):
                content = json.dumps(payload, ensure_ascii=False)
            else:
                content = str(payload)
        except Exception:
            content = str(payload)
        self._details[idx] = content
        # 只保留最近 200 条详情，防止内存持续上涨
        if len(self._details) > 200:
            keys = sorted(self._details.keys())
            for k in keys[:-200]:
                self._details.pop(k, None)
        return idx
