from datetime import timedelta


def future_dates(today, deadline):
    start = today
    if deadline < start:
        return []
    days = []
    cursor = start
    while cursor <= deadline:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days

