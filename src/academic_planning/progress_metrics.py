"""Pure progress calculations."""


def is_completed(item):
    if isinstance(item, dict):
        return bool(item.get("completed") or item.get("done"))
    return bool(getattr(item, "completed", False))


def completion_counts(items):
    items = list(items or [])
    completed = sum(1 for item in items if is_completed(item))
    return {
        "total": len(items),
        "completed": completed,
        "pending": len(items) - completed,
    }
