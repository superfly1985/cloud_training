#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集配置可视化工具
简单的GUI界面，用于选择源文件路径、标注文件，并读取标注文件中的类别种类和映射关系
同时提供完整的YOLO数据集处理功能
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
from pathlib import Path
import sys
import threading
import subprocess
from datetime import datetime
import chardet

class DatasetConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("数据集配置与处理工具")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # 存储选择的路径和配置
        self.source_path = ""
        self.annotation_file = ""
        self.output_path = ""
        self.class_config = {}
        
        # 训练参数
        self.train_ratio = 0.7
        self.val_ratio = 0.2
        self.test_ratio = 0.1
        
        # 处理状态
        self.is_processing = False
        
        self.setup_ui()
    
    def safe_read_file(self, file_path):
        """安全读取文件，自动检测编码"""
        try:
            # 首先尝试检测文件编码
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            detected = chardet.detect(raw_data)
            detected_encoding = detected.get('encoding', 'utf-8') if detected else 'utf-8'
            
            # 尝试多种编码
            encodings_to_try = [
                'utf-8',
                detected_encoding,
                'gbk',
                'gb2312',
                'big5',
                'latin1',
                'cp1252'
            ]
            
            # 去重并保持顺序
            encodings_to_try = list(dict.fromkeys(encodings_to_try))
            
            for encoding in encodings_to_try:
                if encoding is None:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"✅ GUI成功使用编码: {encoding}")
                    return content
                except (UnicodeDecodeError, UnicodeError) as e:
                    print(f"❌ GUI编码 {encoding} 失败: {str(e)[:100]}")
                    continue
                except Exception as e:
                    print(f"❌ GUI读取文件时出错 ({encoding}): {str(e)[:100]}")
                    continue
            
            # 如果所有编码都失败，尝试忽略错误
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                print(f"⚠️  GUI使用UTF-8忽略错误模式读取成功")
                return content
            except Exception as e:
                print(f"❌ GUI最终读取失败: {str(e)}")
                return None
                
        except Exception as e:
            print(f"❌ GUI文件读取异常: {str(e)}")
            return None
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="数据集配置与处理工具", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 文件路径配置区域
        path_frame = ttk.LabelFrame(main_frame, text="文件路径配置", padding="10")
        path_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        path_frame.columnconfigure(1, weight=1)
        
        # 源文件目录选择
        ttk.Label(path_frame, text="源文件目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.source_path_var = tk.StringVar()
        source_entry = ttk.Entry(path_frame, textvariable=self.source_path_var, width=50)
        source_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(path_frame, text="浏览", command=self.select_source_directory).grid(row=0, column=2, padx=(5, 0), pady=5)
        
        # 标注文件选择
        ttk.Label(path_frame, text="标注文件:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.annotation_file_var = tk.StringVar()
        annotation_entry = ttk.Entry(path_frame, textvariable=self.annotation_file_var, width=50)
        annotation_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(path_frame, text="浏览", command=self.select_annotation_file).grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # 输出目录选择
        ttk.Label(path_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_path_var = tk.StringVar()
        self.output_path_var.set(r"d:\OneDrive\24.Visual AI\data\yolo_dataset")  # 默认路径
        output_entry = ttk.Entry(path_frame, textvariable=self.output_path_var, width=50)
        output_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(path_frame, text="浏览", command=self.select_output_directory).grid(row=2, column=2, padx=(5, 0), pady=5)
        
        # 训练参数配置区域
        param_frame = ttk.LabelFrame(main_frame, text="训练参数配置", padding="10")
        param_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 数据集分割比例
        ttk.Label(param_frame, text="训练集比例:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.train_ratio_var = tk.DoubleVar(value=0.7)
        train_scale = ttk.Scale(param_frame, from_=0.1, to=0.9, variable=self.train_ratio_var, orient=tk.HORIZONTAL, length=150)
        train_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.train_label = ttk.Label(param_frame, text="70%")
        self.train_label.grid(row=0, column=2, padx=5, pady=5)
        train_scale.configure(command=self.update_train_ratio)
        
        ttk.Label(param_frame, text="验证集比例:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.val_ratio_var = tk.DoubleVar(value=0.2)
        val_scale = ttk.Scale(param_frame, from_=0.1, to=0.5, variable=self.val_ratio_var, orient=tk.HORIZONTAL, length=150)
        val_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.val_label = ttk.Label(param_frame, text="20%")
        self.val_label.grid(row=1, column=2, padx=5, pady=5)
        val_scale.configure(command=self.update_val_ratio)
        
        ttk.Label(param_frame, text="测试集比例:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.test_label_value = ttk.Label(param_frame, text="10%")
        self.test_label_value.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="读取配置", command=self.load_config).pack(side=tk.LEFT, padx=5)
        self.process_button = ttk.Button(button_frame, text="开始处理数据", command=self.start_processing, state=tk.NORMAL)
        self.process_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.StringVar(value="就绪")
        progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        progress_label.grid(row=4, column=0, columnspan=3, pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 分隔线
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # 配置信息显示区域
        ttk.Label(main_frame, text="处理日志与配置信息:", font=("Arial", 12, "bold")).grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
        
        # 创建文本显示区域
        self.config_text = scrolledtext.ScrolledText(main_frame, height=15, width=80, wrap=tk.WORD)
        self.config_text.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 配置网格权重，使文本区域可以扩展
        main_frame.rowconfigure(8, weight=1)
    
    def select_source_directory(self):
        """选择源文件目录"""
        directory = filedialog.askdirectory(
            title="选择源文件目录",
            initialdir=os.getcwd()
        )
        if directory:
            self.source_path = directory
            self.source_path_var.set(directory)
            self.update_status(f"已选择源目录: {directory}")
    
    def select_annotation_file(self):
        """选择标注文件"""
        file_path = filedialog.askopenfilename(
            title="选择标注文件",
            initialdir=self.source_path if self.source_path else os.getcwd(),
            filetypes=[
                ("JSON文件", "*.json"),
                ("文本文件", "*.txt"),
                ("XML文件", "*.xml"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.annotation_file = file_path
            self.annotation_file_var.set(file_path)
            self.update_status(f"已选择标注文件: {os.path.basename(file_path)}")
    
    def select_output_directory(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=os.path.dirname(self.output_path_var.get()) if self.output_path_var.get() else os.getcwd()
        )
        if directory:
            self.output_path = directory
            self.output_path_var.set(directory)
            self.update_status(f"已选择输出目录: {directory}")
    
    def update_train_ratio(self, value):
        """更新训练集比例"""
        ratio = float(value)
        self.train_ratio = ratio
        self.train_label.config(text=f"{int(ratio*100)}%")
        # 自动调整验证集和测试集比例
        remaining = 1.0 - ratio
        val_ratio = min(0.3, remaining * 0.67)  # 验证集不超过30%
        test_ratio = remaining - val_ratio
        
        self.val_ratio_var.set(val_ratio)
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.val_label.config(text=f"{int(val_ratio*100)}%")
        self.test_label_value.config(text=f"{int(test_ratio*100)}%")
    
    def update_val_ratio(self, value):
        """更新验证集比例"""
        val_ratio = float(value)
        train_ratio = self.train_ratio_var.get()
        test_ratio = 1.0 - train_ratio - val_ratio
        
        if test_ratio < 0.05:  # 测试集最少5%
            test_ratio = 0.05
            val_ratio = 1.0 - train_ratio - test_ratio
            self.val_ratio_var.set(val_ratio)
        
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.val_label.config(text=f"{int(val_ratio*100)}%")
        self.test_label_value.config(text=f"{int(test_ratio*100)}%")
    
    def load_config(self):
        """读取并解析配置文件"""
        if not self.annotation_file:
            messagebox.showwarning("警告", "请先选择标注文件！")
            return
        
        try:
            self.update_status("正在读取配置文件...")
            
            # 使用安全读取方法
            content = self.safe_read_file(self.annotation_file)
            if content is None:
                messagebox.showerror("错误", f"无法读取标注文件: {self.annotation_file}")
                return
            
            if self.annotation_file.endswith('.json'):
                data = json.loads(content)
            else:
                # 对于非JSON文件，尝试按行读取
                data = {"content": content}
            
            # 解析配置
            self.parse_config(data)
            
        except Exception as e:
            messagebox.showerror("错误", f"读取配置文件失败: {str(e)}")
            self.update_status(f"读取失败: {str(e)}")
    
    def parse_config(self, data):
        """解析配置数据"""
        config_info = []
        config_info.append("=" * 60)
        config_info.append("📋 标注文件配置信息")
        config_info.append("=" * 60)
        config_info.append("")
        
        # 基本信息
        config_info.append(f"📁 源文件目录: {self.source_path}")
        config_info.append(f"📄 标注文件: {os.path.basename(self.annotation_file)}")
        config_info.append(f"📄 文件路径: {self.annotation_file}")
        config_info.append("")
        
        # 尝试解析不同格式的配置
        classes_found = False
        
        # 1. 检查是否有直接的classes字段
        if 'classes' in data:
            config_info.append("🏷️  类别配置 (classes):")
            config_info.append("-" * 40)
            classes = data['classes']
            if isinstance(classes, dict):
                for key, value in classes.items():
                    config_info.append(f"  {key}: {value}")
            elif isinstance(classes, list):
                for i, cls in enumerate(classes):
                    config_info.append(f"  {i}: {cls}")
            classes_found = True
            config_info.append("")
        
        # 2. 检查是否有class_mapping字段
        if 'class_mapping' in data:
            config_info.append("🔄 类别映射 (class_mapping):")
            config_info.append("-" * 40)
            mapping = data['class_mapping']
            if isinstance(mapping, dict):
                for key, value in mapping.items():
                    config_info.append(f"  {key} → {value}")
            classes_found = True
            config_info.append("")
        
        # 3. 检查是否有categories字段
        if 'categories' in data:
            config_info.append("📂 类别信息 (categories):")
            config_info.append("-" * 40)
            categories = data['categories']
            if isinstance(categories, list):
                for cat in categories:
                    if isinstance(cat, dict):
                        cat_id = cat.get('id', 'N/A')
                        cat_name = cat.get('name', 'N/A')
                        config_info.append(f"  ID: {cat_id}, 名称: {cat_name}")
                    else:
                        config_info.append(f"  {cat}")
            elif isinstance(categories, dict):
                for key, value in categories.items():
                    config_info.append(f"  {key}: {value}")
            classes_found = True
            config_info.append("")
        
        # 4. 检查annotations中的类别信息
        if 'annotations' in data:
            config_info.append("📝 标注信息:")
            config_info.append("-" * 40)
            annotations = data['annotations']
            
            if isinstance(annotations, dict):
                config_info.append(f"  标注图片数量: {len(annotations)}")
                
                # 统计类别
                all_classes = set()
                for img_path, img_annotations in annotations.items():
                    if isinstance(img_annotations, list):
                        for ann in img_annotations:
                            if isinstance(ann, dict) and 'class' in ann:
                                all_classes.add(ann['class'])
                
                if all_classes:
                    config_info.append("  发现的类别:")
                    for cls in sorted(all_classes):
                        config_info.append(f"    - {cls}")
                    classes_found = True
            config_info.append("")
        
        # 5. 显示文件的主要结构
        config_info.append("📊 文件结构:")
        config_info.append("-" * 40)
        if isinstance(data, dict):
            for key in data.keys():
                value = data[key]
                if isinstance(value, dict):
                    config_info.append(f"  {key}: 字典 ({len(value)} 项)")
                elif isinstance(value, list):
                    config_info.append(f"  {key}: 列表 ({len(value)} 项)")
                else:
                    config_info.append(f"  {key}: {type(value).__name__}")
        config_info.append("")
        
        # 如果没有找到类别信息，显示提示
        if not classes_found:
            config_info.append("⚠️  未找到标准的类别配置信息")
            config_info.append("   请检查文件格式是否正确")
            config_info.append("")
        
        # 显示原始数据（截取前500字符）
        config_info.append("📄 原始数据预览:")
        config_info.append("-" * 40)
        raw_data = json.dumps(data, ensure_ascii=False, indent=2)
        if len(raw_data) > 1000:
            config_info.append(raw_data[:1000] + "\n... (数据过长，已截取)")
        else:
            config_info.append(raw_data)
        
        # 更新显示
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, "\n".join(config_info))
        
        self.update_status("配置读取完成！")
    
    def start_processing(self):
        """开始处理数据"""
        if self.is_processing:
            messagebox.showwarning("警告", "数据处理正在进行中，请等待完成！")
            return
        
        # 检查必要参数
        if not self.source_path:
            messagebox.showwarning("警告", "请先选择源文件目录！")
            return
        
        if not os.path.exists(self.source_path):
            messagebox.showerror("错误", "源文件目录不存在！")
            return
        
        output_path = self.output_path_var.get()
        if not output_path:
            messagebox.showwarning("警告", "请设置输出目录！")
            return
        
        # 在后台线程中处理数据
        self.is_processing = True
        self.process_button.config(state=tk.DISABLED, text="处理中...")
        self.progress_bar.start()
        self.progress_var.set("正在处理数据...")
        
        # 启动处理线程
        processing_thread = threading.Thread(target=self.process_data_thread)
        processing_thread.daemon = True
        processing_thread.start()
    
    def process_data_thread(self):
        """在后台线程中处理数据"""
        try:
            self.log_message("=" * 60)
            self.log_message("🚀 开始处理数据集")
            self.log_message("=" * 60)
            self.log_message(f"📁 源目录: {self.source_path}")
            self.log_message(f"📁 输出目录: {self.output_path_var.get()}")
            self.log_message(f"📊 训练集: {int(self.train_ratio*100)}%, 验证集: {int(self.val_ratio*100)}%, 测试集: {int(self.test_ratio*100)}%")
            self.log_message("")
            
            # 构建命令
            script_path = os.path.join(os.path.dirname(__file__), "create_yolo_dataset.py")
            cmd = [
                sys.executable, script_path,
                "--source", self.source_path,
                "--output", self.output_path_var.get(),
                "--train-ratio", str(self.train_ratio),
                "--val-ratio", str(self.val_ratio),
                "--test-ratio", str(self.test_ratio)
            ]
            
            self.log_message(f"🔧 执行命令: {' '.join(cmd)}")
            self.log_message("")
            
            # 执行处理脚本
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                universal_newlines=True
            )
            
            # 实时显示输出
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_message(line)
            
            # 等待进程完成
            return_code = process.wait()
            
            if return_code == 0:
                self.log_message("")
                self.log_message("✅ 数据处理完成！")
                self.log_message(f"📁 输出目录: {self.output_path_var.get()}")
                self.root.after(0, lambda: messagebox.showinfo("成功", "数据处理完成！"))
            else:
                self.log_message("")
                self.log_message(f"❌ 数据处理失败，返回码: {return_code}")
                self.root.after(0, lambda: messagebox.showerror("错误", "数据处理失败！"))
                
        except Exception as e:
            error_msg = f"处理过程中发生错误: {str(e)}"
            self.log_message(f"❌ {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        
        finally:
            # 恢复UI状态
            self.root.after(0, self.processing_finished)
    
    def processing_finished(self):
        """处理完成后恢复UI状态"""
        self.is_processing = False
        self.process_button.config(state=tk.NORMAL, text="开始处理数据")
        self.progress_bar.stop()
        self.progress_var.set("处理完成")
    
    def log_message(self, message):
        """在日志区域添加消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_log_text(log_line))
    
    def _update_log_text(self, message):
        """更新日志文本区域"""
        self.config_text.insert(tk.END, message)
        self.config_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_all(self):
        """清空所有内容"""
        if self.is_processing:
            messagebox.showwarning("警告", "数据处理正在进行中，无法清空！")
            return
            
        self.source_path = ""
        self.annotation_file = ""
        self.source_path_var.set("")
        self.annotation_file_var.set("")
        self.config_text.delete(1.0, tk.END)
        self.progress_var.set("就绪")
        self.update_status("已清空所有内容")
    
    def update_status(self, message):
        """更新状态信息"""
        print(f"[状态] {message}")

def main():
    """主函数"""
    root = tk.Tk()
    app = DatasetConfigGUI(root)
    
    # 设置窗口图标（如果有的话）
    try:
        # 可以设置窗口图标
        pass
    except:
        pass
    
    # 启动GUI
    root.mainloop()

if __name__ == "__main__":
    main()