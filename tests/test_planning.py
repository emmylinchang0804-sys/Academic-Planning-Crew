from datetime import date

from academic_planning.workflows.planning_flow import fallback_plan


def test_fallback_plan_creates_future_reading_tasks():
    today = date(2026, 6, 23)
    result = fallback_plan(
        "Leer 90 paginas de Historia para el 26/06/2026",
        today=today,
        context={},
    )

    assert result["needs_clarification"] is False
    assert result["activity"]["activity_type"] == "Lectura"
    assert result["todo_items"]
    assert all(item["date"] >= today.isoformat() for item in result["todo_items"])


def test_fallback_plan_requests_missing_deadline():
    result = fallback_plan("Preparar un ensayo", today=date(2026, 6, 23))

    assert result["needs_clarification"] is True
    assert result["question"]
