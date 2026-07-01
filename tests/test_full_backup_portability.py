import json

from ui import shared


def test_full_backup_export_contains_only_current_user_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    first_id = "a" * 32
    second_id = "b" * 32
    first = shared.default_store()
    second = shared.default_store()
    first["todo_items"].append({"title": "Tarea Ana"})
    first["events"].append({"title": "Evento Ana"})
    second["todo_items"].append({"title": "Tarea Bea"})
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)

    payload = json.loads(shared.full_backup_export_json(shared.load_store(first_id)))

    assert payload["kind"] == "full_user_backup"
    assert payload["content"]["todo_items"] == [{"title": "Tarea Ana"}]
    assert payload["content"]["events"] == [{"title": "Evento Ana"}]
    assert "Tarea Bea" not in json.dumps(payload, ensure_ascii=False)


def test_full_backup_import_valid_data_overwrites_current_store():
    store = shared.default_store()
    store["todo_items"].append({"title": "Vieja"})
    source = shared.default_store()
    source["todo_items"].append({"title": "Nueva"})
    source["events"].append({"title": "Evento nuevo"})
    source["habits"].append({"title": "Leer", "history": {}})
    source["settings"]["display_mode"] = "Oscuro"
    payload = shared.full_backup_export_payload(source)

    imported, errors = shared.validate_full_backup_import(payload)
    assert errors == []

    shared.apply_full_backup_import(store, imported)

    assert [item["title"] for item in store["todo_items"]] == ["Nueva"]
    assert [item["title"] for item in store["events"]] == ["Evento nuevo"]
    assert [item["title"] for item in store["habits"]] == ["Leer"]
    assert store["settings"]["display_mode"] == "Oscuro"


def test_full_backup_import_rejects_invalid_file():
    imported, errors = shared.validate_full_backup_import(
        {
            "version": 1,
            "app": "Academic Planning Crew",
            "kind": "full_user_backup",
            "content": {"todo_items": "no es lista"},
        }
    )

    assert imported is None
    assert errors


def test_full_backup_does_not_export_or_import_sensitive_data():
    store = shared.default_store()
    store["password"] = "plain"
    store["todo_items"].append(
        {
            "title": "Privada",
            "password": "plain",
            "nested": {"hash": "abc", "safe": "ok"},
        }
    )
    store["settings"]["api_key"] = "secret"

    payload = shared.full_backup_export_payload(store)
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "plain" not in dumped
    assert "secret" not in dumped
    assert "abc" not in dumped

    imported, errors = shared.validate_full_backup_import(payload)
    assert errors == []
    target = shared.default_store()
    shared.apply_full_backup_import(target, imported)

    dumped_target = json.dumps(target, ensure_ascii=False)
    assert "plain" not in dumped_target
    assert "secret" not in dumped_target
    assert "abc" not in dumped_target
    assert target["todo_items"][0]["nested"]["safe"] == "ok"


def test_full_backup_import_does_not_affect_other_users(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    first_id = "a" * 32
    second_id = "b" * 32
    first = shared.default_store()
    second = shared.default_store()
    first["todo_items"].append({"title": "Antes"})
    second["todo_items"].append({"title": "Bea intacta"})
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)
    backup_source = shared.default_store()
    backup_source["todo_items"].append({"title": "Restaurada"})
    imported, errors = shared.validate_full_backup_import(
        shared.full_backup_export_payload(backup_source)
    )
    assert errors == []

    first_loaded = shared.load_store(first_id)
    shared.apply_full_backup_import(first_loaded, imported)
    shared.save_store(first_loaded, first_id)

    assert [item["title"] for item in shared.load_store(first_id)["todo_items"]] == ["Restaurada"]
    assert [item["title"] for item in shared.load_store(second_id)["todo_items"]] == ["Bea intacta"]
