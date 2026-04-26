import os
import winsound
from plyer import notification

class Notifier:
    """系统通知工具类"""
    
    @staticmethod
    def notify(title, message, app_name="云端训练助手"):
        """发送桌面通知"""
        try:
            notification.notify(
                title=title,
                message=message,
                app_name=app_name,
                timeout=10
            )
        except Exception as e:
            print(f"发送通知失败: {e}")

    @staticmethod
    def play_sound(sound_type="success"):
        """播放系统提示音"""
        try:
            if sound_type == "success":
                # 简单的成功音效
                winsound.Beep(1000, 200)
                winsound.Beep(1200, 300)
            elif sound_type == "error":
                # 错误音效
                winsound.MessageBeep(winsound.MB_ICONHAND)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
