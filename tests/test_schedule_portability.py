import json

from ui import shared


def test_schedule_export_contains_only_schedule_related_data():
    store = shared.default_store()
    store["courses"].append({"name": "Biología"})
    store["availability"].append(
        {
            "availability_id": "av_1",
            "title": "Biología",
            "day_index": 0,
            "day_of_week": "Lunes",
            "start_time": "08:00",
            "end_time": "09:00",
            "availability_type": "Clase",
            "color": "#8b5cf6",
        }
    )
    store["todo_items"].append({"title": "No exportar"})
    store["events"].append({"title": "No exportar"})
    store["habits"].append({"title": "No exportar"})
    store["settings"]["display_mode"] = "Oscuro"
    store["settings"]["week_view_mode"] = "grid"

    payload = json.loads(shared.schedule_export_json(store))

    assert payload["app"] == "Academic Planning Crew"
    assert payload["content"]["courses"] == [{"name": "Biología"}]
    assert payload["content"]["availability"][0]["title"] == "Biología"
    assert "todo_items" not in payload["content"]
    assert "events" not in payload["content"]
    assert "habits" not in payload["content"]
    assert payload["content"]["settings"]["week_view_mode"] == "grid"
    assert "display_mode" not in payload["content"]["settings"]


def test_schedule_import_validates_and_merges_without_overwriting():
    store = shared.default_store()
    store["availability"].append(
        {
            "availability_id": "av_old",
            "title": "Matemática",
            "day_index": 1,
            "start_time": "09:00",
            "end_time": "10:00",
        }
    )
    payload = {
        "version": 1,
        "app": "Academic Planning Crew",
        "content": {
            "courses": [{"name": "Historia"}],
            "availability": [
                {
                    "availability_id": "av_new",
                    "title": "Historia",
                    "day_index": 2,
                    "start_time": "10:00",
                    "end_time": "11:00",
                }
            ],
            "settings": {"week_view_mode": "grid", "display_mode": "Oscuro"},
        },
    }

    imported, errors = shared.validate_schedule_import(payload)
    assert errors == []

    shared.apply_schedule_import(store, imported, replace=False)

    assert [item["title"] for item in store["availability"]] == [
        "Matemática",
        "Historia",
    ]
    assert store["courses"] == [{"name": "Historia"}]
    assert store["settings"]["week_view_mode"] == "grid"
    assert store["settings"]["display_mode"] == "Automático"


def test_schedule_import_rejects_invalid_shape():
    imported, errors = shared.validate_schedule_import(
        {
            "version": 1,
            "app": "Academic Planning Crew",
            "content": {"availability": "invalid"},
        }
    )

    assert imported is None
    assert errors
