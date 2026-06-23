"""Weekly planning, tasks, and agent-assisted planning screens."""

from ui.shared import tab_chat, tab_todo, tab_week


def render_week(store):
    tab_week(store)


def render_todos(store):
    tab_todo(store)


def render_agents(store):
    tab_chat(store)
