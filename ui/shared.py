import calendar
import base64
import html as html_lib
import json
import os
import re
import sys
import uuid
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from academic_planning.crew import AcademicPlanningCrew
from academic_planning.habits import (
    habit_best_streak as core_habit_best_streak,
    habit_history as core_habit_history,
    habit_streak as core_habit_streak,
    habit_week_count as core_habit_week_count,
    habit_week_dates as core_habit_week_dates,
    habit_week_progress as core_habit_week_progress,
    is_habit_done as core_is_habit_done,
)
from academic_planning.progress_metrics import completion_counts, is_completed
from academic_planning.storage.factory import get_storage
from academic_planning.workflows.planning_flow import (
    academic_description_from_message,
    academic_title_from_message,
    detect_subject,
    load_dotenv,
    normalize_text,
    redistribute_reading_plan,
)
from academic_planning.profile import (
    default_profile,
    load_profile,
    save_profile,
)
from academic_planning.weekly_goals import (
    GOAL_TYPES,
    create_weekly_goal as build_weekly_goal,
    week_start as goal_week_start,
    weekly_goal_progress,
)

configured_data_dir = os.environ.get("ACADEMIC_PLANNING_DATA_DIR", "").strip()
DATA_DIR = Path(configured_data_dir).expanduser() if configured_data_dir else APP_DIR / "data"
if not DATA_DIR.is_absolute():
    DATA_DIR = APP_DIR / DATA_DIR
STORE_PATH = DATA_DIR / "academic_planning_store.json"
BACKUP_DIR = DATA_DIR / "backups"
USERS_DIR = DATA_DIR / "users"
USER_STORE_FILENAME = "academic_data.json"
load_dotenv(APP_DIR)

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
DAY_ALIASES = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}
SCHEDULE_COLOR_PALETTE = [
    ("Cielo pastel", "#93c5fd"),
    ("Lavanda suave", "#c4b5fd"),
    ("Lila nube", "#ddd6fe"),
    ("Rosa algodón", "#f9a8d4"),
    ("Durazno", "#fdba74"),
    ("Menta clara", "#a7f3d0"),
    ("Verde agua", "#99f6e4"),
    ("Limón suave", "#fde68a"),
    ("Coral pastel", "#fda4af"),
    ("Celeste hielo", "#bae6fd"),
    ("Malva", "#e9d5ff"),
    ("Pistacho", "#bbf7d0"),
    ("Perla azul", "#bfdbfe"),
    ("Niebla violeta", "#d8b4fe"),
]
COURSE_PALETTE = [color for _, color in SCHEDULE_COLOR_PALETTE]
EVENT_TYPES = {
    "Entrega": {"icon": chr(0x1F4CC), "color": "#a78bfa", "meaning": "entrega"},
    "Examen": {"icon": chr(0x1F4DD), "color": "#fda4af", "meaning": "examen"},
    "Cumpleanos": {"icon": chr(0x1F382), "color": "#f9a8d4", "meaning": "cumpleanos"},
    "Reunion": {"icon": chr(0x1F91D), "color": "#99f6e4", "meaning": "reunion"},
    "Personal": {"icon": chr(0x2B50), "color": "#c4b5fd", "meaning": "personal"},
    "Descanso": {"icon": chr(0x1F319), "color": "#bfdbfe", "meaning": "descanso"},
}
APP_THEMES = {
    "Lila": {"primary": "#8b5cf6", "dark": "#5b21b6", "soft": "#f5f3ff", "border": "#ddd6fe", "shadow": "rgba(88,28,135,.10)"},
    "Azul": {"primary": "#2563eb", "dark": "#1e40af", "soft": "#eff6ff", "border": "#bfdbfe", "shadow": "rgba(30,64,175,.10)"},
    "Verde": {"primary": "#059669", "dark": "#065f46", "soft": "#ecfdf5", "border": "#a7f3d0", "shadow": "rgba(6,95,70,.10)"},
    "Rosa": {"primary": "#db2777", "dark": "#9d174d", "soft": "#fdf2f8", "border": "#fbcfe8", "shadow": "rgba(157,23,77,.10)"},
    "Naranja": {"primary": "#ea580c", "dark": "#9a3412", "soft": "#fff7ed", "border": "#fed7aa", "shadow": "rgba(154,52,18,.10)"},
    "Gris": {"primary": "#64748b", "dark": "#334155", "soft": "#f1f5f9", "border": "#cbd5e1", "shadow": "rgba(51,65,85,.10)"},
}
DEFAULT_APP_THEME = "Lila"
DISPLAY_MODES = ["Claro", "Oscuro", "Automático"]
AUTH_DISPLAY_MODES = ["Claro", "Oscuro"]
DEFAULT_DASHBOARD_WIDGETS = {
    "tasks": True,
    "habits": True,
    "calendar": True,
    "statistics": True,
    "goals": True,
    "recent_activity": True,
}
DEFAULT_TODO_SECTIONS = {
    "overdue": True,
    "today": True,
    "week": True,
    "done": True,
}
SCHEDULE_EXPORT_VERSION = 1
SCHEDULE_DATA_KEYS = ("courses", "availability", "schedule", "classes", "timetable")
SCHEDULE_SETTING_KEYS = (
    "custom_schedule_colors",
    "week_view_mode",
    "show_weekends",
    "compact_schedule_cards",
    "study_start",
    "study_end",
)
FULL_BACKUP_EXPORT_VERSION = 1
FULL_BACKUP_STORE_KEYS = (
    "student",
    "profile",
    "courses",
    "availability",
    "activities",
    "todo_items",
    "events",
    "habits",
    "weekly_goals",
    "progress",
    "chat",
    "agent_log",
    "settings",
    "schedule",
    "classes",
    "timetable",
)
SENSITIVE_BACKUP_KEYS = {
    "password",
    "password_hash",
    "hash",
    "salt",
    "token",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "users",
}


def make_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def default_store():
    return {
        "student": {"name": "", "career": "", "semester": "", "timezone": "America/Guatemala"},
        "profile": default_profile(),
        "courses": [],
        "availability": [],
        "activities": [],
        "todo_items": [],
        "events": [],
        "habits": [],
        "weekly_goals": [],
        "progress": [],
        "chat": [],
        "agent_log": [],
        "settings": {"app_theme": DEFAULT_APP_THEME, "display_mode": "Automático", "dashboard_widgets": dict(DEFAULT_DASHBOARD_WIDGETS), "todo_sections": dict(DEFAULT_TODO_SECTIONS), "study_start": "07:00", "study_end": "21:00", "week_view_mode": "agenda", "show_weekends": True, "compact_schedule_cards": True, "month_view_density": "comfortable", "month_theme": "clean", "show_todos_in_month": False, "show_habits_in_month": False, "month_show_weekends": True, "event_type_colors": {}, "today_plan_mode": "balanced", "todo_view_mode": "smart"},
    }


def active_user_id():
    try:
        user = st.session_state.get("auth_user", {})
    except Exception:
        user = {}
    if isinstance(user, dict) and user.get("user_id"):
        return user.get("user_id")
    try:
        return st.session_state.get("current_user_id")
    except Exception:
        return None


def storage_backend():
    storage = get_storage(data_dir=DATA_DIR)
    if hasattr(storage, "users_dir"):
        storage.users_dir = USERS_DIR
    if hasattr(storage, "legacy_store_path"):
        storage.legacy_store_path = STORE_PATH
    if hasattr(storage, "legacy_backup_dir"):
        storage.legacy_backup_dir = BACKUP_DIR
    return storage


def auth_users_path():
    return DATA_DIR / "auth" / "users.json"


def user_data_dir(user_id=None):
    selected_user_id = user_id or active_user_id()
    if not selected_user_id:
        return DATA_DIR
    return storage_backend().user_data_dir(selected_user_id)


def store_path_for_user(user_id=None):
    selected_user_id = user_id or active_user_id()
    if not selected_user_id:
        return STORE_PATH
    return storage_backend().user_store_path(selected_user_id)


def backup_dir_for_user(user_id=None):
    selected_user_id = user_id or active_user_id()
    if not selected_user_id:
        return BACKUP_DIR
    return storage_backend().user_backup_dir(selected_user_id)


def archive_user_data(user_id):
    return storage_backend().delete_user_data(user_id)


def load_store(user_id=None):
    defaults = default_store()
    store = storage_backend().load_user_data(user_id)
    if not isinstance(store, dict):
        store = default_store()
    for key, value in defaults.items():
        current = store.get(key)
        if isinstance(value, dict) and not isinstance(current, dict):
            store[key] = value
        elif isinstance(value, list) and not isinstance(current, list):
            store[key] = value
        else:
            store.setdefault(key, value)
    load_profile(store)
    store.setdefault("todo_items", [])
    store.setdefault("weekly_goals", [])
    store.setdefault("settings", {})
    store["settings"].setdefault("app_theme", DEFAULT_APP_THEME)
    store["settings"].setdefault("display_mode", "Automático")
    widgets = store["settings"].setdefault("dashboard_widgets", {})
    for key, visible in DEFAULT_DASHBOARD_WIDGETS.items():
        widgets.setdefault(key, visible)
    todo_sections = store["settings"].setdefault("todo_sections", {})
    for key, visible in DEFAULT_TODO_SECTIONS.items():
        todo_sections.setdefault(key, visible)
    store["settings"].setdefault("custom_schedule_colors", [])
    store["settings"].setdefault("week_view_mode", "agenda")
    store["settings"].setdefault("show_weekends", True)
    store["settings"].setdefault("compact_schedule_cards", True)
    store["settings"].setdefault("month_view_density", "comfortable")
    store["settings"].setdefault("month_theme", "clean")
    store["settings"]["show_todos_in_month"] = False
    store["settings"]["show_habits_in_month"] = False
    store["settings"].setdefault("month_show_weekends", True)
    store["settings"].setdefault("event_type_colors", {})
    store["settings"].setdefault("today_plan_mode", "balanced")
    store["settings"].setdefault("todo_view_mode", "smart")
    store.setdefault("progress", [])
    for event_type, cfg in EVENT_TYPES.items():
        store["settings"]["event_type_colors"].setdefault(event_type, cfg["color"])
    for item in store.get("todo_items", []):
        ensure_todo_defaults(item)
    return store


def app_theme_name(store):
    selected = str(store.get("settings", {}).get("app_theme", DEFAULT_APP_THEME))
    return selected if selected in APP_THEMES else DEFAULT_APP_THEME


def set_app_theme(store, theme_name):
    selected = theme_name if theme_name in APP_THEMES else DEFAULT_APP_THEME
    store.setdefault("settings", {})["app_theme"] = selected
    return selected


def display_mode(store):
    selected = str(store.get("settings", {}).get("display_mode", "Automático"))
    return selected if selected in DISPLAY_MODES else "Automático"


def set_display_mode(store, mode):
    selected = mode if mode in DISPLAY_MODES else "Automático"
    store.setdefault("settings", {})["display_mode"] = selected
    return selected


def session_display_mode():
    try:
        selected = st.session_state.get("preferred_display_mode", "Claro")
    except Exception:
        selected = "Claro"
    return selected if selected in AUTH_DISPLAY_MODES else "Claro"


def set_session_display_mode(mode):
    selected = mode if mode in AUTH_DISPLAY_MODES else "Claro"
    st.session_state["preferred_display_mode"] = selected
    if st.session_state.get("pending_display_mode") != selected:
        st.session_state["pending_display_mode"] = selected
    return selected


def consume_pending_session_theme():
    try:
        selected = st.session_state.pop("pending_display_mode", None)
    except Exception:
        selected = None
    return selected if selected in AUTH_DISPLAY_MODES else None


def initialize_store_theme_from_session(store):
    selected = consume_pending_session_theme() or session_display_mode()
    set_display_mode(store, selected)
    try:
        st.session_state["preferred_display_mode"] = selected
        st.session_state["theme_initialized"] = True
    except Exception:
        pass
    return selected


def apply_pending_session_theme(store):
    selected = consume_pending_session_theme()
    if selected in AUTH_DISPLAY_MODES:
        if display_mode(store) != selected:
            set_display_mode(store, selected)
            try:
                st.session_state["preferred_display_mode"] = selected
                st.session_state["theme_initialized"] = True
            except Exception:
                pass
            return True
    return False


def schedule_export_payload(store):
    settings = store.get("settings", {}) if isinstance(store.get("settings"), dict) else {}
    related_settings = {
        key: settings.get(key)
        for key in SCHEDULE_SETTING_KEYS
        if key in settings
    }
    payload = {
        "version": SCHEDULE_EXPORT_VERSION,
        "app": "Academic Planning Crew",
        "exported_at": now_iso(),
        "content": {
            "courses": store.get("courses", []),
            "availability": store.get("availability", []),
            "schedule": store.get("schedule", []),
            "classes": store.get("classes", []),
            "timetable": store.get("timetable", []),
            "settings": related_settings,
        },
    }
    return payload


def schedule_export_json(store):
    return json.dumps(schedule_export_payload(store), ensure_ascii=False, indent=2)


def remove_sensitive_backup_data(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SENSITIVE_BACKUP_KEYS:
                continue
            clean[key] = remove_sensitive_backup_data(item)
        return clean
    if isinstance(value, list):
        return [remove_sensitive_backup_data(item) for item in value]
    return value


def full_backup_export_payload(store):
    content = {}
    for key in FULL_BACKUP_STORE_KEYS:
        if key in store:
            content[key] = remove_sensitive_backup_data(store.get(key))
    content["statistics"] = completion_stats(store)
    return {
        "version": FULL_BACKUP_EXPORT_VERSION,
        "app": "Academic Planning Crew",
        "kind": "full_user_backup",
        "exported_at": now_iso(),
        "content": content,
    }


def full_backup_export_json(store):
    return json.dumps(full_backup_export_payload(store), ensure_ascii=False, indent=2)


def validate_full_backup_import(payload):
    if not isinstance(payload, dict):
        return None, ["El archivo no contiene un objeto JSON válido."]
    if payload.get("app") != "Academic Planning Crew" or payload.get("kind") != "full_user_backup":
        return None, ["Este archivo no parece ser un respaldo completo de Academic Planning Crew."]
    try:
        version = int(payload.get("version", 0) or 0)
    except (TypeError, ValueError):
        return None, ["La versión del respaldo no es válida."]
    if version > FULL_BACKUP_EXPORT_VERSION:
        return None, ["El respaldo fue creado con una versión más nueva y puede no ser compatible."]

    content = payload.get("content")
    if not isinstance(content, dict):
        return None, ["Falta la sección content del respaldo."]

    defaults = default_store()
    errors = []
    cleaned = {}
    for key, default_value in defaults.items():
        value = content.get(key, default_value)
        if isinstance(default_value, list):
            if value is None:
                value = []
            if not isinstance(value, list):
                errors.append(f"La sección {key} debe ser una lista.")
            else:
                cleaned[key] = remove_sensitive_backup_data(value)
        elif isinstance(default_value, dict):
            if value is None:
                value = {}
            if not isinstance(value, dict):
                errors.append(f"La sección {key} debe ser un objeto.")
            else:
                merged = dict(default_value)
                merged.update(remove_sensitive_backup_data(value))
                cleaned[key] = merged

    for key in ("schedule", "classes", "timetable"):
        value = content.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            errors.append(f"La sección {key} debe ser una lista.")
        else:
            cleaned[key] = remove_sensitive_backup_data(value)

    statistics = content.get("statistics", {})
    if statistics is not None and not isinstance(statistics, dict):
        errors.append("La sección statistics debe ser un objeto.")

    if errors:
        return None, errors
    return cleaned, []


def apply_full_backup_import(store, imported):
    fresh = default_store()
    for key, value in imported.items():
        if key in FULL_BACKUP_STORE_KEYS:
            fresh[key] = remove_sensitive_backup_data(value)
    store.clear()
    store.update(fresh)
    load_profile(store)
    add_log(store, "Cuenta", "Respaldo completo importado", {"sections": sorted(imported)})
    return store


def validate_schedule_import(payload):
    if not isinstance(payload, dict):
        return None, ["El archivo no contiene un objeto JSON válido."]
    if payload.get("app") != "Academic Planning Crew":
        return None, ["Este archivo no parece ser un horario exportado por Academic Planning Crew."]
    try:
        version = int(payload.get("version", 0) or 0)
    except (TypeError, ValueError):
        return None, ["La versión del archivo no es válida."]
    if version > SCHEDULE_EXPORT_VERSION:
        return None, ["El archivo fue creado con una versión más nueva y puede no ser compatible."]

    content = payload.get("content")
    if not isinstance(content, dict):
        return None, ["Falta la sección content del horario."]

    errors = []
    cleaned = {}
    for key in SCHEDULE_DATA_KEYS:
        value = content.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            errors.append(f"La sección {key} debe ser una lista.")
        else:
            cleaned[key] = value

    settings = content.get("settings", {})
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        errors.append("La configuración relacionada debe ser un objeto.")
    else:
        cleaned["settings"] = {
            key: value
            for key, value in settings.items()
            if key in SCHEDULE_SETTING_KEYS
        }

    availability = cleaned.get("availability", [])
    for index, block in enumerate(availability, start=1):
        if not isinstance(block, dict):
            errors.append(f"El bloque de disponibilidad #{index} no es válido.")
            continue
        required = ("title", "day_index", "start_time", "end_time")
        missing = [key for key in required if key not in block]
        if missing:
            errors.append(f"Al bloque #{index} le faltan campos: {', '.join(missing)}.")
        try:
            day_index = int(block.get("day_index", 0))
        except (TypeError, ValueError):
            errors.append(f"El bloque #{index} tiene un día inválido.")
            continue
        if day_index < 0 or day_index > 6:
            errors.append(f"El bloque #{index} tiene un día fuera de rango.")

    if errors:
        return None, errors
    return cleaned, []


def apply_schedule_import(store, imported, replace=False):
    if replace:
        for key in SCHEDULE_DATA_KEYS:
            store[key] = list(imported.get(key, []))
    else:
        for key in SCHEDULE_DATA_KEYS:
            store.setdefault(key, [])
            if isinstance(store[key], list):
                store[key].extend(list(imported.get(key, [])))
            else:
                store[key] = list(imported.get(key, []))
    store.setdefault("settings", {}).update(imported.get("settings", {}))
    add_log(
        store,
        "Student Profile Manager",
        "Horario importado desde JSON",
        {"replace": bool(replace), "availability": len(imported.get("availability", []))},
    )
    return store


def dashboard_preferences(store):
    widgets = store.setdefault("settings", {}).setdefault("dashboard_widgets", {})
    for key, visible in DEFAULT_DASHBOARD_WIDGETS.items():
        widgets.setdefault(key, visible)
    return widgets


def todo_section_preferences(store):
    sections = store.setdefault("settings", {}).setdefault("todo_sections", {})
    for key, visible in DEFAULT_TODO_SECTIONS.items():
        sections.setdefault(key, visible)
    return sections


def required_text(value, field_name):
    clean = str(value or "").strip()
    if not clean:
        return "", f"Escribe {field_name} antes de guardar."
    return clean, ""


def short_todo_title(title):
    clean = re.sub(r"\s+", " ", str(title or "Pendiente")).strip()
    return clean[:47].rstrip(" .,-") + "..." if len(clean) > 50 else clean


def normalize_todo_text(value):
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9áéíóúñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def todo_similarity(left, right):
    return SequenceMatcher(None, normalize_todo_text(left), normalize_todo_text(right)).ratio()


def is_similar_todo(existing, candidate):
    if existing.get("done"):
        return False
    same_date = existing.get("date") == candidate.get("date")
    same_internal = existing.get("internal_task_id") and existing.get("internal_task_id") == candidate.get("internal_task_id")
    similar_title = todo_similarity(existing.get("title"), candidate.get("title")) >= 0.86
    return same_date and (same_internal or similar_title)


def ensure_todo_defaults(item):
    item.setdefault("priority", "Media")
    item.setdefault("estimated_minutes", 30)
    item.setdefault("energy", "Normal")
    item.setdefault("description", "")
    item["title"] = short_todo_title(item.get("title", "Pendiente"))
    item.setdefault("internal_task_id", make_id("task"))
    return item


def demo_meta(section):
    return {"demo": True, "source": "sample_data", "section": section}


def is_demo_item(item):
    if not isinstance(item, dict):
        return False
    meta = item.get("meta")
    return bool(item.get("demo") is True or (isinstance(meta, dict) and meta.get("demo") is True))


def create_schedule_block(store, title, day, start_time, end_time, block_type="Clase", color=None, metadata=None):
    clean_title, error = required_text(title, "el nombre de la clase o actividad")
    if error:
        return None, error
    if isinstance(day, str):
        if day not in DAYS_ES:
            return None, "Selecciona un dia valido."
        day_index = DAYS_ES.index(day)
        day_name = day
    else:
        try:
            day_index = int(day)
        except (TypeError, ValueError):
            return None, "Selecciona un dia valido."
        if day_index < 0 or day_index >= len(DAYS_ES):
            return None, "Selecciona un dia valido."
        day_name = DAYS_ES[day_index]
    start = parse_time(start_time) if isinstance(start_time, str) else start_time
    end = parse_time(end_time) if isinstance(end_time, str) else end_time
    if not start or not end:
        return None, "Ingresa horas validas."
    if minutes(end) <= minutes(start):
        return None, "La hora de fin debe ser despues del inicio."
    block = {
        "availability_id": make_id("av"),
        "title": clean_title,
        "day_index": day_index,
        "day_of_week": day_name,
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "availability_type": block_type or "Clase",
        "color": color or color_for_subject(store, clean_title, COURSE_PALETTE[len(store.get("availability", [])) % len(COURSE_PALETTE)]),
    }
    if metadata:
        block.update(metadata)
    store.setdefault("availability", []).append(block)
    return block, ""


def add_schedule_block(store, title, day, start_time, end_time, block_type="Clase", color=None, metadata=None):
    block, error = create_schedule_block(store, title, day, start_time, end_time, block_type, color, metadata)
    if error:
        return None, error
    remember_course_color(store, block["title"], block["color"])
    add_log(store, "Student Profile Manager", "Clase agregada al horario", {"title": block["title"], "day": block["day_of_week"]})
    return block, ""


def update_schedule_block(store, block_id, title, day, start_time, end_time, block_type="Clase", color=None):
    block = next((item for item in store.get("availability", []) if item.get("availability_id") == block_id), None)
    if not block:
        return False, "No encontre ese bloque de horario."
    clean_title, error = required_text(title, "el nombre")
    if error:
        return False, error
    day_index = DAYS_ES.index(day) if day in DAYS_ES else None
    if day_index is None:
        return False, "Selecciona un dia valido."
    start = parse_time(start_time) if isinstance(start_time, str) else start_time
    end = parse_time(end_time) if isinstance(end_time, str) else end_time
    if not start or not end:
        return False, "Ingresa horas validas."
    if minutes(end) <= minutes(start):
        return False, "La hora de fin debe ser despues del inicio."
    conflicts = schedule_conflicts(store, day_index, start, end, exclude_id=block_id)
    if conflicts:
        return False, f"Choque de horario con: {conflict_text(conflicts)}"
    selected_color = color or block.get("color", COURSE_PALETTE[0])
    remember_course_color(store, clean_title, selected_color)
    block.update({
        "title": clean_title,
        "day_index": day_index,
        "day_of_week": day,
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "availability_type": block_type,
        "color": selected_color,
    })
    add_log(store, "Student Profile Manager", "Bloque de horario editado", {"title": clean_title, "day": day})
    return True, ""


def build_sample_data(reference_day=None):
    today = reference_day or date.today()
    week = week_start(today)
    event_days = [today + timedelta(days=offset) for offset in (1, 3, 6, 10)]
    subject_colors = {
        "Matemática": "#fde68a",
        "Física": "#bfdbfe",
        "Química": "#a7f3d0",
        "Ética": "#fdba74",
        "Biología": "#86efac",
        "Literatura": "#f9a8d4",
        "Estadística": "#bbf7d0",
        "Computación": "#93c5fd",
        "Liderazgo": "#c4b5fd",
        "Mate aplicada": "#fef3c7",
        "Inglés": "#fca5a5",
        "Robótica": "#d6d3d1",
        "Programación": "#bae6fd",
        "Seminario": "#ddd6fe",
        "Laboratorio": "#d8b4fe",
    }
    schedule_specs = [
        ("Matemática", "Lunes", "07:00", "07:40"), ("Matemática", "Lunes", "07:40", "08:20"),
        ("Física", "Lunes", "08:20", "09:00"), ("Química", "Lunes", "09:20", "10:00"),
        ("Ética", "Lunes", "10:00", "10:40"), ("Biología", "Lunes", "10:40", "11:20"),
        ("Literatura", "Lunes", "11:40", "12:20"), ("Estadística", "Lunes", "12:20", "13:00"),
        ("Literatura", "Martes", "07:00", "07:40"), ("Matemática", "Martes", "07:40", "08:20"),
        ("Computación", "Martes", "08:20", "09:00"), ("Computación", "Martes", "09:20", "10:00"),
        ("Liderazgo", "Martes", "10:00", "10:40"), ("Mate aplicada", "Martes", "10:40", "11:20"),
        ("Inglés", "Martes", "11:40", "12:20"), ("Robótica", "Martes", "12:20", "13:00"),
        ("Literatura", "Miércoles", "07:00", "07:40"), ("Programación", "Miércoles", "07:40", "08:20"),
        ("Programación", "Miércoles", "08:20", "09:00"), ("Estadística", "Miércoles", "09:20", "10:00"),
        ("Seminario", "Miércoles", "10:00", "10:40"), ("Seminario", "Miércoles", "10:40", "11:20"),
        ("Inglés", "Miércoles", "11:40", "12:20"), ("Biología", "Miércoles", "12:20", "13:00"),
        ("Computación", "Jueves", "07:00", "07:40"), ("Computación", "Jueves", "07:40", "08:20"),
        ("Ética", "Jueves", "08:20", "09:00"), ("Inglés", "Jueves", "09:20", "10:00"),
        ("Matemática", "Jueves", "10:00", "10:40"), ("Mate aplicada", "Jueves", "10:40", "11:20"),
        ("Química", "Jueves", "11:40", "12:20"), ("Física", "Jueves", "12:20", "13:00"),
        ("Programación", "Viernes", "07:00", "07:40"), ("Laboratorio", "Viernes", "07:40", "08:20"),
        ("Mate aplicada", "Viernes", "08:20", "09:00"), ("Química", "Viernes", "09:20", "10:00"),
        ("Literatura", "Viernes", "10:00", "10:40"), ("Biología", "Viernes", "10:40", "11:20"),
        ("Matemática", "Viernes", "11:40", "12:20"), ("Inglés", "Viernes", "12:20", "13:00"),
    ]
    courses = [
        {"course_id": f"demo_course_{idx}", "name": name, "color": color, "meta": demo_meta("courses")}
        for idx, (name, color) in enumerate(subject_colors.items(), start=1)
    ]
    availability = []
    for idx, (title, day, start, end) in enumerate(schedule_specs, start=1):
        day_index = DAYS_ES.index(day)
        availability.append({
            "availability_id": f"demo_av_{idx}",
            "title": title,
            "day_index": day_index,
            "day_of_week": day,
            "start_time": start,
            "end_time": end,
            "availability_type": "Clase",
            "color": subject_colors.get(title, COURSE_PALETTE[idx % len(COURSE_PALETTE)]),
            "meta": demo_meta("availability"),
        })
    events = [
        {"event_id": "demo_event_exam", "title": "Examen parcial de Fisica", "date": event_days[0].isoformat(), "type": "Examen", "course": "Fisica", "color": "#fda4af", "meta": demo_meta("events")},
        {"event_id": "demo_event_project", "title": "Entrega de proyecto de Programacion", "date": event_days[1].isoformat(), "type": "Entrega", "course": "Programacion", "color": "#a78bfa", "meta": demo_meta("events")},
        {"event_id": "demo_event_group", "title": "Reunion de grupo para presentacion", "date": event_days[2].isoformat(), "type": "Reunion", "course": "Historia", "color": "#99f6e4", "meta": demo_meta("events")},
        {"event_id": "demo_event_presentation", "title": "Presentacion de Historia", "date": event_days[3].isoformat(), "type": "Entrega", "course": "Historia", "color": "#fdba74", "meta": demo_meta("events")},
    ]
    todo_items = [
        {"todo_id": "demo_todo_1", "title": "Resolver guia de limites", "course": "Matematicas", "date": today.isoformat(), "priority": "Alta", "estimated_minutes": 50, "energy": "Alta", "done": False, "order": 1, "description": "Practicar ejercicios 1 al 12.", "meta": demo_meta("todo_items")},
        {"todo_id": "demo_todo_2", "title": "Subir avance del proyecto", "course": "Programacion", "date": (today + timedelta(days=1)).isoformat(), "priority": "Alta", "estimated_minutes": 75, "energy": "Normal", "done": False, "order": 2, "description": "Agregar captura y conclusiones.", "meta": demo_meta("todo_items")},
        {"todo_id": "demo_todo_3", "title": "Leer capitulo de Historia", "course": "Historia", "date": (today + timedelta(days=2)).isoformat(), "priority": "Media", "estimated_minutes": 40, "energy": "Baja", "done": False, "order": 3, "meta": demo_meta("todo_items")},
        {"todo_id": "demo_todo_4", "title": "Repasar vocabulario de Ingles", "course": "Ingles", "date": today.isoformat(), "priority": "Media", "estimated_minutes": 25, "energy": "Normal", "done": True, "order": 4, "meta": demo_meta("todo_items")},
        {"todo_id": "demo_todo_5", "title": "Entregar laboratorio de Fisica", "course": "Fisica", "date": (today + timedelta(days=4)).isoformat(), "priority": "Alta", "estimated_minutes": 60, "energy": "Alta", "done": False, "order": 5, "meta": demo_meta("todo_items")},
    ]
    habits = []
    habit_specs = [
        ("Estudiar 1 hora", 5, "#8b5cf6"),
        ("Leer", 4, "#93c5fd"),
        ("Repasar apuntes", 5, "#f9a8d4"),
        ("Dormir temprano", 5, "#a7f3d0"),
        ("Hacer ejercicio", 3, "#fdba74"),
    ]
    for idx, (title, target, color) in enumerate(habit_specs, start=1):
        history = {}
        for offset in range(0, min(target, 4)):
            history[(week + timedelta(days=offset)).isoformat()] = True
        habits.append({
            "habit_id": f"demo_habit_{idx}",
            "title": title,
            "weekly_target": target,
            "color": color,
            "history": history,
            "meta": demo_meta("habits"),
        })
    activities = [
        {"activity_id": "demo_activity_project", "title": "Proyecto final: planificador academico", "course": "Programacion", "deadline": event_days[1].isoformat(), "estimated_hours": 5, "priority": "Alta", "status": "En progreso", "meta": demo_meta("activities")},
        {"activity_id": "demo_activity_exam", "title": "Preparacion para parcial de Fisica", "course": "Fisica", "deadline": event_days[0].isoformat(), "estimated_hours": 3, "priority": "Alta", "status": "Pendiente", "meta": demo_meta("activities")},
    ]
    progress = [
        {"progress_id": "demo_progress_1", "activity_id": "demo_activity_project", "title": "Estructura del proyecto", "done": True, "date": today.isoformat(), "meta": demo_meta("progress")},
        {"progress_id": "demo_progress_2", "activity_id": "demo_activity_project", "title": "Validacion visual", "done": False, "date": (today + timedelta(days=1)).isoformat(), "meta": demo_meta("progress")},
        {"progress_id": "demo_progress_3", "activity_id": "demo_activity_exam", "title": "Formulario de formulas", "done": True, "date": today.isoformat(), "meta": demo_meta("progress")},
    ]
    weekly_goals = [
        {
            "goal_id": "demo_goal_weekly",
            "title": "Completar 8 horas de estudio enfocado",
            "goal_type": "study_hours",
            "target": 8,
            "week_start": week.isoformat(),
            "meta": demo_meta("weekly_goals"),
        }
    ]
    logs = [
        {"time": now_iso(), "agent": "Demo", "action": "Datos de demostracion cargados", "payload": {"sample": True}, "meta": demo_meta("agent_log")}
    ]
    return {
        "courses": courses,
        "availability": availability,
        "events": events,
        "todo_items": [ensure_todo_defaults(item) for item in todo_items],
        "habits": habits,
        "activities": activities,
        "progress": progress,
        "weekly_goals": weekly_goals,
        "agent_log": logs,
    }


def apply_sample_data(store, reference_day=None):
    sample = build_sample_data(reference_day)
    remove_sample_data(store, create_backup_first=False)
    for key, items in sample.items():
        store.setdefault(key, [])
        store[key].extend(items)
    settings = store.setdefault("settings", {})
    settings["sample_data_loaded"] = True
    settings["sample_data_loaded_at"] = now_iso()
    settings.setdefault("dashboard_widgets", dict(DEFAULT_DASHBOARD_WIDGETS))
    settings["week_view_mode"] = "agenda"
    add_log(store, "Demo", "Datos de demostracion cargados", {"sections": sorted(sample)})
    return sample


def remove_sample_data(store, create_backup_first=True):
    if create_backup_first:
        create_backup(store, "before_delete_sample_data")
    counts = {}
    for key in ("courses", "availability", "events", "todo_items", "habits", "activities", "progress", "weekly_goals", "agent_log", "schedule", "classes", "timetable"):
        items = store.get(key)
        if not isinstance(items, list):
            continue
        before = len(items)
        store[key] = [item for item in items if not is_demo_item(item)]
        counts[key] = before - len(store[key])
    settings = store.setdefault("settings", {})
    settings["sample_data_loaded"] = False
    settings.pop("sample_data_loaded_at", None)
    add_log(store, "Demo", "Datos de demostracion eliminados", {"deleted": counts})
    return counts


def save_store(store, user_id=None):
    try:
        storage_backend().save_user_data(user_id, store)
        return True
    except OSError:
        return False


def create_backup(store, reason="manual", user_id=None):
    return storage_backend().backup_user_data(user_id, store, reason)


def reset_store(keep_profile=False, keep_settings=True, user_id=None):
    current = load_store(user_id)
    create_backup(current, "before_reset", user_id)
    fresh = default_store()
    if keep_profile:
        fresh["profile"] = load_profile(current)
        fresh["student"] = current.get("student", fresh["student"])
    if keep_settings:
        fresh["settings"] = current.get("settings", fresh["settings"])
    save_store(fresh, user_id)
    return fresh


def add_log(store, agent, action, payload=None):
    store["agent_log"].insert(0, {"time": now_iso(), "agent": agent, "action": action, "payload": payload or {}})
    store["agent_log"] = store["agent_log"][:120]


def visible_agent_logs(store, limit=None):
    logs = [
        log for log in store.get("agent_log", [])
        if str(log.get("agent", "")).strip().lower() != "integrations"
        and "conectado (mock)" not in str(log.get("action", "")).lower()
    ]
    return logs[:limit] if limit is not None else logs


def render_data_table(data, empty_message="Sin datos."):
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    if frame.empty:
        st.caption(empty_message)
        return
    headers = "".join(f"<th>{html_lib.escape(str(column))}</th>" for column in frame.columns)
    rows = []
    for values in frame.fillna("").astype(str).itertuples(index=False, name=None):
        cells = "".join(f"<td>{html_lib.escape(value)}</td>" for value in values)
        rows.append(f"<tr>{cells}</tr>")
    st.markdown(
        f"<div class='app-table-wrap'><table class='app-table'><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def chart_colors(store):
    theme = APP_THEMES[app_theme_name(store)]
    dark = display_mode(store) == "Oscuro"
    return {
        "background": "#1f2937" if dark else "#ffffff",
        "text": "#e5e7eb" if dark else "#344054",
        "grid": "#475569" if dark else "#e4e7ec",
        "primary": theme["primary"],
        "secondary": "#38bdf8" if dark else "#0ea5e9",
    }


def styled_chart(chart, store, height=280):
    colors = chart_colors(store)
    return (
        chart.properties(height=height, background=colors["background"])
        .configure_view(stroke=colors["grid"])
        .configure_axis(
            labelColor=colors["text"],
            titleColor=colors["text"],
            domainColor=colors["grid"],
            tickColor=colors["grid"],
            gridColor=colors["grid"],
        )
        .configure_legend(labelColor=colors["text"], titleColor=colors["text"])
        .configure_title(color=colors["text"])
    )


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def parse_time(value):
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and 0 <= float(value) < 1:
        return time_from_minutes(round(float(value) * 24 * 60))
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S", "%H"):
        try:
            return datetime.strptime(str(value).strip(), fmt).time()
        except ValueError:
            pass
    parsed = pd.to_datetime(value, errors="coerce")
    if not pd.isna(parsed):
        return parsed.time().replace(second=0, microsecond=0)
    return None


def normalize_day(value):
    text = str(value or "").strip().lower()
    aliases = {
        "lunes": "Lunes", "lun": "Lunes",
        "martes": "Martes", "mar": "Martes",
        "miercoles": "Miercoles", "miércoles": "Miercoles", "mie": "Miercoles", "mié": "Miercoles",
        "jueves": "Jueves", "jue": "Jueves",
        "viernes": "Viernes", "vie": "Viernes",
        "sabado": "Sabado", "sábado": "Sabado", "sab": "Sabado", "sáb": "Sabado",
        "domingo": "Domingo", "dom": "Domingo",
    }
    return aliases.get(text)


def normalize_schedule_columns(df):
    mapping = {}
    for col in df.columns:
        raw = str(col).strip().lower()
        if raw in {"dia", "día", "day"}:
            mapping["day"] = col
        elif raw in {"inicio", "start", "hora inicio", "empieza"}:
            mapping["start"] = col
        elif raw in {"fin", "end", "hora fin", "termina"}:
            mapping["end"] = col
        elif raw in {"nombre", "materia", "curso", "clase", "actividad"}:
            mapping["title"] = col
        elif raw in {"tipo", "categoria", "categoría"}:
            mapping["type"] = col
        elif raw in {"color", "colour"}:
            mapping["color"] = col
    return mapping


def read_schedule_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(uploaded_file, sep=None, engine="python")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(uploaded_file)
    return pd.DataFrame()


def json_from_text(text):
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end >= start:
        clean = clean[start:end + 1]
    return json.loads(clean)


def schedule_df_from_markdown(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip().startswith("|")]
    data = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        data.append(cells)
    if len(data) < 2:
        return pd.DataFrame(columns=["dia", "inicio", "fin", "nombre", "tipo"])
    headers = [h.lower().replace("día", "dia") for h in data[0]]
    rows = []
    for cells in data[1:]:
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells[:len(headers)])))
    df = pd.DataFrame(rows)
    wanted = ["dia", "inicio", "fin", "nombre", "tipo"]
    for col in wanted:
        if col not in df.columns:
            df[col] = "Clase" if col == "tipo" else ""
    return df[wanted]


