from datetime import date

from academic_planning.habits import habit_best_streak
from academic_planning.profile import default_profile, save_profile
from academic_planning.weekly_goals import create_weekly_goal, weekly_goal_progress
from ui import shared


def test_habit_best_streak_supports_gaps():
    habit = {
        "history": {
            "2026-06-01": True,
            "2026-06-02": True,
            "2026-06-04": True,
            "2026-06-05": True,
            "2026-06-06": True,
        }
    }

    assert habit_best_streak(habit) == 3


def test_weekly_goal_progress_for_completed_tasks():
    goal = create_weekly_goal(
        "Completar 2 tareas",
        "completed_tasks",
        2,
        start_day=date(2026, 6, 23),
        goal_id="goal_test",
    )
    store = {
        "todo_items": [
            {"date": "2026-06-23", "done": True},
            {"date": "2026-06-24", "done": True},
            {"date": "2026-06-25", "done": False},
        ],
        "habits": [],
    }

    assert weekly_goal_progress(goal, store, date(2026, 6, 23))["percentage"] == 100


def test_dashboard_preferences_keep_existing_values():
    store = shared.default_store()
    store["settings"]["dashboard_widgets"] = {"tasks": False}

    preferences = shared.dashboard_preferences(store)

    assert preferences["tasks"] is False
    assert preferences["goals"] is True
    assert preferences["recent_activity"] is True


def test_default_todo_sections_are_visible():
    store = shared.default_store()

    assert shared.todo_section_preferences(store) == {
        "overdue": True,
        "today": True,
        "week": True,
        "done": True,
    }


def test_todo_section_preferences_keep_saved_values():
    store = shared.default_store()
    store["settings"]["todo_sections"] = {
        "overdue": False,
        "today": True,
    }

    preferences = shared.todo_section_preferences(store)

    assert preferences["overdue"] is False
    assert preferences["today"] is True
    assert preferences["week"] is True
    assert preferences["done"] is True


def test_todo_section_preferences_round_trip(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "STORE_PATH", data_dir / "academic_planning_store.json")
    monkeypatch.setattr(shared, "BACKUP_DIR", data_dir / "backups")
    store = shared.default_store()
    shared.todo_section_preferences(store)["done"] = False

    shared.save_store(store)
    loaded = shared.load_store()

    assert shared.todo_section_preferences(loaded)["done"] is False


def test_load_store_repairs_invalid_collection_types(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store_path = data_dir / "academic_planning_store.json"
    store_path.write_text(
        '{"settings": [], "todo_items": {}, "activities": "invalid"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "STORE_PATH", store_path)
    monkeypatch.setattr(shared, "BACKUP_DIR", data_dir / "backups")

    loaded = shared.load_store()

    assert isinstance(loaded["settings"], dict)
    assert loaded["todo_items"] == []
    assert loaded["activities"] == []


def test_retired_integration_logs_are_hidden_from_ui():
    store = shared.default_store()
    store["agent_log"] = [
        {"agent": "Integrations", "action": "Servicio conectado (mock)"},
        {"agent": "Progress Monitor", "action": "Pendiente completado"},
    ]

    visible = shared.visible_agent_logs(store)

    assert len(visible) == 1
    assert visible[0]["agent"] == "Progress Monitor"


def test_display_mode_preference():
    store = shared.default_store()

    assert shared.display_mode(store) == "Automático"
    assert shared.set_display_mode(store, "Oscuro") == "Oscuro"
    assert shared.display_mode(store) == "Oscuro"


def test_profile_extended_fields_are_saved():
    store = {}
    profile = default_profile()
    profile.update({
        "name": "Emmy",
        "primary_goal": "Terminar el semestre",
        "favorite_theme": "Verde",
        "main_weekly_goal": "Estudiar 10 horas",
    })

    saved = save_profile(store, profile)

    assert saved["primary_goal"] == "Terminar el semestre"
    assert saved["favorite_theme"] == "Verde"
    assert saved["main_weekly_goal"] == "Estudiar 10 horas"
