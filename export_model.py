import argparse
from ultralytics import YOLO

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=str, required=True)
    p.add_argument('--format', type=str, default='onnx')  # onnx, openvino, torchscript, engine...
    return p.parse_args()

def main():
    args = parse_args()
    m = YOLO(args.model)
    out = m.export(format=args.format)
    print(f'[export] 导出完成: {out}')

if __name__ == '__main__':
    main()