def schedule_rows_from_simple_table(df, default_color="#2563eb"):
    clean = df.copy()
    clean.columns = [str(col).strip().lower().replace("día", "dia") for col in clean.columns]
    clean = clean.rename(columns={
        "day": "dia",
        "start": "inicio",
        "end": "fin",
        "title": "nombre",
        "materia": "nombre",
        "clase": "nombre",
        "type": "tipo",
    })
    for col in ["dia", "inicio", "fin", "nombre", "tipo"]:
        if col not in clean.columns:
            clean[col] = "Clase" if col == "tipo" else ""
    items = []
    for _, row in clean.iterrows():
        items.append({
            "dia": row.get("dia", ""),
            "inicio": row.get("inicio", ""),
            "fin": row.get("fin", ""),
            "nombre": row.get("nombre", ""),
            "tipo": row.get("tipo", "Clase"),
        })
    return schedule_rows_from_items(items, default_color=default_color)


def schedule_rows_from_df(df):
    mapping = normalize_schedule_columns(df)
    rows = []
    errors = []
    required = {"day", "start", "end", "title"}
    if not required.issubset(mapping):
        missing = ", ".join(sorted(required - set(mapping)))
        return [], [f"Faltan columnas: {missing}. Usa dia, inicio, fin, nombre."]
    for idx, row in df.iterrows():
        day = normalize_day(row.get(mapping["day"]))
        start_time = parse_time(str(row.get(mapping["start"], "")).strip())
        end_time = parse_time(str(row.get(mapping["end"], "")).strip())
        title = str(row.get(mapping["title"], "")).strip()
        typ = str(row.get(mapping.get("type", ""), "Clase")).strip() or "Clase"
        color = str(row.get(mapping.get("color", ""), "#2563eb")).strip() or "#2563eb"
        if not day or not start_time or not end_time or minutes(end_time) <= minutes(start_time):
            errors.append(f"Fila {idx + 1}: revisa dia, inicio y fin.")
            continue
        if not color.startswith("#") or len(color) != 7:
            color = "#2563eb"
        rows.append({
            "availability_id": make_id("av"),
            "title": title or typ,
            "day_index": DAYS_ES.index(day),
            "day_of_week": day,
            "start_time": start_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "availability_type": typ,
            "color": color,
        })
    return rows, errors


def schedule_rows_from_items(items, default_color="#2563eb"):
    rows = []
    errors = []
    for idx, item in enumerate(items or []):
        day = normalize_day(item.get("dia") or item.get("day") or item.get("day_of_week"))
        start_time = parse_time(item.get("inicio") or item.get("start") or item.get("start_time"))
        end_time = parse_time(item.get("fin") or item.get("end") or item.get("end_time"))
        title = str(item.get("nombre") or item.get("title") or item.get("materia") or item.get("clase") or "").strip()
        typ = str(item.get("tipo") or item.get("type") or "Clase").strip() or "Clase"
        color = str(item.get("color") or default_color or "#2563eb").strip()
        if not day or not start_time or not end_time or minutes(end_time) <= minutes(start_time):
            errors.append(f"Elemento {idx + 1}: revisa dia, inicio y fin.")
            continue
        if not color.startswith("#") or len(color) != 7:
            color = default_color
        rows.append({
            "availability_id": make_id("av"),
            "title": title or typ,
            "day_index": DAYS_ES.index(day),
            "day_of_week": day,
            "start_time": start_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "availability_type": typ,
            "color": color,
        })
    return rows, errors


def read_schedule_image(uploaded_file, default_color="#2563eb"):
    load_dotenv(APP_DIR)
    if not os.environ.get("OPENAI_API_KEY"):
        return [], ["Falta OPENAI_API_KEY en .env para leer horarios desde imagen."]
    prompt = (
        "Lee esta imagen de un horario academico y conviértela primero en una tabla limpia. "
        "Extrae solo clases o bloques fijos; ignora pausas, almuerzo, nombres de docentes, numeros de periodo y encabezados. "
        "Devuelve SOLO una tabla Markdown con columnas: dia | inicio | fin | nombre | tipo. "
        "Usa dias en espanol y horas en formato 24h HH:MM. Si una celda ocupa varios periodos, usa la hora inicial y final completa. "
        "Si una hora o dia no se ve claro, omite ese bloque. No agregues explicaciones."
    )
    raw = uploaded_file.getvalue()
    mime = uploaded_file.type or "image/png"
    image_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    model = os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    errors = []
    try:
        from openai import OpenAI
        client = OpenAI()

        try:
            response = client.responses.create(
                model=model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }],
            )
            table_text = response.output_text.strip()
            df = schedule_df_from_markdown(table_text)
            rows, row_errors = schedule_rows_from_simple_table(df, default_color=default_color)
            return rows, errors + row_errors, table_text
        except Exception as exc:
            errors.append(f"Responses API: {exc}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
            )
            table_text = (response.choices[0].message.content or "").strip()
            df = schedule_df_from_markdown(table_text)
            rows, row_errors = schedule_rows_from_simple_table(df, default_color=default_color)
            return rows, errors + row_errors, table_text
        except Exception as exc:
            errors.append(f"Chat Completions: {exc}")
            return [], errors, ""
    except Exception as exc:
        return [], [f"No pude iniciar OpenAI: {exc}"], ""


def week_start(selected):
    return selected - timedelta(days=selected.weekday())


def minutes(t):
    return t.hour * 60 + t.minute


def time_from_minutes(total):
    total = max(0, min(int(total), 23 * 60 + 59))
    return time(total // 60, total % 60)


def schedule_palette(store):
    custom = store.get("settings", {}).get("custom_schedule_colors", [])
    seen = set()
    palette = []
    for name, value in SCHEDULE_COLOR_PALETTE:
        if value.lower() not in seen:
            palette.append((name, value))
            seen.add(value.lower())
    for idx, value in enumerate(custom, 1):
        clean = str(value).strip()
        if clean.startswith("#") and len(clean) == 7 and clean.lower() not in seen:
            palette.append((f"Personal {idx}", clean))
            seen.add(clean.lower())
    return palette


def palette_preview(store):
    chips = []
    for name, value in schedule_palette(store):
        chips.append(
            f"<span style='display:inline-flex;align-items:center;gap:5px;margin:0 8px 6px 0;font-size:.74rem;color:#475467'>"
            f"<span style='height:13px;width:13px;border-radius:4px;background:{value};border:1px solid rgba(0,0,0,.08)'></span>{name}</span>"
        )
    st.markdown("".join(chips), unsafe_allow_html=True)


def selected_color_preview(value, caption="Seleccionado"):
    color = value or COURSE_PALETTE[0]
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;height:38px;margin-top:28px;'>"
        f"<span style='height:24px;width:34px;border-radius:7px;background:{color};border:1px solid rgba(0,0,0,.1);box-shadow:inset 0 0 0 1px rgba(255,255,255,.35)'></span>"
        f"<span style='font-size:.78rem;color:#475467'><b>{html_lib.escape(caption)}</b><br>{html_lib.escape(color)}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def color_selector(store, target_key, key, default_color=None, allow_custom=True):
    palette = schedule_palette(store)
    fallback = default_color or COURSE_PALETTE[0]
    pending_key = f"{target_key}_pending"
    if pending_key in st.session_state:
        st.session_state[target_key] = st.session_state.pop(pending_key)
    options = [value for _, value in palette]
    if fallback not in options:
        options.insert(0, fallback)
    current = st.session_state.get(target_key, fallback)
    if current not in options:
        options.append(current)
    st.session_state.setdefault(target_key, current)
    swatch_col, select_col, add_col = st.columns([.12, 1, .20])
    selected = select_col.selectbox(
        "Color",
        options,
        key=target_key,
    )
    swatch_col.markdown(
        f"<div style='height:68px;display:flex;align-items:end;justify-content:center;padding-bottom:10px;'>"
        f"<span title='{selected}' style='height:22px;width:22px;border-radius:6px;background:{selected};border:1px solid rgba(0,0,0,.16);display:inline-block;box-shadow:0 1px 2px rgba(16,24,40,.10)'></span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if allow_custom:
        add_col.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
        with add_col.popover("+"):
            custom = st.color_picker("Nuevo color", value=selected if str(selected).startswith("#") else fallback, key=f"{key}_custom")
            if st.button("Guardar", key=f"{key}_save", width="stretch"):
                store.setdefault("settings", {}).setdefault("custom_schedule_colors", [])
                if custom not in store["settings"]["custom_schedule_colors"] and custom not in COURSE_PALETTE:
                    store["settings"]["custom_schedule_colors"].append(custom)
                st.session_state[pending_key] = custom
                save_store(store)
                st.rerun()
    else:
        add_col.write("")
    selected = st.session_state.get(target_key, fallback)
    return selected


def ensure_course(store, name):
    clean = (name or "General").strip() or "General"
    for course in store["courses"]:
        if course.get("name", "").lower() == clean.lower():
            return course["course_id"]
    course = {"course_id": make_id("course"), "name": clean, "color": COURSE_PALETTE[len(store["courses"]) % len(COURSE_PALETTE)]}
    store["courses"].append(course)
    return course["course_id"]


def course_name(store, course_id):
    for course in store["courses"]:
        if course.get("course_id") == course_id:
            return course.get("name", "General")
    return "General"


def course_color(store, course_id):
    for index, course in enumerate(store["courses"]):
        if course.get("course_id") == course_id:
            course.setdefault("color", COURSE_PALETTE[index % len(COURSE_PALETTE)])
            return course["color"]
    return "#2563eb"


def remember_course_color(store, name, color):
    clean = (name or "").strip()
    if not clean or not color:
        return
    course_id = ensure_course(store, clean)
    for course in store["courses"]:
        if course.get("course_id") == course_id:
            course["color"] = color
            break


def color_for_subject(store, name, fallback="#2563eb"):
    clean = (name or "").strip().lower()
    if clean:
        for course in store["courses"]:
            if course.get("name", "").strip().lower() == clean:
                return course.get("color", fallback)
    for block in store.get("availability", []):
        if block.get("title", "").strip().lower() == clean and block.get("color"):
            return block["color"]
    return fallback


def schedule_conflicts(store, day_idx, start_time, end_time, exclude_id=None):
    start_min = minutes(start_time)
    end_min = minutes(end_time)
    conflicts = []
    for block in store.get("availability", []):
        if exclude_id and block.get("availability_id") == exclude_id:
            continue
        if int(block.get("day_index", -1)) != int(day_idx):
            continue
        block_start = parse_time(block.get("start_time"))
        block_end = parse_time(block.get("end_time"))
        if not block_start or not block_end:
            continue
        if start_min < minutes(block_end) and end_min > minutes(block_start):
            conflicts.append(block)
    return conflicts


def conflict_text(conflicts):
    return ", ".join(
        f"{item.get('title', 'Horario')} ({item.get('start_time')} - {item.get('end_time')})"
        for item in conflicts
    )


def prepare_imported_schedule_rows(store, rows, replace=False):
    clean_rows = []
    errors = []
    base_rows = [] if replace else store.get("availability", [])
    temp_store = {"availability": list(base_rows)}
    for row in rows:
        title = row.get("title", "")
        row["color"] = color_for_subject(store, title, row.get("color", "#2563eb"))
        start_time = parse_time(row.get("start_time"))
        end_time = parse_time(row.get("end_time"))
        if not start_time or not end_time:
            errors.append(f"{title}: hora invalida.")
            continue
        conflicts = schedule_conflicts(temp_store, row.get("day_index", 0), start_time, end_time)
        if conflicts:
            errors.append(f"{title}: choque con {conflict_text(conflicts)}.")
            continue
        clean_rows.append(row)
        temp_store["availability"].append(row)
        remember_course_color(store, title, row.get("color"))
    return clean_rows, errors


def pastel(hex_color):
    color = (hex_color or "#2563eb").lstrip("#")
    if len(color) != 6:
        return "#eef4ff"
    r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:], 16)
    r = round(r + (255 - r) * 0.86)
    g = round(g + (255 - g) * 0.86)
    b = round(b + (255 - b) * 0.86)
    return f"rgb({r},{g},{b})"


def completion_stats(store):
    todos = store["todo_items"]
    total = len(todos)
    done = sum(1 for item in todos if item.get("done"))
    overdue = sum(1 for item in todos if not item.get("done") and item.get("date", "") < date.today().isoformat())
    return {"total": total, "done": done, "pending": total - done, "overdue": overdue, "pct": round(done / total * 100, 1) if total else 0}


def habit_color(index):
    return COURSE_PALETTE[index % len(COURSE_PALETTE)]


def habit_history(habit):
    return core_habit_history(habit)


def is_habit_done(habit, day):
    return core_is_habit_done(habit, day)


def set_habit_done(habit, day, done):
    history = habit_history(habit)
    key = day.isoformat()
    if done:
        history[key] = True
    else:
        history.pop(key, None)
    if day == date.today():
        habit["done_today"] = done
    habit["streak"] = habit_streak(habit)


def habit_streak(habit, end_day=None):
    return core_habit_streak(habit, end_day)


def habit_best_streak(habit):
    return core_habit_best_streak(habit)


def habit_week_dates(selected=None):
    return core_habit_week_dates(selected)


def habit_week_count(habit, days):
    return core_habit_week_count(habit, days)


def habit_week_progress(habit, days):
    return core_habit_week_progress(habit, days)


def habit_month_stats(store, selected_month):
    habits = store.get("habits", [])
    _, last_day = calendar.monthrange(selected_month.year, selected_month.month)
    month_days = [date(selected_month.year, selected_month.month, day) for day in range(1, last_day + 1)]
    total_slots = len(month_days) * len(habits)
    completed_slots = sum(1 for habit in habits for day in month_days if is_habit_done(habit, day))
    perfect_days = sum(1 for day in month_days if habits and all(is_habit_done(habit, day) for habit in habits))
    best_streak = 0
    for habit in habits:
        running = 0
        for day in month_days:
            running = running + 1 if is_habit_done(habit, day) else 0
            best_streak = max(best_streak, running)
    percentage = round(completed_slots / total_slots * 100) if total_slots else 0
    return percentage, best_streak, perfect_days


def overdue_todos(store):
    today_key = date.today().isoformat()
    return [item for item in store.get("todo_items", []) if not item.get("done") and item.get("date", "") < today_key]


