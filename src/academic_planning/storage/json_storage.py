"""JSON storage backend compatible with the current file layout."""

import re
import shutil
from datetime import datetime
from pathlib import Path

from academic_planning.storage.base import StorageBackend
from academic_planning.tools.database_tool import create_json_backup, read_json, write_json


USER_STORE_FILENAME = "academic_data.json"


class JSONStorage(StorageBackend):
    """Persist user data, backups and auth records in local JSON files."""

    def __init__(self, data_dir, auth_users_path=None):
        self.data_dir = Path(data_dir)
        self.users_dir = self.data_dir / "users"
        self.legacy_store_path = self.data_dir / "academic_planning_store.json"
        self.legacy_backup_dir = self.data_dir / "backups"
        self.deleted_accounts_dir = self.data_dir / "deleted_accounts"
        self.auth_users_path = Path(auth_users_path) if auth_users_path else self.data_dir / "auth" / "users.json"

    def validate_user_id(self, user_id):
        clean_user_id = str(user_id or "").strip()
        if not clean_user_id:
            return None
        if not re.fullmatch(r"[a-f0-9]{32}", clean_user_id):
            raise ValueError("Identificador de usuario invalido.")
        return clean_user_id

    def user_data_dir(self, user_id=None):
        clean_user_id = self.validate_user_id(user_id)
        if not clean_user_id:
            return self.data_dir
        return self.users_dir / clean_user_id

    def user_store_path(self, user_id=None):
        clean_user_id = self.validate_user_id(user_id)
        if not clean_user_id:
            return self.legacy_store_path
        return self.user_data_dir(clean_user_id) / USER_STORE_FILENAME

    def user_backup_dir(self, user_id=None):
        clean_user_id = self.validate_user_id(user_id)
        if not clean_user_id:
            return self.legacy_backup_dir
        return self.user_data_dir(clean_user_id) / "backups"

    def load_user_data(self, user_id):
        return read_json(self.user_store_path(user_id), {})

    def save_user_data(self, user_id, data):
        write_json(self.user_store_path(user_id), data)
        return True

    def backup_user_data(self, user_id, data=None, reason="manual"):
        payload = self.load_user_data(user_id) if data is None else data
        return create_json_backup(self.user_backup_dir(user_id), payload, reason)

    def export_user_data(self, user_id):
        return self.load_user_data(user_id)

    def import_user_data(self, user_id, data):
        self.save_user_data(user_id, data)
        return True

    def delete_user_data(self, user_id):
        source = self.user_data_dir(user_id)
        if not source.exists():
            return None
        self.deleted_accounts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_user_id = self.validate_user_id(user_id)
        destination = self.deleted_accounts_dir / f"{clean_user_id}_{timestamp}"
        counter = 1
        while destination.exists():
            destination = self.deleted_accounts_dir / f"{clean_user_id}_{timestamp}_{counter}"
            counter += 1
        shutil.move(str(source), str(destination))
        return destination

    def load_auth_users(self):
        registry = read_json(self.auth_users_path, {"version": 1, "users": []})
        if not isinstance(registry, dict) or not isinstance(registry.get("users"), list):
            return {"version": 1, "users": []}
        registry.setdefault("version", 1)
        return registry

    def save_auth_users(self, users):
        registry = users if isinstance(users, dict) else {"version": 1, "users": list(users or [])}
        registry.setdefault("version", 1)
        registry.setdefault("users", [])
        write_json(self.auth_users_path, registry)
        return True
