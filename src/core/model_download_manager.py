import os
import time


class ModelDownloadManager:
    """模型下载业务管理：批量下载、重名处理、进度回调"""

    def __init__(self, server_manager):
        self.server_manager = server_manager

    def _build_local_path(self, local_dir, model_name):
        path = os.path.join(local_dir, model_name)
        if os.path.exists(path):
            name, ext = os.path.splitext(model_name)
            path = os.path.join(local_dir, f"{name}_{int(time.time())}{ext}")
        return path

    def _format_speed(self, speed_bps):
        speed = float(max(0.0, speed_bps))
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        idx = 0
        while speed >= 1024 and idx < len(units) - 1:
            speed /= 1024.0
            idx += 1
        return f"{speed:.1f} {units[idx]}"

    def download_models(self, models, local_dir, progress_callback=None):
        """
        progress_callback(event: dict)
        event keys:
          - type: start/item/finish
          - index/total/name/success/error/local_path/progress/success_count/fail_count
        """
        total = len(models or [])
        success_count = 0
        fail_count = 0

        if progress_callback:
            progress_callback({"type": "start", "total": total})

        for i, model in enumerate(models or []):
            name = model.get("name", "unknown")
            remote_path = model.get("path", "")
            local_path = self._build_local_path(local_dir, name)
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

            if progress_callback:
                progress_callback({
                    "type": "item",
                    "stage": "downloading",
                    "index": i + 1,
                    "total": total,
                    "name": name,
                    "progress": ((i + 1) / total) * 100 if total else 100,
                })

            ok, out = self._download_single_model(
                remote_path=remote_path,
                local_path=local_path,
                item_index=i + 1,
                total_items=total,
                name=name,
                progress_callback=progress_callback,
            )
            if ok:
                success_count += 1
            else:
                fail_count += 1

            if progress_callback:
                progress_callback({
                    "type": "item",
                    "stage": "finished",
                    "index": i + 1,
                    "total": total,
                    "name": name,
                    "success": ok,
                    "error": out if not ok else "",
                    "local_path": local_path,
                    "progress": ((i + 1) / total) * 100 if total else 100,
                })

        summary = {
            "type": "finish",
            "total": total,
            "success_count": success_count,
            "fail_count": fail_count,
        }
        if progress_callback:
            progress_callback(summary)
        return summary

    def _download_single_model(self, remote_path, local_path, item_index, total_items, name, progress_callback=None):
        sftp = self.server_manager.get_sftp()
        if not sftp:
            return False, "SFTP连接不可用"

        start_ts = time.time()
        last_emit = [start_ts]
        last_bytes = [0]
        total_size = [0]

        try:
            try:
                total_size[0] = int(sftp.stat(remote_path).st_size)
            except Exception:
                total_size[0] = 0

            def _cb(transferred, total):
                total_size[0] = int(total or total_size[0] or 0)
                now = time.time()
                delta_t = max(1e-6, now - last_emit[0])
                if (now - last_emit[0]) < 0.25 and transferred < (total_size[0] or 0):
                    return
                delta_b = max(0, int(transferred) - int(last_bytes[0]))
                speed_bps = delta_b / delta_t if delta_t > 0 else 0.0
                last_emit[0] = now
                last_bytes[0] = int(transferred)

                file_percent = (float(transferred) / float(total_size[0]) * 100.0) if total_size[0] > 0 else 0.0
                base_percent = ((item_index - 1) / total_items) * 100.0 if total_items else 0.0
                weighted = base_percent + (file_percent / total_items if total_items else file_percent)

                if progress_callback:
                    progress_callback({
                        "type": "item",
                        "stage": "downloading",
                        "index": item_index,
                        "total": total_items,
                        "name": name,
                        "transferred": int(transferred),
                        "total_size": int(total_size[0]),
                        "file_progress": file_percent,
                        "progress": weighted,
                        "speed_bps": speed_bps,
                        "speed_text": self._format_speed(speed_bps),
                    })

            sftp.get(remote_path, local_path, callback=_cb)
            # 收尾再推一次 100%
            elapsed = max(1e-6, time.time() - start_ts)
            total_b = int(total_size[0] or os.path.getsize(local_path))
            avg_bps = total_b / elapsed
            if progress_callback:
                progress_callback({
                    "type": "item",
                    "stage": "downloading",
                    "index": item_index,
                    "total": total_items,
                    "name": name,
                    "transferred": total_b,
                    "total_size": total_b,
                    "file_progress": 100.0,
                    "progress": (item_index / total_items) * 100 if total_items else 100,
                    "speed_bps": avg_bps,
                    "speed_text": self._format_speed(avg_bps),
                })
            return True, "下载成功"
        except Exception as e:
            return False, str(e)
        finally:
            try:
                sftp.close()
            except Exception:
                pass
