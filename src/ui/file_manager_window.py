import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

class FileManagerWindow:
    """远程文件管理窗口 UI 类"""
    def __init__(self, parent, file_manager, initial_path="/root/yolo_dataset", log_callback=None):
        self.parent = parent
        self.file_manager = file_manager
        self.log_callback = log_callback
        
        self.win = tk.Toplevel(parent)
        self.win.title("远程文件管理")
        self.win.geometry("720x480")
        
        self._create_ui(initial_path)
        self.refresh()

    def _create_ui(self, initial_path):
        top = ttk.Frame(self.win, padding=8)
        top.pack(fill=tk.X)
        
        self.path_var = tk.StringVar(value=initial_path)
        ttk.Label(top, text="远程路径:").pack(side=tk.LEFT)
        
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        
        self.btn_refresh = ttk.Button(top, text="刷新", command=self.refresh)
        self.btn_refresh.pack(side=tk.LEFT, padx=4)
        
        self.btn_delete = ttk.Button(top, text="删除选中", bootstyle="danger", command=self.delete_selected)
        self.btn_delete.pack(side=tk.LEFT)

        cols = ("name", "type", "size")
        self.tree = ttk.Treeview(self.win, columns=cols, show="headings")
        self.tree.heading("name", text="名称")
        self.tree.heading("type", text="类型")
        self.tree.heading("size", text="大小(Byte)")
        self.tree.column("name", width=420, anchor=tk.W)
        self.tree.column("type", width=80, anchor=tk.W)
        self.tree.column("size", width=120, anchor=tk.E)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def exists(self):
        """判断窗口是否存在"""
        return self.win and self.win.winfo_exists()

    def lift(self):
        """将窗口置顶"""
        if self.exists():
            self.win.lift()

    def refresh(self):
        remote_dir = self.path_var.get().strip() or "/"
        ok, msg, items = self.file_manager.list_dir(remote_dir)
        
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        if not ok:
            if self.log_callback:
                self.log_callback(f"文件列表失败: {msg}")
            return
            
        for item in items:
            item_type = "目录" if item["is_dir"] else "文件"
            self.tree.insert("", tk.END, values=(item["name"], item_type, item["size"]))

    def delete_selected(self):
        cur = self.tree.focus()
        if not cur:
            return
            
        values = self.tree.item(cur, "values")
        filename = values[0]
        remote_path = f"{self.path_var.get().rstrip('/')}/{filename}"
        
        if not messagebox.askyesno("确认", f"确认删除？\n{remote_path}", parent=self.win):
            return
            
        ok, msg = self.file_manager.delete_path(remote_path)
        if self.log_callback:
            self.log_callback("删除成功" if ok else f"删除失败: {msg}")
        self.refresh()

    def lift(self):
        self.win.lift()

    def exists(self):
        return self.win.winfo_exists()