def replan_overdue(store, mode):
    items = overdue_todos(store)
    if not items:
        return 0
    create_backup(store, f"before_replan_{mode}")
    today = date.today()
    for index, item in enumerate(items):
        if mode == "today":
            target = today
        elif mode == "tomorrow":
            target = today + timedelta(days=1)
        else:
            activity = next((act for act in store.get("activities", []) if act.get("activity_id") == item.get("activity_id")), None)
            deadline = parse_date(activity.get("deadline")) if activity else None
            if deadline and deadline >= today:
                spread_days = [today + timedelta(days=i) for i in range((deadline - today).days + 1)]
                target = spread_days[index % len(spread_days)]
            else:
                target = today + timedelta(days=1)
        item["date"] = target.isoformat()
        item["order"] = len(store.get("todo_items", [])) + index
    add_log(store, "Progress Monitor", "Pendientes vencidos replanificados", {"mode": mode, "items": len(items)})
    return len(items)


def apply_css(store=None):
    store = store or st.session_state.get("_app_store", {})
    if not isinstance(store, dict):
        store = {}
    if not store.get("settings"):
        store = {"settings": {"app_theme": DEFAULT_APP_THEME, "display_mode": session_display_mode()}}
    st.markdown(
        """
        <style>
        .main .block-container {padding-top: 1rem; max-width: 1500px;}
        .app-title {font-size:2rem; font-weight:800; color:#101828;}
        .app-subtitle {color:#667085; margin-bottom:1rem;}
        .section-title {font-size:1.22rem; font-weight:760; margin:.4rem 0;}
        .week-day, .todo-day {border:1px solid #e4e7ec; background:#fff; border-radius:8px; padding:10px; min-height:120px;}
        .day-title {font-weight:800; color:#101828;}
        .day-date {font-size:.78rem; color:#667085; margin-bottom:8px;}
        .schedule-card, .todo-card {border-left:5px solid #2563eb; border-radius:8px; padding:8px 9px; margin-bottom:8px; overflow:hidden;}
        .schedule-title, .todo-title {font-weight:740; color:#101828; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
        .schedule-grid {width:100%; border-collapse:separate; border-spacing:0; table-layout:fixed; border:1px solid #d0d5dd; border-radius:8px; overflow:hidden; background:#fff;}
        .schedule-grid th {font-size:.78rem; color:#344054; background:#f8fafc; padding:7px 5px; border-bottom:1px solid #d0d5dd;}
        .schedule-grid td {height:54px; border-bottom:1px solid #eaecf0; border-right:1px solid #eaecf0; vertical-align:top; padding:4px; overflow:hidden;}
        .schedule-grid tr:last-child td {border-bottom:0;}
        .schedule-grid td:last-child, .schedule-grid th:last-child {border-right:0;}
        .schedule-time {width:82px; font-size:.72rem; color:#667085; background:#f8fafc; font-weight:700; text-align:center; vertical-align:middle !important;}
        .schedule-block {height:44px; border-left:4px solid #2563eb; border-radius:6px; padding:4px 6px; overflow:hidden;}
        .schedule-block-title {font-size:.76rem; font-weight:800; color:#101828; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
        .schedule-block-meta {font-size:.66rem; color:#667085; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
        .schedule-continuation {height:44px; border-left:4px solid #2563eb; border-radius:6px; opacity:.72;}
        .week-toolbar {border:1px solid #e4e7ec; background:#fff; border-radius:8px; padding:12px 14px; margin:8px 0 12px;}
        .week-summary {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:8px 0 12px;}
        .week-summary-card {border:1px solid #e4e7ec; border-radius:8px; background:#fff; padding:12px 14px;}
        .week-summary-label {font-size:.72rem; color:#667085; font-weight:800; text-transform:uppercase;}
        .week-summary-value {font-size:1.2rem; color:#101828; font-weight:850; margin-top:2px;}
        .agenda-day {border:1px solid #e4e7ec; background:#fff; border-radius:8px; padding:12px; margin-bottom:12px;}
        .agenda-day.today {border-color:#7dd3fc; box-shadow:0 0 0 3px rgba(14,165,233,.08);}
        .agenda-day-head {display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:10px;}
        .agenda-day-title {font-size:1rem; font-weight:850; color:#101828;}
        .agenda-day-date {font-size:.78rem; color:#667085; margin-top:2px;}
        .agenda-day-count {font-size:.72rem; color:#344054; background:#f2f4f7; border-radius:999px; padding:3px 8px; font-weight:800; white-space:nowrap;}
        .agenda-section {font-size:.72rem; color:#667085; font-weight:850; text-transform:uppercase; margin:10px 0 6px;}
        .agenda-card {border:1px solid #eef2f6; border-left:5px solid #2563eb; border-radius:8px; padding:9px 10px; margin-bottom:8px; background:#fcfcfd;}
        .agenda-card.compact {padding:7px 9px; margin-bottom:6px;}
        .agenda-card-title {font-weight:820; color:#101828; overflow-wrap:anywhere;}
        .agenda-card-meta {font-size:.75rem; color:#667085; margin-top:3px;}
        .agenda-empty {border:1px dashed #d0d5dd; border-radius:8px; color:#667085; padding:12px; font-size:.84rem; background:#f8fafc;}
        .today-focus {border:1px solid #bae6fd; background:#f0f9ff; border-radius:8px; padding:14px 16px; margin-bottom:12px;}
        .today-focus-title {font-size:.78rem; color:#0369a1; text-transform:uppercase; font-weight:850;}
        .today-focus-main {font-size:1.05rem; color:#0f172a; font-weight:850; margin-top:3px;}
        .today-focus-note {font-size:.82rem; color:#475569; margin-top:4px;}
        .today-hero {border:1px solid #d9e5f5; border-radius:10px; background:linear-gradient(135deg,#ffffff 0%,#f4f8ff 60%,#edf7f4 100%); padding:16px 18px; margin:10px 0 12px; box-shadow:0 10px 28px rgba(16,24,40,.05);}
        .today-hero-top {display:flex; justify-content:space-between; gap:12px; align-items:flex-start;}
        .today-hero-kicker {font-size:.74rem; color:#2563eb; text-transform:uppercase; font-weight:900; letter-spacing:.03em;}
        .today-hero-title {font-size:1.22rem; color:#101828; font-weight:900; margin-top:3px; overflow-wrap:anywhere;}
        .today-hero-note {font-size:.83rem; color:#475467; margin-top:5px; line-height:1.42;}
        .today-date-pill {white-space:nowrap; border:1px solid #c7d7fe; background:#eef4ff; color:#1d4ed8; border-radius:999px; padding:5px 10px; font-size:.76rem; font-weight:850;}
        .dashboard-card {border:1px solid #e5e7eb; border-radius:10px; background:#fff; padding:12px 13px; min-height:96px; box-shadow:0 5px 18px rgba(16,24,40,.035);}
        .dashboard-label {font-size:.72rem; color:#64748b; text-transform:uppercase; font-weight:850; letter-spacing:.02em;}
        .dashboard-value {font-size:1rem; color:#111827; font-weight:850; margin-top:5px; overflow-wrap:anywhere;}
        .dashboard-note {font-size:.76rem; color:#667085; margin-top:5px; line-height:1.35;}
        .day-plan {border:1px solid #dbeafe; background:#fbfdff; border-radius:10px; padding:12px 14px; margin:8px 0 14px; box-shadow:0 5px 18px rgba(16,24,40,.025);}
        .day-plan-step {display:grid; grid-template-columns:28px 1fr; gap:10px; align-items:start; border-top:1px solid #e8eef7; padding-top:10px; margin-top:10px;}
        .day-plan-step:first-child {border-top:0; padding-top:0; margin-top:0;}
        .plan-chip {width:28px; height:28px; border-radius:999px; display:flex; align-items:center; justify-content:center; background:#2563eb; color:white; font-weight:850; font-size:.78rem;}
        .plan-title {font-weight:850; color:#101828; overflow-wrap:anywhere;}
        .plan-meta {font-size:.76rem; color:#667085;}
        .smart-list-card {border:1px solid #e4e7ec; border-radius:8px; background:#fff; padding:10px 12px; margin-bottom:8px;}
        .smart-list-card.done {background:#f8fafc; border-color:#edf2f7; opacity:.78;}
        .smart-list-title {font-weight:800; color:#101828; overflow-wrap:anywhere;}
        .smart-list-card.done .smart-list-title {text-decoration:line-through; color:#667085;}
        .smart-list-meta {font-size:.76rem; color:#667085; margin-top:2px;}
        @media (max-width: 900px) {
            .week-summary {grid-template-columns:repeat(2,minmax(0,1fr));}
            .agenda-day-head {display:block;}
            .agenda-day-count {display:inline-block; margin-top:6px;}
        }
        .schedule-manager-head {font-size:.78rem; color:#667085; font-weight:800; margin:.25rem 0 .35rem;}
        .schedule-manager-row {border:1px solid #e4e7ec; border-radius:8px; padding:7px 9px; margin-bottom:7px; background:#fff;}
        .schedule-manager-title {font-weight:780; font-size:.9rem; color:#101828; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
        .schedule-manager-meta {font-size:.75rem; color:#667085;}
        .subtle {font-size:.76rem; color:#667085;}
        .todo-list-day {border:1px solid #e4e7ec; background:#fff; border-radius:8px; padding:10px 12px; margin-bottom:10px;}
        .todo-row-note {font-size:.76rem; color:#667085; margin-top:-8px; margin-bottom:4px;}
        .todo-overdue [data-testid="stTextInput"] input {color:#b42318; border-color:#fecdca; background:#fff5f5;}
        .todo-overdue div[data-testid="stDateInput"] input {color:#b42318;}
        .todo-done input {opacity:.7;}
        .todo-done [data-testid="stTextInput"] input {text-decoration:line-through; color:#98a2b3; background:#f8fafc;}
        .todo-card-clean {border:1px solid #e4e7ec; border-radius:10px; background:#fff; padding:12px; margin-bottom:10px; box-shadow:0 4px 14px rgba(16,24,40,.025);}
        .todo-card-clean.done {background:#f8fafc; border-color:#edf2f7; opacity:.82;}
        .todo-card-meta {font-size:.75rem; color:#667085; margin:.15rem 0 .45rem;}
        .todo-section-head {display:flex; justify-content:space-between; gap:10px; align-items:center; margin:14px 0 8px;}
        .todo-empty-note {font-size:.78rem; color:#667085; margin:-2px 0 6px; padding:2px 0;}
        .recent-activity-row {display:grid; grid-template-columns:145px 180px 1fr; gap:12px; align-items:center; border:1px solid #e4e7ec; border-radius:8px; padding:9px 11px; margin-bottom:7px; background:#fff;}
        .recent-activity-time {font-size:.72rem; color:#667085;}
        .recent-activity-agent {font-size:.78rem; color:#344054; font-weight:800;}
        .recent-activity-action {font-size:.82rem; color:#101828; font-weight:700;}
        .app-table-wrap {width:100%; overflow-x:auto; border:1px solid #e4e7ec; border-radius:8px; background:#fff;}
        .app-table {width:100%; border-collapse:collapse; font-size:.8rem;}
        .app-table th {text-align:left; color:#667085; background:#f8fafc; font-weight:800; padding:9px 10px; border-bottom:1px solid #e4e7ec;}
        .app-table td {color:#101828; padding:9px 10px; border-bottom:1px solid #eaecf0;}
        .app-table tr:last-child td {border-bottom:0;}
        .todo-section-title {font-size:1rem; font-weight:850; color:#101828;}
        .todo-section-count {font-size:.74rem; font-weight:800; color:#667085; background:#f2f4f7; border-radius:999px; padding:3px 8px;}
        div[data-testid="stTextInput"] input {font-size:.86rem;}
        input, textarea, [contenteditable="true"] {
            caret-color:#4c1d95 !important;
        }
        input:focus, textarea:focus, [contenteditable="true"]:focus {
            outline-color:#8b5cf6 !important;
            box-shadow:0 0 0 1px rgba(139,92,246,.28) !important;
        }
        div[data-testid="stCheckbox"] label {font-size:.82rem;}
        .month-toolbar {border:1px solid #e4e7ec; background:#fff; border-radius:8px; padding:12px 14px; margin:8px 0 12px;}
        .month-legend {display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 12px;}
        .month-legend-chip {display:inline-flex; align-items:center; gap:6px; border:1px solid #e4e7ec; border-radius:999px; padding:4px 9px; font-size:.74rem; color:#344054; background:#fff;}
        .month-dot {width:9px; height:9px; border-radius:999px; display:inline-block;}
        .month-week-head {font-size:.72rem; color:#667085; font-weight:850; text-transform:uppercase; text-align:center; padding:4px 0 7px;}
        .month-cell {min-height:150px; border:1px solid #e4e7ec; padding:9px; background:#fff; border-radius:8px; margin-bottom:10px; overflow:hidden; box-shadow:0 2px 8px rgba(16,24,40,.025);}
        .month-cell.clean {background:#fff;}
        .month-cell.colorful {background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);}
        .month-cell.faded {background:#f8fafc; color:#98a2b3;}
        .month-cell.today {border-color:#38bdf8; box-shadow:0 0 0 3px rgba(14,165,233,.12);}
        .month-cell.heavy {border-bottom:4px solid #f59e0b;}
        .month-cell-link, .month-cell-link * {text-decoration:none !important;} .month-cell-link {color:inherit; display:block;}
        .month-cell-top {display:flex; justify-content:space-between; align-items:center; gap:6px; margin-bottom:7px;}
        .month-day-number {font-weight:850; color:#101828; font-size:.92rem;}
        .month-day-count {font-size:.68rem; color:#475467; background:#eef2f6; border-radius:999px; padding:2px 7px; font-weight:800; white-space:nowrap;}
        .month-load {height:6px; background:#eef2f6; border-radius:999px; overflow:hidden; margin-bottom:7px;}
        .month-load-fill {height:6px; border-radius:999px;}
        .month-chip {font-size:.72rem; line-height:.95rem; border-left:4px solid #2563eb; padding:4px 6px; margin-bottom:5px; background:#f8fafc; border-radius:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#101828;}
        .month-chip.done {opacity:.58; text-decoration:line-through;}
        .month-more {font-size:.7rem; color:#667085; font-weight:750; margin-top:2px;}
        .month-empty {font-size:.74rem; color:#98a2b3; border:1px dashed #e4e7ec; border-radius:7px; padding:8px; background:#fcfcfd;}
        .month-detail {border:1px solid #e4e7ec; border-radius:8px; background:#fff; padding:14px 16px; margin:10px 0 14px;}
        .month-detail-title {font-size:1.04rem; font-weight:850; color:#101828;}
        .month-detail-meta {font-size:.8rem; color:#667085; margin-top:2px;}
        .month-detail-row {border:1px solid #eef2f6; border-left:5px solid #2563eb; border-radius:8px; background:#fcfcfd; padding:9px 10px; margin-bottom:8px;}
        .month-detail-row-title {font-weight:820; color:#101828; overflow-wrap:anywhere;}
        .month-detail-row-meta {font-size:.75rem; color:#667085; margin-top:2px;}
        @media (max-width: 900px) {
            .month-cell {min-height:118px; padding:7px;}
            .month-chip {font-size:.68rem; padding:3px 5px;}
            .month-day-count {display:none;}
        }
        div[data-testid="stMetric"] {background:#fff; border:1px solid #e4e7ec; padding:10px; border-radius:8px;}
        .habit-hero {border:1px solid #e4e7ec; background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%); border-radius:12px; padding:18px 20px; margin:8px 0 14px; box-shadow:0 8px 22px rgba(16,24,40,.05);}
        .habit-title {font-size:1.45rem; font-weight:850; color:#101828;}
        .habit-caption {color:#667085; font-size:.92rem; margin-top:3px;}
        .habit-stat-card {border:1px solid #e4e7ec; background:#fff; border-radius:12px; padding:14px 16px; min-height:95px; box-shadow:0 4px 14px rgba(16,24,40,.04);}
        .habit-stat-label {font-size:.76rem; color:#667085; font-weight:800; text-transform:uppercase;}
        .habit-stat-value {font-size:1.55rem; color:#101828; font-weight:850; line-height:1.25;}
        .habit-panel {border:1px solid #e4e7ec; background:#fff; border-radius:12px; padding:12px 14px; margin:10px 0; box-shadow:0 8px 20px rgba(16,24,40,.04);}
        .habit-row-card {border:1px solid #eef2f6; background:#fcfcfd; border-radius:12px; padding:10px 12px; margin:7px 0;}
        .habit-name {font-weight:820; color:#101828; overflow-wrap:anywhere;}
        body {
            background:
                radial-gradient(circle at 9% 12%, rgba(196,181,253,.28) 0 2px, transparent 3px),
                radial-gradient(circle at 82% 18%, rgba(217,70,239,.18) 0 1.5px, transparent 3px),
                radial-gradient(circle at 72% 78%, rgba(167,139,250,.22) 0 2px, transparent 4px),
                linear-gradient(180deg,#fbfaff 0%,#f8f5ff 42%,#ffffff 100%);
        }
        .main .block-container {
            background:rgba(255,255,255,.78);
            border:1px solid rgba(196,181,253,.32);
            border-radius:18px;
            box-shadow:0 18px 48px rgba(88,28,135,.07);
            margin-top:10px;
        }
        .app-title {
            color:#4c1d95;
            letter-spacing:.01em;
        }
        .app-title::after {
            content:" ✦";
            color:#a855f7;
        }
        .app-subtitle {
            color:#6d5f85;
        }
        .section-title {
            color:#4c1d95;
        }
        .section-title::before {
            content:"✦ ";
            color:#c084fc;
        }
        div[data-testid="stMetric"], .dashboard-card, .today-hero, .todo-card-clean, .agenda-day, .month-cell, .habit-stat-card, .habit-panel {
            border-color:#ddd6fe !important;
            box-shadow:0 10px 28px rgba(88,28,135,.055) !important;
        }
        .today-hero {
            background:
                radial-gradient(circle at 92% 18%, rgba(216,180,254,.42) 0 2px, transparent 4px),
                linear-gradient(135deg,#ffffff 0%,#faf5ff 58%,#f0f9ff 100%) !important;
        }
        .day-plan {
            border-color:#ddd6fe !important;
            background:#fdfbff !important;
        }
        .plan-chip {
            background:#8b5cf6 !important;
        }
        .smart-list-card, .month-detail, .month-detail-row {
            border-color:#e9d5ff !important;
        }
        button[kind="primary"], div[data-testid="stButton"] button {
            border-radius:10px;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color:#6d28d9;
        }
        .chat-hero {
            border:1px solid #ddd6fe;
            border-radius:14px;
            padding:16px 18px;
            margin:8px 0 14px;
            background:
                radial-gradient(circle at 8% 18%, rgba(192,132,252,.36) 0 2px, transparent 4px),
                radial-gradient(circle at 88% 22%, rgba(244,114,182,.22) 0 1.5px, transparent 4px),
                linear-gradient(135deg,#ffffff 0%,#faf5ff 58%,#f5f3ff 100%);
            box-shadow:0 12px 34px rgba(88,28,135,.08);
        }
        .chat-hero-title {font-size:1.18rem; font-weight:900; color:#4c1d95;}
        .chat-hero-note {font-size:.86rem; color:#6b5f7d; margin-top:3px;}
        .chat-empty {
            border:1px dashed #c4b5fd;
            border-radius:12px;
            background:#fdfbff;
            padding:14px;
            color:#6b5f7d;
        }
        .habit-meta {font-size:.75rem; color:#667085; margin-top:2px;}
        .habit-chip {display:inline-block; border-radius:999px; padding:2px 8px; color:#344054; background:#eef2f6; font-size:.72rem; font-weight:750; margin-top:5px;}
        .habit-day-head {text-align:center; color:#667085; font-weight:800; font-size:.76rem; padding-top:4px;}
        .habit-progress-track {height:10px; background:#eef2f6; border-radius:999px; overflow:hidden; margin-top:8px;}
        .habit-progress-fill {height:10px; border-radius:999px;}
        .habit-calendar-cell {border:1px solid #e4e7ec; border-radius:10px; min-height:108px; background:#fff; padding:8px; margin-bottom:8px; box-shadow:0 2px 8px rgba(16,24,40,.035);}
        .habit-calendar-cell.empty {background:#f8fafc; color:#98a2b3;}
        .habit-calendar-day {font-weight:850; color:#101828; font-size:.88rem;}
        .habit-calendar-note {font-size:.7rem; color:#667085; margin-top:4px; line-height:.9rem;}

        /* Pastel star polish */
        .stApp {
            background:
                radial-gradient(circle at 12% 8%, rgba(216,180,254,.45) 0 2px, transparent 3px),
                radial-gradient(circle at 28% 18%, rgba(249,168,212,.34) 0 1.5px, transparent 3px),
                radial-gradient(circle at 76% 10%, rgba(147,197,253,.38) 0 2px, transparent 4px),
                radial-gradient(circle at 88% 74%, rgba(167,243,208,.36) 0 2px, transparent 4px),
                linear-gradient(180deg,#fffaff 0%,#f8f3ff 44%,#f7fbff 100%) !important;
        }
        .main .block-container {
            background:
                radial-gradient(circle at 98% 2%, rgba(233,213,255,.42) 0 90px, transparent 92px),
                rgba(255,255,255,.82) !important;
            border:1px solid rgba(196,181,253,.48) !important;
            border-radius:22px !important;
        }
        .app-title {
            color:#4c1d95 !important;
            text-shadow:0 2px 14px rgba(168,85,247,.18);
        }
        .app-title::after {content:" \\2726 \\2727"; color:#c084fc;}
        .section-title {color:#5b21b6 !important;}
        .section-title::before {content:"\\2726  "; color:#f0abfc;}
        .section-title::after {content:"  \\2737"; color:#bae6fd;}
        div[data-testid="stMetric"] {
            background:linear-gradient(135deg,#ffffff 0%,#fdf4ff 100%) !important;
            border-color:#e9d5ff !important;
            border-top:4px solid #c4b5fd !important;
        }
        div[data-testid="stMetric"]:nth-of-type(2n) {border-top-color:#f9a8d4 !important;}
        div[data-testid="stMetric"]:nth-of-type(3n) {border-top-color:#93c5fd !important;}
        .today-hero, .chat-hero, .habit-hero {
            position:relative;
            overflow:hidden;
            background:
                radial-gradient(circle at 90% 18%, rgba(249,168,212,.35) 0 4px, transparent 5px),
                radial-gradient(circle at 78% 34%, rgba(186,230,253,.45) 0 3px, transparent 4px),
                linear-gradient(135deg,#ffffff 0%,#fdf4ff 52%,#eef6ff 100%) !important;
            border-color:#e9d5ff !important;
        }
        .today-hero::after, .chat-hero::after, .habit-hero::after {
            content:"\\2726  \\2737  \\2726";
            position:absolute;
            right:18px;
            top:12px;
            color:#c084fc;
            font-size:1.2rem;
            letter-spacing:.35rem;
            opacity:.72;
        }
        .dashboard-card, .week-summary-card, .agenda-day, .todo-card-clean, .month-cell, .habit-stat-card, .habit-panel, .smart-list-card {
            position:relative;
            border-color:#e9d5ff !important;
            background:linear-gradient(180deg,#ffffff 0%,#fffbff 100%) !important;
            box-shadow:0 12px 28px rgba(88,28,135,.06) !important;
        }
        .dashboard-card::after, .todo-card-clean::after, .agenda-day::after, .month-cell::after {
            content:"\\2726";
            position:absolute;
            right:10px;
            top:7px;
            color:#d8b4fe;
            font-size:.82rem;
            opacity:.78;
            pointer-events:none;
        }
        .agenda-card, .schedule-block, .smart-list-card, .month-chip, .month-detail-row, .habit-row-card {
            border-radius:12px !important;
            box-shadow:0 6px 18px rgba(88,28,135,.045) !important;
        }
        .agenda-card-title::before, .schedule-block-title::before, .smart-list-title::before, .todo-section-title::before {
            content:"\\2726 ";
            color:#c084fc;
            font-weight:900;
        }
        .plan-chip {
            background:linear-gradient(135deg,#a78bfa,#f9a8d4) !important;
            box-shadow:0 8px 18px rgba(168,85,247,.22);
        }
        .today-date-pill, .agenda-day-count, .todo-section-count, .month-legend-chip, .habit-chip {
            background:#f5f3ff !important;
            color:#6d28d9 !important;
            border:1px solid #ddd6fe !important;
        }
        .schedule-grid {
            border-color:#ddd6fe !important;
            box-shadow:0 12px 28px rgba(88,28,135,.05);
        }
        .schedule-grid th, .schedule-time {
            background:#faf5ff !important;
            color:#6d28d9 !important;
        }
        .month-cell.today, .agenda-day.today {
            border-color:#c084fc !important;
            box-shadow:0 0 0 4px rgba(192,132,252,.15), 0 12px 28px rgba(88,28,135,.06) !important;
        }
        .chat-empty {
            background:
                radial-gradient(circle at 96% 20%, rgba(249,168,212,.34) 0 4px, transparent 5px),
                #fdfbff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    theme = APP_THEMES[app_theme_name(store)]
    mode = display_mode(store)
    dark_css = """
        .stApp, section[data-testid="stSidebar"] {background:#0f172a !important; color:#f8fafc !important;}
        section[data-testid="stSidebar"] > div {background:linear-gradient(180deg,#111827 0%,#172033 100%) !important;}
        header[data-testid="stHeader"] {
            background:rgba(15,23,42,.96) !important;
            border-bottom:1px solid #334155 !important;
        }
        header[data-testid="stHeader"] button,
        header[data-testid="stHeader"] svg {color:#f8fafc !important; fill:#f8fafc !important;}
        [data-testid="stToolbar"], [data-testid="stDecoration"] {background:transparent !important;}
        [data-testid="stMainMenu"],
        [data-testid="stMainMenu"] *,
        [data-testid="stToolbar"] [role="menu"],
        [data-testid="stToolbar"] [role="menu"] *,
        [data-testid="stToolbar"] [data-baseweb="popover"],
        [data-testid="stToolbar"] [data-baseweb="popover"] > div,
        [data-testid="stToolbar"] [data-baseweb="popover"] > div > div,
        [data-testid="stToolbar"] [data-baseweb="popover"] ul,
        [data-baseweb="popover"] [role="menu"],
        [data-baseweb="popover"] [role="menu"] *,
        [data-baseweb="popover"] div:has(> [role="menu"]) {
            background:#1f2937 !important;
            color:#f8fafc !important;
            border-color:#526174 !important;
        }
        [data-testid="stToolbar"] [data-baseweb="popover"] {
            border:1px solid #526174 !important;
            box-shadow:0 20px 48px rgba(0,0,0,.38) !important;
        }
        [data-baseweb="popover"] {
            background:transparent !important;
        }
        [role="menuitem"], [data-testid="stMainMenu"] button {
            background:#1f2937 !important;
            color:#f8fafc !important;
        }
        [role="menuitem"]:hover, [data-testid="stMainMenu"] button:hover {
            background:#334155 !important;
            color:#ffffff !important;
        }
        [data-testid="stMainMenu"] hr,
        [data-testid="stMainMenu"] [role="separator"] {
            border-color:#475569 !important;
            background:#475569 !important;
        }
        .main .block-container {background:rgba(15,23,42,.97) !important; border-color:#475569 !important;}
        .app-title, .section-title, .chat-hero-title, h1, h2, h3, h4,
        p, label, span, [data-testid="stMarkdownContainer"] {color:#f8fafc !important;}
        .app-subtitle, .dashboard-note, .smart-list-meta, .habit-meta, .subtle,
        .todo-card-meta, .agenda-card-meta, .schedule-block-meta, .month-detail-row-meta,
        [data-testid="stCaptionContainer"], small {color:#cbd5e1 !important;}
        div[data-testid="stMetric"], .dashboard-card, .today-hero, .chat-hero, .habit-hero,
        .week-summary-card, .agenda-day, .todo-card-clean, .month-cell, .month-detail,
        .habit-stat-card, .habit-panel, .smart-list-card, .schedule-grid, .month-detail-row,
        .agenda-card, .schedule-block, .habit-row-card, .todo-list-day, .week-toolbar,
        .month-toolbar, .day-plan {
            background:linear-gradient(
                145deg,
                color-mix(in srgb, var(--app-primary) 18%, #1f2937) 0%,
                #172033 72%
            ) !important;
            border-color:#526174 !important; color:#f8fafc !important;
        }
        .today-hero, .chat-hero, .habit-hero, .dashboard-card, .week-summary-card {
            background:linear-gradient(
                135deg,
                color-mix(in srgb, var(--app-primary) 22%, #263449) 0%,
                #172033 68%
            ) !important;
        }
        input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div,
        [data-baseweb="textarea"] textarea, [data-baseweb="input"] input {
            background:#111827 !important; color:#f8fafc !important; border-color:#64748b !important;
            caret-color:#ffffff !important;
        }
        [data-testid="stTextInputRootElement"],
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stNumberInput"] [data-baseweb="input"],
        [data-testid="stTextArea"] [data-baseweb="textarea"],
        [data-testid="stMultiSelect"] [data-baseweb="select"],
        [data-testid="stSelectbox"] [data-baseweb="select"] {
            background:#111827 !important;
            color:#f8fafc !important;
            border-color:#64748b !important;
        }
        input::placeholder, textarea::placeholder,
        [data-baseweb="select"] input::placeholder {color:#94a3b8 !important; opacity:1 !important;}
        [data-baseweb="select"] span,
        [data-baseweb="select"] div,
        [data-testid="stMultiSelect"] span,
        [data-testid="stSelectbox"] span {
            color:#f8fafc !important;
        }
        [data-baseweb="tag"] {
            background:color-mix(in srgb, var(--app-primary) 32%, #273449) !important;
            color:#ffffff !important;
            border-color:var(--app-primary) !important;
        }
        input:focus, textarea:focus, [contenteditable="true"]:focus {
            border-color:var(--app-primary) !important;
            box-shadow:0 0 0 1px color-mix(in srgb, var(--app-primary) 52%, transparent) !important;
            caret-color:#ffffff !important;
        }
        [data-baseweb="select"] svg, [data-testid="stSelectbox"] svg {fill:#e2e8f0 !important;}
        div[data-testid="stButton"] button:not([kind="primary"]),
        div[data-testid="stFormSubmitButton"] button:not([kind="primary"]) {
            background:#273449 !important; border-color:#64748b !important; color:#f8fafc !important;
        }
        [data-testid="stPopover"] > button,
        [data-testid="stPopover"] button {
            background:#273449 !important;
            border-color:#64748b !important;
            color:#f8fafc !important;
        }
        [data-testid="stPopover"] button p,
        [data-testid="stPopover"] button span,
        [data-testid="stPopover"] button svg {
            color:#f8fafc !important;
            fill:#f8fafc !important;
        }
        div[data-testid="stButton"] button:not([kind="primary"]):hover {
            background:#334155 !important; border-color:var(--app-primary) !important;
        }
        [data-testid="stPopover"] button:hover {
            background:#334155 !important;
            border-color:var(--app-primary) !important;
        }
        [data-testid="stCheckbox"] label {
            color:#f8fafc !important;
        }
        [data-testid="stCheckbox"] label[data-baseweb="checkbox"] > div:first-child {
            background:#334155 !important;
            border:1px solid #94a3b8 !important;
        }
        [data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > div:first-child,
        [data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input[aria-checked="true"]) > div:first-child {
            background:var(--app-primary) !important;
            border-color:var(--app-primary) !important;
        }
        [data-testid="stCheckbox"] [role="checkbox"],
        [data-testid="stCheckbox"] [role="switch"] {
            background:#334155 !important;
            border-color:#94a3b8 !important;
        }
        [data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"],
        [data-testid="stCheckbox"] [role="switch"][aria-checked="true"] {
            background:var(--app-primary) !important;
            border-color:var(--app-primary) !important;
        }
        [data-testid="stButtonGroup"] [role="radiogroup"],
        [data-testid="stButtonGroup"] div[data-baseweb="button-group"] {
            background:#1e293b !important; border:1px solid #64748b !important;
        }
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_control"] {
            background:#1e293b !important; color:#e2e8f0 !important; border-color:#475569 !important;
        }
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_control"] p,
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_control"] span {
            color:#e2e8f0 !important;
        }
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] {
            background:var(--app-primary-dark) !important;
            border-color:var(--app-primary) !important;
            color:#ffffff !important;
        }
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] p,
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] span {
            color:#ffffff !important;
        }
        .dashboard-value, .smart-list-title, .habit-name, .month-detail-title,
        .todo-card-title, .agenda-card-title, .schedule-block-title,
        .month-detail-row-title, .day-title, .plan-title, .todo-section-title,
        .today-hero-title, .habit-title, .week-summary-value {
            color:#ffffff !important;
        }
        .habit-stat-value {color:#ffffff !important;}
        .habit-stat-label, .habit-caption {color:#aebbd0 !important;}
        .today-hero-note, .plan-meta, .dashboard-label, .week-summary-label,
        .agenda-day-date, .dashboard-note {color:#cbd5e1 !important;}
        .schedule-manager-title, .schedule-block-title, .agenda-card-title {
            color:#ffffff !important;
        }
        .schedule-manager-meta, .schedule-block-meta, .agenda-card-meta,
        .schedule-manager-head {color:#cbd5e1 !important;}
        .schedule-manager-row {
            background:linear-gradient(
                145deg,
                color-mix(in srgb, var(--app-primary) 12%, #1f2937) 0%,
                #172033 100%
            ) !important;
            border-color:#526174 !important;
        }
        .schedule-grid {background:#111827 !important; border-color:#526174 !important;}
        .schedule-grid th, .schedule-grid .schedule-time {
            background:#1e293b !important;
            color:#e2e8f0 !important;
            border-color:#475569 !important;
        }
        .schedule-grid td {
            background:#111827 !important;
            border-color:#334155 !important;
            color:#e2e8f0 !important;
        }
        .schedule-grid td:empty {background:#172033 !important;}
        .schedule-block {
            background:linear-gradient(
                145deg,
                color-mix(in srgb, var(--app-primary) 16%, #263449) 0%,
                #1b2638 100%
            ) !important;
        }
        .schedule-continuation {
            background:color-mix(in srgb, var(--app-primary) 12%, #1b2638) !important;
            opacity:.9 !important;
        }
        .habit-calendar-cell {
            background:linear-gradient(
                145deg,
                color-mix(in srgb, var(--app-primary) 10%, #1f2937) 0%,
                #172033 100%
            ) !important;
            border-color:#526174 !important;
            box-shadow:0 6px 16px rgba(0,0,0,.16) !important;
        }
        .habit-calendar-cell.empty {
            background:#141e2f !important;
            border-color:#334155 !important;
        }
        .habit-calendar-day {color:#ffffff !important;}
        .habit-calendar-note {color:#cbd5e1 !important;}
        .habit-progress-track {background:#334155 !important;}
        .month-week-head {
            color:#e2e8f0 !important;
        }
        .month-empty {
            background:#172033 !important;
            color:#cbd5e1 !important;
            border-color:#475569 !important;
        }
        .todo-section-count, .today-date-pill, .agenda-day-count, .habit-chip,
        .month-legend-chip {
            background:color-mix(in srgb, var(--app-primary) 20%, #29364b) !important;
            color:#f8fafc !important;
            border-color:color-mix(in srgb, var(--app-primary) 42%, #64748b) !important;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color:#ffffff !important;
            border-bottom-color:var(--app-primary) !important;
        }
        .agenda-card-title::before, .schedule-block-title::before,
        .smart-list-title::before, .todo-section-title::before {
            color:#d8b4fe !important;
        }
        [data-testid="stAlert"] {
            background:#172a4a !important; border-color:#365b8c !important; color:#f8fafc !important;
        }
        [data-testid="stAlert"] p, [data-testid="stAlert"] span {color:#f8fafc !important;}
        [data-testid="stExpander"] details, [data-testid="stExpander"] summary {
            background:#1e293b !important; border-color:#526174 !important; color:#f8fafc !important;
        }
        [data-testid="stExpander"] summary p, [data-testid="stExpander"] summary svg {
            color:#f8fafc !important; fill:#f8fafc !important;
        }
        [data-testid="stPopoverBody"],
        [data-testid="stPopoverBody"] > div,
        [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] {
            background:#1f2937 !important;
            color:#f8fafc !important;
        }
        [data-testid="stPopoverBody"] {
            border:1px solid #526174 !important;
            box-shadow:0 20px 48px rgba(0,0,0,.38) !important;
        }
        [data-testid="stPopoverBody"] [data-testid="stTextInputRootElement"],
        [data-testid="stPopoverBody"] [data-testid="stDateInput"] > div,
        [data-testid="stPopoverBody"] [data-baseweb="select"] > div {
            background:#111827 !important;
            color:#f8fafc !important;
            border-color:#64748b !important;
        }
        [data-baseweb="popover"], [data-baseweb="menu"], [data-baseweb="calendar"],
        [data-baseweb="calendar"] > div, [data-baseweb="calendar"] [role="grid"],
        [data-baseweb="calendar"] [role="row"], [data-baseweb="calendar"] [role="columnheader"] {
            background:#1f2937 !important;
            color:#f8fafc !important;
        }
        [data-baseweb="menu"] li, [role="option"] {
            background:#1f2937 !important;
            color:#f8fafc !important;
        }
        [data-baseweb="menu"] li:hover, [role="option"]:hover {
            background:#334155 !important;
        }
        [data-baseweb="calendar"] button,
        [data-baseweb="calendar"] [role="button"],
        [data-baseweb="calendar"] [role="gridcell"],
        [data-baseweb="calendar"] [aria-label],
        [data-baseweb="calendar"] span {
            background:#1f2937 !important;
            color:#f8fafc !important;
            border-color:#526174 !important;
        }
        [data-baseweb="calendar"] button:hover,
        [data-baseweb="calendar"] [role="gridcell"]:hover {
            background:#334155 !important;
            color:#ffffff !important;
        }
        [data-baseweb="calendar"] [aria-selected="true"],
        [data-baseweb="calendar"] [aria-current="date"],
        [data-baseweb="calendar"] button[aria-selected="true"] {
            background:var(--app-primary) !important;
            color:#ffffff !important;
        }
        [data-baseweb="calendar"] svg {
            fill:#f8fafc !important;
            color:#f8fafc !important;
        }
        [data-testid="stNumberInput"] button {
            background:#273449 !important; color:#f8fafc !important; border-color:#64748b !important;
        }
        [data-testid="stNumberInput"] button svg {fill:#f8fafc !important;}
        [data-testid="stDataFrame"] {
            background:#1f2937 !important; border:1px solid #526174 !important; border-radius:8px !important;
        }
        [data-testid="stChatInput"] {
            background:#1f2937 !important; border:1px solid #526174 !important; border-radius:12px !important;
        }
        [data-testid="stChatInput"] > div,
        [data-testid="stChatInput"] textarea {
            background:#111827 !important; color:#f8fafc !important;
        }
        [data-testid="stChatInput"] button {
            background:var(--app-primary-dark) !important; color:#ffffff !important;
        }
        [data-testid="stChatInput"] button svg {fill:#ffffff !important;}
        .chat-empty {
            background:linear-gradient(
                135deg,
                color-mix(in srgb, var(--app-primary) 14%, #1f2937) 0%,
                #172033 100%
            ) !important;
            border-color:#526174 !important; color:#e2e8f0 !important;
        }
        [data-testid="stDownloadButton"] button {
            background:var(--app-primary-dark) !important;
            color:#ffffff !important;
            border-color:var(--app-primary) !important;
        }
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span {color:#ffffff !important;}
        .app-table-wrap {background:#1f2937 !important; border-color:#526174 !important;}
        .app-table th {background:#273449 !important; color:#dbeafe !important; border-color:#526174 !important;}
        .app-table td {color:#f8fafc !important; border-color:#3f4d61 !important;}
        .app-table tbody tr:nth-child(even) {background:#1b2638 !important;}
        .recent-activity-row {
            background:linear-gradient(
                135deg,
                color-mix(in srgb, var(--app-primary) 12%, #1f2937) 0%,
                #172033 100%
            ) !important;
            border-color:#526174 !important;
        }
        .recent-activity-time {color:#94a3b8 !important;}
        .recent-activity-agent {color:#dbeafe !important;}
        .recent-activity-action {color:#ffffff !important;}
        hr, [data-testid="stSidebar"] hr {border-color:#475569 !important;}
    """
    mode_css = dark_css if mode == "Oscuro" else ""
    automatic_css = f"@media (prefers-color-scheme: dark) {{{dark_css}}}" if mode == "Automático" else ""
    st.markdown(
        f"""
        <style>
        :root {{
            --app-primary: {theme["primary"]};
            --app-primary-dark: {theme["dark"]};
            --app-primary-soft: {theme["soft"]};
            --app-primary-border: {theme["border"]};
            --app-primary-shadow: {theme["shadow"]};
        }}
        .stApp {{
            background:linear-gradient(180deg, #ffffff 0%, var(--app-primary-soft) 100%) !important;
        }}
        .main .block-container {{
            background:rgba(255,255,255,.90) !important;
            border-color:var(--app-primary-border) !important;
        }}
        .app-title, .section-title, .chat-hero-title {{
            color:var(--app-primary-dark) !important;
        }}
        .app-title::after, .section-title::before, .section-title::after,
        .today-hero::after, .chat-hero::after, .habit-hero::after,
        .dashboard-card::after, .todo-card-clean::after, .agenda-day::after,
        .month-cell::after, .agenda-card-title::before, .schedule-block-title::before,
        .smart-list-title::before, .todo-section-title::before {{
            color:var(--app-primary) !important;
        }}
        div[data-testid="stMetric"], .dashboard-card, .today-hero, .chat-hero,
        .habit-hero, .week-summary-card, .agenda-day, .todo-card-clean,
        .month-cell, .month-detail, .habit-stat-card, .habit-panel,
        .smart-list-card, .schedule-grid {{
            border-color:var(--app-primary-border) !important;
            box-shadow:0 10px 28px var(--app-primary-shadow) !important;
        }}
        .today-hero, .chat-hero, .habit-hero, .dashboard-card,
        .week-summary-card, .agenda-day, .todo-card-clean, .month-cell,
        .habit-stat-card, .smart-list-card {{
            background:linear-gradient(
                135deg,
                #ffffff 22%,
                color-mix(in srgb, var(--app-primary) 12%, var(--app-primary-soft)) 100%
            ) !important;
        }}
        .todo-card-clean, .agenda-card, .schedule-block, .habit-row-card,
        .month-detail-row, .smart-list-card {{
            background:linear-gradient(
                145deg,
                #ffffff 32%,
                color-mix(in srgb, var(--app-primary) 10%, var(--app-primary-soft)) 100%
            ) !important;
        }}
        div[data-testid="stMetric"] {{
            border-top-color:var(--app-primary) !important;
        }}
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button {{
            background:var(--app-primary) !important;
            border-color:var(--app-primary) !important;
            color:#ffffff !important;
        }}
        div[data-testid="stButton"] button:not([kind="primary"]) {{
            border-color:var(--app-primary-border) !important;
            color:var(--app-primary-dark) !important;
        }}
        div[data-testid="stButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {{
            border-color:var(--app-primary-dark) !important;
            color:var(--app-primary-dark);
        }}
        div[data-testid="stTabs"] button[aria-selected="true"],
        .today-hero-kicker, .today-focus-title {{
            color:var(--app-primary-dark) !important;
        }}
        .today-date-pill, .agenda-day-count, .todo-section-count,
        .month-legend-chip, .habit-chip, .schedule-grid th, .schedule-time {{
            background:var(--app-primary-soft) !important;
            color:var(--app-primary-dark) !important;
            border-color:var(--app-primary-border) !important;
        }}
        .plan-chip {{
            background:var(--app-primary) !important;
            box-shadow:0 8px 18px var(--app-primary-shadow) !important;
        }}
        .month-cell.today, .agenda-day.today {{
            border-color:var(--app-primary) !important;
            box-shadow:0 0 0 4px var(--app-primary-shadow) !important;
        }}
        {mode_css}
        {automatic_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_profile(store):
    with st.sidebar:
        st.markdown("## Apariencia")
        current_theme = app_theme_name(store)
        selected_theme = st.selectbox(
            "Color base",
            list(APP_THEMES),
            index=list(APP_THEMES).index(current_theme),
            key="app_theme_selector",
        )
        if selected_theme != current_theme:
            set_app_theme(store, selected_theme)
            save_store(store)
            st.rerun()
        current_mode = display_mode(store)
        selected_mode = st.segmented_control(
            "Modo",
            DISPLAY_MODES,
            default=current_mode,
            key="display_mode_selector",
        )
        if selected_mode and selected_mode != current_mode:
            set_display_mode(store, selected_mode)
            if selected_mode in AUTH_DISPLAY_MODES:
                st.session_state["preferred_display_mode"] = selected_mode
                st.session_state.pop("pending_display_mode", None)
            save_store(store)
            st.rerun()
        st.caption("La preferencia se guarda en la memoria local.")
        with st.expander("Widgets de Hoy", expanded=False):
            widgets = dashboard_preferences(store)
            widget_labels = {
                "tasks": "Próximas tareas",
                "habits": "Hábitos",
                "calendar": "Calendario",
                "statistics": "Estadísticas",
                "goals": "Metas",
                "recent_activity": "Actividad reciente",
            }
            changed = False
            for key, label in widget_labels.items():
                selected = st.checkbox(label, value=bool(widgets.get(key, True)), key=f"dashboard_widget_{key}")
                if widgets.get(key) != selected:
                    widgets[key] = selected
                    changed = True
            if changed:
                save_store(store)
        st.divider()
        st.markdown("## Cuenta")
        st.caption("Preferencias y portabilidad de tus datos.")
        current_account_mode = display_mode(store)
        account_mode = st.segmented_control(
            "Tema",
            AUTH_DISPLAY_MODES,
            default=current_account_mode if current_account_mode in AUTH_DISPLAY_MODES else "Claro",
            key="account_display_mode_selector",
        )
        if account_mode and account_mode != current_account_mode:
            set_display_mode(store, account_mode)
            st.session_state["preferred_display_mode"] = account_mode
            st.session_state.pop("pending_display_mode", None)
            save_store(store)
            st.rerun()

        st.download_button(
            "Descargar todos mis datos",
            full_backup_export_json(store),
            file_name="academic_planning_backup.json",
            mime="application/json",
            width="stretch",
        )

        with st.expander("Importar todos mis datos", expanded=False):
            st.warning(
                "Esto sobrescribirá los datos de esta cuenta. Antes de importar "
                "se creará un respaldo automático de tus datos actuales."
            )
            uploaded_full_backup = st.file_uploader(
                "Selecciona academic_planning_backup.json",
                type=["json"],
                key="account_full_backup_import",
            )
            confirm_full_import = st.checkbox(
                "Confirmo que quiero sobrescribir los datos de esta cuenta",
                value=False,
                key="account_confirm_full_backup_import",
            )
            imported_full_backup = None
            if uploaded_full_backup:
                try:
                    payload = json.loads(uploaded_full_backup.getvalue().decode("utf-8"))
                    imported_full_backup, full_import_errors = validate_full_backup_import(payload)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    full_import_errors = [f"No pude leer el JSON: {exc}"]
                if full_import_errors:
                    for error in full_import_errors[:8]:
                        st.warning(error)
                else:
                    st.success("Respaldo válido.")
                    st.caption(
                        f"Tareas: {len(imported_full_backup.get('todo_items', []))} · "
                        f"Eventos: {len(imported_full_backup.get('events', []))} · "
                        f"Hábitos: {len(imported_full_backup.get('habits', []))} · "
                        f"Horario: {len(imported_full_backup.get('availability', []))} bloques"
                    )
            if st.button(
                "Importar todos mis datos",
                width="stretch",
                disabled=not (uploaded_full_backup and imported_full_backup and confirm_full_import),
                key="account_import_full_backup_button",
            ):
                create_backup(store, "before_full_backup_import")
                apply_full_backup_import(store, imported_full_backup)
                save_store(store)
                st.session_state["full_backup_import_success"] = "Datos importados en esta cuenta."
                st.rerun()

        full_backup_message = st.session_state.pop("full_backup_import_success", None)
        if full_backup_message:
            st.success(full_backup_message)

        st.download_button(
            "Descargar horario",
            schedule_export_json(store),
            file_name="horario.json",
            mime="application/json",
            width="stretch",
        )

        with st.expander("Importar horario", expanded=False):
            uploaded_schedule_json = st.file_uploader(
                "Selecciona horario.json",
                type=["json"],
                key="account_schedule_json_import",
            )
            replace_import = st.checkbox(
                "Reemplazar mi horario actual",
                value=False,
                key="account_replace_schedule_json",
            )
            confirm_import = st.checkbox(
                "Confirmo que quiero importar este horario",
                value=False,
                key="account_confirm_schedule_json",
            )
            imported_schedule = None
            if uploaded_schedule_json:
                try:
                    payload = json.loads(uploaded_schedule_json.getvalue().decode("utf-8"))
                    imported_schedule, import_errors = validate_schedule_import(payload)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    import_errors = [f"No pude leer el JSON: {exc}"]
                if import_errors:
                    for error in import_errors[:6]:
                        st.warning(error)
                else:
                    st.success("Archivo válido.")
                    st.caption(
                        f"Disponibilidad: {len(imported_schedule.get('availability', []))} bloques · "
                        f"Cursos: {len(imported_schedule.get('courses', []))}"
                    )
                    if replace_import:
                        st.warning("Esto reemplazará tu horario actual. Se creará un respaldo antes de importar.")
                    else:
                        st.info("Se agregará al horario actual sin borrar lo existente.")
            if st.button(
                "Importar horario",
                width="stretch",
                disabled=not (uploaded_schedule_json and imported_schedule and confirm_import),
                key="account_import_schedule_json_button",
            ):
                create_backup(store, "before_schedule_json_import")
                apply_schedule_import(store, imported_schedule, replace=replace_import)
                save_store(store)
                st.success("Horario importado.")
                st.rerun()

        password_change_message = st.session_state.pop("password_change_success", None)
        if password_change_message:
            st.success(password_change_message)
        active_user = st.session_state.get("auth_user", {}) if hasattr(st, "session_state") else {}
        if active_user.get("user_id"):
            with st.expander("Cambiar contraseña", expanded=False):
                with st.form("account_change_password_form", clear_on_submit=True):
                    current_password = st.text_input(
                        "Contraseña actual",
                        type="password",
                        key="account_current_password",
                    )
                    new_password = st.text_input(
                        "Nueva contraseña",
                        type="password",
                        key="account_new_password",
                        help="Mínimo 8 caracteres.",
                    )
                    confirm_password = st.text_input(
                        "Confirmar nueva contraseña",
                        type="password",
                        key="account_confirm_new_password",
                    )
                    submitted = st.form_submit_button("Actualizar contraseña", width="stretch")
                if submitted:
                    from academic_planning.auth import UserRegistry

                    registry = UserRegistry(auth_users_path())
                    _, error = registry.change_password_confirmed(
                        active_user.get("user_id"),
                        current_password,
                        new_password,
                        confirm_password,
                    )
                    if error:
                        st.error(error)
                    else:
                        st.session_state["password_change_success"] = "Contraseña actualizada."
                        st.rerun()
        demo_counts = {
            key: sum(1 for item in store.get(key, []) if is_demo_item(item))
            for key in ("courses", "availability", "events", "todo_items", "habits", "activities", "progress", "weekly_goals")
            if isinstance(store.get(key), list)
        }
        demo_total = sum(demo_counts.values())
        if demo_total:
            with st.expander("Datos de demostración", expanded=False):
                st.caption(f"Hay {demo_total} elementos de demostración en tu cuenta. Se borrarán solo esos elementos.")
                confirm_demo_delete = st.checkbox(
                    "Confirmo que quiero borrar los datos de demostración",
                    key="account_confirm_delete_sample_data",
                )
                if st.button(
                    "Borrar datos de demostración",
                    width="stretch",
                    disabled=not confirm_demo_delete,
                    key="account_delete_sample_data_button",
                ):
                    counts = remove_sample_data(store)
                    save_store(store)
                    st.success(f"Datos de demostración borrados: {sum(counts.values())}.")
                    st.rerun()
        else:
            st.caption("No hay datos de demostración activos en esta cuenta.")

        confirm_demo_restore = st.checkbox(
            "Confirmo que quiero restaurar los datos demo",
            key="account_confirm_restore_sample_data",
        )
        if st.button(
            "Restaurar datos demo",
            width="stretch",
            disabled=not confirm_demo_restore,
            key="account_restore_sample_data_button",
        ):
            create_backup(store, "before_restore_sample_data")
            sample = apply_sample_data(store)
            save_store(store)
            st.success(f"Datos de demostración restaurados: {sum(len(items) for items in sample.values())}.")
            st.rerun()

        if active_user.get("user_id"):
            with st.expander("Eliminar cuenta", expanded=False):
                st.warning("Esta acción eliminará tu cuenta y todos tus datos. No se puede deshacer.")
                confirmation = st.text_input(
                    "Escribe ELIMINAR para confirmar",
                    key="account_delete_confirmation",
                )
                current_password = st.text_input(
                    "Contraseña actual",
                    type="password",
                    key="account_delete_password",
                )
                can_delete = confirmation == "ELIMINAR" and bool(current_password)
                if st.button(
                    "Eliminar cuenta",
                    width="stretch",
                    disabled=not can_delete,
                    key="account_delete_button",
                ):
                    from academic_planning.auth import UserRegistry, logout_session

                    registry = UserRegistry(auth_users_path())
                    deleted_user, error = registry.delete_account(active_user.get("user_id"), current_password)
                    if error:
                        st.error(error)
                    else:
                        archive_user_data(deleted_user["user_id"])
                        logout_session(st.session_state)
                        st.session_state["account_deleted"] = True
                        st.rerun()
        st.divider()
        st.markdown("## Perfil del Estudiante")
        profile = load_profile(store)
        with st.form("profile"):
            profile["name"] = st.text_input("Nombre", profile.get("name", ""))
            profile["email"] = st.text_input("Correo electrónico", profile.get("email", ""))
            profile["academic_level"] = st.text_input("Grado o nivel académico", profile.get("academic_level", ""))
            profile["primary_goal"] = st.text_input("Objetivo principal", profile.get("primary_goal", ""))
            profile["favorite_theme"] = st.selectbox(
                "Tema favorito",
                list(APP_THEMES),
                index=list(APP_THEMES).index(profile.get("favorite_theme", DEFAULT_APP_THEME)) if profile.get("favorite_theme") in APP_THEMES else 0,
            )
            profile["main_weekly_goal"] = st.text_input("Meta semanal principal", profile.get("main_weekly_goal", ""))
            profile["timezone"] = st.text_input("Zona horaria", profile.get("timezone", "America/Guatemala"))
            profile["study_preferences"] = st.text_area("Preferencias de estudio (opcional)", profile.get("study_preferences", ""), height=70)
            if st.form_submit_button("Guardar perfil", width="stretch"):
                save_profile(store, profile)
                add_log(store, "Student Profile Manager", "Perfil actualizado")
                save_store(store)
                st.success("Guardado")

        st.divider()
        st.markdown("## Datos")
        keep_profile = st.checkbox("Conservar perfil al reiniciar", value=True)
        keep_settings = st.checkbox("Conservar configuraciones al reiniciar", value=True)
        confirm_reset = st.checkbox("Confirmo que quiero borrar todo")
        if st.button("Reiniciar todo", width="stretch", disabled=not confirm_reset):
            reset_store(keep_profile=keep_profile, keep_settings=keep_settings)
            st.success("Todo quedó reiniciado.")
            st.rerun()


def visual_schedule_editor(store, block_id):
    block = next((item for item in store.get("availability", []) if item.get("availability_id") == block_id), None)
    if not block:
        return
    st.markdown("#### Editar desde horario")
    st.caption(f"{block.get('title', 'Horario')} · {block.get('start_time')} - {block.get('end_time')}")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        edit_title = c1.text_input("Nombre", value=block.get("title", ""), key=f"visual_title_{block_id}")
        edit_day = c2.selectbox("Dia", DAYS_ES, index=max(0, min(6, int(block.get("day_index", 0)))), key=f"visual_day_{block_id}")
        edit_start = c3.time_input("Inicio", value=parse_time(block.get("start_time")) or time(8, 0), step=300, key=f"visual_start_{block_id}")
        edit_end = c4.time_input("Fin", value=parse_time(block.get("end_time")) or time(8, 40), step=300, key=f"visual_end_{block_id}")
        t1, t2 = st.columns([.8, 1.4])
        edit_type = t1.selectbox(
            "Tipo",
            ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"],
            index=["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"].index(block.get("availability_type", "Clase")) if block.get("availability_type", "Clase") in ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"] else 0,
            key=f"visual_type_{block_id}",
        )
        with t2:
            edit_color = color_selector(store, f"visual_color_hex_{block_id}", f"visual_schedule_{block_id}", block.get("color", "#2563eb"), allow_custom=False)
        a1, a2, a3 = st.columns([1, 1, 4])
        if a1.button("Guardar", key=f"visual_save_{block_id}", width="stretch"):
            if not edit_title.strip():
                st.error("Escribe el nombre.")
            elif minutes(edit_end) <= minutes(edit_start):
                st.error("La hora de fin debe ser después del inicio.")
            else:
                conflicts = schedule_conflicts(store, DAYS_ES.index(edit_day), edit_start, edit_end, exclude_id=block_id)
                if conflicts:
                    st.error(f"Choque de horario con: {conflict_text(conflicts)}")
                else:
                    remember_course_color(store, edit_title.strip(), edit_color)
                    block["title"] = edit_title.strip()
                    block["day_index"] = DAYS_ES.index(edit_day)
                    block["day_of_week"] = edit_day
                    block["start_time"] = edit_start.strftime("%H:%M")
                    block["end_time"] = edit_end.strftime("%H:%M")
                    block["availability_type"] = edit_type
                    block["color"] = edit_color
                    add_log(store, "Student Profile Manager", "Bloque editado desde horario visual", {"title": edit_title.strip()})
                    save_store(store)
                    if "edit_schedule" in st.query_params:
                        del st.query_params["edit_schedule"]
                    st.rerun()
        if a2.button("Cerrar", key=f"visual_close_{block_id}", width="stretch"):
            if "edit_schedule" in st.query_params:
                del st.query_params["edit_schedule"]
            st.rerun()


def schedule_clean_blocks(store, filters=None):
    filters = filters or {}
    blocks = []
    for block in store.get("availability", []):
        start_time = parse_time(block.get("start_time"))
        end_time = parse_time(block.get("end_time"))
        if not start_time or not end_time or minutes(end_time) <= minutes(start_time):
            continue
        clean = dict(block)
        clean["_start"] = minutes(start_time)
        clean["_end"] = minutes(end_time)
        if not schedule_block_matches(clean, filters):
            continue
        blocks.append(clean)
    return sorted(blocks, key=lambda item: (int(item.get("day_index", 0)), int(item.get("_start", 0))))


def schedule_block_matches(block, filters):
    subjects = set(filters.get("subjects") or [])
    types = set(filters.get("types") or [])
    if subjects and str(block.get("title", "Horario")) not in subjects:
        return False
    if types and str(block.get("availability_type", "Clase")) not in types:
        return False
    return True


def schedule_filter_options(store):
    blocks = store.get("availability", [])
    subjects = sorted({str(block.get("title", "")).strip() for block in blocks if str(block.get("title", "")).strip()})
    types = sorted({str(block.get("availability_type", "Clase")).strip() or "Clase" for block in blocks})
    return subjects, types


def schedule_day_part(start_min):
    if start_min < 12 * 60:
        return "Mañana"
    if start_min < 18 * 60:
        return "Tarde"
    return "Noche"


def render_schedule_card(block, compact=True):
    color = block.get("color", "#2563eb")
    bg = pastel(color)
    title = html_lib.escape(str(block.get("title", "Horario")))
    typ = html_lib.escape(str(block.get("availability_type", "Clase")))
    time_label = f"{block.get('start_time')} - {block.get('end_time')}"
    block_id = html_lib.escape(str(block.get("availability_id", "")))
    compact_class = " compact" if compact else ""
    return (
        f"<a href='?edit_schedule={block_id}' target='_self' style='text-decoration:none;display:block'>"
        f"<div class='agenda-card{compact_class}' style='border-left-color:{color}; background:{bg}'>"
        f"<div class='agenda-card-title'>{title}</div>"
        f"<div class='agenda-card-meta'>{time_label} · {typ}</div>"
        f"</div></a>"
    )


def render_week_summary(days, blocks):
    today_key = date.today().isoformat()
    today_classes = [block for block in blocks if int(block.get("day_index", -1)) == date.today().weekday()]
    busy_day = "Sin clases"
    if blocks:
        counts = {idx: 0 for idx in range(7)}
        for block in blocks:
            counts[int(block.get("day_index", 0))] += 1
        busy_idx = max(counts, key=counts.get)
        busy_day = f"{DAYS_ES[busy_idx]} · {counts[busy_idx]} bloques" if counts[busy_idx] else "Sin clases"
    total_minutes = sum(max(0, int(block.get("_end", 0)) - int(block.get("_start", 0))) for block in blocks)
    visible_days = len(days)
    cards = [
        ("Bloques visibles", len(blocks)),
        ("Horas de clase", f"{round(total_minutes / 60, 1)} h"),
        ("Clases hoy", len(today_classes) if any(day.isoformat() == today_key for day in days) else "Fuera de vista"),
        ("Día más cargado", busy_day),
    ]
    html = "<div class='week-summary'>"
    for label, value in cards:
        html += f"<div class='week-summary-card'><div class='week-summary-label'>{label}</div><div class='week-summary-value'>{value}</div></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_week_agenda(store, selected, show_weekends=True, filters=None, compact=True):
    start = week_start(selected)
    days = [start + timedelta(days=i) for i in range(7 if show_weekends else 5)]
    blocks = schedule_clean_blocks(store, filters)
    state_filter = (filters or {}).get("state", "Todos")
    if state_filter == "Con clases":
        days = [day for day in days if any(int(block.get("day_index", -1)) == day.weekday() for block in blocks)]
    elif state_filter == "Sin clases":
        days = [day for day in days if not any(int(block.get("day_index", -1)) == day.weekday() for block in blocks)]
    st.markdown('<div class="section-title">Semana: agenda limpia</div>', unsafe_allow_html=True)
    if not days:
        st.info("No hay días que coincidan con los filtros.")
        return
    render_week_summary(days, blocks)
    if not blocks and state_filter != "Sin clases":
        st.info("No hay bloques de horario que coincidan con los filtros.")
    for day in days:
        day_idx = day.weekday()
        day_blocks = [block for block in blocks if int(block.get("day_index", -1)) == day_idx]
        today_class = " today" if day == date.today() else ""
        count_label = f"{len(day_blocks)} bloque{'s' if len(day_blocks) != 1 else ''}"
        html = (
            f"<div class='agenda-day{today_class}'>"
            f"<div class='agenda-day-head'><div><div class='agenda-day-title'>{DAYS_ES[day_idx]}</div>"
            f"<div class='agenda-day-date'>{day.strftime('%d/%m/%Y')}</div></div>"
            f"<div class='agenda-day-count'>{count_label}</div></div>"
        )
        if not day_blocks:
            html += "<div class='agenda-empty'>Sin clases fijas. Buen espacio para estudiar, descansar o adelantar pendientes.</div>"
        else:
            current_part = None
            for block in day_blocks:
                part = schedule_day_part(int(block.get("_start", 0)))
                if part != current_part:
                    current_part = part
                    html += f"<div class='agenda-section'>{part}</div>"
                html += render_schedule_card(block, compact=compact)
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
    edit_id = st.query_params.get("edit_schedule")
    if isinstance(edit_id, list):
        edit_id = edit_id[0] if edit_id else None
    if edit_id:
        visual_schedule_editor(store, str(edit_id))


def render_week_grid(store, selected, show_weekends=True, filters=None):
    start = week_start(selected)
    days = [start + timedelta(days=i) for i in range(7 if show_weekends else 5)]
    st.markdown('<div class="section-title">Semana: vista compacta</div>', unsafe_allow_html=True)
    blocks = schedule_clean_blocks(store, filters)
    boundaries = {int(block["_start"]) for block in blocks} | {int(block["_end"]) for block in blocks}
    if not blocks:
        st.info("Sin horario fijo para esta semana.")
        return

    ordered = sorted(boundaries)
    intervals = [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1) if ordered[i + 1] > ordered[i]]
    header = "<table class='schedule-grid'><thead><tr><th class='schedule-time'>Hora</th>"
    for day in days:
        header += f"<th>{DAYS_ES[day.weekday()]}<br><span class='subtle'>{day.strftime('%d/%m')}</span></th>"
    html = header + "</tr></thead><tbody>"

    for start_min, end_min in intervals:
        start_label = time_from_minutes(start_min).strftime("%H:%M")
        end_label = time_from_minutes(end_min).strftime("%H:%M")
        html += f"<tr><td class='schedule-time'>{start_label}<br>{end_label}</td>"
        for day in days:
            day_idx = day.weekday()
            block = next(
                (
                    item for item in blocks
                    if int(item.get("day_index", -1)) == day_idx
                    and int(item["_start"]) <= start_min
                    and int(item["_end"]) >= end_min
                ),
                None,
            )
            if not block:
                html += "<td></td>"
                continue
            color = block.get("color", "#2563eb")
            bg = pastel(color)
            if int(block["_start"]) == start_min:
                title = html_lib.escape(str(block.get("title", "Horario")))
                typ = html_lib.escape(str(block.get("availability_type", "Clase")))
                time_label = f"{block.get('start_time')} - {block.get('end_time')}"
                block_id = html_lib.escape(str(block.get("availability_id", "")))
                html += (
                    f"<td><a href='?edit_schedule={block_id}' target='_self' style='text-decoration:none;display:block'>"
                    f"<div class='schedule-block' style='border-left-color:{color}; background:{bg}'>"
                    f"<div class='schedule-block-title'>{title}</div>"
                    f"<div class='schedule-block-meta'>{time_label} · {typ}</div>"
                    f"</div></a></td>"
                )
            else:
                html += f"<td><div class='schedule-continuation' style='border-left-color:{color}; background:{bg}'></div></td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    edit_id = st.query_params.get("edit_schedule")
    if isinstance(edit_id, list):
        edit_id = edit_id[0] if edit_id else None
    if edit_id:
        visual_schedule_editor(store, str(edit_id))


def render_week(store, selected, mode="agenda", show_weekends=True, filters=None, compact=True):
    if mode == "grid":
        render_week_grid(store, selected, show_weekends=show_weekends, filters=filters)
    else:
        render_week_agenda(store, selected, show_weekends=show_weekends, filters=filters, compact=compact)


def manual_schedule_form(store):
    st.divider()
    st.subheader("Editar horario semanal")
    st.caption("Agrega clases rápido, carga un archivo o sube una imagen de tu horario.")

    with st.expander("Agregar clase rapida", expanded=True):
        q1, q2, q3, q4 = st.columns([2.2, 1.2, 1.1, 1.1])
        quick_title = q1.text_input("Clase o actividad", placeholder="Biologia, laboratorio, asesoria...", key="quick_schedule_title")
        quick_day = q2.selectbox("Dia", DAYS_ES, key="quick_schedule_day")
        quick_start = q3.time_input("Inicio", value=time(8, 0), step=300, key="quick_schedule_start")
        quick_duration = q4.selectbox("Duracion", [30, 40, 45, 50, 60, 75, 80, 90, 120, 150, 180], index=1, format_func=lambda x: f"{x} min")
        t1, t2 = st.columns([.78, 1.62])
        quick_type = t1.selectbox(
            "Tipo",
            ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"],
            key="quick_schedule_type",
        )
        suggested_color = color_for_subject(store, quick_title, COURSE_PALETTE[len(store["availability"]) % len(COURSE_PALETTE)])
        if quick_title.strip() and st.session_state.get("quick_schedule_last_title") != quick_title.strip():
            st.session_state["quick_schedule_color_hex"] = suggested_color
            st.session_state["quick_schedule_last_title"] = quick_title.strip()
        with t2:
            quick_color = color_selector(store, "quick_schedule_color_hex", "quick_schedule", suggested_color)
        if st.button("Agregar al horario", width="stretch", key="quick_schedule_submit"):
            start_total = minutes(quick_start)
            end_total = start_total + int(quick_duration)
            if not quick_title.strip():
                st.error("Escribe el nombre de la clase o actividad.")
            elif end_total > 23 * 60 + 59:
                st.error("La actividad termina después de medianoche. Ajusta la hora o duración.")
            else:
                end_time = time_from_minutes(end_total)
                conflicts = schedule_conflicts(store, DAYS_ES.index(quick_day), quick_start, end_time)
                if conflicts:
                    st.error(f"Choque de horario con: {conflict_text(conflicts)}")
                else:
                    _, error = add_schedule_block(store, quick_title, quick_day, quick_start, end_time, quick_type, quick_color)
                    if error:
                        st.error(error)
                    else:
                        save_store(store)
                        st.success("Clase agregada.")
                        st.rerun()

    with st.expander("Cargar horario desde archivo o imagen", expanded=False):
        st.caption("Archivos de tabla: CSV, TXT, XLSX o XLS. Imágenes: PNG, JPG, JPEG o WEBP. Para imagen se usa la API desde .env.")
        st.caption("Color para lo importado")
        import_color = color_selector(store, "import_schedule_color_hex", "import_schedule", COURSE_PALETTE[len(store["availability"]) % len(COURSE_PALETTE)])
        uploaded_schedule = st.file_uploader("Archivo de horario", type=["csv", "txt", "xlsx", "xls", "png", "jpg", "jpeg", "webp"], key="schedule_file_upload")
        replace_schedule = st.checkbox("Reemplazar mi horario actual con el archivo", value=False, key="replace_schedule_upload")
        if uploaded_schedule:
            try:
                suffix = Path(uploaded_schedule.name).suffix.lower()
                if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                    st.image(uploaded_schedule, caption="Horario cargado", width="stretch")
                    st.caption("Primero convierto la imagen en tabla editable. Luego esa tabla se importa al horario.")
                    if st.button("Convertir imagen en tabla", width="stretch"):
                        imported_rows, import_errors, table_text = read_schedule_image(uploaded_schedule, default_color=import_color)
                        st.session_state["schedule_image_rows"] = imported_rows
                        st.session_state["schedule_image_errors"] = import_errors
                        st.session_state["schedule_image_table"] = table_text
                    table_text = st.text_area(
                        "Tabla detectada",
                        value=st.session_state.get("schedule_image_table", ""),
                        height=220,
                        placeholder="| dia | inicio | fin | nombre | tipo |\n| Lunes | 07:00 | 07:40 | Matematica | Clase |",
                        key="schedule_image_table_editor",
                    )
                    if st.button("Leer esta tabla", width="stretch"):
                        df = schedule_df_from_markdown(table_text)
                        imported_rows, import_errors = schedule_rows_from_simple_table(df, default_color=import_color)
                        st.session_state["schedule_image_rows"] = imported_rows
                        st.session_state["schedule_image_errors"] = import_errors
                        st.session_state["schedule_image_table"] = table_text
                    imported_rows = st.session_state.get("schedule_image_rows", [])
                    import_errors = st.session_state.get("schedule_image_errors", [])
                    if import_errors:
                        with st.expander("Detalles del intento de lectura", expanded=True):
                            for error in import_errors[:6]:
                                st.warning(error)
                    if imported_rows:
                        preview_rows = [{
                            "Dia": DAYS_ES[int(row.get("day_index", 0))],
                            "Inicio": row.get("start_time"),
                            "Fin": row.get("end_time"),
                            "Nombre": row.get("title"),
                            "Tipo": row.get("availability_type"),
                        } for row in imported_rows]
                        st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)
                        if st.button("Importar bloques leidos", width="stretch"):
                            clean_rows, conflict_errors = prepare_imported_schedule_rows(store, imported_rows, replace_schedule)
                            for error in conflict_errors[:8]:
                                st.warning(error)
                            if replace_schedule:
                                create_backup(store, "before_replace_schedule")
                                store["availability"] = clean_rows
                            else:
                                store["availability"].extend(clean_rows)
                            add_log(store, "Student Profile Manager", "Horario importado desde imagen", {"blocks": len(clean_rows), "replace": replace_schedule})
                            save_store(store)
                            st.session_state.pop("schedule_image_rows", None)
                            st.session_state.pop("schedule_image_errors", None)
                            st.session_state.pop("schedule_image_table", None)
                            st.success(f"Importé {len(clean_rows)} bloques desde la imagen.")
                            st.rerun()
                    elif st.session_state.get("schedule_image_errors") == []:
                        st.info("La imagen se pudo procesar, pero no se detectaron bloques claros.")
                else:
                    preview_df = read_schedule_file(uploaded_schedule)
                    if preview_df.empty:
                        st.warning("No pude leer filas en este archivo.")
                    else:
                        st.dataframe(preview_df.head(8), width="stretch", hide_index=True)
                        imported_rows, import_errors = schedule_rows_from_df(preview_df)
                        for row in imported_rows:
                            row["color"] = row.get("color") or import_color
                        if import_errors:
                            with st.expander("Filas que necesitan revisión", expanded=True):
                                for error in import_errors[:12]:
                                    st.warning(error)
                                if len(import_errors) > 12:
                                    st.caption(f"Hay {len(import_errors) - 12} avisos mas.")
                        st.caption(f"Listas para importar: {len(imported_rows)} clases/bloques.")
                        if st.button("Importar horario", width="stretch", disabled=not imported_rows):
                            clean_rows, conflict_errors = prepare_imported_schedule_rows(store, imported_rows, replace_schedule)
                            for error in conflict_errors[:8]:
                                st.warning(error)
                            if replace_schedule:
                                create_backup(store, "before_replace_schedule")
                                store["availability"] = clean_rows
                            else:
                                store["availability"].extend(clean_rows)
                            add_log(store, "Student Profile Manager", "Horario importado", {"blocks": len(clean_rows), "replace": replace_schedule})
                            save_store(store)
                            st.success("Horario importado.")
                            st.rerun()
            except Exception as exc:
                st.error(f"No pude leer ese archivo: {exc}")

    st.markdown("#### Horario agregado")
    st.caption("Edita o elimina bloques por dia. Los colores vienen de la misma paleta para que puedas repetirlos exactamente.")
    blocks = sorted(store["availability"], key=lambda b: (int(b.get("day_index", 0)), b.get("start_time", "")))
    if not blocks:
        st.info("Todavía no hay bloques de horario.")
        return

    day_tabs = st.tabs(DAYS_ES)
    for day_idx, tab in enumerate(day_tabs):
        with tab:
            day_blocks = [block for block in blocks if int(block.get("day_index", -1)) == day_idx]
            if not day_blocks:
                st.info("Sin bloques en este dia.")
                continue
            st.markdown("<div class='schedule-manager-head'>Hora · Actividad · Acciones</div>", unsafe_allow_html=True)
            for block in day_blocks:
                block_id = block.get("availability_id") or make_id("av")
                block["availability_id"] = block_id
                st.markdown("<div class='schedule-manager-row'>", unsafe_allow_html=True)
                cols = st.columns([.18, 1.05, 2.5, .72, .72])
                cols[0].markdown(f"<div style='height:18px;width:18px;border-radius:5px;background:{block.get('color', '#2563eb')};border:1px solid rgba(0,0,0,.08)'></div>", unsafe_allow_html=True)
                cols[1].markdown(f"<div class='schedule-manager-meta'>{block.get('start_time')} - {block.get('end_time')}</div>", unsafe_allow_html=True)
                cols[2].markdown(
                    f"<div class='schedule-manager-title'>{html_lib.escape(str(block.get('title', 'Horario')))}</div>"
                    f"<div class='schedule-manager-meta'>{html_lib.escape(str(block.get('availability_type', 'Clase')))}</div>",
                    unsafe_allow_html=True,
                )
                with cols[3].popover("Editar"):
                    edit_title = st.text_input("Nombre", value=block.get("title", ""), key=f"edit_title_{block_id}")
                    edit_day = st.selectbox(
                        "Dia",
                        DAYS_ES,
                        index=max(0, min(6, int(block.get("day_index", 0)))),
                        key=f"edit_day_{block_id}",
                    )
                    edit_start = st.time_input(
                        "Inicio",
                        value=parse_time(block.get("start_time")) or time(8, 0),
                        step=300,
                        key=f"edit_start_{block_id}",
                    )
                    edit_end = st.time_input(
                        "Fin",
                        value=parse_time(block.get("end_time")) or time(8, 40),
                        step=300,
                        key=f"edit_end_{block_id}",
                    )
                    edit_type = st.selectbox(
                        "Tipo",
                        ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"],
                        index=["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"].index(block.get("availability_type", "Clase")) if block.get("availability_type", "Clase") in ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"] else 0,
                        key=f"edit_type_{block_id}",
                    )
                    edit_color = color_selector(store, f"edit_color_hex_{block_id}", f"edit_schedule_{block_id}", block.get("color", "#2563eb"), allow_custom=False)
                    if st.button("Guardar cambios", width="stretch", key=f"save_schedule_{block_id}"):
                        saved, error = update_schedule_block(
                            store,
                            block_id,
                            edit_title,
                            edit_day,
                            edit_start,
                            edit_end,
                            edit_type,
                            edit_color,
                        )
                        if not saved:
                            st.error(error)
                        else:
                            save_store(store)
                            st.rerun()
                if cols[4].button("Eliminar", key=f"delete_schedule_{block_id}"):
                    store["availability"] = [item for item in store["availability"] if item.get("availability_id") != block_id]
                    save_store(store)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


def tab_week(store):
    settings = store.setdefault("settings", {})
    selected = st.date_input("Semana", value=date.today(), key="week_date")
    start = week_start(selected)
    show_weekends = bool(settings.get("show_weekends", True))
    end = start + timedelta(days=6 if show_weekends else 4)
    st.caption(f"Semana del {start.strftime('%d/%m')} al {end.strftime('%d/%m')}")

    view_labels = {"agenda": "Agenda por día", "grid": "Vista compacta semanal"}
    current_mode = settings.get("week_view_mode", "agenda")
    current_label = view_labels.get(current_mode, "Agenda por día")
    selected_label = st.segmented_control(
        "Vista",
        list(view_labels.values()),
        default=current_label,
        key="week_view_mode_control",
    )
    mode = "grid" if selected_label == "Vista compacta semanal" else "agenda"
    c2, c3 = st.columns(2)
    new_show_weekends = c2.toggle("Mostrar fin de semana", value=show_weekends, key="week_show_weekends")
    compact = c3.toggle("Tarjetas compactas", value=bool(settings.get("compact_schedule_cards", True)), key="week_compact_cards")
    if settings.get("week_view_mode") != mode or settings.get("show_weekends") != new_show_weekends or settings.get("compact_schedule_cards") != compact:
        settings["week_view_mode"] = mode
        settings["show_weekends"] = new_show_weekends
        settings["compact_schedule_cards"] = compact
        save_store(store)

    subjects, types = schedule_filter_options(store)
    with st.expander("Filtros", expanded=False):
        f1, f2, f3 = st.columns([1.4, 1, 1])
        selected_subjects = f1.multiselect("Materia", subjects, key="week_filter_subjects")
        selected_types = f2.multiselect("Tipo", types, key="week_filter_types")
        state = f3.selectbox("Estado", ["Todos", "Con clases", "Sin clases"], key="week_filter_state")
    filters = {"subjects": selected_subjects, "types": selected_types, "state": state}
    render_week(store, selected, mode=mode, show_weekends=new_show_weekends, filters=filters, compact=compact)

    with st.expander("Administrar horario", expanded=False):
        manual_schedule_form(store)


def next_class_for_today(classes):
    now_minutes = datetime.now().hour * 60 + datetime.now().minute
    upcoming = [block for block in classes if minutes(parse_time(block.get("end_time")) or time(0, 0)) >= now_minutes]
    return upcoming[0] if upcoming else (classes[-1] if classes else None)


def todo_priority_rank(item):
    return {"Alta": 0, "Media": 1, "Baja": 2}.get(item.get("priority", "Media"), 1)


def todo_minutes(item):
    try:
        return max(5, int(item.get("estimated_minutes", 30) or 30))
    except (TypeError, ValueError):
        return 30


def todo_meta_line(item):
    pieces = []
    if item.get("course"):
        pieces.append(item.get("course"))
    pieces.append(item.get("date", "Sin fecha"))
    pieces.append(item.get("priority", "Media"))
    pieces.append(f"{todo_minutes(item)} min")
    pieces.append(item.get("energy", "Normal"))
    return " · ".join(str(piece) for piece in pieces if piece)


def progress_completed(item):
    return is_completed(item)


def item_course(item):
    course = str(item.get("course") or item.get("subject") or item.get("title") or "General").strip()
    return course or "General"


def academic_statistics(store):
    today = date.today()
    week_days = habit_week_dates(today)
    week_start_day = week_days[0]
    week_end_day = week_days[-1]
    todos = store.get("todo_items", [])
    events = store.get("events", [])
    habits = store.get("habits", [])
    progress_items = store.get("progress", [])

    todo_counts = completion_counts(todos)
    todo_total = todo_counts["total"]
    todo_done = todo_counts["completed"]
    todo_pending = todo_counts["pending"]

    habit_target = sum(max(1, int(habit.get("weekly_target", 5) or 5)) for habit in habits)
    habit_done = sum(
        min(habit_week_count(habit, week_days), max(1, int(habit.get("weekly_target", 5) or 5)))
        for habit in habits
    )
    progress_counts = completion_counts(progress_items)
    progress_total = progress_counts["total"]
    progress_done = progress_counts["completed"]
    compliance_total = todo_total + habit_target + progress_total
    compliance_done = todo_done + habit_done + progress_done
    compliance_pct = round(compliance_done / compliance_total * 100, 1) if compliance_total else 0

    course_load = {}
    weekly_minutes = 0
    for item in todos:
        item_date = parse_date(item.get("date"))
        course = item_course(item)
        minutes_value = todo_minutes(item)
        course_load.setdefault(course, {"Materia": course, "Pendientes": 0, "Completadas": 0, "Minutos": 0})
        course_load[course]["Minutos"] += minutes_value
        if item.get("done"):
            course_load[course]["Completadas"] += 1
        else:
            course_load[course]["Pendientes"] += 1
        if item_date and week_start_day <= item_date <= week_end_day:
            weekly_minutes += minutes_value

    for activity in store.get("activities", []):
        course = str(activity.get("course") or "General").strip() or "General"
        course_load.setdefault(course, {"Materia": course, "Pendientes": 0, "Completadas": 0, "Minutos": 0})
        deadline = parse_date(activity.get("deadline"))
        if deadline and week_start_day <= deadline <= week_end_day and not any(
            item.get("activity_id") == activity.get("activity_id") for item in todos
        ):
            try:
                weekly_minutes += int(float(activity.get("estimated_hours", 0) or 0) * 60)
            except (TypeError, ValueError):
                pass

    upcoming = []
    for item in todos:
        item_date = parse_date(item.get("date"))
        if item_date and item_date >= today and not item.get("done"):
            upcoming.append({
                "Fecha": item_date.isoformat(),
                "Tipo": "Pendiente",
                "Titulo": item.get("title", "Pendiente"),
                "Materia": item.get("course", "General"),
            })
    for event in events:
        event_date = parse_date(event.get("date"))
        if event_date and event_date >= today:
            upcoming.append({
                "Fecha": event_date.isoformat(),
                "Tipo": event.get("type", "Evento"),
                "Titulo": event.get("title", "Evento"),
                "Materia": event.get("course", "General"),
            })
    upcoming = sorted(upcoming, key=lambda item: item["Fecha"])[:10]

    return {
        "todo_total": todo_total,
        "todo_done": todo_done,
        "todo_pending": todo_pending,
        "compliance_pct": compliance_pct,
        "course_load": sorted(course_load.values(), key=lambda item: item["Minutos"], reverse=True),
        "upcoming": upcoming,
        "weekly_hours": round(weekly_minutes / 60, 1),
        "habit_done": habit_done,
        "habit_target": habit_target,
        "progress_done": progress_done,
        "progress_total": progress_total,
    }


def next_upcoming_event(store, today):
    events = []
    for event in store.get("events", []):
        event_date = parse_date(event.get("date"))
        if event_date and event_date >= today:
            events.append(event)
    return sorted(events, key=lambda item: item.get("date", ""))[0] if events else None


def today_progress_summary(store, today):
    today_items = todos_for_day(store, today)
    total = len(today_items)
    done = sum(1 for item in today_items if item.get("done"))
    pct = round(done / total * 100) if total else 0
    return total, done, pct


def dashboard_recommendation(today_classes, today_todos, overdue, upcoming_events):
    active_today = [item for item in today_todos if not item.get("done")]
    if overdue:
        item = sorted(overdue, key=lambda x: (todo_priority_rank(x), x.get("date", "")))[0]
        return ("Atiende lo vencido", item.get("title", "Pendiente vencido"), f"Prioridad {item.get('priority', 'Media')} · {todo_minutes(item)} min")
    if active_today:
        item = sorted(active_today, key=lambda x: (todo_priority_rank(x), todo_minutes(x)))[0]
        return ("Haz esto primero", item.get("title", "Pendiente de hoy"), f"Prioridad {item.get('priority', 'Media')} · energía {item.get('energy', 'Normal')}")
    next_class = next_class_for_today(today_classes)
    if next_class:
        return ("Prepárate para clase", next_class.get("title", "Clase"), f"{next_class.get('start_time')} - {next_class.get('end_time')}")
    if upcoming_events:
        event = upcoming_events[0]
        return ("Prepara un evento", event.get("title", "Evento"), f"Fecha: {event.get('date', '')}")
    return ("Día despejado", "Sin urgencias detectadas", "Buen momento para adelantar o descansar.")


def build_day_plan(store, today, today_classes, today_todos, overdue, upcoming_events):
    steps = []
    for item in sorted(overdue, key=lambda x: (todo_priority_rank(x), x.get("date", "")))[:3]:
        steps.append({"kind": "Vencido", "title": item.get("title", "Pendiente"), "meta": f"Venció {item.get('date', '')} · {todo_minutes(item)} min"})
    for item in sorted([i for i in today_todos if not i.get("done")], key=lambda x: (todo_priority_rank(x), todo_minutes(x)))[:4]:
        steps.append({"kind": "Hoy", "title": item.get("title", "Pendiente"), "meta": todo_meta_line(item)})
    next_class = next_class_for_today(today_classes)
    if next_class:
        steps.append({"kind": "Clase", "title": next_class.get("title", "Clase"), "meta": f"{next_class.get('start_time')} - {next_class.get('end_time')} · {next_class.get('availability_type', 'Clase')}"})
    for event in upcoming_events[:2]:
        steps.append({"kind": "Evento", "title": event.get("title", "Evento"), "meta": event.get("date", "")})
    return steps[:7]


def render_dashboard_card(label, value, note):
    st.markdown(
        f"<div class='dashboard-card'><div class='dashboard-label'>{html_lib.escape(str(label))}</div>"
        f"<div class='dashboard-value'>{html_lib.escape(str(value))}</div>"
        f"<div class='dashboard-note'>{html_lib.escape(str(note))}</div></div>",
        unsafe_allow_html=True,
    )


def render_day_plan(steps):
    if not steps:
        st.info("Tu día está libre de urgencias. Puedes usar este espacio para repasar o adelantar una entrega futura.")
        return
    html = "<div class='day-plan'>"
    for idx, step in enumerate(steps, start=1):
        html += (
            f"<div class='day-plan-step'><div class='plan-chip'>{idx}</div><div>"
            f"<div class='plan-title'>{html_lib.escape(step.get('title', ''))}</div>"
            f"<div class='plan-meta'>{html_lib.escape(step.get('kind', ''))} · {html_lib.escape(step.get('meta', ''))}</div>"
            f"</div></div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_smart_item(title, meta, color="#2563eb", done=False):
    done_class = " done" if done else ""
    st.markdown(
        f"<div class='smart-list-card{done_class}' style='border-left:5px solid {color}'>"
        f"<div class='smart-list-title'>{html_lib.escape(str(title))}</div>"
        f"<div class='smart-list-meta'>{html_lib.escape(str(meta))}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_recent_activity(store, limit=5):
    logs = visible_agent_logs(store, limit)
    if not logs:
        st.caption("Todavía no hay actividad registrada.")
        return
    for log in logs:
        st.markdown(
            f"<div class='recent-activity-row'>"
            f"<div class='recent-activity-time'>{html_lib.escape(str(log.get('time', '')))}</div>"
            f"<div class='recent-activity-agent'>{html_lib.escape(str(log.get('agent', 'Sistema')))}</div>"
            f"<div class='recent-activity-action'>{html_lib.escape(str(log.get('action', 'Actividad registrada')))}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def create_goal(store, title, goal_type, target, start_day=None):
    try:
        goal = build_weekly_goal(
            title,
            goal_type,
            target,
            start_day=start_day,
            goal_id=make_id("goal"),
        )
    except (TypeError, ValueError) as exc:
        return False, str(exc)
    store.setdefault("weekly_goals", []).append(goal)
    add_log(store, "Progress Monitor", "Meta semanal creada", {"goal": goal["title"]})
    save_store(store)
    return True, ""


def active_weekly_goals(store, reference_day=None):
    current_start = goal_week_start(reference_day).isoformat()
    return [
        goal for goal in store.get("weekly_goals", [])
        if goal.get("week_start") == current_start
    ]


def render_weekly_goals(store, editable=False):
    goals = active_weekly_goals(store)
    if editable:
        with st.expander("Agregar meta semanal", expanded=not goals):
            with st.form("weekly_goal_form", clear_on_submit=True):
                title = st.text_input("Meta", placeholder="Estudiar 10 horas")
                goal_label = st.selectbox("Tipo", list(GOAL_TYPES.values()))
                target = st.number_input("Objetivo", min_value=1.0, value=5.0, step=1.0)
                if st.form_submit_button("Crear meta", width="stretch"):
                    goal_type = next(key for key, label in GOAL_TYPES.items() if label == goal_label)
                    saved, error = create_goal(store, title, goal_type, target)
                    if saved:
                        st.rerun()
                    st.error(error)
    if not goals:
        st.info("No hay metas para esta semana.")
        return
    for goal in goals:
        progress = weekly_goal_progress(goal, store)
        c1, c2 = st.columns([1, .18])
        with c1:
            st.markdown(f"**{goal.get('title', 'Meta semanal')}**")
            unit = "h" if goal.get("goal_type") == "study_hours" else ""
            st.caption(f"{progress['current']}{unit} de {progress['target']:g}{unit}")
            st.progress(progress["percentage"])
        if editable and c2.button("Eliminar", key=f"delete_goal_{goal.get('goal_id')}"):
            store["weekly_goals"] = [
                item for item in store.get("weekly_goals", [])
                if item.get("goal_id") != goal.get("goal_id")
            ]
            save_store(store)
            st.rerun()


def motivational_message(profile, pending_tasks, pending_habits):
    name = str(profile.get("name") or "").strip()
    greeting = f"Buenos días, {name}." if name else "Buenos días."
    if not pending_tasks and not pending_habits:
        return greeting, "Tu día está al día. Puedes avanzar con calma en tu objetivo principal."
    return greeting, f"Tienes {pending_tasks} tareas y {pending_habits} hábitos pendientes hoy."


def tab_today(store):
    today = date.today()
    day_idx = today.weekday()
    st.markdown('<div class="section-title">Hoy</div>', unsafe_allow_html=True)
    st.caption(f"{DAYS_ES[day_idx]} {today.strftime('%d/%m/%Y')}")

    today_classes = sorted(
        [item for item in store.get("availability", []) if int(item.get("day_index", -1)) == day_idx],
        key=lambda item: item.get("start_time", ""),
    )
    today_todos = todos_for_day(store, today)
    overdue = sorted(overdue_todos(store), key=lambda item: (todo_priority_rank(item), item.get("date", "")))
    upcoming_events = []
    for event in store.get("events", []):
        event_date = parse_date(event.get("date"))
        if event_date and today <= event_date <= today + timedelta(days=14):
            upcoming_events.append(event)
    upcoming_events.sort(key=lambda item: item.get("date", ""))
    today_events = [event for event in upcoming_events if event.get("date") == today.isoformat()]
    pending_habits = [habit for habit in store.get("habits", []) if not is_habit_done(habit, today)]
    widgets = dashboard_preferences(store)
    profile = load_profile(store)
    greeting, motivation = motivational_message(
        profile,
        len([item for item in today_todos if not item.get("done")]),
        len(pending_habits),
    )

    next_class = next_class_for_today(today_classes)
    urgent = overdue[0] if overdue else next((item for item in today_todos if not item.get("done")), None)
    next_event = upcoming_events[0] if upcoming_events else None
    total_today, done_today, progress_pct = today_progress_summary(store, today)
    rec_label, rec_title, rec_note = dashboard_recommendation(today_classes, today_todos, overdue, upcoming_events)

    st.markdown(
        f"<div class='today-hero'><div class='today-hero-top'><div>"
        f"<div class='today-hero-kicker'>{html_lib.escape(rec_label)}</div>"
        f"<div class='today-hero-title'>{html_lib.escape(str(rec_title))}</div>"
        f"<div class='today-hero-note'>{html_lib.escape(str(rec_note))}</div>"
        f"</div><div class='today-date-pill'>{DAYS_ES[day_idx]} {today.strftime('%d/%m')}</div></div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"### {greeting}")
    st.write(motivation)
    if profile.get("primary_goal"):
        st.caption(f"Objetivo principal: {profile['primary_goal']}")

    if widgets["statistics"]:
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            render_dashboard_card("Próxima clase", next_class.get("title", "Sin clases") if next_class else "Sin clases", f"{next_class.get('start_time')} - {next_class.get('end_time')}" if next_class else "Horario despejado")
        with d2:
            render_dashboard_card("Pendiente urgente", urgent.get("title", "Nada urgente") if urgent else "Nada urgente", todo_meta_line(urgent) if urgent else "Sin vencidos ni tareas de hoy")
        with d3:
            render_dashboard_card("Eventos hoy", len(today_events), next_event.get("title", "Sin eventos") if next_event else "Agenda despejada")
        with d4:
            render_dashboard_card("Avance del día", f"{progress_pct}%", f"{done_today}/{total_today} pendientes completados" if total_today else "Sin pendientes hoy")

    if widgets["tasks"]:
        st.subheader("Planear mi día")
        render_day_plan(build_day_plan(store, today, today_classes, today_todos, overdue, upcoming_events))

    with st.expander("Filtros de hoy", expanded=False):
        status = st.radio("Estado", ["Todo", "Pendientes", "Vencidos", "Completados"], horizontal=True, key="today_status_filter")
        subject_options = sorted({str(item.get("course", "")).strip() for item in today_todos if str(item.get("course", "")).strip()})
        class_options = sorted({str(item.get("title", "")).strip() for item in today_classes if str(item.get("title", "")).strip()})
        selected_subjects = st.multiselect("Materia o clase", sorted(set(subject_options + class_options)), key="today_subject_filter")

    filtered_todos = list(today_todos)
    if status == "Pendientes":
        filtered_todos = [item for item in filtered_todos if not item.get("done")]
    elif status == "Completados":
        filtered_todos = [item for item in filtered_todos if item.get("done")]
    elif status == "Vencidos":
        filtered_todos = overdue
    if selected_subjects:
        filtered_todos = [item for item in filtered_todos if item.get("course") in selected_subjects or item.get("title") in selected_subjects]
        today_classes = [item for item in today_classes if item.get("title") in selected_subjects]

    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Clases de hoy")
        if not today_classes:
            st.info("No hay clases fijas hoy.")
        for block in today_classes:
            render_smart_item(
                block.get("title", "Horario"),
                f"{block.get('start_time')} - {block.get('end_time')} · {block.get('availability_type', 'Clase')}",
                block.get("color", "#2563eb"),
            )
    with c2:
        st.subheader("Pendientes")
        if not widgets["tasks"]:
            st.caption("Widget oculto desde la configuración lateral.")
        elif not filtered_todos:
            st.info("Sin pendientes con esos filtros.")
        for index, item in enumerate(filtered_todos if widgets["tasks"] else []):
            widget_id = f"{item.get('todo_id') or 'todo'}_{index}"
            t0, t1 = st.columns([0.14, 1])
            checked = t0.checkbox(
                "Hecho",
                value=bool(item.get("done")),
                key=f"today_done_{widget_id}",
                label_visibility="collapsed",
            )
            if checked != bool(item.get("done")):
                item["done"] = checked
                save_store(store)
                st.rerun()
            with t1:
                render_smart_item(item.get("title", "Pendiente"), todo_meta_line(item), item.get("color", "#2563eb"), done=bool(item.get("done")))

    c3, c4 = st.columns([1, 1])
    with c3:
        st.subheader("Eventos de hoy")
        if not widgets["calendar"]:
            st.caption("Widget oculto desde la configuración lateral.")
        elif not today_events:
            st.caption("Sin eventos para hoy.")
        for event in today_events if widgets["calendar"] else []:
            render_smart_item(
                f"{event.get('icon', chr(0x1F4CC))} {event.get('title', '')}",
                event.get("date", ""),
                event.get("color", "#2563eb"),
            )
    with c4:
        st.subheader("Hábitos pendientes")
        if not widgets["habits"]:
            st.caption("Widget oculto desde la configuración lateral.")
        elif not pending_habits:
            st.caption("Todos los hábitos están completos.")
        for habit in pending_habits if widgets["habits"] else []:
            render_smart_item(habit.get("title", "Hábito"), f"Racha actual: {habit_streak(habit)} días", habit.get("color", "#8b5cf6"))

    if widgets["goals"]:
        st.subheader("Metas semanales")
        render_weekly_goals(store, editable=True)

    if widgets["recent_activity"]:
        st.subheader("Actividad reciente")
        render_recent_activity(store)

def month_settings(store):
    settings = store.setdefault("settings", {})
    settings.setdefault("month_view_density", "comfortable")
    settings.setdefault("month_theme", "clean")
    settings["show_todos_in_month"] = False
    settings["show_habits_in_month"] = False
    settings.setdefault("month_show_weekends", True)
    colors = settings.setdefault("event_type_colors", {})
    for event_type, cfg in EVENT_TYPES.items():
        colors.setdefault(event_type, cfg["color"])
    return settings


def event_type_color(store, event_type, fallback="#2563eb"):
    return month_settings(store).get("event_type_colors", {}).get(event_type, fallback)


def month_visible_days(selected, show_weekends=True):
    cal = __import__("calendar").Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(selected.year, selected.month):
        weeks.append(week if show_weekends else week[:5])
    return weeks


def month_todos_for_day(store, day, include_done=True):
    items = [item for item in store.get("todo_items", []) if item.get("date") == day.isoformat()]
    if not include_done:
        items = [item for item in items if not item.get("done")]
    return sorted(items, key=lambda item: (bool(item.get("done")), int(item.get("order", 0))))


def month_classes_for_day(store, day):
    return sorted(
        [item for item in store.get("availability", []) if int(item.get("day_index", -1)) == day.weekday()],
        key=lambda item: item.get("start_time", ""),
    )


def month_habit_summary(store, day):
    habits = store.get("habits", [])
    if not habits:
        return None
    done = sum(1 for habit in habits if is_habit_done(habit, day))
    return {"done": done, "total": len(habits)}


def month_item_matches_filter(item, active_filter):
    if active_filter == "Todos":
        return True
    if active_filter == "Entregas":
        return item.get("kind") == "event" and item.get("type") == "Entrega"
    if active_filter == "Exámenes":
        return item.get("kind") == "event" and item.get("type") == "Examen"
    if active_filter == "Personales":
        return item.get("kind") == "event" and item.get("type") == "Personal"
    return True


def month_items_for_day(store, day, active_filter="Todos", show_todos=True, show_habits=False):
    items = []
    for event in store.get("events", []):
        if event.get("date") == day.isoformat():
            event_type = event.get("type", "Personal")
            items.append({
                "kind": "event",
                "id": event.get("event_id", ""),
                "title": event.get("title", "Evento"),
                "meta": event_type,
                "type": event_type,
                "icon": event.get("icon", EVENT_TYPES.get(event_type, {}).get("icon", chr(0x2B50))),
                "color": event.get("color") or event_type_color(store, event_type, "#2563eb"),
                "raw": event,
            })
    return [item for item in items if month_item_matches_filter(item, active_filter)]


def month_day_weight(store, day, items):
    classes = month_classes_for_day(store, day)
    class_load = min(4, round(len(classes) / 3))
    unfinished = sum(1 for item in items if item.get("kind") == "todo" and not item.get("done"))
    important = sum(1 for item in items if item.get("type") in {"Entrega", "Examen", "Vencido"})
    return class_load + unfinished * 2 + important * 3


def month_weight_color(weight):
    if weight >= 10:
        return "#dc2626"
    if weight >= 6:
        return "#f59e0b"
    if weight >= 3:
        return "#0ea5e9"
    return "#98a2b3"


def render_month_legend(store, show_todos=True, show_habits=False):
    chips = []
    for event_type, cfg in EVENT_TYPES.items():
        chips.append((cfg["icon"], cfg["meaning"].title(), event_type_color(store, event_type, cfg["color"])))
    html = "<div class='month-legend'>"
    for icon, label, color in chips:
        html += f"<span class='month-legend-chip'><span class='month-dot' style='background:{color}'></span>{icon} {html_lib.escape(label)}</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_month_cell(store, day, selected_month, active_filter, settings):
    show_todos = bool(settings.get("show_todos_in_month", True))
    show_habits = bool(settings.get("show_habits_in_month", False))
    density = settings.get("month_view_density", "comfortable")
    theme = settings.get("month_theme", "clean")
    visible_limit = 4 if density == "compact" else 5
    items = month_items_for_day(store, day, active_filter, show_todos, show_habits)
    weight = month_day_weight(store, day, items)
    faded = " faded" if day.month != selected_month.month else ""
    today_class = " today" if day == date.today() else ""
    heavy = " heavy" if weight >= 6 else ""
    cell_class = f"month-cell {theme}{faded}{today_class}{heavy}"
    load_width = min(100, weight * 10)
    load_color = month_weight_color(weight)
    href = f"?month_day={day.isoformat()}"
    html = f"<a class='month-cell-link' href='{href}' target='_self'><div class='{cell_class}'>"
    html += f"<div class='month-cell-top'><span class='month-day-number'>{day.day}</span></div>"
    html += f"<div class='month-load'><div class='month-load-fill' style='width:{load_width}%; background:{load_color}'></div></div>"
    if not items:
        html += "<div class='month-empty'>Libre</div>"
    else:
        for item in items[:visible_limit]:
            color = item.get("color", "#2563eb")
            bg = pastel(color)
            done = " done" if item.get("done") else ""
            label = html_lib.escape(f"{item.get('icon', '')} {item.get('title', '')}".strip())
            html += f"<div class='month-chip{done}' style='border-left-color:{color}; background:{bg}'>{label}</div>"
        if len(items) > visible_limit:
            html += f"<div class='month-more'>+{len(items) - visible_limit} más</div>"
    html += "</div></a>"
    return html


def selected_month_day(default_day, selected_month):
    raw = st.query_params.get("month_day")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    parsed = parse_date(raw) if raw else None
    if parsed and parsed.year == selected_month.year and parsed.month == selected_month.month:
        return parsed
    return default_day if default_day.month == selected_month.month else selected_month


def create_event(store, title, event_date, event_type, color):
    clean_title, error = required_text(title, "un título para el evento")
    if error:
        return False, error
    if not isinstance(event_date, date):
        return False, "Selecciona una fecha válida para el evento."
    store["events"].append({
        "event_id": make_id("event"),
        "title": clean_title,
        "date": event_date.isoformat(),
        "icon": EVENT_TYPES.get(event_type, EVENT_TYPES["Personal"])["icon"],
        "type": event_type,
        "color": color,
    })
    save_store(store)
    return True, ""


def save_event_from_detail(store, event, title, event_date, event_type, color):
    clean_title, error = required_text(title, "un título para el evento")
    if error:
        return False, error
    if not isinstance(event_date, date):
        return False, "Selecciona una fecha válida para el evento."
    event["title"] = clean_title
    event["date"] = event_date.isoformat()
    event["type"] = event_type
    event["icon"] = EVENT_TYPES.get(event_type, EVENT_TYPES["Personal"])["icon"]
    event["color"] = color
    save_store(store)
    return True, ""


def render_day_detail(store, day, active_filter, settings):
    show_todos = bool(settings.get("show_todos_in_month", True))
    show_habits = bool(settings.get("show_habits_in_month", False))
    items = month_items_for_day(store, day, active_filter, show_todos, show_habits)
    classes = month_classes_for_day(store, day)
    day_events = [event for event in store.get("events", []) if event.get("date") == day.isoformat()]
    weight = month_day_weight(store, day, items)
    st.markdown(
        f"<div class='month-detail'><div class='month-detail-title'>{DAYS_ES[day.weekday()]} {day.strftime('%d/%m/%Y')}</div>"
        f"<div class='month-detail-meta'>{len(day_events)} eventos · {len(classes)} clases fijas · peso {weight}</div></div>",
        unsafe_allow_html=True,
    )

    with st.popover("Agregar evento"):
        with st.form(f"event_quick_{day.isoformat()}", clear_on_submit=True):
            title = st.text_input("Evento", placeholder="Parcial, entrega, reunión...")
            event_date = st.date_input("Fecha", value=day, key=f"event_date_detail_{day.isoformat()}")
            event_type = st.selectbox("Tipo", list(EVENT_TYPES.keys()), key=f"event_type_detail_{day.isoformat()}")
            color = st.color_picker("Color", event_type_color(store, event_type, EVENT_TYPES[event_type]["color"]), key=f"event_color_detail_{day.isoformat()}")
            if st.form_submit_button("Guardar evento", width="stretch"):
                saved, error = create_event(store, title, event_date, event_type, color)
                if saved:
                    st.rerun()
                st.error(error)
    if classes:
        with st.expander("Clases fijas de este día", expanded=False):
            for block in classes:
                render_smart_item(block.get("title", "Clase"), f"{block.get('start_time')} - {block.get('end_time')} · {block.get('availability_type', 'Clase')}", block.get("color", "#2563eb"))

    day_events = [event for event in store.get("events", []) if event.get("date") == day.isoformat()]
    if day_events:
        st.subheader("Eventos")
    for event in day_events:
        event_id = event.get("event_id", make_id("event"))
        event["event_id"] = event_id
        color = event.get("color") or event_type_color(store, event.get("type", "Personal"), "#2563eb")
        st.markdown(
            f"<div class='month-detail-row' style='border-left-color:{color}; background:{pastel(color)}'>"
            f"<div class='month-detail-row-title'>{html_lib.escape(str(event.get('icon', '') + ' ' + event.get('title', 'Evento')))}</div>"
            f"<div class='month-detail-row-meta'>{html_lib.escape(str(event.get('type', 'Evento')))} · {event.get('date', '')}</div></div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"Editar {event.get('title', 'evento')}", expanded=False):
            e1, e2 = st.columns([1.4, 1])
            title = e1.text_input("Título", value=event.get("title", ""), key=f"month_edit_title_{event_id}")
            event_date = e2.date_input("Fecha", value=parse_date(event.get("date")) or day, key=f"month_edit_date_{event_id}")
            e3, e4 = st.columns([1, 1])
            event_type = e3.selectbox("Tipo", list(EVENT_TYPES.keys()), index=list(EVENT_TYPES.keys()).index(event.get("type", "Personal")) if event.get("type", "Personal") in EVENT_TYPES else 0, key=f"month_edit_type_{event_id}")
            picked_color = e4.color_picker("Color", value=color, key=f"month_edit_color_{event_id}")
            b1, b2 = st.columns([1, 1])
            if b1.button("Guardar cambios", key=f"month_save_event_{event_id}", width="stretch"):
                saved, error = save_event_from_detail(store, event, title, event_date, event_type, picked_color)
                if saved:
                    st.rerun()
                st.error(error)
            confirm = st.checkbox("Confirmar eliminación", key=f"month_confirm_delete_{event_id}")
            if b2.button("Eliminar", key=f"month_delete_event_{event_id}", width="stretch", disabled=not confirm):
                store["events"] = [item for item in store["events"] if item.get("event_id") != event_id]
                save_store(store)
                st.rerun()

    day_todos = month_todos_for_day(store, day)
    if show_todos and day_todos:
        st.subheader("Pendientes")
        for todo in day_todos:
            color = todo.get("color", event_type_color(store, "Pendiente", "#7c3aed"))
            cols = st.columns([.12, 2.6, .7])
            done = cols[0].checkbox("", value=bool(todo.get("done")), key=f"month_done_{todo.get('todo_id')}")
            title = cols[1].text_input("Pendiente", value=todo.get("title", ""), key=f"month_todo_title_{todo.get('todo_id')}", label_visibility="collapsed")
            new_date = cols[2].date_input("Fecha", value=parse_date(todo.get("date")) or day, key=f"month_todo_date_{todo.get('todo_id')}", label_visibility="collapsed")
            changed = done != bool(todo.get("done")) or title != todo.get("title") or new_date.isoformat() != todo.get("date")
            if changed:
                todo["done"] = done
                todo["title"] = title.strip() or todo.get("title", "Pendiente")
                todo["date"] = new_date.isoformat()
                save_store(store)
                st.rerun()
            st.markdown(f"<div class='month-detail-row-meta' style='margin-top:-8px; margin-bottom:8px; color:{color}'>{html_lib.escape(str(todo.get('course', 'General')))}</div>", unsafe_allow_html=True)

    if show_habits:
        summary = month_habit_summary(store, day)
        if summary:
            st.subheader("Hábitos")
            st.caption(f"{summary['done']}/{summary['total']} completados en este día.")


def render_month_preferences(store):
    settings = month_settings(store)
    with st.expander("Personalizar calendario", expanded=False):
        p1, p2, p3 = st.columns([1, 1, 1])
        density_label = p1.segmented_control(
            "Densidad",
            ["Cómoda", "Compacta"],
            default="Compacta" if settings.get("month_view_density") == "compact" else "Cómoda",
            key="month_density_control",
        )
        theme_label = p2.segmented_control(
            "Estilo",
            ["Limpio", "Colorido"],
            default="Colorido" if settings.get("month_theme") == "colorful" else "Limpio",
            key="month_theme_control",
        )
        show_weekends = p3.toggle("Mostrar fin de semana", value=bool(settings.get("month_show_weekends", True)), key="month_weekend_toggle")
        new_density = "compact" if density_label == "Compacta" else "comfortable"
        new_theme = "colorful" if theme_label == "Colorido" else "clean"
        changed = (
            settings.get("month_view_density") != new_density
            or settings.get("month_theme") != new_theme
            or settings.get("month_show_weekends") != show_weekends
        )
        settings["month_view_density"] = new_density
        settings["month_theme"] = new_theme
        settings["month_show_weekends"] = show_weekends
        settings["show_todos_in_month"] = False
        settings["show_habits_in_month"] = False

        st.caption("Colores por tipo")
        color_cols = st.columns(3)
        editable_types = list(EVENT_TYPES.keys())
        for index, event_type in enumerate(editable_types):
            fallback = EVENT_TYPES.get(event_type, {}).get("color", {"Pendiente": "#7c3aed", "Vencido": "#b42318", "Hábito": "#0f766e"}.get(event_type, "#2563eb"))
            current = event_type_color(store, event_type, fallback)
            picked = color_cols[index % 3].color_picker(event_type, value=current, key=f"month_type_color_{event_type}")
            if picked != current:
                settings.setdefault("event_type_colors", {})[event_type] = picked
                changed = True
        if changed:
            save_store(store)


def tab_month(store):
    settings = month_settings(store)
    m1, m2 = st.columns([1, .5])
    month_name = m1.selectbox("Mes", MONTHS_ES, index=date.today().month - 1, key="month_name")
    year = m2.number_input("Año", min_value=2020, max_value=2100, value=date.today().year, step=1, key="month_year")
    selected = date(int(year), MONTHS_ES.index(month_name) + 1, 1)
    selected_day = selected_month_day(date.today(), selected)

    st.markdown(f"<div class='section-title'>{month_name} {int(year)}</div>", unsafe_allow_html=True)
    filters = ["Todos", "Entregas", "Exámenes", "Personales"]
    active_filter = st.segmented_control("Filtro", filters, default="Todos", key="month_filter")
    render_month_preferences(store)
    render_month_legend(store, False, False)

    weeks = month_visible_days(selected, bool(settings.get("month_show_weekends", True)))
    visible_days = DAYS_ES if bool(settings.get("month_show_weekends", True)) else DAYS_ES[:5]
    header = st.columns(len(visible_days))
    for i, day in enumerate(visible_days):
        header[i].markdown(f"<div class='month-week-head'>{day[:3]}</div>", unsafe_allow_html=True)
    for week in weeks:
        cols = st.columns(len(visible_days))
        for i, d in enumerate(week):
            cols[i].markdown(render_month_cell(store, d, selected, active_filter, settings), unsafe_allow_html=True)

    render_day_detail(store, selected_day, active_filter, settings)

    month_events = sorted(
        [event for event in store["events"] if parse_date(event.get("date")) and parse_date(event.get("date")).year == selected.year and parse_date(event.get("date")).month == selected.month],
        key=lambda event: event.get("date", ""),
    )
    if month_events:
        with st.expander("Eventos del mes", expanded=False):
            for event in month_events:
                color = event.get("color") or event_type_color(store, event.get("type", "Personal"), "#2563eb")
                st.markdown(
                    f"<div class='month-detail-row' style='border-left-color:{color}; background:{pastel(color)}'>"
                    f"<div class='month-detail-row-title'>{html_lib.escape(str(event.get('icon', chr(0x1F4CC)) + ' ' + event.get('title', 'Evento')))}</div>"
                    f"<div class='month-detail-row-meta'>{event.get('date', '')} · {html_lib.escape(str(event.get('type', 'Evento')))}</div></div>",
                    unsafe_allow_html=True,
                )


def todos_for_day(store, d):
    items = [item for item in store["todo_items"] if item.get("date") == d.isoformat()]
    return sorted(items, key=lambda item: (bool(item.get("done")), int(item.get("order", 0))))


def move_todo(store, todo_id, direction):
    item = next((t for t in store["todo_items"] if t.get("todo_id") == todo_id), None)
    if not item:
        return
    same_day = sorted([t for t in store["todo_items"] if t.get("date") == item.get("date")], key=lambda t: int(t.get("order", 0)))
    idx = next((i for i, t in enumerate(same_day) if t.get("todo_id") == todo_id), None)
    target = idx - 1 if direction == "up" else idx + 1
    if idx is None or target < 0 or target >= len(same_day):
        return
    same_day[idx]["order"], same_day[target]["order"] = same_day[target].get("order", target), same_day[idx].get("order", idx)


def update_reading_progress(store, item, pages_done):
    meta = item.get("meta", {})
    if meta.get("kind") != "reading":
        return
    planned_end = int(meta.get("page_end", 0))
    start_page = int(meta.get("page_start", 1))
    actual_end = start_page + int(pages_done) - 1
    activity_id = item.get("activity_id")
    activity = next((a for a in store["activities"] if a.get("activity_id") == activity_id), None)
    if not activity or actual_end >= planned_end:
        return
    future = [
        t for t in store["todo_items"]
        if t.get("activity_id") == activity_id
        and t.get("todo_id") != item.get("todo_id")
        and not t.get("done")
        and t.get("date", "") > item.get("date", "")
    ]
    for old in future:
        store["todo_items"].remove(old)
    remaining_start = actual_end + 1
    total_pages = int(activity.get("metadata", {}).get("total_pages", planned_end))
    deadline = parse_date(activity.get("deadline")) or date.today()
    new_items = redistribute_reading_plan(activity_id, activity.get("title", "Lectura"), remaining_start, total_pages, date.today() + timedelta(days=1), deadline)
    existing_keys = {
        (todo.get("activity_id"), todo.get("date"), todo.get("title"))
        for todo in store["todo_items"]
    }
    clean_items = []
    for new_item in new_items:
        key = (new_item.get("activity_id"), new_item.get("date"), new_item.get("title"))
        if key in existing_keys:
            continue
        new_item["order"] = len(store["todo_items"]) + len(clean_items)
        ensure_todo_defaults(new_item)
        clean_items.append(new_item)
    store["todo_items"].extend(clean_items)


def todo_section_items(store, start, end):
    today = date.today()
    overdue_ids = {item.get("todo_id") for item in overdue_todos(store)}
    today_ids = {item.get("todo_id") for item in todos_for_day(store, today)}
    week_items = []
    completed = []
    for item in store.get("todo_items", []):
        item_date = parse_date(item.get("date"))
        if not item_date:
            continue
        if item.get("done") and start <= item_date <= end:
            completed.append(item)
        elif start <= item_date <= end and item.get("todo_id") not in overdue_ids and item.get("todo_id") not in today_ids:
            week_items.append(item)
    return (
        sorted(overdue_todos(store), key=lambda item: (item.get("date", ""), todo_priority_rank(item))),
        [item for item in todos_for_day(store, today) if not item.get("done")],
        sorted(week_items, key=lambda item: (item.get("date", ""), todo_priority_rank(item), int(item.get("order", 0)))),
        sorted(completed, key=lambda item: (item.get("date", ""), int(item.get("order", 0)))),
    )


def render_todo_section_header(title, items):
    st.markdown(
        f"<div class='todo-section-head'><div class='todo-section-title'>{html_lib.escape(title)}</div>"
        f"<div class='todo-section-count'>{len(items)}</div></div>",
        unsafe_allow_html=True,
    )


def render_todo_card(store, item, key_prefix):
    ensure_todo_defaults(item)
    is_done = bool(item.get("done"))
    is_overdue = not is_done and item.get("date", "") < date.today().isoformat()
    color = "#b42318" if is_overdue else item.get("color", "#2563eb")
    title_class = "text-decoration:line-through;color:#667085;" if is_done else ""
    status_note = "Vencida" if is_overdue else "Completada" if is_done else item.get("date", "Sin fecha")

    st.markdown(
        f"<div class='todo-card-clean {'done' if is_done else ''}' style='border-left:5px solid {color}'>",
        unsafe_allow_html=True,
    )
    c0, c1, c2 = st.columns([0.14, 2.7, 0.9])
    done = c0.checkbox(
        "Hecho",
        value=is_done,
        key=f"{key_prefix}_done_{item.get('todo_id')}",
        label_visibility="collapsed",
    )
    description_html = ""
    if item.get("description"):
        description_html = f"<div class='todo-card-meta'>{html_lib.escape(item.get('description', ''))}</div>"
    c1.markdown(
        f"<div class='todo-card-title' style='font-weight:850;overflow-wrap:anywhere;{title_class}'>{html_lib.escape(item.get('title', 'Pendiente'))}</div>"
        f"{description_html}"
        f"<div class='todo-card-meta'>{html_lib.escape(todo_meta_line(item))}</div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<div style='text-align:right;font-size:.74rem;font-weight:850;color:{color};'>{html_lib.escape(status_note)}</div>",
        unsafe_allow_html=True,
    )

    if done != is_done:
        item["done"] = done
        save_store(store)
        st.rerun()

    with st.expander("Editar detalles", expanded=False):
        e1, e2 = st.columns([2.2, 0.9])
        title = e1.text_input("Actividad", value=item.get("title", ""), key=f"{key_prefix}_title_{item.get('todo_id')}")
        new_date = e2.date_input("Fecha", value=parse_date(item.get("date")) or date.today(), key=f"{key_prefix}_date_{item.get('todo_id')}")
        description = st.text_area("Descripción", value=item.get("description", ""), key=f"{key_prefix}_description_{item.get('todo_id')}")

        m1, m2, m3 = st.columns([1, 1, 1])
        priority = m1.selectbox(
            "Prioridad",
            ["Alta", "Media", "Baja"],
            index=["Alta", "Media", "Baja"].index(item.get("priority", "Media")) if item.get("priority", "Media") in ["Alta", "Media", "Baja"] else 1,
            key=f"{key_prefix}_priority_{item.get('todo_id')}",
        )
        energy = m2.selectbox(
            "Energía",
            ["Baja", "Normal", "Alta"],
            index=["Baja", "Normal", "Alta"].index(item.get("energy", "Normal")) if item.get("energy", "Normal") in ["Baja", "Normal", "Alta"] else 1,
            key=f"{key_prefix}_energy_{item.get('todo_id')}",
        )
        estimated = m3.number_input("Minutos", min_value=5, max_value=360, step=5, value=todo_minutes(item), key=f"{key_prefix}_minutes_{item.get('todo_id')}")

        a1, a2, a3 = st.columns([1, 1, 1])
        if a1.button("Subir", key=f"{key_prefix}_up_{item.get('todo_id')}", width="stretch"):
            move_todo(store, item["todo_id"], "up")
            save_store(store)
            st.rerun()
        if a2.button("Bajar", key=f"{key_prefix}_down_{item.get('todo_id')}", width="stretch"):
            move_todo(store, item["todo_id"], "down")
            save_store(store)
            st.rerun()
        if a3.button("Eliminar", key=f"{key_prefix}_delete_{item.get('todo_id')}", width="stretch"):
            store["todo_items"] = [t for t in store["todo_items"] if t.get("todo_id") != item.get("todo_id")]
            save_store(store)
            st.rerun()

        changed = (
            title != item.get("title")
            or new_date.isoformat() != item.get("date")
            or priority != item.get("priority")
            or energy != item.get("energy")
            or int(estimated) != todo_minutes(item)
            or description != item.get("description", "")
        )
        if changed:
            item["title"] = short_todo_title(title)
            item["description"] = description.strip()
            item["date"] = new_date.isoformat()
            item["priority"] = priority
            item["energy"] = energy
            item["estimated_minutes"] = int(estimated)
            save_store(store)

        if item.get("meta", {}).get("kind") == "reading":
            planned = int(item["meta"].get("page_end", 0)) - int(item["meta"].get("page_start", 0)) + 1
            r1, r2 = st.columns([1, 2])
            pages_done = r1.number_input("Páginas leídas", min_value=0, max_value=5000, value=planned, step=5, key=f"{key_prefix}_pages_{item.get('todo_id')}")
            if r2.button("Actualizar lectura y replanificar", key=f"{key_prefix}_replan_{item.get('todo_id')}", width="stretch"):
                item["done"] = True
                update_reading_progress(store, item, pages_done)
                save_store(store)
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def tab_todo(store):
    settings = store.setdefault("settings", {})
    settings.setdefault("todo_view_mode", "smart")
    section_preferences = todo_section_preferences(store)
    selected = st.date_input("Semana de To-do", value=date.today(), key="todo_week")
    start = week_start(selected)
    end = start + timedelta(days=6)
    days = [start + timedelta(days=i) for i in range(7)]
    st.markdown('<div class="section-title">To-do inteligente</div>', unsafe_allow_html=True)
    st.caption(f"Semana del {start.strftime('%d/%m')} al {end.strftime('%d/%m')}")

    with st.expander("Secciones visibles", expanded=False):
        labels = {
            "overdue": "Vencidos",
            "today": "Hoy",
            "week": "Esta semana",
            "done": "Completados",
        }
        columns = st.columns(4)
        changed = False
        for column, (key, label) in zip(columns, labels.items()):
            visible = column.checkbox(
                label,
                value=bool(section_preferences.get(key, True)),
                key=f"todo_section_visible_{key}",
            )
            if section_preferences.get(key) != visible:
                section_preferences[key] = visible
                changed = True
        if changed:
            save_store(store)
            st.rerun()

    with st.form("manual_todo", clear_on_submit=True):
        c1, c2, c3 = st.columns([2.2, .9, 1])
        title = c1.text_input("Nuevo pendiente", placeholder="Leer páginas 1-62, revisar ensayo...")
        selected_day = c2.selectbox("Día", DAYS_ES, index=date.today().weekday())
        course = c3.text_input("Materia", value="General")
        c4, c5, c6 = st.columns([1, 1, 1])
        priority = c4.selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1)
        energy = c5.selectbox("Energía", ["Baja", "Normal", "Alta"], index=1)
        estimated = c6.number_input("Minutos", min_value=5, max_value=360, value=30, step=5)
        if st.form_submit_button("Agregar pendiente", width="stretch") and title:
            target_date = days[DAYS_ES.index(selected_day)]
            course_id = ensure_course(store, course)
            manual_item = {
                "todo_id": make_id("todo"),
                "title": short_todo_title(title),
                "description": "",
                "date": target_date.isoformat(),
                "course": course,
                "color": course_color(store, course_id),
                "done": False,
                "order": len(store["todo_items"]),
                "activity_id": "",
                "internal_task_id": make_id("task"),
                "priority": priority,
                "estimated_minutes": int(estimated),
                "energy": energy,
            }
            ensure_todo_defaults(manual_item)
            if any(is_similar_todo(existing, manual_item) for existing in store.get("todo_items", [])):
                st.warning("Ya existe un pendiente muy similar para esa fecha.")
            else:
                store["todo_items"].append(manual_item)
                save_store(store)
                st.rerun()

    overdue_items = overdue_todos(store)
    if overdue_items:
        with st.container(border=True):
            st.markdown(f"**Pendientes vencidos:** {len(overdue_items)}")
            r1, r2, r3 = st.columns(3)
            if r1.button("Mover vencidos a hoy", width="stretch"):
                count = replan_overdue(store, "today")
                save_store(store)
                st.success(f"Moví {count} pendientes a hoy.")
                st.rerun()
            if r2.button("Mover vencidos a mañana", width="stretch"):
                count = replan_overdue(store, "tomorrow")
                save_store(store)
                st.success(f"Moví {count} pendientes a mañana.")
                st.rerun()
            if r3.button("Redistribuir hasta entrega", width="stretch"):
                count = replan_overdue(store, "spread")
                save_store(store)
                st.success(f"Redistribuí {count} pendientes.")
                st.rerun()

    overdue_items, today_items, week_items, completed_items = todo_section_items(store, start, end)
    sections = [
        ("Vencidos", overdue_items, "overdue"),
        ("Hoy", today_items, "today"),
        ("Esta semana", week_items, "week"),
        ("Completados", completed_items, "done"),
    ]
    for title, items, key in sections:
        if not section_preferences.get(key, True):
            continue
        render_todo_section_header(title, items)
        if not items:
            st.markdown("<div class='todo-empty-note'>Sin pendientes.</div>", unsafe_allow_html=True)
            continue
        for index, item in enumerate(items):
            render_todo_card(store, item, f"{key}_{index}")

def save_agent_plan(store, result):
    activity = dict(result.get("activity") or {})
    source_message = activity.get("source_message") or result.get("source_message") or ""
    if source_message:
        summarized_title = academic_title_from_message(source_message, activity.get("activity_type"))
        current_title = str(activity.get("title") or "").strip()
        if not current_title or len(current_title) > 50 or normalize_text(current_title) == normalize_text(source_message):
            activity["title"] = summarized_title
        else:
            activity["title"] = short_todo_title(current_title)
        activity["course"] = activity.get("course") or detect_subject(source_message) or "General"
        activity.setdefault("description", academic_description_from_message(source_message, activity["title"]))
    title, error = required_text(activity.get("title"), "un nombre para la actividad")
    if error:
        return False, error
    activity["title"] = title
    raw_deadline = activity.get("deadline")
    deadline = parse_date(raw_deadline) if raw_deadline else None
    if raw_deadline and not deadline:
        return False, "La fecha límite de la actividad no es válida."
    if deadline and deadline < date.today():
        return False, "La fecha límite no puede estar en el pasado."
    if deadline:
        activity["deadline"] = deadline.isoformat()
    course_id = ensure_course(store, activity.get("course", "General"))
    activity["course_id"] = course_id
    activity["activity_id"] = make_id("act")
    color = course_color(store, course_id)
    saved_count = 0
    skipped_count = 0
    for index, raw_item in enumerate(result.get("todo_items", [])):
        item = dict(raw_item)
        if source_message:
            item_title = str(item.get("title") or "").strip()
            if not item_title or len(item_title) > 50 or normalize_text(item_title) == normalize_text(source_message):
                item["title"] = academic_title_from_message(source_message, activity.get("activity_type"))
            else:
                item["title"] = short_todo_title(item_title)
            item.setdefault("description", academic_description_from_message(source_message, item["title"]))
        item["todo_id"] = make_id("todo")
        item["activity_id"] = activity["activity_id"]
        item["course"] = course_name(store, course_id)
        item["color"] = color
        if activity.get("time") and not item.get("time"):
            item["time"] = activity["time"]
        item.setdefault("done", False)
        item.setdefault("order", len(store["todo_items"]))
        item.setdefault("internal_task_id", f"{activity['activity_id']}_{index + 1:03d}")
        item.setdefault("description", "")
        ensure_todo_defaults(item)
        if any(is_similar_todo(existing, item) for existing in store.get("todo_items", [])):
            skipped_count += 1
            continue
        store["todo_items"].append(item)
        saved_count += 1
    if saved_count:
        store["activities"].append(activity)
    if activity.get("deadline") and saved_count:
        event_id = make_id("event")
        activity.setdefault("event_ids", []).append(event_id)
        event = {
            "event_id": event_id,
            "title": short_todo_title(activity.get("title", "Entrega")),
            "date": activity["deadline"],
            "icon": chr(0x1F4CC),
            "type": "Entrega",
            "color": color,
            "activity_id": activity["activity_id"],
        }
        if activity.get("time"):
            event["time"] = activity["time"]
        store["events"].append(event)
    response = result.get("summary", f"Actividad dividida en {saved_count} pendientes.")
    if skipped_count:
        response = f"{response} Omití {skipped_count} pendiente(s) repetido(s)."
    store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
    add_log(store, "Academic Planning Crew", "Plan confirmado y guardado", {"items": saved_count, "duplicates_skipped": skipped_count})
    save_store(store)
    return True, response


def tab_chat(store):
    st.markdown('<div class="section-title">Chat / agentes</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='chat-hero'><div class='chat-hero-title'>Chat académico ✦</div>"
        "<div class='chat-hero-note'>Describe una actividad, pide ayuda para dividir tareas o pregunta qué conviene hacer primero.</div></div>",
        unsafe_allow_html=True,
    )
    with st.expander("Memoria y análisis", expanded=False):
        st.caption(f"Mensajes guardados: {len(store['chat'])}")
        st.caption(f"Actividades en memoria: {len(store['activities'])}")
        st.caption(f"Pendientes en To-do: {len(store['todo_items'])}")
        if st.button("Limpiar historial del chat", width="stretch", key="clear_chat_history"):
            store["chat"] = []
            st.session_state.pop("pending_agent_plan", None)
            save_store(store)
            st.success("Historial del chat limpiado.")
            st.rerun()
        recent_logs = visible_agent_logs(store, 6)
        if recent_logs:
            render_data_table(pd.DataFrame(recent_logs))
    if not store.get("chat"):
        st.markdown("<div class='chat-empty'>Sin mensajes anteriores. Puedes empezar una conversación nueva.</div>", unsafe_allow_html=True)
    for msg in store["chat"][-8:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    pending = st.session_state.get("pending_agent_plan")
    if pending:
        activity = pending.get("activity", {})
        with st.container(border=True):
            st.subheader("Propuesta de plan")
            st.write(f"**Actividad:** {activity.get('title', 'Actividad')}")
            st.write(f"**Tipo:** {activity.get('activity_type', '')} · **Entrega:** {activity.get('deadline', '')} · **Prioridad:** {activity.get('priority', '')}")
            todo_preview = pending.get("todo_items", [])
            if todo_preview:
                st.dataframe(
                    pd.DataFrame([{"fecha": item.get("date"), "pendiente": item.get("title")} for item in todo_preview]),
                    width="stretch",
                    hide_index=True,
                )
            p1, p2 = st.columns([1, 1])
            if p1.button("Confirmar y guardar", width="stretch"):
                saved, message = save_agent_plan(store, pending)
                if saved:
                    st.session_state.pop("pending_agent_plan", None)
                    st.success("Plan guardado.")
                    st.rerun()
                st.error(message)
            if p2.button("Descartar propuesta", width="stretch"):
                store["chat"].append({"role": "assistant", "content": "Propuesta descartada. Puedes pedirme otra versión.", "time": now_iso()})
                st.session_state.pop("pending_agent_plan", None)
                save_store(store)
                st.rerun()
    message = st.chat_input("Escribe la actividad...")
    if message:
        store["chat"].append({"role": "user", "content": message, "time": now_iso()})
        crew = AcademicPlanningCrew(today=date.today())
        context = {
            "profile": load_profile(store),
            "availability": store.get("availability", []),
            "settings": store.get("settings", {}),
            "habits": store.get("habits", []),
            "events": store.get("events", []),
            "recent_chat": store.get("chat", [])[-12:],
            "activities": store.get("activities", []),
            "todo_items": store.get("todo_items", []),
        }
        result = crew.plan_from_message(message, context)
        for log in result.get("agent_log", []):
            add_log(store, log.get("agent", "Agent"), log.get("action", ""), log.get("payload", {}))
        if result.get("needs_clarification"):
            response = result.get("question", "Necesito un poco más de información para dividirlo bien.")
            store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
            save_store(store)
            st.rerun()
        st.session_state["pending_agent_plan"] = result
        response = result.get("summary") or "Preparé una propuesta clara. Revísala y confirma si quieres guardarla."
        store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
        save_store(store)
        st.rerun()

def associated_event_filter(activity):
    activity_id = activity.get("activity_id")
    event_ids = set(activity.get("event_ids", []) or [])

    def is_associated(event):
        return bool(
            (activity_id and event.get("activity_id") == activity_id)
            or (event.get("event_id") in event_ids)
        )

    return is_associated


def delete_activity_bundle(store, activity, delete_activity=True, delete_todos=True, delete_events=False):
    activity_id = activity.get("activity_id")
    event_filter = associated_event_filter(activity)
    associated_events = [event for event in store.get("events", []) if event_filter(event)]
    deleted_activity = False
    deleted_progress = 0
    deleted_todos = 0
    deleted_events = 0

    if delete_activity:
        before_activities = len(store.get("activities", []))
        if activity_id:
            store["activities"] = [item for item in store.get("activities", []) if item.get("activity_id") != activity_id]
        else:
            store["activities"] = [item for item in store.get("activities", []) if item is not activity]
        deleted_activity = len(store.get("activities", [])) < before_activities

        if activity_id and isinstance(store.get("progress"), list):
            before_progress = len(store.get("progress", []))
            store["progress"] = [item for item in store.get("progress", []) if item.get("activity_id") != activity_id]
            deleted_progress = before_progress - len(store.get("progress", []))

    if delete_todos and activity_id:
        before_todos = len(store.get("todo_items", []))
        store["todo_items"] = [item for item in store.get("todo_items", []) if item.get("activity_id") != activity_id]
        deleted_todos = before_todos - len(store.get("todo_items", []))

    if delete_events:
        before_events = len(store.get("events", []))
        store["events"] = [event for event in store.get("events", []) if not event_filter(event)]
        deleted_events = before_events - len(store.get("events", []))

    kept_events = max(0, len(associated_events) - deleted_events)
    add_log(store, "Progress Monitor", "Eliminacion selectiva de actividad", {
        "activity_id": activity_id,
        "activity_deleted": deleted_activity,
        "progress_deleted": deleted_progress,
        "todos_deleted": deleted_todos,
        "events_deleted": deleted_events,
        "events_kept": kept_events,
        "delete_activity": delete_activity,
        "delete_todos": delete_todos,
        "delete_events": delete_events,
    })
    save_store(store)
    return {
        "activity_deleted": deleted_activity,
        "progress_deleted": deleted_progress,
        "todos_deleted": deleted_todos,
        "events_deleted": deleted_events,
        "events_kept": kept_events,
    }


def tab_statistics(store):
    st.markdown('<div class="section-title">Estadisticas academicas</div>', unsafe_allow_html=True)
    stats = academic_statistics(store)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Completadas", stats["todo_done"])
    c2.metric("Pendientes", stats["todo_pending"])
    c3.metric("Cumplimiento", f"{stats['compliance_pct']}%")
    c4.metric("Proximas", len(stats["upcoming"]))
    c5.metric("Estudio semanal", f"{stats['weekly_hours']} h")
    st.progress(int(min(100, stats["compliance_pct"])))

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Carga por materia")
        if stats["course_load"]:
            load_df = pd.DataFrame(stats["course_load"])
            colors = chart_colors(store)
            load_chart = alt.Chart(load_df).mark_bar(
                color=colors["primary"],
                cornerRadiusTopLeft=5,
                cornerRadiusTopRight=5,
            ).encode(
                x=alt.X("Materia:N", sort="-y", title=None),
                y=alt.Y("Minutos:Q", title="Minutos estimados"),
                tooltip=["Materia", "Minutos", "Pendientes", "Completadas"],
            )
            st.altair_chart(styled_chart(load_chart, store), width="stretch")
            render_data_table(load_df)
        else:
            st.info("Todavia no hay pendientes con materia para calcular carga.")

    with right:
        st.subheader("Actividades proximas")
        if stats["upcoming"]:
            render_data_table(pd.DataFrame(stats["upcoming"]))
        else:
            st.info("No hay pendientes ni eventos proximos registrados.")

        st.subheader("Base del cumplimiento")
        summary = pd.DataFrame([
            {"Fuente": "Tareas", "Completado": stats["todo_done"], "Total": stats["todo_total"]},
            {"Fuente": "Habitos semanales", "Completado": stats["habit_done"], "Total": stats["habit_target"]},
            {"Fuente": "Progress", "Completado": stats["progress_done"], "Total": stats["progress_total"]},
        ])
        render_data_table(summary)

    st.subheader("Tendencias")
    chart_left, chart_right = st.columns(2)
    today = date.today()
    last_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    with chart_left:
        completed_by_week = []
        current_week = goal_week_start(today)
        for offset in range(5, -1, -1):
            start = current_week - timedelta(days=offset * 7)
            end = start + timedelta(days=6)
            completed_by_week.append({
                "Semana": start.strftime("%d/%m"),
                "Tareas": sum(
                    1 for item in store.get("todo_items", [])
                    if item.get("done") and start.isoformat() <= item.get("date", "") <= end.isoformat()
                ),
                "Hábitos": sum(
                    1 for habit in store.get("habits", [])
                    for day, completed in (habit.get("history") or {}).items()
                    if completed and start.isoformat() <= day <= end.isoformat()
                ),
            })
        st.caption("Tareas y hábitos completados por semana")
        completed_df = pd.DataFrame(completed_by_week).melt(
            id_vars=["Semana"],
            value_vars=["Tareas", "Hábitos"],
            var_name="Tipo",
            value_name="Completados",
        )
        colors = chart_colors(store)
        completed_chart = alt.Chart(completed_df).mark_bar(
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
        ).encode(
            x=alt.X("Semana:N", title=None),
            y=alt.Y("Completados:Q", title="Completados"),
            color=alt.Color(
                "Tipo:N",
                scale=alt.Scale(range=[colors["primary"], colors["secondary"]]),
                legend=alt.Legend(title=None),
            ),
            xOffset="Tipo:N",
            tooltip=["Semana", "Tipo", "Completados"],
        )
        st.altair_chart(styled_chart(completed_chart, store), width="stretch")

    with chart_right:
        activity_by_day = []
        for day in last_days:
            day_key = day.isoformat()
            activity_by_day.append({
                "Día": day.strftime("%d/%m"),
                "Acciones": sum(1 for log in visible_agent_logs(store) if str(log.get("time", "")).startswith(day_key)),
            })
        st.caption("Actividad registrada · últimos 7 días")
        activity_df = pd.DataFrame(activity_by_day)
        activity_chart = alt.Chart(activity_df).mark_line(
            color=chart_colors(store)["primary"],
            point=True,
            strokeWidth=3,
        ).encode(
            x=alt.X("Día:N", title=None),
            y=alt.Y("Acciones:Q", title="Acciones"),
            tooltip=["Día", "Acciones"],
        )
        st.altair_chart(styled_chart(activity_chart, store), width="stretch")

    st.subheader("Progreso de metas")
    goals = active_weekly_goals(store)
    if goals:
        goal_rows = []
        for goal in goals:
            goal_progress = weekly_goal_progress(goal, store)
            goal_rows.append({
                "Meta": goal.get("title", "Meta"),
                "Progreso": goal_progress["percentage"],
            })
        goal_df = pd.DataFrame(goal_rows)
        goal_chart = alt.Chart(goal_df).mark_bar(
            color=chart_colors(store)["primary"],
            cornerRadiusEnd=5,
        ).encode(
            y=alt.Y("Meta:N", sort="-x", title=None),
            x=alt.X("Progreso:Q", scale=alt.Scale(domain=[0, 100]), title="Progreso (%)"),
            tooltip=["Meta", "Progreso"],
        )
        st.altair_chart(styled_chart(goal_chart, store, height=220), width="stretch")
    else:
        st.info("Crea una meta semanal desde Hoy para ver su progreso aquí.")


def tab_progress(store):
    st.markdown('<div class="section-title">Progreso</div>', unsafe_allow_html=True)
    stats = completion_stats(store)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completado", f"{stats['pct']}%")
    c2.metric("Hechos", stats["done"])
    c3.metric("Pendientes", stats["pending"])
    c4.metric("Atrasados", stats["overdue"])
    st.progress(int(stats["pct"]))
    delete_summary = st.session_state.pop("progress_delete_summary", None)
    if delete_summary:
        st.success(delete_summary)
    if not store["activities"]:
        st.info("Todavía no hay actividades guardadas.")
        return
    for index, activity in enumerate(list(store["activities"])):
        activity_id = activity.get("activity_id")
        todos = [t for t in store.get("todo_items", []) if activity_id and t.get("activity_id") == activity_id]
        event_ids = set(activity.get("event_ids", []) or [])
        event_filter = associated_event_filter(activity)
        events = [
            e for e in store.get("events", [])
            if event_filter(e)
        ]
        done = sum(1 for t in todos if t.get("done"))
        with st.container(border=True):
            cols = st.columns([2.4, 1, 1, 1.1])
            cols[0].markdown(f"**{activity.get('title', 'Actividad')}**")
            cols[0].caption(f"{activity.get('activity_type', 'Actividad')} · Entrega: {activity.get('deadline', 'Sin fecha')}")
            cols[1].metric("Avance", f"{done}/{len(todos)}")
            cols[2].metric("Eventos", len(events))
            delete_key = f"delete_activity_{activity_id or index}"
            delete_activity_key = f"delete_activity_progress_{activity_id or index}"
            delete_todos_key = f"delete_activity_todos_{activity_id or index}"
            delete_events_key = f"delete_activity_events_{activity_id or index}"
            if not activity_id:
                st.warning("Esta actividad es antigua y no tiene activity_id. Se puede eliminar la actividad, pero no se borrarán pendientes por título.")
            options = st.columns([1, 1, 1])
            delete_activity_opt = options[0].checkbox("Eliminar actividad/progreso", value=True, key=delete_activity_key)
            delete_todos_opt = options[1].checkbox("Eliminar pendientes asociados", value=True, key=delete_todos_key)
            delete_events_opt = options[2].checkbox("Eliminar eventos del calendario", value=False, key=delete_events_key)
            has_selection = delete_activity_opt or delete_todos_opt or delete_events_opt
            if cols[3].button("Aplicar eliminacion", key=delete_key, width="stretch", disabled=not has_selection):
                result = delete_activity_bundle(
                    store,
                    activity,
                    delete_activity=delete_activity_opt,
                    delete_todos=delete_todos_opt,
                    delete_events=delete_events_opt,
                )
                activity_message = "Se eliminó la actividad." if result["activity_deleted"] else "No se eliminó la actividad."
                progress_note = f" Se eliminaron {result['progress_deleted']} registros de progreso." if result["progress_deleted"] else ""
                st.session_state["progress_delete_summary"] = (
                    f"{activity_message}{progress_note} "
                    f"Se eliminaron {result['todos_deleted']} pendientes. "
                    f"Se conservaron {result['events_kept']} eventos."
                )
                st.rerun()


def render_habit_stats(store, days):
    habits = store.get("habits", [])
    today = date.today()
    completed_today = sum(1 for habit in habits if is_habit_done(habit, today))
    total_week = sum(max(1, int(habit.get("weekly_target", 5) or 5)) for habit in habits)
    completed_week = sum(min(habit_week_count(habit, days), max(1, int(habit.get("weekly_target", 5) or 5))) for habit in habits)
    weekly_progress = round(completed_week / total_week * 100) if total_week else 0
    current_streak = max([habit_streak(habit) for habit in habits] or [0])
    best_streak = max([habit_best_streak(habit) for habit in habits] or [0])
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, "Racha actual", f"🔥 {current_streak} días", "Constancia activa"),
        (c2, "Mejor racha", f"🔥 {best_streak} días", "Histórico"),
        (c3, "Progreso semanal", f"{weekly_progress}%", f"{completed_week}/{total_week} marcas" if total_week else "Sin hábitos"),
        (c4, "Completados hoy", f"{completed_today}/{len(habits)}", "Avance de hoy"),
    ]
    for col, label, value, caption in cards:
        col.markdown(f"""<div class="habit-stat-card"><div class="habit-stat-label">{label}</div><div class="habit-stat-value">{value}</div><div class="habit-caption">{caption}</div></div>""", unsafe_allow_html=True)


def create_habit(store, title, category="", target=5):
    clean_title, error = required_text(title, "un nombre para el hábito")
    if error:
        return False, error
    store["habits"].append({
        "habit_id": make_id("habit"),
        "title": clean_title,
        "category": str(category or "").strip() or "Rutina",
        "weekly_target": max(1, min(7, int(target or 5))),
        "history": {},
        "done_today": False,
        "streak": 0,
        "color": habit_color(len(store.get("habits", []))),
        "created_at": now_iso(),
    })
    add_log(store, "Progress Monitor", "Hábito creado", {"habit": clean_title})
    save_store(store)
    return True, ""


def render_habit_form(store):
    with st.expander("Agregar nuevo hábito", expanded=not bool(store.get("habits"))):
        with st.form("habit_create_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            title = c1.text_input("Hábito", placeholder="Repasar vocabulario, leer 20 min...")
            category = c2.text_input("Categoría", placeholder="Estudio")
            target = c3.number_input("Meta semanal", 1, 7, 5)
            if st.form_submit_button("Crear hábito", width="stretch"):
                saved, error = create_habit(store, title, category, target)
                if saved:
                    st.rerun()
                st.error(error)


def render_habit_week(store):
    selected = st.date_input("Semana", value=date.today(), key="habit_week_pick")
    days = habit_week_dates(selected)
    render_habit_stats(store, days)
    render_habit_form(store)
    habits = store.get("habits", [])
    if not habits:
        st.info("Agrega tu primer hábito para empezar a construir una racha semanal.")
        return
    st.markdown('<div class="habit-panel">', unsafe_allow_html=True)
    header = st.columns([2.5] + [0.72] * 7 + [1.15])
    header[0].markdown("**Hábito**")
    for col, day in zip(header[1:8], days):
        col.markdown(f"<div class='habit-day-head'>{DAYS_ES[day.weekday()][:3]}<br>{day.strftime('%d/%m')}</div>", unsafe_allow_html=True)
    header[8].markdown("**Progreso**")
    for index, habit in enumerate(habits):
        habit_history(habit)
        color = habit.get("color") or habit_color(index)
        habit["color"] = color
        completed, target, progress = habit_week_progress(habit, days)
        row = st.columns([2.5] + [0.72] * 7 + [1.15])
        current_streak = habit_streak(habit)
        best_streak = habit_best_streak(habit)
        row[0].markdown(f"""<div class="habit-row-card" style="border-left:5px solid {color}"><div class="habit-name">{html_lib.escape(str(habit.get('title', 'Hábito')))}</div><div class="habit-meta">{html_lib.escape(str(habit.get('category', 'Rutina')))} · meta {target}/semana · 🔥 {current_streak} días · mejor {best_streak}</div><span class="habit-chip">{completed}/{target} esta semana</span></div>""", unsafe_allow_html=True)
        for day_col, day in zip(row[1:8], days):
            checked = day_col.checkbox(" ", value=is_habit_done(habit, day), key=f"habit_done_{habit['habit_id']}_{day.isoformat()}")
            if checked != is_habit_done(habit, day):
                set_habit_done(habit, day, checked)
                add_log(store, "Progress Monitor", "Hábito actualizado", {"habit": habit.get("title"), "date": day.isoformat(), "done": checked})
                save_store(store)
                st.rerun()
        row[8].markdown(f"""<div class="habit-row-card"><div class="habit-meta">{progress}%</div><div class="habit-progress-track"><div class="habit-progress-fill" style="width:{progress}%; background:{color};"></div></div></div>""", unsafe_allow_html=True)
        with st.expander(f"Editar {habit.get('title', 'hábito')}"):
            e1, e2, e3 = st.columns([2, 1, 1])
            new_title = e1.text_input("Nombre", habit.get("title", ""), key=f"edit_habit_title_{habit['habit_id']}")
            new_category = e2.text_input("Categoría", habit.get("category", "Rutina"), key=f"edit_habit_category_{habit['habit_id']}")
            new_target = e3.number_input("Meta", 1, 7, int(habit.get("weekly_target", 5) or 5), key=f"edit_habit_target_{habit['habit_id']}")
            a1, a2, a3 = st.columns(3)
            if a1.button("Guardar cambios", key=f"save_habit_{habit['habit_id']}"):
                habit["title"] = new_title.strip() or habit.get("title", "Hábito")
                habit["category"] = new_category.strip() or "Rutina"
                habit["weekly_target"] = int(new_target)
                save_store(store)
                st.rerun()
            confirm_reset = st.checkbox("Confirmar reinicio de historial", key=f"confirm_habit_reset_{habit['habit_id']}")
            if a2.button("Reiniciar historial", key=f"reset_habit_{habit['habit_id']}", disabled=not confirm_reset):
                habit["history"] = {}; habit["done_today"] = False; habit["streak"] = 0
                save_store(store); st.rerun()
            if a3.button("Eliminar", key=f"delete_habit_{habit['habit_id']}"):
                store["habits"] = [item for item in store["habits"] if item.get("habit_id") != habit.get("habit_id")]
                save_store(store); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def render_habit_calendar(store):
    selected = st.date_input("Mes", value=date.today(), key="habit_month_pick")
    selected_month = date(selected.year, selected.month, 1)
    percentage, best_streak, perfect_days = habit_month_stats(store, selected_month)
    c1, c2, c3 = st.columns(3); c1.metric("Progreso mensual", f"{percentage}%"); c2.metric("Mejor racha", best_streak); c3.metric("Días perfectos", perfect_days)
    habits = store.get("habits", [])
    _, last_day = calendar.monthrange(selected_month.year, selected_month.month)
    cells = [None] * selected_month.weekday() + [date(selected_month.year, selected_month.month, day) for day in range(1, last_day + 1)]
    while len(cells) % 7: cells.append(None)
    for week_index in range(0, len(cells), 7):
        cols = st.columns(7)
        for col, day in zip(cols, cells[week_index:week_index + 7]):
            if day is None:
                col.markdown('<div class="habit-calendar-cell empty"></div>', unsafe_allow_html=True); continue
            completed = [habit for habit in habits if is_habit_done(habit, day)]
            ratio = round(len(completed) / len(habits) * 100) if habits else 0
            color = "#0f766e" if ratio == 100 and habits else "#dc6803" if ratio > 0 else "#e4e7ec"
            names = ", ".join(html_lib.escape(str(habit.get("title", "Hábito"))) for habit in completed[:3]) or "Sin marcas"
            more = "" if len(completed) <= 3 else f" +{len(completed) - 3} más"
            col.markdown(f"""<div class="habit-calendar-cell" style="border-top:4px solid {color}"><div class="habit-calendar-day">{day.day}</div><div class="habit-progress-track"><div class="habit-progress-fill" style="width:{ratio}%; background:{color};"></div></div><div class="habit-calendar-note">{len(completed)}/{len(habits)} completados</div><div class="habit-calendar-note">{names}{more}</div></div>""", unsafe_allow_html=True)
    if habits:
        with st.expander("Detalle por día"):
            detail_day = st.date_input("Selecciona un día", value=date.today(), key="habit_detail_day")
            completed = [habit.get("title", "Hábito") for habit in habits if is_habit_done(habit, detail_day)]
            st.write("Completados: " + (", ".join(completed) if completed else "ninguno"))


def tab_habits(store):
    for habit in store.get("habits", []): habit_history(habit)
    st.markdown("""<div class="habit-hero"><div class="habit-title">Hábitos</div><div class="habit-caption">Panel semanal con energía de Habitica y limpieza tipo Notion para cuidar tus rutinas académicas.</div></div>""", unsafe_allow_html=True)
    week_tab, calendar_tab = st.tabs(["Semana", "Calendario"])
    with week_tab: render_habit_week(store)
    with calendar_tab: render_habit_calendar(store)


def clear_selected_memory(store, options):
    create_backup(store, "before_selective_memory_clear")
    before = {
        "activities": len(store.get("activities", [])),
        "progress": len(store.get("progress", [])) if isinstance(store.get("progress"), list) else 0,
        "todo_items": len(store.get("todo_items", [])),
        "events": len(store.get("events", [])),
        "habits": len(store.get("habits", [])),
        "chat": len(store.get("chat", [])),
        "agent_log": len(store.get("agent_log", [])),
        "availability": len(store.get("availability", [])),
        "schedule": len(store.get("schedule", [])) if isinstance(store.get("schedule"), list) else 0,
        "classes": len(store.get("classes", [])) if isinstance(store.get("classes"), list) else 0,
        "timetable": len(store.get("timetable", [])) if isinstance(store.get("timetable"), list) else 0,
        "settings": len(store.get("settings", {})) if isinstance(store.get("settings"), dict) else 0,
        "profile": len(store.get("profile", {})) if isinstance(store.get("profile"), dict) else 0,
    }

    deleted = []
    kept = []
    if options.get("activities"):
        store["activities"] = []
        if isinstance(store.get("progress"), list):
            store["progress"] = []
        deleted.append(f"actividades/progreso ({before['activities']} actividades, {before['progress']} registros)")
    else:
        kept.append("actividades/progreso")

    if options.get("todos"):
        store["todo_items"] = []
        deleted.append(f"pendientes ({before['todo_items']})")
    else:
        kept.append("pendientes")

    if options.get("events"):
        store["events"] = []
        deleted.append(f"eventos ({before['events']})")
    else:
        kept.append("eventos")

    if options.get("habits"):
        store["habits"] = []
        deleted.append(f"hábitos ({before['habits']})")
    else:
        kept.append("hábitos")

    if options.get("logs"):
        store["chat"] = []
        store["agent_log"] = []
        deleted.append(f"logs/chat ({before['agent_log']} logs, {before['chat']} chats)")
    else:
        kept.append("logs/chat")

    if options.get("schedule"):
        store["availability"] = []
        for key in ("schedule", "classes", "timetable"):
            if key in store:
                store[key] = []
        deleted.append(
            f"horario/clases ({before['availability']} bloques, "
            f"{before['schedule']} schedule, {before['classes']} classes, {before['timetable']} timetable)"
        )
    else:
        kept.append("horario/clases y datos de horario")

    if options.get("profile"):
        save_profile(store, default_profile())
        deleted.append(f"perfil ({before['profile']} campos)")
    else:
        kept.append("perfil")

    if options.get("settings"):
        store["settings"] = default_store().get("settings", {})
        deleted.append(f"configuraciones ({before['settings']} claves)")
    else:
        kept.append("configuraciones")

    if not options.get("logs"):
        add_log(store, "Memory", "Eliminación selectiva de datos", {"deleted": deleted, "kept": kept})

    save_store(store)
    return deleted, kept


def tab_memory(store):
    st.markdown('<div class="section-title">Memoria y estructura</div>', unsafe_allow_html=True)
    st.caption("La logica de agentes vive en `src/academic_planning`: crew, config, tools, memory, models y workflows.")
    memory_summary = st.session_state.pop("memory_clear_summary", None)
    if memory_summary:
        st.success(memory_summary)
    with st.expander("Eliminar datos", expanded=False):
        st.warning("Esta acción borra solo las secciones seleccionadas y crea un respaldo antes de aplicar cambios.")
        col_a, col_b = st.columns(2)
        delete_activities = col_a.checkbox("Eliminar actividades/progreso", value=False, key="memory_delete_activities")
        delete_todos = col_a.checkbox("Eliminar pendientes", value=False, key="memory_delete_todos")
        delete_events = col_a.checkbox("Eliminar eventos", value=False, key="memory_delete_events")
        delete_habits = col_b.checkbox("Eliminar hábitos", value=False, key="memory_delete_habits")
        delete_logs = col_b.checkbox("Eliminar logs/chat", value=False, key="memory_delete_logs")
        delete_schedule = col_b.checkbox("Eliminar horario/clases", value=False, key="memory_delete_schedule")
        delete_profile = col_a.checkbox("Eliminar perfil del estudiante", value=False, key="memory_delete_profile")
        delete_settings = col_a.checkbox("Eliminar configuraciones", value=False, key="memory_delete_settings")
        if not delete_schedule:
            st.info("El horario se conservará: bloques de horario, clases y datos usados por la vista semanal.")
        if not delete_profile and not delete_settings:
            st.info("Perfil y configuraciones se conservan por defecto.")
        selected = any([delete_activities, delete_todos, delete_events, delete_habits, delete_logs, delete_schedule, delete_profile, delete_settings])
        confirm = st.checkbox("Confirmo que quiero eliminar las secciones seleccionadas", key="memory_confirm_selective_delete")
        if st.button("Eliminar datos seleccionados", width="stretch", disabled=not selected or not confirm):
            deleted, kept = clear_selected_memory(store, {
                "activities": delete_activities,
                "todos": delete_todos,
                "events": delete_events,
                "habits": delete_habits,
                "logs": delete_logs,
                "schedule": delete_schedule,
                "profile": delete_profile,
                "settings": delete_settings,
            })
            deleted_text = ", ".join(deleted) if deleted else "nada"
            kept_text = ", ".join(kept) if kept else "nada"
            st.session_state["memory_clear_summary"] = f"Se eliminó: {deleted_text}. Se conservó: {kept_text}."
            st.rerun()
    st.subheader("Bitacora de agentes")
    render_data_table(pd.DataFrame(visible_agent_logs(store)))
    st.download_button("Descargar memoria JSON", json.dumps(store, ensure_ascii=False, indent=2), file_name="academic_planning_memory.json")



