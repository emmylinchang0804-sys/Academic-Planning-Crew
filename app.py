import base64
import html as html_lib
import json
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from academic_planning.crew import AcademicPlanningCrew
from academic_planning.workflows.planning_flow import load_dotenv, redistribute_reading_plan

DATA_DIR = APP_DIR / "data"
STORE_PATH = DATA_DIR / "academic_planning_store.json"
load_dotenv(APP_DIR)

DAYS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
DAY_ALIASES = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}
SCHEDULE_COLOR_PALETTE = [
    ("Azul cielo", "#60a5fa"),
    ("Azul tinta", "#2563eb"),
    ("Menta", "#5eead4"),
    ("Verde hoja", "#22c55e"),
    ("Lavanda", "#a78bfa"),
    ("Uva", "#9333ea"),
    ("Rosa", "#f472b6"),
    ("Fucsia", "#c11574"),
    ("Coral", "#fb7185"),
    ("Naranja", "#fb923c"),
    ("Amarillo", "#facc15"),
    ("Turquesa", "#06b6d4"),
    ("Gris suave", "#94a3b8"),
    ("Grafito", "#475467"),
]
COURSE_PALETTE = [color for _, color in SCHEDULE_COLOR_PALETTE]
EVENT_TYPES = {
    "Entrega": {"icon": chr(0x1F4CC), "color": "#2563eb", "meaning": "entrega"},
    "Examen": {"icon": chr(0x1F4DD), "color": "#dc2626", "meaning": "examen"},
    "Cumpleanos": {"icon": chr(0x1F382), "color": "#c11574", "meaning": "cumpleanos"},
    "Reunion": {"icon": chr(0x1F91D), "color": "#0f766e", "meaning": "reunion"},
    "Personal": {"icon": chr(0x2B50), "color": "#6941c6", "meaning": "personal"},
    "Descanso": {"icon": chr(0x1F319), "color": "#667085", "meaning": "descanso"},
}
st.set_page_config(page_title="Academic Planning Crew", page_icon="APC", layout="wide")


def make_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def default_store():
    return {
        "student": {"name": "", "career": "", "semester": "", "timezone": "America/Guatemala"},
        "courses": [],
        "availability": [],
        "activities": [],
        "todo_items": [],
        "events": [],
        "habits": [],
        "chat": [],
        "agent_log": [],
        "settings": {"study_start": "07:00", "study_end": "21:00"},
    }


def load_store():
    DATA_DIR.mkdir(exist_ok=True)
    if not STORE_PATH.exists():
        save_store(default_store())
    try:
        store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        store = default_store()
    for key, value in default_store().items():
        store.setdefault(key, value)
    store.setdefault("todo_items", [])
    store.setdefault("settings", {})
    store["settings"].setdefault("custom_schedule_colors", [])
    return store


def save_store(store):
    DATA_DIR.mkdir(exist_ok=True)
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_store(keep_profile=False):
    current = load_store()
    fresh = default_store()
    if keep_profile:
        fresh["student"] = current.get("student", fresh["student"])
    save_store(fresh)
    return fresh


