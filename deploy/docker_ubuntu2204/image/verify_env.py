import importlib
import sys


def get_ver(module_name):
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:
        raise RuntimeError(f"import {module_name} failed: {exc}") from exc
    return getattr(mod, "__version__", "unknown")


def main():
    expected = {
        "torch": "2.5.1",
        "torchvision": "0.20.1",
        "torchaudio": "2.5.1",
        "ultralytics": "8.4.41",
        "numpy": "1.26.4",
        "cv2": "4.7.0",
        "onnx": "1.16.1",
        "tensorflow": "2.19.1",
        "google.protobuf": "5.29.5",
    }

    print("Python:", sys.version.replace("\n", " "))
    errors = []

    for module_name, should_start in expected.items():
        version = get_ver(module_name)
        print(f"{module_name}: {version}")
        if not str(version).startswith(should_start):
            errors.append(f"{module_name} version mismatch: got {version}, expected prefix {should_start}")

    if errors:
        print("\n[VERIFY FAILED]")
        for item in errors:
            print("-", item)
        raise SystemExit(1)

    print("\n[VERIFY OK] All key versions match expected baseline.")


if __name__ == "__main__":
    main()
