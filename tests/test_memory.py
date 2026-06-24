import json
from datetime import datetime

from academic_planning.tools.database_tool import create_json_backup, read_json, write_json


def test_store_round_trip_and_backup(tmp_path):
    store_path = tmp_path / "data" / "academic_planning_store.json"
    store = {"todo_items": [{"title": "Repasar", "date": "2026-06-24"}]}
    write_json(store_path, store)
    loaded = read_json(store_path, {})
    backup_path = create_json_backup(
        tmp_path / "data" / "backups",
        loaded,
        "test backup",
        now=datetime(2026, 6, 23, 12, 0, 0),
    )

    assert loaded["todo_items"][0]["title"] == "Repasar"
    assert json.loads(backup_path.read_text(encoding="utf-8"))["todo_items"]
    assert backup_path.name == "academic_planning_20260623_120000_test_backup.json"


def test_read_json_returns_default_for_corrupt_file(tmp_path):
    store_path = tmp_path / "data" / "academic_planning_store.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text("{not valid json", encoding="utf-8")

    assert read_json(store_path, {"safe": True}) == {"safe": True}
