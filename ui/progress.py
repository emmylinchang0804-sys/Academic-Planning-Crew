"""Progress and statistics screens."""

from ui.shared import tab_progress, tab_statistics


def render(store):
    tab_progress(store)


def render_statistics(store):
    tab_statistics(store)
