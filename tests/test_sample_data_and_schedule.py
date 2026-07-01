from datetime import date, time
from types import SimpleNamespace

from ui import shared


def test_schedule_save_works_in_light_and_dark_modes(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    user_id = "d" * 32

    for mode in ("Claro", "Oscuro"):
        store = shared.default_store()
        shared.set_display_mode(store, mode)

        block, error = shared.add_schedule_block(
            store,
            f"Programacion {mode}",
            "Lunes",
            time(8, 0),
            time(9, 0),
            "Clase",
            "#8b5cf6",
        )

        assert error == ""
        assert block["title"] == f"Programacion {mode}"
        assert shared.save_store(store, user_id)
        reloaded = shared.load_store(user_id)
        assert reloaded["settings"]["display_mode"] == mode
        assert reloaded["availability"][0]["title"] == f"Programacion {mode}"


def test_sample_data_loads_realistic_sections():
    store = shared.default_store()

    sample = shared.apply_sample_data(store, reference_day=date(2026, 7, 1))

    assert len(sample["availability"]) == 40
    assert {item["title"] for item in store["availability"]} >= {
        "Matemática",
        "Programación",
        "Física",
        "Inglés",
        "Literatura",
    }
    assert ("Lunes", "09:00", "09:20") not in {
        (item["day_of_week"], item["start_time"], item["end_time"])
        for item in store["availability"]
    }
    assert ("Viernes", "12:20", "13:00", "Inglés") in {
        (item["day_of_week"], item["start_time"], item["end_time"], item["title"])
        for item in store["availability"]
    }
    assert len(store["events"]) >= 4
    assert any(item.get("done") for item in store["todo_items"])
    assert len(store["habits"]) >= 5
    assert store["weekly_goals"][0]["title"]
    assert store["settings"]["sample_data_loaded"] is True
    assert all(shared.is_demo_item(item) for item in store["availability"])


def test_delete_sample_data_keeps_manual_user_data():
    store = shared.default_store()
    shared.apply_sample_data(store, reference_day=date(2026, 7, 1))
    manual_todo = {"todo_id": "manual", "title": "Tarea manual", "date": "2026-07-05"}
    manual_event = {"event_id": "manual", "title": "Evento manual", "date": "2026-07-06"}
    store["todo_items"].append(manual_todo)
    store["events"].append(manual_event)

    counts = shared.remove_sample_data(store, create_backup_first=False)

    assert sum(counts.values()) > 0
    assert store["todo_items"] == [manual_todo]
    assert store["events"] == [manual_event]
    assert store["availability"] == []
    assert store["settings"]["sample_data_loaded"] is False


def test_sample_data_removal_is_scoped_to_current_user(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    first_id = "e" * 32
    second_id = "f" * 32

    first = shared.default_store()
    second = shared.default_store()
    shared.apply_sample_data(first, reference_day=date(2026, 7, 1))
    second["todo_items"].append({"todo_id": "manual", "title": "Privada", "date": "2026-07-05"})
    shared.save_store(first, first_id)
    shared.save_store(second, second_id)

    loaded_first = shared.load_store(first_id)
    shared.remove_sample_data(loaded_first, create_backup_first=False)
    shared.save_store(loaded_first, first_id)

    assert shared.load_store(first_id)["availability"] == []
    assert shared.load_store(second_id)["todo_items"][0]["title"] == "Privada"


def test_registration_store_with_sample_data_preserves_light_theme(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", SimpleNamespace(session_state=fake_session))
    shared.set_session_display_mode("Claro")
    store = shared.default_store()

    selected = shared.initialize_store_theme_from_session(store)
    shared.apply_sample_data(store, reference_day=date(2026, 7, 1))

    assert selected == "Claro"
    assert store["settings"]["display_mode"] == "Claro"
    assert "pending_display_mode" not in fake_session
    assert fake_session["theme_initialized"] is True


def test_registration_store_with_sample_data_preserves_dark_theme(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", SimpleNamespace(session_state=fake_session))
    shared.set_session_display_mode("Oscuro")
    store = shared.default_store()

    shared.initialize_store_theme_from_session(store)
    shared.apply_sample_data(store, reference_day=date(2026, 7, 1))

    assert store["settings"]["display_mode"] == "Oscuro"
    assert "pending_display_mode" not in fake_session
    assert all(shared.is_demo_item(item) for item in store["availability"])


def test_registration_store_without_sample_data_preserves_selected_theme(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", SimpleNamespace(session_state=fake_session))
    shared.set_session_display_mode("Oscuro")
    store = shared.default_store()

    shared.initialize_store_theme_from_session(store)

    assert store["settings"]["display_mode"] == "Oscuro"
    assert store["availability"] == []
    assert "pending_display_mode" not in fake_session


def test_pending_theme_is_applied_once_without_alternation(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", SimpleNamespace(session_state=fake_session))
    store = shared.default_store()
    shared.set_display_mode(store, "Claro")
    shared.set_session_display_mode("Oscuro")

    first_apply = shared.apply_pending_session_theme(store)
    second_apply = shared.apply_pending_session_theme(store)

    assert first_apply is True
    assert second_apply is False
    assert store["settings"]["display_mode"] == "Oscuro"
    assert "pending_display_mode" not in fake_session


def test_manual_auth_theme_change_updates_pending_only_when_changed(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", SimpleNamespace(session_state=fake_session))

    shared.set_session_display_mode("Oscuro")
    shared.set_session_display_mode("Oscuro")

    assert fake_session["preferred_display_mode"] == "Oscuro"
    assert fake_session["pending_display_mode"] == "Oscuro"
