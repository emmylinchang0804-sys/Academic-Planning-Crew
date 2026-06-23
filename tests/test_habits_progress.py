from datetime import date

from academic_planning.habits import habit_streak, habit_week_dates, habit_week_progress
from academic_planning.progress_metrics import completion_counts


def test_habit_week_progress_and_streak():
    days = habit_week_dates(date(2026, 6, 25))
    habit = {
        "weekly_target": 3,
        "history": {
            days[0].isoformat(): True,
            days[1].isoformat(): True,
            days[2].isoformat(): True,
        },
    }

    completed, target, percentage = habit_week_progress(habit, days)

    assert (completed, target, percentage) == (3, 3, 100)
    assert habit_streak(habit, end_day=days[2]) == 3


def test_completion_counts_support_todos_and_progress():
    stats = completion_counts(
        [
            {"done": True},
            {"completed": True},
            {"done": False},
        ]
    )

    assert stats == {"total": 3, "completed": 2, "pending": 1}
