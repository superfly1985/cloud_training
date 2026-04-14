import argparse
from ultralytics import YOLO

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=str, default='yolov8n.pt')
    p.add_argument('--data', type=str, required=True)
    p.add_argument('--epochs', type=int, default=100)
    p.add_argument('--imgsz', type=int, default=640)
    p.add_argument('--device', type=str, default='')  # ''=自动, 'cpu' 或 '0'
    return p.parse_args()

def main():
    args = parse_args()
    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, device=args.device)
    print('[train] 训练完成，输出目录位于 runs/detect/train')

if __name__ == '__main__':
    main()
