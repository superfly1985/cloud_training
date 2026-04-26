class ConfigBindingManager:
    """UI 与配置的双向字段映射"""

    def __init__(self):
        self._load_mapping = {
            "server_config": {
                "hostname": "hostname_var",
                "port": "port_var",
                "username": "username_var",
                "password": "password_var",
            },
            "dataset_config": {
                "local_path": "dataset_path_var",
                "remote_path": "remote_dataset_path_var",
                "dataset_name": "dataset_name_var",
                "num_classes": "num_classes_var",
            },
            "training_config": {
                "epochs": "epochs_var",
                "batch_size": "batch_size_var",
                "learning_rate": "learning_rate_var",
                "image_size": "image_size_var",
                "base_model": "base_model_var",
                "model_name_suffix": "model_name_suffix_var",
                "augment_scale": "augment_scale_var",
                "augment_fliplr": "augment_fliplr_var",
                "augment_hsv_h": "augment_hsv_h_var",
                "augment_hsv_s": "augment_hsv_s_var",
                "augment_hsv_v": "augment_hsv_v_var",
                "augment_flipud": "flipud_var",
                "augment_perspective": "perspective_var",
            },
        }
        self._update_mapping = {
            "server_config": {
                "hostname": ("hostname_var", str),
                "port": ("port_var", int),
                "username": ("username_var", str),
                "password": ("password_var", str),
            },
            "dataset_config": {
                "local_path": ("dataset_path_var", str),
                "remote_path": ("remote_dataset_path_var", str),
                "dataset_name": ("dataset_name_var", str),
            },
            "training_config": {
                "epochs": ("epochs_var", int),
                "batch_size": ("batch_size_var", int),
                "learning_rate": ("learning_rate_var", float),
                "image_size": ("image_size_var", int),
                "base_model": ("base_model_var", str),
                "model_name_suffix": ("model_name_suffix_var", str),
                "augment_scale": ("augment_scale_var", float),
                "augment_fliplr": ("augment_fliplr_var", float),
                "augment_flipud": ("flipud_var", float),
                "augment_perspective": ("perspective_var", float),
                "augment_hsv_h": ("augment_hsv_h_var", float),
                "augment_hsv_s": ("augment_hsv_s_var", float),
                "augment_hsv_v": ("augment_hsv_v_var", float),
            },
        }

    def load_config_to_ui(self, ui, config_manager):
        for section, fields in self._load_mapping.items():
            if not hasattr(config_manager, section):
                continue
            config_data = getattr(config_manager, section)
            for key, ui_var_name in fields.items():
                if key not in config_data or not hasattr(ui, ui_var_name):
                    continue
                getattr(ui, ui_var_name).set(str(config_data[key]))

    def update_config_from_ui(self, ui, config_manager):
        for section, fields in self._update_mapping.items():
            if not hasattr(config_manager, section):
                continue
            config_data = getattr(config_manager, section)
            for key, (ui_var_name, type_func) in fields.items():
                if not hasattr(ui, ui_var_name):
                    continue
                raw_value = getattr(ui, ui_var_name).get()
                value = raw_value.strip() if hasattr(raw_value, "strip") else raw_value
                try:
                    if value != "":
                        config_data[key] = type_func(value)
                except (ValueError, TypeError):
                    continue
