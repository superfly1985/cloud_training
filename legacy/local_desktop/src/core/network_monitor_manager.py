import re
import subprocess


class NetworkMonitorManager:
    """本地到远端的网络质量监控"""

    def measure_ping_loss(self, host):
        """返回 (ping_text, loss_text)"""
        if not host:
            return "--", "--"
        try:
            # 兼容 Windows 打包，添加 creationflags 隐藏命令行窗口
            startupinfo = None
            creationflags = 0
            import os
            if os.name == "nt":
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                
            completed = subprocess.run(
                ["ping", "-n", "4", "-w", "1000", host],
                capture_output=True,
                text=True,
                timeout=12,
                encoding="utf-8",
                errors="ignore",
                creationflags=creationflags
            )
            output = f"{completed.stdout}\n{completed.stderr}"
            loss_match = re.search(r"(\d+)\s*%\s*(?:loss|丢失)", output, re.IGNORECASE)
            loss_text = f"{loss_match.group(1)}%" if loss_match else "--"

            avg_match = re.search(r"(?:Average|平均)\s*[=:：]\s*(\d+)\s*ms", output, re.IGNORECASE)
            if avg_match:
                ping_text = f"{avg_match.group(1)}ms"
            else:
                values = re.findall(r"(\d+)\s*ms", output, re.IGNORECASE)
                ping_text = f"{values[-1]}ms" if values else "--"
            return ping_text, loss_text
        except Exception:
            return "--", "--"
