from datetime import date

from ui import shared
from academic_planning.workflows.planning_flow import fallback_plan, plan_activity


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


def test_chat_plan_summarizes_study_title_and_description():
    result = plan_activity(
        "mañana tengo que estudiar para el examen de mate porque no entendí bien funciones y también tengo que repasar ejercicios",
        today=date(2026, 7, 1),
        context={},
    )

    assert result["needs_clarification"] is False
    assert result["activity"]["title"] == "Estudiar funciones de Matemática"
    assert len(result["activity"]["title"]) <= 50
    assert result["activity"]["course"] == "Matemática"
    assert result["activity"]["deadline"] == "2026-07-02"
    assert result["activity"]["description"] == "Repasar ejercicios y prepararse para el examen."


def test_chat_plan_summarizes_project_delivery_title():
    result = plan_activity(
        "el viernes tengo entrega del proyecto de programación y necesito terminar la interfaz",
        today=date(2026, 7, 1),
        context={},
    )

    assert result["needs_clarification"] is False
    assert result["activity"]["title"] == "Entrega proyecto de Programación"
    assert len(result["activity"]["title"]) <= 50
    assert result["activity"]["course"] == "Programación"
    assert result["activity"]["deadline"] == "2026-07-03"
    assert result["activity"]["description"] == "Terminar la interfaz antes de la entrega."


def test_save_agent_plan_does_not_use_literal_prompt_as_title():
    store = shared.default_store()
    prompt = "el viernes tengo entrega del proyecto de programación y necesito terminar la interfaz"
    result = {
        "activity": {
            "title": prompt,
            "activity_type": "Proyecto",
            "deadline": "2099-07-03",
            "source_message": prompt,
        },
        "todo_items": [{"title": prompt, "date": "2099-07-02"}],
    }

    saved, _ = shared.save_agent_plan(store, result)

    assert saved is True
    assert store["activities"][0]["title"] == "Entrega proyecto de Programación"
    assert store["todo_items"][0]["title"] == "Entrega proyecto de Programación"
    assert store["events"][0]["title"] == "Entrega proyecto de Programación"


def test_chat_plan_preserves_mentioned_time_when_saved():
    store = shared.default_store()
    result = plan_activity(
        "el viernes a las 15:30 tengo entrega del proyecto de programación",
        today=date(2026, 7, 1),
        context={},
    )

    saved, _ = shared.save_agent_plan(store, result)

    assert saved is True
    assert store["activities"][0]["time"] == "15:30"
    assert store["todo_items"][0]["time"] == "15:30"
    assert store["events"][0]["time"] == "15:30"
