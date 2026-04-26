import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import io

class ChartManager:
    """训练数据可视化管理类"""
    
    def __init__(self):
        self.fig, self.ax = plt.subplots(figsize=(5, 4), dpi=100)
        self.canvas = None
        self._setup_style()

    def _setup_style(self):
        plt.style.use('ggplot')
        self.ax.set_title("Training Loss")
        self.ax.set_xlabel("Epoch")
        self.ax.set_ylabel("Loss")

    def create_canvas(self, parent):
        """为 Tkinter 父容器创建画布"""
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        return self.canvas.get_tk_widget()

    def update_from_csv(self, csv_content):
        """从 CSV 内容更新图表"""
        try:
            df = pd.read_csv(io.StringIO(csv_content))
            if df.empty:
                return
            
            # 常见的 YOLO results.csv 列名（带空格或不带空格）
            df.columns = [c.strip() for c in df.columns]
            
            epoch_col = 'epoch'
            loss_cols = [c for c in df.columns if 'loss' in c.lower() and 'val' not in c.lower()]
            
            if epoch_col not in df.columns or not loss_cols:
                return

            self.ax.clear()
            for col in loss_cols:
                self.ax.plot(df[epoch_col], df[col], label=col)
            
            self.ax.legend()
            self.ax.set_title("Training Loss Trend")
            self.ax.set_xlabel("Epoch")
            self.ax.set_ylabel("Value")
            
            if self.canvas:
                self.canvas.draw()
        except Exception as e:
            print(f"更新图表失败: {e}")
