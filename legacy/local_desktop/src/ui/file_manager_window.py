import tkinter as tk
from tkinter import messagebox
import posixpath
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
        self.win.transient(parent)
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.grab_set()
        self.win.focus_force()
        self._center_to_parent()
        self.win.after(0, self._center_to_parent)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._item_meta = {}
        
        self._create_ui(initial_path)
        self.refresh()

    def _center_to_parent(self):
        """将窗口默认居中到父窗口中心。"""
        self.parent.update_idletasks()
        self.win.update_idletasks()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        win_w = self.win.winfo_width() or self.win.winfo_reqwidth()
        win_h = self.win.winfo_height() or self.win.winfo_reqheight()
        x = parent_x + max(0, (parent_w - win_w) // 2)
        y = parent_y + max(0, (parent_h - win_h) // 2)
        self.win.geometry(f"+{x}+{y}")

    def _create_ui(self, initial_path):
        top = ttk.Frame(self.win, padding=8)
        top.pack(fill=tk.X)
        
        self.path_var = tk.StringVar(value=initial_path)
        ttk.Label(top, text="远程路径:").pack(side=tk.LEFT)
        
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        entry.bind("<Return>", lambda _e: self.refresh())
        self.path_entry = entry
        
        self.btn_root = ttk.Button(top, text="根目录", command=lambda: self._goto_path("/"))
        self.btn_root.pack(side=tk.LEFT, padx=4)

        self.btn_up = ttk.Button(top, text="上级", command=self._go_up)
        self.btn_up.pack(side=tk.LEFT, padx=4)

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
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _normalize_remote_path(self, remote_path):
        path = (remote_path or "").strip()
        if not path:
            return "/"
        if not path.startswith("/"):
            path = "/" + path
        return posixpath.normpath(path) or "/"

    def _join_remote_path(self, base, name):
        base_norm = self._normalize_remote_path(base)
        return self._normalize_remote_path(posixpath.join(base_norm, name))

    def _goto_path(self, remote_path):
        self.path_var.set(self._normalize_remote_path(remote_path))
        self.refresh()

    def _go_up(self):
        current = self._normalize_remote_path(self.path_var.get())
        if current == "/":
            return
        parent = posixpath.dirname(current.rstrip("/")) or "/"
        self._goto_path(parent)

    def _on_tree_double_click(self, _event):
        cur = self.tree.focus()
        if not cur:
            return
        meta = self._item_meta.get(cur)
        if not meta:
            return
        if meta.get("is_parent"):
            self._go_up()
            return
        if meta.get("is_dir"):
            self._goto_path(meta.get("path", "/"))

    def exists(self):
        """判断窗口是否存在"""
        return bool(self.win and self.win.winfo_exists())

    def lift(self):
        """将窗口置顶"""
        if self.exists():
            try:
                self.win.grab_set()
            except Exception:
                pass
            self.win.lift()
            self.win.focus_force()

    def refresh(self):
        remote_dir = self._normalize_remote_path(self.path_var.get())
        self.path_var.set(remote_dir)
        ok, msg, items = self.file_manager.list_dir(remote_dir)
        self._item_meta = {}
        
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        if not ok:
            if self.log_callback:
                self.log_callback(f"文件列表失败: {msg}")
            messagebox.showerror("错误", f"读取目录失败:\n{msg}", parent=self.win)
            return

        if remote_dir != "/":
            iid = self.tree.insert("", tk.END, values=("..", "目录", "-"))
            self._item_meta[iid] = {"is_parent": True, "is_dir": True, "path": posixpath.dirname(remote_dir) or "/"}

        for item in items:
            item_type = "目录" if item["is_dir"] else "文件"
            item_name = str(item.get("name", ""))
            iid = self.tree.insert("", tk.END, values=(item_name, item_type, item.get("size", 0)))
            self._item_meta[iid] = {
                "is_parent": False,
                "is_dir": bool(item.get("is_dir")),
                "path": self._join_remote_path(remote_dir, item_name),
            }

    def delete_selected(self):
        cur = self.tree.focus()
        if not cur:
            return
        meta = self._item_meta.get(cur)
        if not meta:
            return
        if meta.get("is_parent"):
            messagebox.showwarning("提示", "“..”为上级目录入口，不能删除。", parent=self.win)
            return
        remote_path = meta.get("path", "")
        if not remote_path:
            messagebox.showwarning("提示", "选中项缺少路径，无法删除。", parent=self.win)
            return
        
        if not messagebox.askyesno("确认", f"确认删除？\n{remote_path}", parent=self.win):
            return
            
        ok, msg = self.file_manager.delete_path(remote_path)
        if self.log_callback:
            self.log_callback("删除成功" if ok else f"删除失败: {msg}")
        self.refresh()

    def _on_close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        if self.exists():
            self.win.destroy()
