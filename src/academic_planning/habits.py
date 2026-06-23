"""Pure habit tracking helpers."""

from datetime import date, timedelta


def habit_history(habit):
    history = habit.setdefault("history", {})
    if isinstance(history, list):
        history = {str(day): True for day in history}
        habit["history"] = history
    elif not isinstance(history, dict):
        history = {}
        habit["history"] = history
    today_key = date.today().isoformat()
    if habit.get("done_today") and today_key not in history:
        history[today_key] = True
    return history


def is_habit_done(habit, day):
    return bool(habit_history(habit).get(day.isoformat(), False))


def habit_streak(habit, end_day=None):
    cursor = end_day or date.today()
    history = habit_history(habit)
    streak = 0
    while history.get(cursor.isoformat(), False):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def habit_best_streak(habit):
    completed_days = []
    for day, completed in habit_history(habit).items():
        if not completed:
            continue
        try:
            completed_days.append(date.fromisoformat(day))
        except (TypeError, ValueError):
            continue
    completed_days.sort()
    best = 0
    running = 0
    previous = None
    for day in completed_days:
        if previous and day == previous + timedelta(days=1):
            running += 1
        else:
            running = 1
        best = max(best, running)
        previous = day
    return best


def habit_week_dates(selected=None):
    selected = selected or date.today()
    start = selected - timedelta(days=selected.weekday())
    return [start + timedelta(days=offset) for offset in range(7)]


def habit_week_count(habit, days):
    return sum(1 for day in days if is_habit_done(habit, day))


def habit_week_progress(habit, days):
    target = max(1, int(habit.get("weekly_target", 5) or 5))
    completed = habit_week_count(habit, days)
    return completed, target, min(100, round(completed / target * 100))
