from ui import shared


def test_empty_habit_is_not_saved():
    store = shared.default_store()

    saved, message = shared.create_habit(store, "   ")

    assert saved is False
    assert "nombre" in message
    assert store["habits"] == []


def test_empty_activity_is_not_saved():
    store = shared.default_store()
    result = {
        "activity": {"title": "   ", "course": "General"},
        "todo_items": [{"title": "Paso de prueba", "date": "2099-01-01"}],
    }

    saved, message = shared.save_agent_plan(store, result)

    assert saved is False
    assert "nombre" in message
    assert store["activities"] == []
    assert store["todo_items"] == []


def test_default_theme_is_lilac():
    store = shared.default_store()

    assert shared.app_theme_name(store) == "Lila"


def test_theme_preference_round_trip(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "STORE_PATH", data_dir / "academic_planning_store.json")
    monkeypatch.setattr(shared, "BACKUP_DIR", data_dir / "backups")
    store = shared.default_store()

    shared.set_app_theme(store, "Verde")
    shared.save_store(store)
    loaded = shared.load_store()

    assert shared.app_theme_name(loaded) == "Verde"
