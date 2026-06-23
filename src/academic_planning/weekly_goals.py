"""Weekly goal creation and progress calculations."""

from datetime import date, timedelta


GOAL_TYPES = {
    "study_hours": "Horas de estudio",
    "completed_tasks": "Tareas completadas",
    "habit_marks": "Hábitos completados",
}


def week_start(day=None):
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def create_weekly_goal(title, goal_type, target, start_day=None, goal_id=""):
    clean_title = str(title or "").strip()
    if not clean_title:
        raise ValueError("La meta necesita un nombre.")
    if goal_type not in GOAL_TYPES:
        raise ValueError("El tipo de meta no es válido.")
    numeric_target = float(target)
    if numeric_target <= 0:
        raise ValueError("La meta debe ser mayor que cero.")
    return {
        "goal_id": goal_id,
        "title": clean_title,
        "goal_type": goal_type,
        "target": numeric_target,
        "week_start": week_start(start_day).isoformat(),
        "created_at": date.today().isoformat(),
    }


def weekly_goal_progress(goal, store, reference_day=None):
    start = date.fromisoformat(goal.get("week_start") or week_start(reference_day).isoformat())
    end = start + timedelta(days=6)
    goal_type = goal.get("goal_type")
    if goal_type == "study_hours":
        minutes = 0
        for item in store.get("todo_items", []):
            if not item.get("done") or not start.isoformat() <= item.get("date", "") <= end.isoformat():
                continue
            try:
                minutes += int(float(item.get("estimated_minutes", 30) or 30))
            except (TypeError, ValueError):
                minutes += 30
        current = round(minutes / 60, 1)
    elif goal_type == "completed_tasks":
        current = sum(
            1
            for item in store.get("todo_items", [])
            if item.get("done") and start.isoformat() <= item.get("date", "") <= end.isoformat()
        )
    elif goal_type == "habit_marks":
        current = sum(
            1
            for habit in store.get("habits", [])
            for day, completed in ((habit.get("history") or {}) if isinstance(habit.get("history"), dict) else {}).items()
            if completed and start.isoformat() <= day <= end.isoformat()
        )
    else:
        current = 0
    target = max(float(goal.get("target", 1) or 1), 0.01)
    return {
        "current": current,
        "target": target,
        "percentage": min(100, round(current / target * 100)),
    }
