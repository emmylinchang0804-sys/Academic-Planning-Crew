import json

from ui import shared


def configure_storage(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    monkeypatch.setattr(shared, "STORE_PATH", data_dir / "academic_planning_store.json")
    monkeypatch.setattr(shared, "BACKUP_DIR", data_dir / "backups")
    return data_dir


def test_delete_demo_data_uses_storage_and_current_user(tmp_path, monkeypatch):
    configure_storage(tmp_path, monkeypatch)
    first_id = "a" * 32
    second_id = "b" * 32
    first = shared.default_store()
    second = shared.default_store()
    shared.apply_sample_data(first)
    second["todo_items"].append({"title": "Privada"})
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)

    counts, error = shared.delete_sample_data_for_user(first_id)

    assert error == ""
    assert sum(counts.values()) > 0
    assert shared.load_store(first_id)["availability"] == []
    assert [item["title"] for item in shared.load_store(second_id)["todo_items"]] == ["Privada"]
    assert list((tmp_path / "data" / "users" / first_id / "backups").glob("*.json"))


def test_import_schedule_uses_storage(tmp_path, monkeypatch):
    configure_storage(tmp_path, monkeypatch)
    user_id = "a" * 32
    store = shared.default_store()
    store["availability"].append(
        {
            "availability_id": "old",
            "title": "Matematica",
            "day_index": 0,
            "start_time": "08:00",
            "end_time": "09:00",
        }
    )
    shared.save_store(store, user_id)
    payload = {
        "version": 1,
        "app": "Academic Planning Crew",
        "content": {
            "availability": [
                {
                    "availability_id": "new",
                    "title": "Historia",
                    "day_index": 2,
                    "start_time": "10:00",
                    "end_time": "11:00",
                }
            ],
            "courses": [{"name": "Historia"}],
            "settings": {"week_view_mode": "grid"},
        },
    }

    ok, message = shared.import_schedule_for_user(user_id, payload, replace=False)

    loaded = shared.load_store(user_id)
    assert ok, message
    assert [item["title"] for item in loaded["availability"]] == ["Matematica", "Historia"]
    assert loaded["courses"] == [{"name": "Historia"}]
    assert loaded["settings"]["week_view_mode"] == "grid"
    assert list((tmp_path / "data" / "users" / user_id / "backups").glob("*.json"))


def test_export_schedule_uses_storage(tmp_path, monkeypatch):
    configure_storage(tmp_path, monkeypatch)
    user_id = "a" * 32
    store = shared.default_store()
    store["availability"].append(
        {
            "availability_id": "av_1",
            "title": "Biologia",
            "day_index": 1,
            "start_time": "07:00",
            "end_time": "08:00",
        }
    )
    shared.save_store(store, user_id)

    exported, error = shared.export_schedule_for_user(user_id)

    payload = json.loads(exported)
    assert error == ""
    assert payload["content"]["availability"][0]["title"] == "Biologia"


def test_invalid_schedule_import_does_not_break_existing_data(tmp_path, monkeypatch):
    configure_storage(tmp_path, monkeypatch)
    user_id = "a" * 32
    store = shared.default_store()
    store["todo_items"].append({"title": "Conservar"})
    store["availability"].append(
        {
            "availability_id": "safe",
            "title": "Seguro",
            "day_index": 3,
            "start_time": "12:00",
            "end_time": "13:00",
        }
    )
    shared.save_store(store, user_id)

    ok, message = shared.import_schedule_for_user(
        user_id,
        {"version": 1, "app": "Academic Planning Crew", "content": {"availability": "invalid"}},
    )

    loaded = shared.load_store(user_id)
    assert not ok
    assert "availability" in message or "seccion" in message.lower()
    assert [item["title"] for item in loaded["todo_items"]] == ["Conservar"]
    assert loaded["availability"][0]["title"] == "Seguro"


def test_account_actions_only_affect_current_user(tmp_path, monkeypatch):
    configure_storage(tmp_path, monkeypatch)
    first_id = "a" * 32
    second_id = "b" * 32
    first = shared.default_store()
    second = shared.default_store()
    first["availability"].append(
        {
            "availability_id": "first",
            "title": "Original",
            "day_index": 0,
            "start_time": "08:00",
            "end_time": "09:00",
        }
    )
    second["availability"].append(
        {
            "availability_id": "second",
            "title": "Otro usuario",
            "day_index": 1,
            "start_time": "09:00",
            "end_time": "10:00",
        }
    )
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)
    payload = {
        "version": 1,
        "app": "Academic Planning Crew",
        "content": {
            "availability": [
                {
                    "availability_id": "replacement",
                    "title": "Reemplazo",
                    "day_index": 4,
                    "start_time": "14:00",
                    "end_time": "15:00",
                }
            ]
        },
    }

    ok, message = shared.import_schedule_for_user(first_id, payload, replace=True)

    assert ok, message
    assert [item["title"] for item in shared.load_store(first_id)["availability"]] == ["Reemplazo"]
    assert [item["title"] for item in shared.load_store(second_id)["availability"]] == ["Otro usuario"]
