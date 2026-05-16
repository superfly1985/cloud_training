#!/usr/bin/env python3
"""
部署工具日志模块
支持时间戳（毫秒）、日志级别、模块名称
"""
import os
import sys
import time
import threading
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class DeployLogger:
    """部署工具专用日志记录器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, log_file=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, log_file=None):
        if self._initialized:
            return
            
        if log_file is None:
            # 默认日志文件路径：与 deploy_gui.py 同级目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            log_file = os.path.join(base_dir, "loog.txt")
        
        self.log_file = log_file
        self.file_lock = threading.Lock()
        self._initialized = True
        
        # 写入启动标记
        self._write_separator()
        self.info("DEPLOY", "日志系统初始化完成")
        self.info("DEPLOY", f"日志文件: {self.log_file}")
    
    def _get_timestamp(self):
        """获取带毫秒的时间戳"""
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
    
    def _format_message(self, level, module, message):
        """格式化日志消息"""
        timestamp = self._get_timestamp()
        return f"[{timestamp}] [{level.value:5}] [{module:12}] {message}"
    
    def _write_to_file(self, formatted_msg):
        """写入日志文件"""
        try:
            with self.file_lock:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(formatted_msg + "\n")
                    f.flush()
        except Exception as e:
            # 如果文件写入失败，输出到stderr
            print(f"[日志写入失败] {e}", file=sys.stderr)
    
    def _write_separator(self):
        """写入分隔线"""
        separator = "=" * 80
        self._write_to_file(f"\n{separator}")
        self._write_to_file(f"[{self._get_timestamp()}] 新的部署会话开始")
        self._write_to_file(f"{separator}")
    
    def log(self, level, module, message):
        """记录日志"""
        formatted = self._format_message(level, module, message)
        self._write_to_file(formatted)
        return formatted
    
    def debug(self, module, message):
        """DEBUG级别日志"""
        return self.log(LogLevel.DEBUG, module, message)
    
    def info(self, module, message):
        """INFO级别日志"""
        return self.log(LogLevel.INFO, module, message)
    
    def warn(self, module, message):
        """WARN级别日志"""
        return self.log(LogLevel.WARN, module, message)
    
    def error(self, module, message):
        """ERROR级别日志"""
        return self.log(LogLevel.ERROR, module, message)
    
    def log_callback(self, module):
        """生成可用于回调的日志函数"""
        def callback(message, level="INFO"):
            level_map = {
                "DEBUG": LogLevel.DEBUG,
                "INFO": LogLevel.INFO,
                "WARN": LogLevel.WARN,
                "WARNING": LogLevel.WARN,
                "ERROR": LogLevel.ERROR,
            }
            log_level = level_map.get(level.upper(), LogLevel.INFO)
            self.log(log_level, module, message)
        return callback


# 全局日志实例
logger = DeployLogger()


def get_logger():
    """获取日志记录器实例"""
    return logger
