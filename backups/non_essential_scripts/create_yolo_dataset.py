"""
智能数据集准备脚本
功能：
1. 对路径中的图片和标注文件进行检查统计
2. 将标注文件转换成YOLO格式
3. 将转换好的文件分成训练组、验证组、测试组
4. 将分好组的图片和标注文件放入指定文件夹，放入前先清空已存在的文件
"""

import os
import shutil
import json
import random
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
import sys
import yaml
import chardet
import traceback

class SmartDatasetPreparer:
    def __init__(self, source_dir, output_dir=None):
        """
        初始化智能数据集准备器
        
        Args:
            source_dir: 包含图片和标注文件的源目录
            output_dir: 输出数据集目录，默认为固定路径
        """
        self.source_dir = Path(source_dir)
        if output_dir is None:
            # 使用云端训练脚本要求的固定路径
            self.output_dir = Path(r"d:\OneDrive\24.Visual AI\data\yolo_dataset")
        else:
            self.output_dir = Path(output_dir)
        
        # 支持的图片格式
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        # 支持的标注格式
        self.annotation_extensions = {'.json', '.txt', '.xml'}
        
        # 类别映射 (支持四类别，包含中英文名称)
        self.class_mapping = {
            # ruler.json中的类别
            '原点': 0,
            '10': 1,
            '20': 2,
            '30': 3,
            # 英文名称
            'origin': 0,
            'ten': 1,
            'twenty': 2,
            'thirty': 3,
            # 原有的三类别支持（向后兼容）
            'pin': 0,        
            'bracket': 1,    
            'double_pin': 2,
            # 中文名称
            '卡丁': 0,
            '支架': 1,
            '双飞卡钉': 2,
            # 其他可能的名称变体
            'kading': 0,
            'zhijia': 1,
            'shuangfei': 2,
            'shuangfeikading': 2,
            'ruler': 0,  # 如果标注文件中使用了ruler作为类别名
        }
        
        print(f"📁 源目录: {self.source_dir}")
        print(f"📁 输出目录: {self.output_dir}")
    
    def safe_read_file(self, file_path):
        """
        安全读取文件，自动检测编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            tuple: (success, content, encoding_used)
        """
        try:
            # 首先尝试检测文件编码
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                
            # 使用chardet检测编码
            detected = chardet.detect(raw_data)
            detected_encoding = detected.get('encoding', 'utf-8')
            confidence = detected.get('confidence', 0)
            
            print(f"🔍 文件编码检测: {file_path}")
            print(f"   检测到编码: {detected_encoding} (置信度: {confidence:.2f})")
            
            # 尝试多种编码方式
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
                    print(f"✅ 成功使用编码: {encoding}")
                    return True, content, encoding
                except (UnicodeDecodeError, UnicodeError) as e:
                    print(f"❌ 编码 {encoding} 失败: {str(e)[:100]}")
                    continue
                except Exception as e:
                    print(f"❌ 读取文件时出错 ({encoding}): {str(e)[:100]}")
                    continue
            
            # 如果所有编码都失败，尝试忽略错误
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                print(f"⚠️  使用UTF-8忽略错误模式读取成功")
                return True, content, 'utf-8-ignore'
            except Exception as e:
                print(f"❌ 最终读取失败: {str(e)}")
                return False, None, None
                
        except Exception as e:
            print(f"❌ 文件读取过程出错: {str(e)}")
            return False, None, None
    
    def check_and_analyze_files(self):
        """
        步骤1: 检查和统计源目录中的图片和标注文件
        """
        print("\n📋 步骤1: 检查和统计文件...")
        
        if not self.source_dir.exists():
            print(f"❌ 错误: 源目录不存在 - {self.source_dir}")
            return False
        
        # 扫描所有文件
        all_files = list(self.source_dir.rglob("*"))
        
        # 分类文件
        image_files = []
        annotation_files = []
        other_files = []
        
        for file_path in all_files:
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in self.image_extensions:
                    image_files.append(file_path)
                elif ext in self.annotation_extensions:
                    annotation_files.append(file_path)
                else:
                    other_files.append(file_path)
        
        # 统计信息
        print(f"📊 文件统计:")
        print(f"   🖼️  图片文件: {len(image_files)} 个")
        print(f"   📝 标注文件: {len(annotation_files)} 个")
        print(f"   📄 其他文件: {len(other_files)} 个")
        
        # 详细分析图片格式
        image_formats = {}
        for img in image_files:
            ext = img.suffix.lower()
            image_formats[ext] = image_formats.get(ext, 0) + 1
        
        print(f"   📈 图片格式分布:")
        for ext, count in image_formats.items():
            print(f"      {ext}: {count} 个")
        
        # 详细分析标注格式
        annotation_formats = {}
        for ann in annotation_files:
            ext = ann.suffix.lower()
            annotation_formats[ext] = annotation_formats.get(ext, 0) + 1
        
        print(f"   📈 标注格式分布:")
        for ext, count in annotation_formats.items():
            print(f"      {ext}: {count} 个")
        
        # 检查是否有统一标注文件
        unified_annotation_file = None
        for ann_file in annotation_files:
            if ann_file.name.lower() in ['mark.json', 'annotations.json', 'labels.json', 'ruler.json']:
                unified_annotation_file = ann_file
                break
        
        if unified_annotation_file:
            print(f"   🔍 发现统一标注文件: {unified_annotation_file.name}")
            # 检查统一标注文件中的图片覆盖情况
            matched_pairs = self.check_unified_annotation_coverage(unified_annotation_file, image_files)
            unmatched_images = set()
            unmatched_annotations = set()
            
            print(f"   🔗 统一标注文件分析:")
            print(f"      ✅ 有标注的图片: {len(matched_pairs)} 个")
            print(f"      ❌ 无标注的图片: {len(image_files) - len(matched_pairs)} 个")
            
            if len(matched_pairs) == 0:
                print("❌ 错误: 统一标注文件中没有找到匹配的图片标注!")
                return False
        else:
            # 传统的一对一匹配检查
            image_stems = {img.stem for img in image_files}
            annotation_stems = {ann.stem for ann in annotation_files}
            
            matched_pairs = image_stems.intersection(annotation_stems)
            unmatched_images = image_stems - annotation_stems
            unmatched_annotations = annotation_stems - image_stems
            
            print(f"   🔗 匹配分析:")
            print(f"      ✅ 匹配的图片-标注对: {len(matched_pairs)} 对")
            print(f"      ❌ 无标注的图片: {len(unmatched_images)} 个")
            print(f"      ❌ 无图片的标注: {len(unmatched_annotations)} 个")
            
            if len(matched_pairs) == 0:
                print("❌ 错误: 没有找到匹配的图片-标注对!")
                return False
        
        # 保存分析结果
        self.image_files = image_files
        self.annotation_files = annotation_files
        self.matched_pairs = matched_pairs
        self.unmatched_images = unmatched_images
        self.unmatched_annotations = unmatched_annotations
        self.unified_annotation_file = unified_annotation_file
        
        return True
    
    def check_unified_annotation_coverage(self, annotation_file, image_files):
        """检查统一标注文件中的图片覆盖情况"""
        try:
            # 使用安全读取方法
            success, content, encoding = self.safe_read_file(annotation_file)
            if not success or content is None:
                print(f"❌ 无法读取标注文件: {annotation_file}")
                return False
            data = json.loads(content)
            
            # 获取标注中的图片路径
            annotated_images = set()
            
            if 'annotations' in data:
                # 处理我们的格式: {"annotations": {"data\\images\\image_0018.jpg": [...]}}
                for img_path in data['annotations'].keys():
                    # 提取文件名（不含路径）
                    img_name = Path(img_path).name
                    annotated_images.add(img_name)
            elif isinstance(data, list):
                # 处理列表格式的标注
                for item in data:
                    if 'image' in item or 'filename' in item or 'file' in item:
                        img_path = item.get('image') or item.get('filename') or item.get('file')
                        img_name = Path(img_path).name
                        annotated_images.add(img_name)
            
            # 检查哪些图片文件有对应的标注
            matched_images = set()
            for img_file in image_files:
                if img_file.name in annotated_images:
                    matched_images.add(img_file.stem)
            
            return matched_images
            
        except Exception as e:
            print(f"⚠️  读取统一标注文件错误: {e}")
            return set()
    
    def convert_annotations_to_yolo(self):
        """
        步骤2: 将标注文件转换为YOLO格式
        """
        print("\n📋 步骤2: 转换标注格式为YOLO格式...")
        
        converted_annotations = {}
        conversion_stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        if hasattr(self, 'unified_annotation_file') and self.unified_annotation_file:
            # 处理统一标注文件
            return self.convert_unified_annotations_to_yolo()
        else:
            # 处理传统的一对一标注文件
            for file_stem in self.matched_pairs:
                # 找到对应的图片和标注文件
                image_file = None
                annotation_file = None
                
                for img in self.image_files:
                    if img.stem == file_stem:
                        image_file = img
                        break
                
                for ann in self.annotation_files:
                    if ann.stem == file_stem:
                        annotation_file = ann
                        break
                
                if not image_file or not annotation_file:
                    conversion_stats['skipped'] += 1
                    continue
                
                # 获取图片尺寸
                try:
                    img = cv2.imread(str(image_file))
                    if img is None:
                        print(f"⚠️  无法读取图片: {image_file}")
                        conversion_stats['failed'] += 1
                        continue
                        
                    img_height, img_width = img.shape[:2]
                except Exception as e:
                    print(f"⚠️  读取图片失败 {image_file}: {e}")
                    conversion_stats['failed'] += 1
                    continue
                
                # 转换标注
                try:
                    yolo_annotations = self.convert_single_annotation(
                        annotation_file, img_width, img_height
                    )
                    
                    if yolo_annotations:
                        converted_annotations[file_stem] = {
                            'image_file': image_file,
                            'yolo_annotations': yolo_annotations,
                            'image_size': (img_width, img_height)
                        }
                        conversion_stats['success'] += 1
                    else:
                        conversion_stats['skipped'] += 1
                        
                except Exception as e:
                    print(f"⚠️  转换标注失败 {annotation_file}: {e}")
                    conversion_stats['failed'] += 1
            
            print(f"📊 转换统计:")
            print(f"   ✅ 成功转换: {conversion_stats['success']} 个")
            print(f"   ❌ 转换失败: {conversion_stats['failed']} 个")
            print(f"   ⏭️  跳过: {conversion_stats['skipped']} 个")
            
            self.converted_annotations = converted_annotations
            return len(converted_annotations) > 0
    
    def convert_unified_annotations_to_yolo(self):
        """处理统一标注文件的转换"""
        print("   🔄 处理统一标注文件...")
        
        converted_annotations = {}
        conversion_stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        try:
            # 使用安全读取方法读取统一标注文件
            success, content, encoding = self.safe_read_file(self.unified_annotation_file)
            if not success or content is None:
                print(f"❌ 无法读取统一标注文件: {self.unified_annotation_file}")
                return conversion_stats
            annotation_data = json.loads(content)
            
            # 获取类别映射
            if 'classes' in annotation_data:
                print(f"   📋 发现类别定义: {list(annotation_data['classes'].keys())}")
            
            # 处理每个有标注的图片
            if 'annotations' in annotation_data:
                for img_path, annotations in annotation_data['annotations'].items():
                    # 提取图片文件名
                    img_name = Path(img_path).name
                    img_stem = Path(img_path).stem
                    
                    # 找到对应的图片文件
                    image_file = None
                    for img_file in self.image_files:
                        if img_file.name == img_name:
                            image_file = img_file
                            break
                    
                    if not image_file:
                        print(f"⚠️  找不到图片文件: {img_name}")
                        conversion_stats['skipped'] += 1
                        continue
                    
                    # 获取图片尺寸
                    try:
                        img = cv2.imread(str(image_file))
                        if img is None:
                            print(f"⚠️  无法读取图片: {image_file}")
                            conversion_stats['failed'] += 1
                            continue
                            
                        img_height, img_width = img.shape[:2]
                    except Exception as e:
                        print(f"⚠️  读取图片失败 {image_file}: {e}")
                        conversion_stats['failed'] += 1
                        continue
                    
                    # 转换标注
                    yolo_lines = []
                    for annotation in annotations:
                        yolo_line = self.process_annotation_item(annotation, img_width, img_height)
                        if yolo_line:
                            yolo_lines.append(yolo_line)
                    
                    if yolo_lines:
                        converted_annotations[img_stem] = {
                            'image_file': image_file,
                            'yolo_annotations': yolo_lines,
                            'image_size': (img_width, img_height)
                        }
                        conversion_stats['success'] += 1
                    else:
                        conversion_stats['skipped'] += 1
            
            print(f"📊 转换统计:")
            print(f"   ✅ 成功转换: {conversion_stats['success']} 个")
            print(f"   ❌ 转换失败: {conversion_stats['failed']} 个")
            print(f"   ⏭️  跳过: {conversion_stats['skipped']} 个")
            
            self.converted_annotations = converted_annotations
            return len(converted_annotations) > 0
            
        except Exception as e:
            print(f"❌ 处理统一标注文件失败: {e}")
            return False
    
    def convert_single_annotation(self, annotation_file, img_width, img_height):
        """
        转换单个标注文件为YOLO格式
        """
        ext = annotation_file.suffix.lower()
        
        if ext == '.json':
            return self.convert_json_to_yolo(annotation_file, img_width, img_height)
        elif ext == '.txt':
            # 检查是否已经是YOLO格式
            return self.convert_txt_to_yolo(annotation_file, img_width, img_height)
        elif ext == '.xml':
            return self.convert_xml_to_yolo(annotation_file, img_width, img_height)
        else:
            print(f"⚠️  不支持的标注格式: {ext}")
            return []
    
    def convert_json_to_yolo(self, json_file, img_width, img_height):
        """转换JSON格式标注为YOLO格式"""
        try:
            # 使用安全读取方法
            success, content, encoding_used = self.safe_read_file(json_file)
            if not success:
                print(f"❌ 无法读取JSON文件: {json_file}")
                return []
            
            # 解析JSON内容
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"❌ JSON格式错误 {json_file}: {e}")
                return []
            
            yolo_lines = []
            
            # 处理不同的JSON格式
            if isinstance(data, list):
                # 列表格式
                for item in data:
                    line = self.process_annotation_item(item, img_width, img_height)
                    if line:
                        yolo_lines.append(line)
            elif isinstance(data, dict):
                # 字典格式
                if 'annotations' in data:
                    for item in data['annotations']:
                        line = self.process_annotation_item(item, img_width, img_height)
                        if line:
                            yolo_lines.append(line)
                elif 'objects' in data:
                    for item in data['objects']:
                        line = self.process_annotation_item(item, img_width, img_height)
                        if line:
                            yolo_lines.append(line)
                else:
                    # 直接处理为单个标注
                    line = self.process_annotation_item(data, img_width, img_height)
                    if line:
                        yolo_lines.append(line)
            
            return yolo_lines
            
        except Exception as e:
            print(f"⚠️  JSON转换错误 {json_file}: {e}")
            return []
    
    def convert_txt_to_yolo(self, txt_file, img_width, img_height):
        """转换TXT格式标注为YOLO格式"""
        try:
            # 使用安全读取方法
            success, content, encoding_used = self.safe_read_file(txt_file)
            if not success:
                print(f"❌ 无法读取TXT文件: {txt_file}")
                return []
            
            lines = content.splitlines()
            
            yolo_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检查是否已经是YOLO格式 (5个数字)
                parts = line.split()
                if len(parts) == 5:
                    try:
                        # 验证是否为有效的YOLO格式
                        class_id = int(parts[0])
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width = float(parts[3])
                        height = float(parts[4])
                        
                        # 检查范围是否合理
                        if 0 <= x_center <= 1 and 0 <= y_center <= 1 and 0 < width <= 1 and 0 < height <= 1:
                            yolo_lines.append(line)
                            continue
                    except ValueError:
                        pass
                
                # 尝试其他格式转换
                # 这里可以添加更多格式的处理逻辑
                
            return yolo_lines
            
        except Exception as e:
            print(f"⚠️  TXT转换错误 {txt_file}: {e}")
            return []
    
    def convert_xml_to_yolo(self, xml_file, img_width, img_height):
        """转换XML格式标注为YOLO格式"""
        # 这里可以添加XML格式的处理逻辑
        print(f"⚠️  XML格式转换暂未实现: {xml_file}")
        return []
    
    def process_annotation_item(self, item, img_width, img_height):
        """处理单个标注项目"""
        try:
            # 尝试不同的字段名
            class_id = None
            bbox = None
            
            # 查找类别ID或名称
            if 'class' in item:
                class_value = item['class']
                if isinstance(class_value, (int, float)):
                    # 直接使用数字ID
                    class_id = int(class_value)
                else:
                    # 字符串类别名称，需要映射
                    class_id = self.get_class_id(str(class_value).lower())
            else:
                # 查找其他可能的类别字段
                for key in ['label', 'category', 'type', 'name']:
                    if key in item:
                        class_id = self.get_class_id(str(item[key]).lower())
                        break
            
            # 查找边界框
            for key in ['bbox', 'box', 'bounding_box', 'coordinates']:
                if key in item:
                    bbox = item[key]
                    break
            
            # 如果没有找到边界框，尝试查找中心点
            if bbox is None:
                for key in ['center', 'point', 'position']:
                    if key in item:
                        center = item[key]
                        if isinstance(center, (list, tuple)) and len(center) >= 2:
                            # 使用默认大小创建边界框
                            default_size = 20  # 像素
                            x, y = center[0], center[1]
                            bbox = [
                                x - default_size//2, y - default_size//2,
                                x + default_size//2, y + default_size//2
                            ]
                        break
            
            if class_id is None or bbox is None:
                return None
            
            # 转换边界框格式
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                
                # 转换为YOLO格式 (归一化的中心点和宽高)
                x_center = (x1 + x2) / 2.0 / img_width
                y_center = (y1 + y2) / 2.0 / img_height
                width = abs(x2 - x1) / img_width
                height = abs(y2 - y1) / img_height
                
                # 确保值在合理范围内
                x_center = max(0, min(1, x_center))
                y_center = max(0, min(1, y_center))
                width = max(0, min(1, width))
                height = max(0, min(1, height))
                
                return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
            
            return None
            
        except Exception as e:
            print(f"⚠️  处理标注项目错误: {e}")
            return None
    
    def get_class_id(self, class_name):
        """根据类别名称获取类别ID"""
        if not class_name:
            return 0
            
        # 清理类别名称，保留中文字符
        original_name = str(class_name).strip()
        lower_name = original_name.lower()
        
        # 直接匹配（优先匹配原始名称）
        if original_name in self.class_mapping:
            return self.class_mapping[original_name]
        if lower_name in self.class_mapping:
            return self.class_mapping[lower_name]
        
        # 模糊匹配
        for key, value in self.class_mapping.items():
            # 检查是否包含关键词
            if key in lower_name or lower_name in key:
                return value
            # 对于中文，也检查原始名称
            if key in original_name or original_name in key:
                return value
        
        # 特殊处理一些常见的变体
        name_variants = {
            '0': 0, '1': 1, '2': 2,  # 数字字符串
            'class_0': 0, 'class_1': 1, 'class_2': 2,
            'type_0': 0, 'type_1': 1, 'type_2': 2,
        }
        
        if lower_name in name_variants:
            return name_variants[lower_name]
        
        # 默认为第一个类别
        print(f"⚠️  未知类别名称: '{original_name}' (小写: '{lower_name}'), 使用默认类别 0")
        return 0
        
    def setup_directories(self):
        """设置YOLO数据集目录结构"""
        print("创建YOLO数据集目录结构...")
        
        # 主目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 训练、验证、测试目录
        self.train_dir = self.output_dir / "train"
        self.val_dir = self.output_dir / "val"
        self.test_dir = self.output_dir / "test"
        
        for split_dir in [self.train_dir, self.val_dir, self.test_dir]:
            (split_dir / "images").mkdir(parents=True, exist_ok=True)
            (split_dir / "labels").mkdir(parents=True, exist_ok=True)
            
        print("目录结构创建完成")
        
    def get_available_files(self):
        """获取可用的图像和标签文件"""
        print("扫描可用文件...")
        
        # 获取所有处理后的图像文件
        image_files = list(self.processed_images_dir.glob("*.jpg"))
        image_files = [f for f in image_files if f.name != "resize_report.json"]
        
        # 获取所有标签文件
        labels_dir = self.converted_annotations_dir / "labels"
        label_files = list(labels_dir.glob("*.txt"))
        
        # 找到同时有图像和标签的文件
        image_names = {f.stem for f in image_files}
        label_names = {f.stem for f in label_files}
        
        common_names = image_names.intersection(label_names)
        
        print(f"找到 {len(image_files)} 个图像文件")
        print(f"找到 {len(label_files)} 个标签文件")
        print(f"匹配的文件对: {len(common_names)}")
        
        return sorted(list(common_names))
        
    def split_dataset(self, train_ratio=0.7, val_ratio=0.2, test_ratio=0.1):
        """
        步骤3: 分割数据集为训练、验证和测试集
        """
        print(f"\n📊 步骤3: 分割数据集 (训练:{train_ratio}, 验证:{val_ratio}, 测试:{test_ratio})...")
        
        # 使用转换后的标注数据
        if not hasattr(self, 'converted_annotations') or not self.converted_annotations:
            print("❌ 没有可用的转换后标注数据")
            return False
        
        # 获取所有文件名
        file_stems = list(self.converted_annotations.keys())
        
        if not file_stems:
            print("❌ 没有找到可用的文件对")
            return False
        
        # 随机打乱文件列表
        random.seed(42)  # 固定随机种子以确保可重现性
        shuffled_files = file_stems.copy()
        random.shuffle(shuffled_files)
        
        total_files = len(shuffled_files)
        train_count = int(total_files * train_ratio)
        val_count = int(total_files * val_ratio)
        test_count = total_files - train_count - val_count
        
        train_files = shuffled_files[:train_count]
        val_files = shuffled_files[train_count:train_count + val_count]
        test_files = shuffled_files[train_count + val_count:]
        
        print(f"📈 数据集分割结果:")
        print(f"   🏋️  训练集: {len(train_files)} 个文件")
        print(f"   ✅ 验证集: {len(val_files)} 个文件")
        print(f"   🧪 测试集: {len(test_files)} 个文件")
        
        self.train_files = train_files
        self.val_files = val_files
        self.test_files = test_files
        
        return True
    
    def clear_and_copy_files(self):
        """
        步骤4: 清空目标文件夹并复制分组后的文件
        """
        print("\n📁 步骤4: 清空目标文件夹并复制文件...")
        
        # 清空目标目录
        if self.output_dir.exists():
            print(f"🗑️  清空现有目录: {self.output_dir}")
            shutil.rmtree(self.output_dir)
        
        # 创建目录结构
        self.setup_directories()
        
        # 复制文件
        copy_stats = {'train': 0, 'val': 0, 'test': 0}
        
        # 复制训练集
        if hasattr(self, 'train_files') and self.train_files:
            copy_stats['train'] = self.copy_split_files(self.train_files, 'train')
        
        # 复制验证集
        if hasattr(self, 'val_files') and self.val_files:
            copy_stats['val'] = self.copy_split_files(self.val_files, 'val')
        
        # 复制测试集
        if hasattr(self, 'test_files') and self.test_files:
            copy_stats['test'] = self.copy_split_files(self.test_files, 'test')
        
        print(f"📊 文件复制统计:")
        print(f"   🏋️  训练集: {copy_stats['train']} 个文件对")
        print(f"   ✅ 验证集: {copy_stats['val']} 个文件对")
        print(f"   🧪 测试集: {copy_stats['test']} 个文件对")
        
        return sum(copy_stats.values()) > 0
    
    def copy_split_files(self, file_stems, split_name):
        """复制指定分组的文件"""
        copied_count = 0
        
        for file_stem in file_stems:
            if file_stem not in self.converted_annotations:
                continue
            
            annotation_data = self.converted_annotations[file_stem]
            image_file = annotation_data['image_file']
            yolo_annotations = annotation_data['yolo_annotations']
            
            # 复制图片文件
            target_image_dir = self.output_dir / split_name / 'images'
            target_image_path = target_image_dir / image_file.name
            
            try:
                shutil.copy2(image_file, target_image_path)
            except Exception as e:
                print(f"⚠️  复制图片失败 {image_file}: {e}")
                continue
            
            # 创建YOLO标注文件
            target_label_dir = self.output_dir / split_name / 'labels'
            target_label_path = target_label_dir / f"{file_stem}.txt"
            
            try:
                with open(target_label_path, 'w', encoding='utf-8') as f:
                    for line in yolo_annotations:
                        f.write(line + '\n')
                
                copied_count += 1
                
            except Exception as e:
                print(f"⚠️  创建标注文件失败 {target_label_path}: {e}")
                # 如果标注文件创建失败，删除对应的图片文件
                if target_image_path.exists():
                    target_image_path.unlink()
        
        return copied_count
    
    def create_dataset_yaml(self):
        """
        步骤5: 创建数据集配置文件
        """
        print("\n📄 步骤5: 创建数据集配置文件...")
        
        # 使用标准英文类别名称
        standard_class_names = ['pin', 'bracket', 'double_pin']
        
        # 创建dataset.yaml内容
        yaml_content = {
            'path': '.',
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': len(standard_class_names),
            'names': standard_class_names
        }
        
        # 写入dataset.yaml文件
        yaml_file = self.output_dir / 'dataset.yaml'
        
        try:
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True)
            
            print(f"✅ 数据集配置文件已创建: {yaml_file}")
            print(f"📋 配置内容:")
            print(f"   📁 数据集路径: {yaml_content['path']}")
            print(f"   🏷️  类别数量: {yaml_content['nc']}")
            print(f"   📝 类别名称: {yaml_content['names']}")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建配置文件失败: {e}")
            return False
        
    def copy_files(self, file_names, split_name):
        """
        复制文件到对应的分割目录
        
        Args:
            file_names: 文件名列表
            split_name: 分割名称 ('train', 'val', 'test')
        """
        print(f"复制 {split_name} 文件...")
        
        split_dir = getattr(self, f"{split_name}_dir")
        images_dir = split_dir / "images"
        labels_dir = split_dir / "labels"
        
        labels_source_dir = self.converted_annotations_dir / "labels"
        
        copied_count = 0
        for file_name in file_names:
            try:
                # 复制图像文件
                src_image = self.processed_images_dir / f"{file_name}.jpg"
                dst_image = images_dir / f"{file_name}.jpg"
                
                if src_image.exists():
                    shutil.copy2(src_image, dst_image)
                else:
                    print(f"警告: 图像文件不存在 {src_image}")
                    continue
                    
                # 复制标签文件
                src_label = labels_source_dir / f"{file_name}.txt"
                dst_label = labels_dir / f"{file_name}.txt"
                
                if src_label.exists():
                    shutil.copy2(src_label, dst_label)
                    copied_count += 1
                else:
                    print(f"警告: 标签文件不存在 {src_label}")
                    # 删除已复制的图像文件
                    if dst_image.exists():
                        dst_image.unlink()
                        
            except Exception as e:
                print(f"复制文件 {file_name} 时出错: {e}")
                
        print(f"{split_name} 分割完成，成功复制 {copied_count} 个文件对")
        return copied_count
        
    def create_dataset_yaml(self):
        """
        步骤5: 创建数据集配置文件
        """
        print("\n📄 步骤5: 创建数据集配置文件...")
        
        # 定义4个主要类别（按ID顺序）
        main_classes = ['原点', '10', '20', '30']
        
        # 创建dataset.yaml内容
        yaml_content = {
            'path': '.',
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': 4,
            'names': main_classes
        }
        
        # 写入dataset.yaml文件
        yaml_file = self.output_dir / 'dataset.yaml'
        
        try:
            # 写入YAML格式
            with open(yaml_file, 'w', encoding='utf-8') as f:
                f.write(f"# YOLO数据集配置文件\n")
                f.write(f"# 创建时间: {datetime.now().isoformat()}\n\n")
                f.write(f"path: {yaml_content['path']}\n")
                f.write(f"train: {yaml_content['train']}\n")
                f.write(f"val: {yaml_content['val']}\n")
                f.write(f"test: {yaml_content['test']}\n\n")
                f.write(f"nc: {yaml_content['nc']}\n")
                f.write(f"names: {yaml_content['names']}\n")
            
            print(f"✅ 数据集配置文件已创建: {yaml_file}")
            print(f"📋 配置内容:")
            print(f"   📁 数据集路径: {yaml_content['path']}")
            print(f"   🏷️  类别数量: {yaml_content['nc']}")
            print(f"   📝 类别名称: {yaml_content['names']}")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建配置文件失败: {e}")
            return False
        
    def create_dataset_info(self, train_count, val_count, test_count):
        """创建数据集信息文件"""
        dataset_info = {
            "creation_time": datetime.now().isoformat(),
            "dataset_path": str(self.output_dir.absolute()),
            "source_images": str(self.processed_images_dir.absolute()),
            "source_annotations": str(self.converted_annotations_dir.absolute()),
            "statistics": {
                "total_files": train_count + val_count + test_count,
                "train_files": train_count,
                "val_files": val_count,
                "test_files": test_count,
                "train_ratio": train_count / (train_count + val_count + test_count),
                "val_ratio": val_count / (train_count + val_count + test_count),
                "test_ratio": test_count / (train_count + val_count + test_count)
            },
            "classes": {
                "count": 1,
                "names": ["pin"],
                "description": "卡钉检测数据集"
            },
            "image_format": {
                "size": "1024x1024",
                "format": "JPG",
                "channels": 3
            },
            "annotation_format": "YOLO (class_id center_x center_y width height)"
        }
        
        info_path = self.output_dir / "dataset_info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
            
        print(f"数据集信息文件已保存: {info_path}")
        return dataset_info
        
    def create_dataset(self):
        """创建完整的YOLO数据集"""
        print("开始创建YOLO数据集...")
        
        # 获取可用文件
        available_files = self.get_available_files()
        
        if not available_files:
            print("错误: 没有找到匹配的图像和标签文件")
            return False
            
        # 分割数据集
        train_files, val_files, test_files = self.split_dataset(available_files)
        
        # 复制文件
        train_count = self.copy_files(train_files, "train")
        val_count = self.copy_files(val_files, "val")
        test_count = self.copy_files(test_files, "test")
        
        # 创建配置文件
        yaml_path = self.create_dataset_yaml()
        dataset_info = self.create_dataset_info(train_count, val_count, test_count)
        
        print(f"\n✅ YOLO数据集创建完成!")
        print(f"📁 数据集路径: {self.output_dir}")
        print(f"📊 统计信息:")
        print(f"   - 训练集: {train_count} 文件")
        print(f"   - 验证集: {val_count} 文件")
        print(f"   - 测试集: {test_count} 文件")
        print(f"   - 总计: {train_count + val_count + test_count} 文件")
        print(f"📄 配置文件: {yaml_path}")
        
        return True

    def process_dataset(self, train_ratio=0.7, val_ratio=0.2, test_ratio=0.1):
        """
        完整的数据集处理流程
        """
        print("🚀 开始智能数据集准备流程...")
        print("=" * 60)
        
        try:
            # 步骤1: 检查和分析文件
            if not self.check_and_analyze_files():
                print("❌ 文件检查失败，流程终止")
                return False
            
            # 步骤2: 转换标注格式
            if not self.convert_annotations_to_yolo():
                print("❌ 标注转换失败，流程终止")
                return False
            
            # 步骤3: 分割数据集
            if not self.split_dataset(train_ratio, val_ratio, test_ratio):
                print("❌ 数据集分割失败，流程终止")
                return False
            
            # 步骤4: 清空并复制文件
            if not self.clear_and_copy_files():
                print("❌ 文件复制失败，流程终止")
                return False
            
            # 步骤5: 创建配置文件
            if not self.create_dataset_yaml():
                print("❌ 配置文件创建失败，流程终止")
                return False
            
            print("\n" + "=" * 60)
            print("🎉 智能数据集准备完成!")
            print(f"📁 输出目录: {self.output_dir}")
            print(f"📄 配置文件: {self.output_dir / 'dataset.yaml'}")
            print("\n✨ 数据集已准备就绪，可以开始训练!")
            
            return True
            
        except Exception as e:
            print(f"❌ 处理过程中发生错误: {e}")
            print(f"📍 错误类型: {type(e).__name__}")
            print(f"📍 错误详情: {str(e)}")
            print("\n🔍 详细错误堆栈:")
            traceback.print_exc()
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='智能数据集准备工具 - 自动处理标注数据并准备YOLO训练数据集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""使用示例:
  python create_yolo_dataset.py --source "D:/my_annotations" 
  python create_yolo_dataset.py --source "D:/my_annotations" --train-ratio 0.8 --val-ratio 0.15 --test-ratio 0.05
  
