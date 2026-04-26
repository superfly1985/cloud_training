import re
import time
from datetime import datetime


class TrainingProgressManager:
    """训练进度解析与状态文本生成。"""

    def __init__(self):
        self.reset()

    def reset(self, total_epochs=None, start_time=None):
        self.start_time = float(start_time) if start_time else None
        self.total_epochs = self._safe_int(total_epochs)
        self.current_epoch = None
        self.batch_current = None
        self.batch_total = None
        self._ansi_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

    def update_from_log_line(self, line):
        text = self._normalize_text(line)
        if not text:
            return self._build_payload()

        # 1) 总轮次
        m_total = re.search(r"Starting training for\s+(\d+)\s+epochs", text, flags=re.IGNORECASE)
        if m_total:
            self.total_epochs = self._safe_int(m_total.group(1)) or self.total_epochs
        else:
            m_arg_total = re.search(r"epochs\s*=\s*(\d+)", text, flags=re.IGNORECASE)
            if m_arg_total:
                self.total_epochs = self._safe_int(m_arg_total.group(1)) or self.total_epochs

        # 2) epoch（兼容原始行与精简行）
        m_epoch = re.search(r"^\s*(\d+)\s*/\s*(\d+)\s+", text)
        if m_epoch:
            self.current_epoch = self._safe_int(m_epoch.group(1))
            self.total_epochs = self._safe_int(m_epoch.group(2)) or self.total_epochs
        else:
            m_epoch_compact = re.search(r"Epoch\s+(\d+)\s*/\s*(\d+)", text, flags=re.IGNORECASE)
            if m_epoch_compact:
                self.current_epoch = self._safe_int(m_epoch_compact.group(1))
                self.total_epochs = self._safe_int(m_epoch_compact.group(2)) or self.total_epochs

        # 3) 批次完成（兼容 tqdm 行）
        m_batch = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:\[|it/s|$)", text)
        if m_batch:
            b_cur = self._safe_int(m_batch.group(1))
            b_total = self._safe_int(m_batch.group(2))
            if b_cur is not None and b_total is not None and b_total > 0 and b_cur <= b_total:
                self.batch_current = b_cur
                self.batch_total = b_total

        return self._build_payload()

    def _build_payload(self):
        return {
            "status_text": self._build_status_text(),
            "batch_text": self._build_batch_text(),
            "duration_text": self._build_duration_text(),
            "eta_text": self._build_eta_text(),
        }

    def _build_status_text(self):
        if self.current_epoch is not None and self.total_epochs:
            return f"训练中: {self.current_epoch}/{self.total_epochs}"
        if self.current_epoch is not None:
            return f"训练中: {self.current_epoch}"
        return None

    def _build_batch_text(self):
        if self.batch_current is not None and self.batch_total:
            return f"批次完成: {self.batch_current}/{self.batch_total}"
        return "批次完成: --/--"

    def _build_duration_text(self):
        if not self.start_time:
            return "时长: 00:00:00"
        elapsed = max(0, int(time.time() - self.start_time))
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"时长: {h:02d}:{m:02d}:{s:02d}"

    def _build_eta_text(self):
        if not self.start_time or not self.current_epoch or not self.total_epochs or self.total_epochs <= 0:
            return "预计完成: --"
        progress = float(self.current_epoch) / float(self.total_epochs)
        if progress <= 0:
            return "预计完成: --"
        elapsed = max(0.0, time.time() - self.start_time)
        remain = max(0.0, elapsed * (1.0 / progress - 1.0))
        eta = datetime.fromtimestamp(time.time() + remain).strftime("%H:%M:%S")
        return f"预计完成: {eta}"

    def _normalize_text(self, line):
        s = str(line or "").strip()
        if not s:
            return ""
        s = s.replace("\x1b[K", "")
        s = self._ansi_re.sub("", s)
        if "\r" in s:
            parts = [p.strip() for p in s.split("\r") if p.strip()]
            s = parts[-1] if parts else ""
        return re.sub(r"\s+", " ", s).strip()

    def _safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return None
