import os
import json
import yaml
import hashlib
import shlex

class DatasetManager:
    """数据集管理模块"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def get_dataset_fingerprint(self, dataset_path):
        """生成数据集指纹，用于快速检查"""
        try:
            if not os.path.exists(dataset_path):
                return ""
            
            # 扫描所有可能的目录
            potential_dirs = [
                'images', 'labels',
                'train/images', 'train/labels',
                'val/images', 'val/labels',
                'test/images', 'test/labels'
            ]
            
            stats = []
            for d in potential_dirs:
                full_path = os.path.join(dataset_path, d)
                if os.path.exists(full_path):
                    s = os.stat(full_path)
                    count = len(os.listdir(full_path))
                    stats.append(f"{d}:{s.st_mtime}:{count}")
            
            if not stats:
                return "invalid"

            # 加上 dataset.yaml 的内容哈希
            yaml_hash = ""
            yaml_path = os.path.join(dataset_path, "dataset.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "rb") as f:
                    yaml_hash = hashlib.md5(f.read()).hexdigest()

            raw_fingerprint = f"{dataset_path}|{'|'.join(stats)}|{yaml_hash}"
            return hashlib.md5(raw_fingerprint.encode()).hexdigest()
        except Exception:
            return "error"

    def check_dataset(self, dataset_path):
        """检查数据集"""
        try:
            # 支持两种结构：
            # 1. 扁平结构：根目录下有 images/ 和 labels/
            # 2. 标准结构：根目录下有 train/images, train/labels, val/images, val/labels
            
            has_images = False
            has_labels = False
            
            # 检查扁平结构
            if os.path.exists(os.path.join(dataset_path, 'images')) and \
               os.path.exists(os.path.join(dataset_path, 'labels')):
                has_images = True
                has_labels = True
            
            # 检查标准结构（只要有 train/images 就认为初步通过）
            if not has_images:
                if os.path.exists(os.path.join(dataset_path, 'train', 'images')) and \
                   os.path.exists(os.path.join(dataset_path, 'train', 'labels')):
                    has_images = True
                    has_labels = True
            
            if not has_images:
                return False, "未找到有效的 YOLO 数据集结构 (缺少 images/labels 或 train/子目录)"
            
            # 统计总数
            info = self.get_dataset_info(dataset_path)
            if info.get('image_count', 0) == 0:
                return False, "未找到图像文件"
            if info.get('label_count', 0) == 0:
                return False, "未找到标签文件"
            
            return True, f"数据集检查通过，共找到 {info['image_count']} 张图片和 {info['label_count']} 条标签"
        except Exception as e:
            return False, str(e)

    def parse_classes_from_labels(self, dataset_path):
        """从所有可能的 labels 目录中推断类别索引集合"""
        label_dirs = [
            os.path.join(dataset_path, "labels"),
            os.path.join(dataset_path, "train", "labels"),
            os.path.join(dataset_path, "val", "labels")
        ]
        
        class_ids = set()
        for ldir in label_dirs:
            if not os.path.isdir(ldir):
                continue
            for name in os.listdir(ldir):
                if not name.endswith(".txt"):
                    continue
                txt_path = os.path.join(ldir, name)
                try:
                    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            parts = line.strip().split()
                            if not parts or not parts[0].isdigit():
                                continue
                            class_ids.add(int(parts[0]))
                except Exception:
                    continue
        return sorted(class_ids)
    
    def create_yaml(self, dataset_path, classes):
        """创建数据集YAML文件"""
        try:
            yaml_content = {
                'path': dataset_path,
                'train': 'images',
                'val': 'images',
                'names': {i: cls for i, cls in enumerate(classes)}
            }
            
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_content, f, allow_unicode=True)
            
            return True, yaml_file
        except Exception as e:
            return False, str(e)
    
    def get_dataset_info(self, dataset_path):
        """获取数据集信息（支持多种结构）"""
        try:
            image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
            
            img_count = 0
            lbl_count = 0
            
            # 遍历所有可能的子目录
            for root, dirs, files in os.walk(dataset_path):
                # 只统计 images 和 labels 目录下的文件
                dirname = os.path.basename(root)
                if dirname == 'images':
                    img_count += len([f for f in files if f.lower().endswith(image_extensions)])
                elif dirname == 'labels':
                    lbl_count += len([f for f in files if f.lower().endswith('.txt')])
            
            # 读取类别信息
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            classes = []
            if os.path.exists(yaml_file):
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml_content = yaml.safe_load(f)
                    if yaml_content and 'names' in yaml_content:
                        if isinstance(yaml_content['names'], dict):
                            classes = list(yaml_content['names'].values())
                        elif isinstance(yaml_content['names'], list):
                            classes = yaml_content['names']
            
            return {
                'image_count': img_count,
                'label_count': lbl_count,
                'class_count': len(classes),
                'classes': classes
            }
        except Exception:
            return {'image_count': 0, 'label_count': 0, 'class_count': 0, 'classes': []}

    def upload_dataset(
        self,
        local_path,
        remote_path,
        server_manager,
        progress_callback=None,
        log_callback=None,
        stop_callback=None,
        use_package=False,
    ):
        """上传完整数据集目录到远端"""
        if use_package:
            if log_callback:
                log_callback("使用打包上传模式...")
            return server_manager.upload_package(
                local_path,
                remote_path,
                progress_callback=progress_callback,
                log_callback=log_callback,
                stop_callback=stop_callback,
            )
        else:
            return server_manager.upload_dir(
                local_path,
                remote_path,
                progress_callback=progress_callback,
                log_callback=log_callback,
                stop_callback=stop_callback,
            )

    def clear_remote_dataset(self, remote_path, server_manager):
        """清空远端训练集目录"""
        ok, msg = server_manager.remove_remote_path(remote_path)
        if not ok:
            return False, msg
        return server_manager.ensure_remote_dir(remote_path)

    def _build_local_image_map(self, dataset_path):
        """构建本地图片相对路径->文件大小映射。"""
        image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        result = {}
        for root, _, files in os.walk(dataset_path):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in image_exts:
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, dataset_path).replace("\\", "/")
                try:
                    result[rel] = int(os.path.getsize(full))
                except Exception:
                    continue
        return result

    def compare_remote_image_diff(self, dataset_path, remote_path, server_manager):
        """
        对比本地与云端图片差异（按相对路径+文件大小）。
        返回:
            {
              ok, msg, local_total, remote_total,
              need_upload, skip_count, need_upload_bytes, todo_rel_paths
            }
        """
        result = {
            "ok": False,
            "msg": "",
            "local_total": 0,
            "remote_total": 0,
            "need_upload": 0,
            "skip_count": 0,
            "need_upload_bytes": 0,
            "todo_rel_paths": [],
        }

        local_map = self._build_local_image_map(dataset_path)
        result["local_total"] = len(local_map)
        if result["local_total"] == 0:
            result["msg"] = "本地未发现可对比的图片文件"
            return result

        remote_root = (remote_path or "").strip()
        if not remote_root or remote_root.startswith("路径:"):
            result["msg"] = "远程路径为空，已跳过云端差异检查"
            return result

        if not server_manager or not server_manager.is_connected:
            result["msg"] = "未连接服务器，已跳过云端差异检查"
            return result

        quoted = shlex.quote(remote_root)
        cmd = (
            f"if [ -d {quoted} ]; then "
            f"find {quoted} -type f "
            "\\( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.bmp' -o -iname '*.webp' \\) "
            "-printf '%P\\t%s\\n' 2>/dev/null; "
            "fi"
        )
        ok, output = server_manager.execute_command(cmd)
        if not ok:
            result["msg"] = output or "云端差异检查失败"
            return result

        remote_map = {}
        if output:
            for line in output.splitlines():
                text = str(line).strip()
                if not text:
                    continue
                if "\t" in text:
                    rel, size_text = text.split("\t", 1)
                else:
                    parts = text.rsplit(" ", 1)
                    if len(parts) != 2:
                        continue
                    rel, size_text = parts
                rel = rel.strip().replace("\\", "/")
                try:
                    remote_map[rel] = int(size_text.strip())
                except Exception:
                    continue

        todo = []
        need_upload_bytes = 0
        for rel, local_size in local_map.items():
            if int(remote_map.get(rel, -1)) != int(local_size):
                todo.append(rel)
                need_upload_bytes += int(local_size)

        result["ok"] = True
        result["remote_total"] = len(remote_map)
        result["need_upload"] = len(todo)
        result["skip_count"] = len(local_map) - len(todo)
        result["need_upload_bytes"] = need_upload_bytes
        result["todo_rel_paths"] = sorted(todo)
        return result