支持的标注格式:
  - JSON格式 (.json)
  - TXT格式 (.txt) 
  - XML格式 (.xml) [部分支持]
  
支持的图片格式:
  - JPG, JPEG, PNG, BMP, TIFF
        """
    )
    
    parser.add_argument('--source', '-s', type=str, required=True,
                        help='标注数据源目录路径（包含图片和标注文件）')
    parser.add_argument('--output', '-o', type=str, 
                        default=r'd:\OneDrive\24.Visual AI\data\yolo_dataset',
                        help='输出目录路径（默认: 云端训练脚本要求的路径）')
    parser.add_argument('--train-ratio', type=float, default=0.7,
                        help='训练集比例 (默认: 0.7)')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='验证集比例 (默认: 0.2)')
    parser.add_argument('--test-ratio', type=float, default=0.1,
                        help='测试集比例 (默认: 0.1)')
    
    args = parser.parse_args()
    
    # 验证输入路径
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ 错误: 源目录不存在: {args.source}")
        sys.exit(1)
    
    if not source_path.is_dir():
        print(f"❌ 错误: 源路径不是目录: {args.source}")
        sys.exit(1)
    
    # 验证比例
    total_ratio = args.train_ratio + args.val_ratio + args.test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        print(f"❌ 错误: 比例总和应为1.0，当前为 {total_ratio}")
        sys.exit(1)
    
    if args.train_ratio <= 0 or args.val_ratio <= 0 or args.test_ratio <= 0:
        print("❌ 错误: 所有比例都必须大于0")
        sys.exit(1)
    
    print("🔧 智能数据集准备工具")
    print("=" * 60)
    print(f"📂 源目录: {args.source}")
    print(f"📁 输出目录: {args.output}")
    print(f"📊 数据分割: 训练{args.train_ratio} | 验证{args.val_ratio} | 测试{args.test_ratio}")
    print("=" * 60)
    
    # 创建数据集处理器
    try:
        preparer = SmartDatasetPreparer(args.source, args.output)
        success = preparer.process_dataset(args.train_ratio, args.val_ratio, args.test_ratio)
        
        if success:
            print("\n🎊 任务完成! 数据集已准备就绪!")
            print("\n📋 下一步操作:")
            print("   1. 检查生成的数据集结构")
            print("   2. 运行云端训练脚本: python start_cloud_gpu_training_final.py")
            print("   3. 使用监控脚本: python real_time_training_monitor.py")
        else:
            print("\n❌ 任务失败! 请检查错误信息并重试")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行错误: {e}")
        print(f"📍 错误类型: {type(e).__name__}")
        print(f"📍 错误详情: {str(e)}")
        print("\n🔍 详细错误堆栈:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
