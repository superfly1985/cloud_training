import os
import yaml


_config = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "app_config.yaml")


def load_config(path=None):
    global _config
    cfg_path = path or CONFIG_PATH
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    _resolve_paths()
    return _config


def _resolve_paths():
    for key in ("base_path", "datasets_path", "runs_path", "pretrained_path",
                "temp_path", "logs_path", "db_path"):
        raw = _config["data"].get(key, "")
        if raw and not os.path.isabs(raw):
            _config["data"][key] = os.path.normpath(os.path.join(PROJECT_ROOT, raw))
    runtime = _config.get("runtime", {})
    for key in ("deploy_state_path", "init_state_path", "env_snapshot_dir"):
        raw = runtime.get(key, "")
        if raw and not os.path.isabs(raw):
            runtime[key] = os.path.normpath(os.path.join(PROJECT_ROOT, raw))


def get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_data_dir(key: str) -> str:
    cfg = get_config()
    path = cfg["data"].get(key, "")
    if path:
        os.makedirs(path, exist_ok=True)
    return path


def get_runtime_path(key: str) -> str:
    cfg = get_config()
    runtime = cfg.get("runtime", {})
    path = runtime.get(key, "")
    if path:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return path
