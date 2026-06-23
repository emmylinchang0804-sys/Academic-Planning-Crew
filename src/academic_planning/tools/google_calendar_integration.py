"""Base hooks for a future Google Calendar integration.

The real OAuth flow and Google Calendar API client are intentionally not wired
yet. These functions define the interface the Streamlit app can call later.
"""


def export_event_to_google_calendar(event):
    """Prepare one local event for a future Google Calendar export."""
    return {
        "status": "pending_oauth",
        "message": "Google Calendar export is not active yet.",
        "event": event,
    }


def import_google_calendar_events():
    """Return external events once Google Calendar OAuth is configured."""
    return []


def sync_calendar_events():
    """Placeholder for two-way calendar synchronization."""
    return {
        "status": "pending_oauth",
        "exported": 0,
        "imported": 0,
        "message": "Google Calendar sync is not active yet.",
    }
