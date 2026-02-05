import os
import shutil
from pathlib import Path

MODELS = [
    'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt'
]

def find_cache_candidates(name: str):
    candidates = []
    home = Path.home()
    # 常见缓存位置（不同环境略有差异）
    candidates.append(home / '.cache' / 'Ultralytics' / name)
    local = os.environ.get('LOCALAPPDATA')
    if local:
        candidates.append(Path(local) / 'Ultralytics' / name)
    roaming = os.environ.get('APPDATA')
    if roaming:
        candidates.append(Path(roaming) / 'Ultralytics' / name)
    return [p for p in candidates if p.exists()]

def main():
    try:
        from ultralytics import YOLO
    except Exception as e:
        print('[download] 请先安装 ultralytics:', e)
        return
    out_dir = Path('models')
    out_dir.mkdir(exist_ok=True)
    for m in MODELS:
        print(f'[download] 准备: {m}')
        try:
            model = YOLO(m)  # 触发自动下载
            print(f'[download] 已加载: {m}')
        except Exception as e:
            print(f'[download] 加载失败 {m}: {e}')
        # 尝试从缓存目录复制到本地 models/
        for c in find_cache_candidates(m):
            dst = out_dir / m
            try:
                shutil.copy2(c, dst)
                print(f'[download] 已复制到 {dst}')
                break
            except Exception as e:
                print(f'[download] 复制失败 {c} -> {dst}: {e}')
    print('[download] 完成')

if __name__ == '__main__':
    main()
