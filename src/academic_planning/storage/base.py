"""Storage backend interface."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Persistence contract used by the UI and authentication layers."""

    @abstractmethod
    def load_user_data(self, user_id):
        raise NotImplementedError

    @abstractmethod
    def save_user_data(self, user_id, data):
        raise NotImplementedError

    @abstractmethod
    def backup_user_data(self, user_id, data=None, reason="manual"):
        raise NotImplementedError

    @abstractmethod
    def export_user_data(self, user_id):
        raise NotImplementedError

    @abstractmethod
    def import_user_data(self, user_id, data):
        raise NotImplementedError

    @abstractmethod
    def delete_user_data(self, user_id):
        raise NotImplementedError

    @abstractmethod
    def load_auth_users(self):
        raise NotImplementedError

    @abstractmethod
    def save_auth_users(self, users):
        raise NotImplementedError
