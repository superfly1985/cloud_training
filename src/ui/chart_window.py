import tkinter as tk
from tkinter import ttk
from src.core.chart_manager import ChartManager

class ChartWindow:
    """独立的图表监控窗口"""
    
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("训练实时监控")
        self.win.geometry("600x500")
        
        self.chart_manager = ChartManager()
        self._init_ui()
        
        # 记录窗口是否正在显示
        self.is_open = True
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_ui(self):
        self.main_frame = ttk.Frame(self.win, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 嵌入 Matplotlib 画布
        self.chart_widget = self.chart_manager.create_canvas(self.main_frame)
        self.chart_widget.pack(fill=tk.BOTH, expand=True)
        
        # 底部控制区
        ctrl_frame = ttk.Frame(self.main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(ctrl_frame, text="自动从服务器同步 results.csv 进行绘制").pack(side=tk.LEFT)
        ttk.Button(ctrl_frame, text="置顶", command=lambda: self.win.attributes("-topmost", True)).pack(side=tk.RIGHT)

    def update_data(self, csv_content):
        """外部调用更新数据"""
        if self.exists():
            self.chart_manager.update_from_csv(csv_content)

    def exists(self):
        return self.win and self.win.winfo_exists()

    def lift(self):
        if self.exists():
            self.win.lift()
            self.win.focus_force()

    def _on_close(self):
        self.is_open = False
        self.win.destroy()
