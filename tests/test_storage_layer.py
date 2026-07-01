import json

from academic_planning.auth import UserRegistry
from academic_planning.storage.factory import get_storage
from academic_planning.storage.json_storage import JSONStorage
from ui import shared


def test_get_storage_returns_json_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    storage = get_storage(data_dir=tmp_path / "data")

    assert isinstance(storage, JSONStorage)


def test_json_storage_loads_and_saves_user_data(tmp_path):
    storage = JSONStorage(tmp_path / "data")
    user_id = "a" * 32
    data = {"todo_items": [{"title": "Privada"}]}

    assert storage.save_user_data(user_id, data)

    assert storage.load_user_data(user_id) == data
    assert (tmp_path / "data" / "users" / user_id / "academic_data.json").exists()


def test_json_storage_keeps_multiuser_data_separated(tmp_path):
    storage = JSONStorage(tmp_path / "data")
    first_id = "a" * 32
    second_id = "b" * 32

    storage.save_user_data(first_id, {"todo_items": [{"title": "Ana"}]})
    storage.save_user_data(second_id, {"todo_items": [{"title": "Bea"}]})

    assert storage.load_user_data(first_id)["todo_items"][0]["title"] == "Ana"
    assert storage.load_user_data(second_id)["todo_items"][0]["title"] == "Bea"
    assert "Bea" not in json.dumps(storage.export_user_data(first_id), ensure_ascii=False)


def test_json_storage_exports_and_imports_user_data(tmp_path):
    storage = JSONStorage(tmp_path / "data")
    source_id = "a" * 32
    target_id = "b" * 32
    source = {"events": [{"title": "Examen"}]}

    storage.save_user_data(source_id, source)
    exported = storage.export_user_data(source_id)
    storage.import_user_data(target_id, exported)

    assert storage.load_user_data(target_id) == source


def test_auth_uses_storage_and_keeps_login_working(tmp_path):
    registry_path = tmp_path / "data" / "auth" / "users.json"
    registry = UserRegistry(registry_path)

    user, error = registry.register("ana@example.com", "strong-pass", "Ana")

    assert error == ""
    assert registry.authenticate("ana@example.com", "strong-pass")["user_id"] == user["user_id"]
    assert registry.storage.load_auth_users()["users"][0]["email"] == "ana@example.com"


def test_storage_delete_account_archives_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    user_id = "a" * 32
    store = shared.default_store()
    store["todo_items"].append({"title": "Conservar en archivo"})
    shared.save_store(store, user_id)

    archived_path = shared.archive_user_data(user_id)

    assert archived_path.exists()
    assert (archived_path / "academic_data.json").exists()
    assert shared.load_store(user_id)["todo_items"] == []


def test_demo_data_round_trip_stays_in_current_user(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    first_id = "a" * 32
    second_id = "b" * 32
    first = shared.default_store()
    second = shared.default_store()
    second["todo_items"].append({"title": "Manual"})

    shared.apply_sample_data(first)
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)

    loaded_first = shared.load_store(first_id)
    counts = shared.remove_sample_data(loaded_first, create_backup_first=False)
    shared.save_store(loaded_first, first_id)

    assert sum(counts.values()) > 0
    assert shared.load_store(first_id)["availability"] == []
    assert shared.load_store(second_id)["todo_items"][0]["title"] == "Manual"