def add_log(store, agent, action, payload=None):
    store["agent_log"].insert(0, {"time": now_iso(), "agent": agent, "action": action, "payload": payload or {}})
    store["agent_log"] = store["agent_log"][:120]


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
        "Lee esta imagen de un horario academico y conviertela primero en una tabla limpia. "
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
    current_index = options.index(st.session_state[target_key]) if st.session_state[target_key] in options else 0
    swatch_col, select_col, add_col = st.columns([.12, 1, .20])
    selected = select_col.selectbox(
        "Color",
        options,
        index=current_index,
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
            if st.button("Guardar", key=f"{key}_save", use_container_width=True):
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


def apply_css():
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
        div[data-testid="stTextInput"] input {font-size:.86rem;}
        div[data-testid="stCheckbox"] label {font-size:.82rem;}
        .month-cell {min-height:125px; border:1px solid #e4e7ec; padding:7px; background:#fff; border-radius:6px; margin-bottom:8px; overflow:hidden;}
        .month-cell.faded {background:#f8fafc; color:#98a2b3;}
        .month-event {font-size:.74rem; line-height:1rem; border-left:4px solid #2563eb; padding:4px 5px; margin-bottom:4px; background:#f8fafc; border-radius:5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
        div[data-testid="stMetric"] {background:#fff; border:1px solid #e4e7ec; padding:10px; border-radius:8px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_profile(store):
    with st.sidebar:
        st.markdown("## Perfil")
        with st.form("profile"):
            store["student"]["name"] = st.text_input("Nombre", store["student"].get("name", ""))
            store["student"]["career"] = st.text_input("Carrera", store["student"].get("career", ""))
            store["student"]["semester"] = st.text_input("Semestre", str(store["student"].get("semester", "")))
            if st.form_submit_button("Guardar perfil", use_container_width=True):
                add_log(store, "Student Profile Manager", "Perfil actualizado")
                save_store(store)
                st.success("Guardado")
        st.divider()
        st.markdown("## Datos")
        keep_profile = st.checkbox("Conservar perfil al reiniciar", value=True)
        confirm_reset = st.checkbox("Confirmo que quiero borrar todo")
        if st.button("Reiniciar todo", use_container_width=True, disabled=not confirm_reset):
            reset_store(keep_profile=keep_profile)
            st.success("Todo quedó reiniciado.")
            st.rerun()


def render_week(store, selected):
    start = week_start(selected)
    days = [start + timedelta(days=i) for i in range(7)]
    st.markdown('<div class="section-title">Semana: horarios fijos</div>', unsafe_allow_html=True)
    blocks = []
    boundaries = set()
    for block in store["availability"]:
        start_time = parse_time(block.get("start_time"))
        end_time = parse_time(block.get("end_time"))
        if start_time and end_time and minutes(end_time) > minutes(start_time):
            clean = dict(block)
            clean["_start"] = minutes(start_time)
            clean["_end"] = minutes(end_time)
            blocks.append(clean)
            boundaries.add(clean["_start"])
            boundaries.add(clean["_end"])
    if not blocks:
        st.info("Sin horario fijo para esta semana.")
        return

    ordered = sorted(boundaries)
    intervals = [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1) if ordered[i + 1] > ordered[i]]
    header = "<table class='schedule-grid'><thead><tr><th class='schedule-time'>Hora</th>"
    for idx, day in enumerate(days):
        header += f"<th>{DAYS_ES[idx]}<br><span class='subtle'>{day.strftime('%d/%m')}</span></th>"
    html = header + "</tr></thead><tbody>"

    for start_min, end_min in intervals:
        start_label = time_from_minutes(start_min).strftime("%H:%M")
        end_label = time_from_minutes(end_min).strftime("%H:%M")
        html += f"<tr><td class='schedule-time'>{start_label}<br>{end_label}</td>"
        for day_idx in range(7):
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
                html += (
                    f"<td><div class='schedule-block' style='border-left-color:{color}; background:{bg}'>"
                    f"<div class='schedule-block-title'>{title}</div>"
                    f"<div class='schedule-block-meta'>{time_label} · {typ}</div>"
                    f"</div></td>"
                )
            else:
                html += f"<td><div class='schedule-continuation' style='border-left-color:{color}; background:{bg}'></div></td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)


def manual_schedule_form(store):
    st.divider()
    st.subheader("Editar horario semanal")
    st.caption("Agrega clases rapido, carga un archivo o sube una imagen de tu horario.")

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
        with t2:
            quick_color = color_selector(store, "quick_schedule_color_hex", "quick_schedule", COURSE_PALETTE[len(store["availability"]) % len(COURSE_PALETTE)])
        if st.button("Agregar al horario", use_container_width=True, key="quick_schedule_submit"):
            start_total = minutes(quick_start)
            end_total = start_total + int(quick_duration)
            if not quick_title.strip():
                st.error("Escribe el nombre de la clase o actividad.")
            elif end_total > 23 * 60 + 59:
                st.error("La actividad termina despues de medianoche. Ajusta la hora o duracion.")
            else:
                end_time = time_from_minutes(end_total)
                store["availability"].append({
                    "availability_id": make_id("av"),
                    "title": quick_title.strip(),
                    "day_index": DAYS_ES.index(quick_day),
                    "day_of_week": quick_day,
                    "start_time": quick_start.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                    "availability_type": quick_type,
                    "color": quick_color,
                })
                add_log(store, "Student Profile Manager", "Clase agregada al horario", {"title": quick_title.strip(), "day": quick_day})
                save_store(store)
                st.success("Clase agregada.")
                st.rerun()

    with st.expander("Cargar horario desde archivo o imagen", expanded=False):
        st.caption("Archivos de tabla: CSV, TXT, XLSX o XLS. Imagenes: PNG, JPG, JPEG o WEBP. Para imagen se usa la API desde .env.")
        st.caption("Color para lo importado")
        import_color = color_selector(store, "import_schedule_color_hex", "import_schedule", COURSE_PALETTE[len(store["availability"]) % len(COURSE_PALETTE)])
        uploaded_schedule = st.file_uploader("Archivo de horario", type=["csv", "txt", "xlsx", "xls", "png", "jpg", "jpeg", "webp"], key="schedule_file_upload")
        replace_schedule = st.checkbox("Reemplazar mi horario actual con el archivo", value=False, key="replace_schedule_upload")
        if uploaded_schedule:
            try:
                suffix = Path(uploaded_schedule.name).suffix.lower()
                if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                    st.image(uploaded_schedule, caption="Horario cargado", use_container_width=True)
                    st.caption("Primero convierto la imagen en tabla editable. Luego esa tabla se importa al horario.")
                    if st.button("Convertir imagen en tabla", use_container_width=True):
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
                    if st.button("Leer esta tabla", use_container_width=True):
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
                        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                        if st.button("Importar bloques leidos", use_container_width=True):
                            if replace_schedule:
                                store["availability"] = imported_rows
                            else:
                                store["availability"].extend(imported_rows)
                            add_log(store, "Student Profile Manager", "Horario importado desde imagen", {"blocks": len(imported_rows), "replace": replace_schedule})
                            save_store(store)
                            st.session_state.pop("schedule_image_rows", None)
                            st.session_state.pop("schedule_image_errors", None)
                            st.session_state.pop("schedule_image_table", None)
                            st.success(f"Importe {len(imported_rows)} bloques desde la imagen.")
                            st.rerun()
                    elif st.session_state.get("schedule_image_errors") == []:
                        st.info("La imagen se pudo procesar, pero no se detectaron bloques claros.")
                else:
                    preview_df = read_schedule_file(uploaded_schedule)
                    if preview_df.empty:
                        st.warning("No pude leer filas en este archivo.")
                    else:
                        st.dataframe(preview_df.head(8), use_container_width=True, hide_index=True)
                        imported_rows, import_errors = schedule_rows_from_df(preview_df)
                        for row in imported_rows:
                            row["color"] = row.get("color") or import_color
                        if import_errors:
                            with st.expander("Filas que necesitan revision", expanded=True):
                                for error in import_errors[:12]:
                                    st.warning(error)
                                if len(import_errors) > 12:
                                    st.caption(f"Hay {len(import_errors) - 12} avisos mas.")
                        st.caption(f"Listas para importar: {len(imported_rows)} clases/bloques.")
                        if st.button("Importar horario", use_container_width=True, disabled=not imported_rows):
                            if replace_schedule:
                                store["availability"] = imported_rows
                            else:
                                store["availability"].extend(imported_rows)
                            add_log(store, "Student Profile Manager", "Horario importado", {"blocks": len(imported_rows), "replace": replace_schedule})
                            save_store(store)
                            st.success("Horario importado.")
                            st.rerun()
            except Exception as exc:
                st.error(f"No pude leer ese archivo: {exc}")

    st.markdown("#### Horario agregado")
    st.caption("Edita o elimina bloques por dia. Los colores vienen de la misma paleta para que puedas repetirlos exactamente.")
    blocks = sorted(store["availability"], key=lambda b: (int(b.get("day_index", 0)), b.get("start_time", "")))
    if not blocks:
        st.info("Todavia no hay bloques de horario.")
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
                    if st.button("Guardar cambios", use_container_width=True, key=f"save_schedule_{block_id}"):
                        if not edit_title.strip():
                            st.error("Escribe el nombre.")
                        elif minutes(edit_end) <= minutes(edit_start):
                            st.error("La hora de fin debe ser despues del inicio.")
                        else:
                            block["title"] = edit_title.strip()
                            block["day_index"] = DAYS_ES.index(edit_day)
                            block["day_of_week"] = edit_day
                            block["start_time"] = edit_start.strftime("%H:%M")
                            block["end_time"] = edit_end.strftime("%H:%M")
                            block["availability_type"] = edit_type
                            block["color"] = edit_color
                            add_log(store, "Student Profile Manager", "Bloque de horario editado", {"title": edit_title.strip(), "day": edit_day})
                            save_store(store)
                            st.rerun()
                if cols[4].button("Eliminar", key=f"delete_schedule_{block_id}"):
                    store["availability"] = [item for item in store["availability"] if item.get("availability_id") != block_id]
                    save_store(store)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


def tab_week(store):
    selected = st.date_input("Semana", value=date.today())
    start = week_start(selected)
    end = start + timedelta(days=6)
    st.caption(f"Semana del {start.strftime('%d/%m')} al {end.strftime('%d/%m')}")
    render_week(store, selected)
    manual_schedule_form(store)


def tab_month(store):
    m1, m2 = st.columns([1, .5])
    month_name = m1.selectbox("Mes", MONTHS_ES, index=date.today().month - 1, key="month_name")
    year = m2.number_input("Año", min_value=2020, max_value=2100, value=date.today().year, step=1, key="month_year")
    selected = date(int(year), MONTHS_ES.index(month_name) + 1, 1)
    st.markdown(f"<div class='section-title'>{month_name} {int(year)}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1.popover("Agregar evento"):
        with st.form("event_form", clear_on_submit=True):
            title = st.text_input("Evento", placeholder="Steven, parcial, entrega...")
            event_date = st.date_input("Fecha", value=date.today(), key="event_date")
            event_type = st.selectbox("Icono", list(EVENT_TYPES.keys()))
            color = st.color_picker("Color", EVENT_TYPES[event_type]["color"])
            if st.form_submit_button("Agregar", use_container_width=True) and title:
                icon = EVENT_TYPES[event_type]["icon"]
                store["events"].append({
                    "event_id": make_id("event"),
                    "title": title,
                    "date": event_date.isoformat(),
                    "icon": icon,
                    "type": event_type,
                    "color": color,
                })
                save_store(store)
                st.rerun()
    with c2:
        legend = "  ".join([f"{cfg['icon']} {cfg['meaning']}" for cfg in EVENT_TYPES.values()])
        st.caption(legend)
    cal = __import__("calendar").Calendar(firstweekday=0)
    header = st.columns(7)
    for i, day in enumerate(DAYS_ES):
        header[i].markdown(f"**{day[:3]}**")
    for week in cal.monthdatescalendar(selected.year, selected.month):
        cols = st.columns(7)
        for i, d in enumerate(week):
            faded = " faded" if d.month != selected.month else ""
            html = f"<div class='month-cell{faded}'><b>{d.day}</b>"
            events = [e for e in store["events"] if e.get("date") == d.isoformat()]
            for event in events[:5]:
                label = f"{event.get('icon', chr(0x1F4CC))} {event.get('title', '')}"
                html += f"<div class='month-event' style='border-left-color:{event.get('color', '#2563eb')}'>{label}</div>"
            html += "</div>"
            cols[i].markdown(html, unsafe_allow_html=True)

    month_events = sorted(
        [event for event in store["events"] if parse_date(event.get("date")) and parse_date(event.get("date")).year == selected.year and parse_date(event.get("date")).month == selected.month],
        key=lambda event: event.get("date", ""),
    )
    if month_events:
        with st.expander("Eventos del mes", expanded=False):
            for event in month_events:
                cols = st.columns([2.6, 1, .7])
                cols[0].write(f"{event.get('icon', chr(0x1F4CC))} {event.get('title', '')}")
                cols[1].write(event.get("date", ""))
                if cols[2].button("Eliminar", key=f"del_event_{event['event_id']}"):
                    store["events"] = [item for item in store["events"] if item.get("event_id") != event["event_id"]]
                    save_store(store)
                    st.rerun()

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
        clean_items.append(new_item)
    store["todo_items"].extend(clean_items)


def tab_todo(store):
    selected = st.date_input("Semana de To-do", value=date.today(), key="todo_week")
    start = week_start(selected)
    end = start + timedelta(days=6)
    days = [start + timedelta(days=i) for i in range(7)]
    st.markdown('<div class="section-title">To-do semanal</div>', unsafe_allow_html=True)
    st.caption(f"Semana del {start.strftime('%d/%m')} al {end.strftime('%d/%m')}")

    with st.form("manual_todo", clear_on_submit=True):
        c1, c2, c3 = st.columns([2.4, 1, 1])
        title = c1.text_input("Nuevo pendiente", placeholder="Leer paginas 1-62, revisar ensayo...")
        selected_day = c2.selectbox("Dia", DAYS_ES, index=date.today().weekday())
        course = c3.text_input("Materia", value="General")
        if st.form_submit_button("Agregar pendiente", use_container_width=True) and title:
            target_date = days[DAYS_ES.index(selected_day)]
            course_id = ensure_course(store, course)
            store["todo_items"].append({
                "todo_id": make_id("todo"),
                "title": title,
                "date": target_date.isoformat(),
                "course": course,
                "color": course_color(store, course_id),
                "done": False,
                "order": len(store["todo_items"]),
                "activity_id": "",
            })
            save_store(store)
            st.rerun()

    for idx, d in enumerate(days):
        items = todos_for_day(store, d)
        st.markdown(f"<div class='todo-list-day'><div class='day-title'>{DAYS_ES[idx]}</div><div class='day-date'>{d.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        if not items:
            st.caption("Sin pendientes")
        for item in items:
            is_overdue = not item.get("done") and item.get("date", "") < date.today().isoformat()
            row_class = "todo-done" if item.get("done") else "todo-overdue" if is_overdue else ""
            st.markdown(f"<div class='{row_class}'>", unsafe_allow_html=True)
            cols = st.columns([0.12, 2.8, .7, .42, .42, .55])
            done = cols[0].checkbox("", value=bool(item.get("done")), key=f"done_inline_{item['todo_id']}")
            title = cols[1].text_input("Actividad", value=item.get("title", ""), key=f"title_inline_{item['todo_id']}", label_visibility="collapsed")
            new_date = cols[2].date_input("Fecha", value=parse_date(item.get("date")) or d, key=f"date_inline_{item['todo_id']}", label_visibility="collapsed")
            if is_overdue:
                cols[1].markdown("<span style='color:#b42318;font-size:.74rem;font-weight:700'>Vencida</span>", unsafe_allow_html=True)
            changed = done != bool(item.get("done")) or title != item.get("title") or new_date.isoformat() != item.get("date")
            if changed:
                item["done"] = done
                item["title"] = title
                item["date"] = new_date.isoformat()
                save_store(store)
            if cols[3].button("↑", key=f"up_inline_{item['todo_id']}"):
                move_todo(store, item["todo_id"], "up")
                save_store(store)
                st.rerun()
            if cols[4].button("↓", key=f"down_inline_{item['todo_id']}"):
                move_todo(store, item["todo_id"], "down")
                save_store(store)
                st.rerun()
            if cols[5].button("Eliminar", key=f"delete_inline_{item['todo_id']}"):
                store["todo_items"] = [t for t in store["todo_items"] if t.get("todo_id") != item["todo_id"]]
                save_store(store)
                st.rerun()
            if item.get("meta", {}).get("kind") == "reading":
                planned = int(item["meta"].get("page_end", 0)) - int(item["meta"].get("page_start", 0)) + 1
                p1, p2 = st.columns([1, 4])
                pages_done = p1.number_input("Paginas leidas", min_value=0, max_value=5000, value=planned, step=5, key=f"pages_inline_{item['todo_id']}")
                if p2.button("Actualizar lectura y replanificar", key=f"replan_inline_{item['todo_id']}"):
                    item["done"] = True
                    update_reading_progress(store, item, pages_done)
                    save_store(store)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

def tab_chat(store):
    st.markdown('<div class="section-title">Chat / agentes</div>', unsafe_allow_html=True)
    st.caption("Describe una actividad. Ejemplo: Tengo que leer 500 paginas para el proximo viernes.")
    with st.expander("Memoria y analisis", expanded=False):
        st.caption(f"Mensajes guardados: {len(store['chat'])}")
        st.caption(f"Actividades en memoria: {len(store['activities'])}")
        st.caption(f"Pendientes en To-do: {len(store['todo_items'])}")
        if store["agent_log"]:
            st.dataframe(pd.DataFrame(store["agent_log"][:6]), use_container_width=True, hide_index=True)
    for msg in store["chat"][-8:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    message = st.chat_input("Escribe la actividad...")
    if message:
        store["chat"].append({"role": "user", "content": message, "time": now_iso()})
        crew = AcademicPlanningCrew(today=date.today())
        context = {
            "profile": store.get("student", {}),
            "availability": store.get("availability", []),
            "recent_chat": store.get("chat", [])[-12:],
            "activities": store.get("activities", []),
            "todo_items": store.get("todo_items", []),
        }
        result = crew.plan_from_message(message, context)
        for log in result.get("agent_log", []):
            add_log(store, log.get("agent", "Agent"), log.get("action", ""), log.get("payload", {}))
        if result.get("needs_clarification"):
            response = result.get("question", "Necesito un poco mas de informacion para dividirlo bien.")
            store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
            save_store(store)
            st.rerun()
        activity = result["activity"]
        course_id = ensure_course(store, activity.get("course", "General"))
        activity["course_id"] = course_id
        activity["activity_id"] = make_id("act")
        store["activities"].append(activity)
        color = course_color(store, course_id)
        for item in result.get("todo_items", []):
            item["todo_id"] = make_id("todo")
            item["activity_id"] = activity["activity_id"]
            item["course"] = course_name(store, course_id)
            item["color"] = color
            item.setdefault("done", False)
            item.setdefault("order", len(store["todo_items"]))
            store["todo_items"].append(item)
        if activity.get("deadline"):
            store["events"].append({"event_id": make_id("event"), "title": activity.get("title", "Entrega"), "date": activity["deadline"], "icon": chr(0x1F4CC), "type": "Entrega", "color": color})
        response = result.get("summary", f"Actividad dividida en {len(result.get('todo_items', []))} pendientes.")
        store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
        save_store(store)
        st.rerun()


def tab_progress(store):
    st.markdown('<div class="section-title">Progreso</div>', unsafe_allow_html=True)
    stats = completion_stats(store)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completado", f"{stats['pct']}%")
    c2.metric("Hechos", stats["done"])
    c3.metric("Pendientes", stats["pending"])
    c4.metric("Atrasados", stats["overdue"])
    st.progress(int(stats["pct"]))
    if store["activities"]:
        rows = []
        for activity in store["activities"]:
            todos = [t for t in store["todo_items"] if t.get("activity_id") == activity.get("activity_id")]
            done = sum(1 for t in todos if t.get("done"))
            rows.append({"actividad": activity.get("title"), "tipo": activity.get("activity_type"), "entrega": activity.get("deadline"), "avance": f"{done}/{len(todos)}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def tab_memory(store):
    st.markdown('<div class="section-title">Memoria y estructura</div>', unsafe_allow_html=True)
    st.caption("La logica de agentes vive en `src/academic_planning`: crew, config, tools, memory, models y workflows.")
    with st.expander("Reiniciar todo", expanded=False):
        st.warning("Esto borra horarios, eventos, actividades, to-dos, chat y bitacora.")
        keep_profile = st.checkbox("Conservar perfil", value=True, key="memory_keep_profile")
        confirm = st.checkbox("Confirmo que quiero reiniciar la app", key="memory_confirm_reset")
        if st.button("Reiniciar memoria completa", use_container_width=True, disabled=not confirm):
            reset_store(keep_profile=keep_profile)
            st.success("Memoria reiniciada.")
            st.rerun()
    st.subheader("Bitacora de agentes")
    st.dataframe(pd.DataFrame(store["agent_log"]), use_container_width=True, hide_index=True)
    st.download_button("Descargar memoria JSON", json.dumps(store, ensure_ascii=False, indent=2), file_name="academic_planning_memory.json")


def main():
    apply_css()
    store = load_store()
    sidebar_profile(store)
    st.markdown('<div class="app-title">Academic Planning Crew</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Semana para horarios fijos, mes para eventos, To-do para ejecucion diaria y agentes para dividir actividades.</div>', unsafe_allow_html=True)
    stats = completion_stats(store)
    top = st.columns(4)
    top[0].metric("Actividades", len(store["activities"]))
    top[1].metric("To-dos", stats["total"])
    top[2].metric("Completado", f"{stats['pct']}%")
    top[3].metric("Atrasados", stats["overdue"])
    tabs = st.tabs(["Semana", "Mes", "To-do", "Chat / Agentes", "Progreso", "Memoria"])
    with tabs[0]:
        tab_week(store)
    with tabs[1]:
        tab_month(store)
    with tabs[2]:
        tab_todo(store)
    with tabs[3]:
        tab_chat(store)
    with tabs[4]:
        tab_progress(store)
    with tabs[5]:
        tab_memory(store)
    save_store(store)


if __name__ == "__main__":
    main()



