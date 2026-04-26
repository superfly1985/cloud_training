import os
import time

class TrainingManager:
    """训练管理模块"""
    
    def __init__(self, config_manager, server_manager, environment_manager=None):
        self.config_manager = config_manager
        self.server_manager = server_manager
        self.environment_manager = environment_manager
    
    def build_model_name(self):
        """根据基础模型和后缀构建模型名称"""
        training_config = self.config_manager.training_config
        base_model = training_config.get('base_model', 'yolov8n.pt')
        suffix = training_config.get('model_name_suffix', '')
        
        # 移除 .pt 扩展名
        base_name = base_model.replace('.pt', '')
        
        if suffix:
            # 这里的逻辑应与 generate_training_script 中的 fmt_kwargs['model_name'] 保持一致
            # 如果有后缀，通常是 base_model_suffix
            return f"{base_name}_{suffix}"
        return base_name

    def get_recommended_params(self, model_name, image_size):
        """根据模型和尺寸推荐 batch_size 和 learning_rate"""
        base_batch_640 = {
            'n': 32,
            's': 24,
            'm': 16,
            'l': 10,
            'x': 8
        }
        
        # 提取模型等级 (n, s, m, l, x)
        import re
        name = str(model_name).lower()
        match = re.search(r'yolov\d+([a-z])', name)
        scale = match.group(1) if match else 's'
        
        # 统一映射
        if scale in ['c', 'b']: scale = 'm'
        if scale == 'e': scale = 'l'
        if scale not in ['n', 's', 'm', 'l', 'x']: scale = 's'
        
        try:
            imgsz = int(image_size)
        except:
            imgsz = 640
            
        if imgsz <= 0: imgsz = 640
        
        # 简单比例换算: (640/imgsz)^2
        factor = (640.0 / float(imgsz)) ** 2
        rec_batch = int(round(base_batch_640.get(scale, 24) * factor))
        
        # 限制范围
        if rec_batch < 2: rec_batch = 2
        if rec_batch > 64: rec_batch = 64
        
        # 学习率推荐 (基础 0.01, 随 batch 调整)
        rec_lr = 0.01 * (rec_batch / 16.0)
        if rec_lr < 0.002: rec_lr = 0.002
        if rec_lr > 0.02: rec_lr = 0.02
        
        return rec_batch, round(rec_lr, 5)

    def start_training(self, log_callback=None):
        """开始训练流程：生成脚本 -> 上传 -> 远程执行"""
        try:
            # 1. 准备路径和名称
            remote_dataset_path = self.config_manager.dataset_config.get('remote_path', '/root/yolo_dataset')
            model_name = self.build_model_name()
            
            # 2. 生成训练脚本
            if log_callback:
                log_callback(">>> 正在生成远程训练脚本...")
            script_content = self.generate_training_script(remote_dataset_path, model_name)
            if not script_content:
                return False, "生成训练脚本内容为空"
                
            # 3. 上传脚本
            local_script_name = "train_v3_remote.py"
            with open(local_script_name, "w", encoding="utf-8") as f:
                f.write(script_content)
            
            remote_script_path = f"{remote_dataset_path.rstrip('/')}/{local_script_name}"
            if log_callback:
                log_callback(f">>> 正在上传脚本到: {remote_script_path}")
                
            success, msg = self.server_manager.upload_file(local_script_name, remote_script_path)
            if not success:
                return False, f"脚本上传失败: {msg}"
            
            # 4. 执行训练命令
            python_cmd = "python3"
            if self.environment_manager:
                python_cmd = self.environment_manager.get_python_cmd_with_fallback() or "python3"
            
            # 使用 nohup 或直接执行（流式回传日志）
            # 切换到数据集目录执行，确保相对路径正确
            cmd = f"cd {remote_dataset_path} && {python_cmd} {local_script_name}"
            
            if log_callback:
                log_callback(f">>> 开始远程执行: {cmd}")
            
            # 使用流式输出
            last_msg = ""
            for ok, line in self.server_manager.execute_command_stream(cmd):
                if not ok:
                    return False, line
                if line == "Done":
                    break
                if log_callback:
                    log_callback(line)
                last_msg = line
            
            return True, "训练任务执行完毕"
            
        except Exception as e:
            import traceback
            return False, f"启动训练异常: {str(e)}\n{traceback.format_exc()}"
        finally:
            # 清理本地临时脚本
            if os.path.exists("train_v3_remote.py"):
                try:
                    os.remove("train_v3_remote.py")
                except:
                    pass

    def stop_training(self):
        """停止远程训练脚本进程。"""
        cmd = (
            "PIDS=$(pgrep -f 'train_v3_remote.py' || true); "
            "if [ -z \"$PIDS\" ]; then "
            "echo 'NOT_RUNNING'; "
            "else "
            "kill -TERM $PIDS 2>/dev/null || true; "
            "sleep 1; "
            "PIDS2=$(pgrep -f 'train_v3_remote.py' || true); "
            "if [ -n \"$PIDS2\" ]; then kill -KILL $PIDS2 2>/dev/null || true; fi; "
            "echo 'STOP_SENT'; "
            "fi"
        )
        ok, out = self.server_manager.execute_command(cmd, timeout=30)
        if not ok:
            return False, out or "停止命令执行失败"
        text = (out or "").strip()
        if "STOP_SENT" in text:
            return True, "已发送停止指令"
        return True, "当前无运行中的训练进程"

    def generate_training_script(self, remote_dataset_path, model_name):
        """生成训练脚本 (深度复刻原版 Python API 逻辑)"""
        try:
            training_config = self.config_manager.training_config
            dataset_config = self.config_manager.dataset_config
            
            # 准备格式化参数
            fmt_kwargs = {
                "dataset_name": dataset_config.get('dataset_name', 'Unknown'),
                "num_classes": dataset_config.get('num_classes', 1),
                "remote_path": remote_dataset_path.replace('\\', '/').rstrip('/'),
                "epochs": training_config.get('epochs', 100),
                "batch_size": training_config.get('batch_size', 16),
                "learning_rate": training_config.get('learning_rate', 0.01),
                "image_size": training_config.get('image_size', 640),
                "base_model": training_config.get('base_model', 'yolov8n.pt'),
                "timestamp": time.strftime("%Y%m%d_%H%M%S"),
                "model_name": model_name,
                
                # 图像增强参数
                "scale": training_config.get('augment_scale', 0.5),
                "fliplr": training_config.get('augment_fliplr', 0.5),
                "flipud": training_config.get('augment_flipud', 0.0),
                "perspective": training_config.get('augment_perspective', 0.0),
                "hsv_h": training_config.get('augment_hsv_h', 0.015),
                "hsv_s": training_config.get('augment_hsv_s', 0.7),
                "hsv_v": training_config.get('augment_hsv_v', 0.4),
                
                # 图像增强激活状态
                "augment_scale_active": training_config.get('augment_scale_active', True),
                "augment_fliplr_active": training_config.get('augment_fliplr_active', True),
                "augment_flipud_active": training_config.get('augment_flipud_active', True),
                "augment_perspective_active": training_config.get('augment_perspective_active', True),
                "augment_hsv_h_active": training_config.get('augment_hsv_h_active', True),
                "augment_hsv_s_active": training_config.get('augment_hsv_s_active', True),
                "augment_hsv_v_active": training_config.get('augment_hsv_v_active', True),
            }

            script_content = f'''# -*- coding: utf-8 -*-
"""
自动生成的YOLO训练脚本 (深度复刻版)
数据集: {fmt_kwargs['dataset_name']}
类别数: {fmt_kwargs['num_classes']}
"""

import os
import sys
import logging
import time

# 环境设置
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ["YOLO_AUTOINSTALL"] = "0"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # 1. 检查并加载模型
        import torch
        from ultralytics import YOLO
        
        # 打印环境信息
        cuda_available = torch.cuda.is_available()
        logger.info(f"CUDA available: {{cuda_available}}")
        if cuda_available:
            logger.info(f"Device: {{torch.cuda.get_device_name(0)}}")
        
        model_name = "{fmt_kwargs['base_model']}"
        logger.info(f"正在加载模型: {{model_name}}")
        
        # 2. 准备数据集路径
        dataset_path = "{fmt_kwargs['remote_path']}"
        yaml_path = os.path.join(dataset_path, "dataset.yaml")
        if not os.path.exists(yaml_path):
            logger.error(f"找不到数据集配置文件: {{yaml_path}}")
            sys.exit(1)
            
        # 3. 加载模型 (带自动重试下载逻辑)
        try:
            model = YOLO(model_name)
        except Exception as e:
            logger.warning(f"初始加载失败: {{e}}，尝试备用方案...")
            # 这里简化了重试逻辑，实际生产中可以增加更多备用路径
            model = YOLO("yolov8n.pt") 
            
        # 4. 构建增强参数
        augment_kwargs = {{}}
        if {fmt_kwargs['augment_scale_active']}: augment_kwargs['scale'] = {fmt_kwargs['scale']}
        if {fmt_kwargs['augment_fliplr_active']}: augment_kwargs['fliplr'] = {fmt_kwargs['fliplr']}
        if {fmt_kwargs['augment_flipud_active']}: augment_kwargs['flipud'] = {fmt_kwargs['flipud']}
        if {fmt_kwargs['augment_perspective_active']}: augment_kwargs['perspective'] = {fmt_kwargs['perspective']}
        if {fmt_kwargs['augment_hsv_h_active']}: augment_kwargs['hsv_h'] = {fmt_kwargs['hsv_h']}
        if {fmt_kwargs['augment_hsv_s_active']}: augment_kwargs['hsv_s'] = {fmt_kwargs['hsv_s']}
        if {fmt_kwargs['augment_hsv_v_active']}: augment_kwargs['hsv_v'] = {fmt_kwargs['hsv_v']}
        
        # 5. 开始训练
        logger.info("开始执行训练任务...")
        device_arg = '0' if cuda_available else 'cpu'
        
        results = model.train(
                data=yaml_path,
                epochs={fmt_kwargs['epochs']},
                batch={fmt_kwargs['batch_size']},
                lr0={fmt_kwargs['learning_rate']},
                imgsz={fmt_kwargs['image_size']},
                device=device_arg,
                project='./runs/train',
                name=f"{fmt_kwargs['model_name']}_{fmt_kwargs['timestamp']}",
                exist_ok=False,
                save=True,
                val=True,
                plots=True,
                **augment_kwargs
            )
        
        # 6. 训练后处理 (深度复刻原版)
        logger.info("正在进行训练后处理 (命名、转换、打包)...")
        
        import re
        import json
        import shutil
        import zipfile
        import yaml
        from datetime import datetime, timezone, timedelta

        def sanitize_name_suffix(text):
            clean = re.sub(r'[^0-9A-Za-z_\\-一-龥]+', '_', str(text or '').strip())
            clean = re.sub(r'_+', '_', clean).strip('_-')
            return clean[:64]

        def ensure_unique_path(path):
            if not os.path.exists(path):
                return path
            base, ext = os.path.splitext(path)
            idx = 1
            while True:
                candidate = f"{{base}}_{{idx}}{{ext}}"
                if not os.path.exists(candidate):
                    return candidate
                idx += 1

        def get_dataset_class_label(yaml_file):
            try:
                with open(yaml_file, "r", encoding="utf-8") as rf:
                    y = yaml.safe_load(rf) or {{}}
                names = y.get("names")
                label = None
                if isinstance(names, dict) and names:
                    def _k_sort(v):
                        sv = str(v)
                        return (0, int(sv)) if sv.isdigit() else (1, sv)
                    first_key = sorted(names.keys(), key=_k_sort)[0]
                    label = names.get(first_key)
                elif isinstance(names, list) and names:
                    label = names[0]
                safe_label = sanitize_name_suffix(label)
                return safe_label if safe_label else "dataset"
            except Exception:
                return "dataset"

        def build_tagged_name(src_path, tag, dataset_label):
            base = os.path.basename(src_path)
            stem, ext = os.path.splitext(base)
            if base.lower() == "dataset.yaml":
                return f"{{dataset_label}}_{{tag}}.yaml"
            if stem.endswith(f"_{{tag}}") or (f"_{{tag}}_" in stem) or stem.startswith(f"{{tag}}_"):
                return base
            return f"{{stem}}_{{tag}}{{ext}}"

        # 获取运行目录
        run_dir = getattr(results, 'save_dir', os.path.join('./runs/train', '{fmt_kwargs['model_name']}'))
        best_candidates = [
            os.path.join(run_dir, 'weights', 'best.pt'),
            os.path.join('./runs/train', '{fmt_kwargs['model_name']}', 'weights', 'best.pt')
        ]
        best_pt = None
        for p in best_candidates:
            if os.path.exists(p):
                best_pt = p
                break
        
        if not best_pt:
            logger.error(f"未找到训练产物 best.pt，候选路径: {{best_candidates}}")
            sys.exit(1)

        # 统一命名尾缀：命名+时间戳 (东八区)
        def cn_now():
            return datetime.now(timezone(timedelta(hours=8)))

        safe_suffix = sanitize_name_suffix("{fmt_kwargs['model_name']}")
        artifact_stamp = cn_now().strftime("%Y%m%d_%H%M%S")
        artifact_tag = f"{{safe_suffix}}_{{artifact_stamp}}"
        
        # 1) 重命名 best.pt（严格：模型命名 + best + 时间戳）
        best_name = f"{{safe_suffix}}_best_{{artifact_stamp}}.pt"
        renamed_best = ensure_unique_path(os.path.join(os.path.dirname(best_pt), best_name))
        os.replace(best_pt, renamed_best)
        best_pt = renamed_best
        logger.info(f"模型已重命名: {{best_pt}}")

        # 2) 自动导出 ONNX (ONNX 较快，作为训练流程一部分)
        logger.info("开始自动导出模型 (ONNX)...")
        export_outputs = {{}}
        try:
            onnx_path = model.export(format="onnx", imgsz={fmt_kwargs['image_size']}, batch=1)
            export_outputs["onnx"] = str(onnx_path)
            logger.info(f"ONNX 导出成功: {{onnx_path}}")
        except Exception as e:
            logger.error(f"ONNX 导出失败: {{e}}")

        # 3) 打包交付件 (ZIP)
        logger.info("正在生成交付打包文件...")
        pack_temp_dir = f"/tmp/train_pack_{{artifact_tag}}"
        if os.path.isdir(pack_temp_dir):
            shutil.rmtree(pack_temp_dir, ignore_errors=True)
        os.makedirs(pack_temp_dir, exist_ok=True)
        
        to_pack = []
        seen = set()

        def add_pack_file(path):
            if not path: return
            if os.path.isdir(path):
                # 如果是文件夹，寻找里面的关键文件
                for root, dirs, files in os.walk(path):
                    for f in files:
                        if f.endswith((".tflite", ".onnx", ".pt")):
                            add_pack_file(os.path.join(root, f))
                return
            
            if not os.path.isfile(path): return
            real = os.path.realpath(path)
            if real in seen: return
            seen.add(real)
            to_pack.append(path)

        add_pack_file(best_pt)
        for p in export_outputs.values():
            add_pack_file(p)
        
        # 附带文件
        for rel_name in [
            "args.yaml", "results.csv", "results.png", "confusion_matrix.png",
            "F1_curve.png", "P_curve.png", "PR_curve.png", "R_curve.png"
        ]:
            add_pack_file(os.path.join(run_dir, rel_name))
        add_pack_file(yaml_path)

        dataset_label = get_dataset_class_label(yaml_path)
        used_names = set()
        staged_files = []
        for src in to_pack:
            tagged_name = build_tagged_name(src, artifact_tag, dataset_label)
            unique_name = tagged_name
            stem, ext = os.path.splitext(tagged_name)
            i = 1
            while unique_name in used_names:
                unique_name = f"{{stem}}_{{i}}{{ext}}"
                i += 1
            used_names.add(unique_name)
            dst = os.path.join(pack_temp_dir, unique_name)
            shutil.copy2(src, dst)
            staged_files.append(dst)

        zip_path = ensure_unique_path(os.path.join(run_dir, f"{{artifact_tag}}.zip"))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fp in staged_files:
                zf.write(fp, arcname=os.path.basename(fp))
        shutil.rmtree(pack_temp_dir, ignore_errors=True)
        
        logger.info(f"训练产物打包完成: {{zip_path}}")
        logger.info("训练任务圆满完成!")
        
    except Exception as e:
        logger.error(f"训练过程中发生异常: {{e}}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
            return script_content
        except Exception as e:
            print(f"Error generating script: {e}")
            return ""
