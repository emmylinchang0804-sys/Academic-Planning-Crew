"""Streamlit entry point for Academic Planning Crew."""

import streamlit as st

from ui import calendar, dashboard, habits, memory, planner, progress
from ui.shared import apply_css, completion_stats, load_store, save_store, sidebar_profile


st.set_page_config(
    page_title="Academic Planning Crew",
    page_icon="APC",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_header(store):
    st.markdown(
        '<div class="app-title">Academic Planning Crew</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="app-subtitle">Semana para horarios fijos, mes para eventos, '
        "To-do para ejecución diaria y agentes para dividir actividades.</div>",
        unsafe_allow_html=True,
    )
    st.caption("Personaliza el color en la barra lateral: Apariencia → Color base.")
    stats = completion_stats(store)
    columns = st.columns(4)
    columns[0].metric("Actividades", len(store["activities"]))
    columns[1].metric("To-dos", stats["total"])
    columns[2].metric("Completado", f"{stats['pct']}%")
    columns[3].metric("Atrasados", stats["overdue"])


def main():
    store = load_store()
    st.session_state["_app_store"] = store
    apply_css()
    sidebar_profile(store)
    render_header(store)

    tabs = st.tabs(
        [
            "Hoy",
            "Semana",
            "Mes",
            "To-do",
            "Chat / Agentes",
            "Estadisticas",
            "Progreso",
            "Habitos",
            "Memoria",
        ]
    )
    screens = [
        dashboard.render,
        planner.render_week,
        calendar.render,
        planner.render_todos,
        planner.render_agents,
        progress.render_statistics,
        progress.render,
        habits.render,
        memory.render,
    ]
    for tab, screen in zip(tabs, screens):
        with tab:
            screen(store)

    save_store(store)


if __name__ == "__main__":
    main()
