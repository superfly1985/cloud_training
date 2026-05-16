class FileManagerManager:
    """远程文件管理业务层"""

    def __init__(self, server_manager):
        self.server_manager = server_manager

    def list_dir(self, remote_dir):
        return self.server_manager.list_remote_dir(remote_dir)

    def delete_path(self, remote_path):
        return self.server_manager.remove_remote_path(remote_path)
