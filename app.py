import calendar
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
BACKUP_DIR = DATA_DIR / "backups"
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


def create_backup(store, reason="manual"):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    clean_reason = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(reason or "manual")).strip("_")[:40] or "manual"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"academic_planning_{stamp}_{clean_reason}.json"
    backup_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


def reset_store(keep_profile=False):
    current = load_store()
    create_backup(current, "before_reset")
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
    history = habit.setdefault("history", {})
    if isinstance(history, list):
        history = {str(day): True for day in history}
        habit["history"] = history
    today_key = date.today().isoformat()
    if habit.get("done_today") and today_key not in history:
        history[today_key] = True
    return history


def is_habit_done(habit, day):
    return bool(habit_history(habit).get(day.isoformat(), False))


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
    end_day = end_day or date.today()
    history = habit_history(habit)
    streak = 0
    cursor = end_day
    while history.get(cursor.isoformat(), False):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def habit_week_dates(selected=None):
    start = week_start(selected or date.today())
    return [start + timedelta(days=i) for i in range(7)]


def habit_week_count(habit, days):
    return sum(1 for day in days if is_habit_done(habit, day))


def habit_week_progress(habit, days):
    target = max(1, int(habit.get("weekly_target", 5) or 5))
    completed = habit_week_count(habit, days)
    return completed, target, min(100, round(completed / target * 100))


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
        .habit-hero {border:1px solid #e4e7ec; background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%); border-radius:12px; padding:18px 20px; margin:8px 0 14px; box-shadow:0 8px 22px rgba(16,24,40,.05);}
        .habit-title {font-size:1.45rem; font-weight:850; color:#101828;}
        .habit-caption {color:#667085; font-size:.92rem; margin-top:3px;}
        .habit-stat-card {border:1px solid #e4e7ec; background:#fff; border-radius:12px; padding:14px 16px; min-height:95px; box-shadow:0 4px 14px rgba(16,24,40,.04);}
        .habit-stat-label {font-size:.76rem; color:#667085; font-weight:800; text-transform:uppercase;}
        .habit-stat-value {font-size:1.55rem; color:#101828; font-weight:850; line-height:1.25;}
        .habit-panel {border:1px solid #e4e7ec; background:#fff; border-radius:12px; padding:12px 14px; margin:10px 0; box-shadow:0 8px 20px rgba(16,24,40,.04);}
        .habit-row-card {border:1px solid #eef2f6; background:#fcfcfd; border-radius:12px; padding:10px 12px; margin:7px 0;}
        .habit-name {font-weight:820; color:#101828; overflow-wrap:anywhere;}
        .habit-meta {font-size:.75rem; color:#667085; margin-top:2px;}
        .habit-chip {display:inline-block; border-radius:999px; padding:2px 8px; color:#344054; background:#eef2f6; font-size:.72rem; font-weight:750; margin-top:5px;}
        .habit-day-head {text-align:center; color:#667085; font-weight:800; font-size:.76rem; padding-top:4px;}
        .habit-progress-track {height:10px; background:#eef2f6; border-radius:999px; overflow:hidden; margin-top:8px;}
        .habit-progress-fill {height:10px; border-radius:999px;}
        .habit-calendar-cell {border:1px solid #e4e7ec; border-radius:10px; min-height:108px; background:#fff; padding:8px; margin-bottom:8px; box-shadow:0 2px 8px rgba(16,24,40,.035);}
        .habit-calendar-cell.empty {background:#f8fafc; color:#98a2b3;}
        .habit-calendar-day {font-weight:850; color:#101828; font-size:.88rem;}
        .habit-calendar-note {font-size:.7rem; color:#667085; margin-top:4px; line-height:.9rem;}
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
        if a1.button("Guardar", key=f"visual_save_{block_id}", use_container_width=True):
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
        if a2.button("Cerrar", key=f"visual_close_{block_id}", use_container_width=True):
            if "edit_schedule" in st.query_params:
                del st.query_params["edit_schedule"]
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
        if st.button("Agregar al horario", use_container_width=True, key="quick_schedule_submit"):
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
                    remember_course_color(store, quick_title.strip(), quick_color)
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
        st.caption("Archivos de tabla: CSV, TXT, XLSX o XLS. Imágenes: PNG, JPG, JPEG o WEBP. Para imagen se usa la API desde .env.")
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
                        st.dataframe(preview_df.head(8), use_container_width=True, hide_index=True)
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
                        if st.button("Importar horario", use_container_width=True, disabled=not imported_rows):
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
                    if st.button("Guardar cambios", use_container_width=True, key=f"save_schedule_{block_id}"):
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
    overdue = sorted(
        [item for item in store.get("todo_items", []) if not item.get("done") and item.get("date", "") < today.isoformat()],
        key=lambda item: item.get("date", ""),
    )
    upcoming_events = []
    for event in store.get("events", []):
        event_date = parse_date(event.get("date"))
        if event_date and today <= event_date <= today + timedelta(days=14):
            upcoming_events.append(event)
    upcoming_events.sort(key=lambda item: item.get("date", ""))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Clases hoy", len(today_classes))
    m2.metric("Pendientes hoy", len([item for item in today_todos if not item.get("done")]))
    m3.metric("Vencidas", len(overdue))
    m4.metric("Eventos próximos", len(upcoming_events))

    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Clases de hoy")
        if not today_classes:
            st.info("No hay clases fijas hoy.")
        for block in today_classes:
            color = block.get("color", "#2563eb")
            st.markdown(
                f"<div class='schedule-card' style='border-left-color:{color};background:{pastel(color)}'>"
                f"<div class='schedule-title'>{html_lib.escape(str(block.get('title', 'Horario')))}</div>"
                f"<div class='subtle'>{block.get('start_time')} - {block.get('end_time')} · {block.get('availability_type', 'Clase')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    with c2:
        st.subheader("Pendientes de hoy")
        if not today_todos:
            st.info("Sin pendientes para hoy.")
        for item in today_todos:
            checked = st.checkbox(
                item.get("title", "Pendiente"),
                value=bool(item.get("done")),
                key=f"today_done_{item.get('todo_id')}",
            )
            if checked != bool(item.get("done")):
                item["done"] = checked
                save_store(store)
                st.rerun()

    c3, c4 = st.columns([1, 1])
    with c3:
        st.subheader("Próximos eventos")
        if not upcoming_events:
            st.caption("Sin eventos en los próximos 14 días.")
        for event in upcoming_events[:8]:
            st.write(f"{event.get('icon', chr(0x1F4CC))} {event.get('date')} · {event.get('title', '')}")
    with c4:
        st.subheader("Alertas")
        if not overdue:
            st.caption("No tienes pendientes vencidos.")
        for item in overdue[:8]:
            st.markdown(
                f"<div style='color:#b42318;font-weight:700;font-size:.88rem'>{html_lib.escape(str(item.get('title', 'Pendiente')))}</div>"
                f"<div class='subtle'>Venció: {item.get('date', '')}</div>",
                unsafe_allow_html=True,
            )


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

    overdue_items = overdue_todos(store)
    if overdue_items:
        with st.container(border=True):
            st.markdown(f"**Pendientes vencidos:** {len(overdue_items)}")
            r1, r2, r3 = st.columns(3)
            if r1.button("Mover vencidos a hoy", use_container_width=True):
                count = replan_overdue(store, "today")
                save_store(store)
                st.success(f"Moví {count} pendientes a hoy.")
                st.rerun()
            if r2.button("Mover vencidos a mañana", use_container_width=True):
                count = replan_overdue(store, "tomorrow")
                save_store(store)
                st.success(f"Moví {count} pendientes a mañana.")
                st.rerun()
            if r3.button("Redistribuir hasta entrega", use_container_width=True):
                count = replan_overdue(store, "spread")
                save_store(store)
                st.success(f"Redistribuí {count} pendientes.")
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


def save_agent_plan(store, result):
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
        store["events"].append({
            "event_id": make_id("event"),
            "title": activity.get("title", "Entrega"),
            "date": activity["deadline"],
            "icon": chr(0x1F4CC),
            "type": "Entrega",
            "color": color,
        })
    response = result.get("summary", f"Actividad dividida en {len(result.get('todo_items', []))} pendientes.")
    store["chat"].append({"role": "assistant", "content": response, "time": now_iso()})
    add_log(store, "Academic Planning Crew", "Plan confirmado y guardado", {"items": len(result.get("todo_items", []))})
    save_store(store)


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
    pending = st.session_state.get("pending_agent_plan")
    if pending:
        activity = pending.get("activity", {})
        with st.container(border=True):
            st.subheader("Propuesta del agente")
            st.write(f"**Actividad:** {activity.get('title', 'Actividad')}")
            st.write(f"**Tipo:** {activity.get('activity_type', '')} · **Entrega:** {activity.get('deadline', '')} · **Prioridad:** {activity.get('priority', '')}")
            todo_preview = pending.get("todo_items", [])
            if todo_preview:
                st.dataframe(
                    pd.DataFrame([{"fecha": item.get("date"), "pendiente": item.get("title")} for item in todo_preview]),
                    use_container_width=True,
                    hide_index=True,
                )
            p1, p2 = st.columns([1, 1])
            if p1.button("Confirmar y guardar", use_container_width=True):
                save_agent_plan(store, pending)
                st.session_state.pop("pending_agent_plan", None)
                st.success("Plan guardado.")
                st.rerun()
            if p2.button("Descartar propuesta", use_container_width=True):
                store["chat"].append({"role": "assistant", "content": "Propuesta descartada. Puedes pedirme otra version.", "time": now_iso()})
                st.session_state.pop("pending_agent_plan", None)
                save_store(store)
                st.rerun()
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
        st.session_state["pending_agent_plan"] = result
        response = "Preparé una propuesta. Revísala y confirma si quieres guardarla."
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


def render_habit_stats(store, days):
    habits = store.get("habits", [])
    today = date.today()
    completed_today = sum(1 for habit in habits if is_habit_done(habit, today))
    total_week = sum(max(1, int(habit.get("weekly_target", 5) or 5)) for habit in habits)
    completed_week = sum(min(habit_week_count(habit, days), max(1, int(habit.get("weekly_target", 5) or 5))) for habit in habits)
    weekly_progress = round(completed_week / total_week * 100) if total_week else 0
    best_streak = max([habit_streak(habit) for habit in habits] or [0])
    c1, c2, c3 = st.columns(3)
    cards = [(c1, "Mejor racha", f"{best_streak} días", "Constancia activa"), (c2, "Progreso semanal", f"{weekly_progress}%", f"{completed_week}/{total_week} marcas" if total_week else "Sin hábitos"), (c3, "Completados hoy", f"{completed_today}/{len(habits)}", "Avance de hoy")]
    for col, label, value, caption in cards:
        col.markdown(f"""<div class="habit-stat-card"><div class="habit-stat-label">{label}</div><div class="habit-stat-value">{value}</div><div class="habit-caption">{caption}</div></div>""", unsafe_allow_html=True)


def render_habit_form(store):
    with st.expander("Agregar nuevo hábito", expanded=not bool(store.get("habits"))):
        with st.form("habit_create_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            title = c1.text_input("Hábito", placeholder="Repasar vocabulario, leer 20 min...")
            category = c2.text_input("Categoría", placeholder="Estudio")
            target = c3.number_input("Meta semanal", 1, 7, 5)
            if st.form_submit_button("Crear hábito", use_container_width=True) and title:
                store["habits"].append({"habit_id": make_id("habit"), "title": title.strip(), "category": category.strip() or "Rutina", "weekly_target": int(target), "history": {}, "done_today": False, "streak": 0, "color": habit_color(len(store.get("habits", []))), "created_at": now_iso()})
                add_log(store, "Progress Monitor", "Hábito creado", {"habit": title.strip()})
                save_store(store)
                st.rerun()


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
        row[0].markdown(f"""<div class="habit-row-card" style="border-left:5px solid {color}"><div class="habit-name">{html_lib.escape(str(habit.get('title', 'Hábito')))}</div><div class="habit-meta">{html_lib.escape(str(habit.get('category', 'Rutina')))} · meta {target}/semana · racha {habit_streak(habit)} días</div><span class="habit-chip">{completed}/{target} esta semana</span></div>""", unsafe_allow_html=True)
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


def tab_memory(store):
    st.markdown('<div class="section-title">Memoria y estructura</div>', unsafe_allow_html=True)
    st.caption("La logica de agentes vive en `src/academic_planning`: crew, config, tools, memory, models y workflows.")
    with st.expander("Reiniciar todo", expanded=False):
        st.warning("Esto borra horarios, eventos, actividades, to-dos, chat y bitácora.")
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
    st.markdown('<div class="app-subtitle">Semana para horarios fijos, mes para eventos, To-do para ejecución diaria y agentes para dividir actividades.</div>', unsafe_allow_html=True)
    stats = completion_stats(store)
    top = st.columns(4)
    top[0].metric("Actividades", len(store["activities"]))
    top[1].metric("To-dos", stats["total"])
    top[2].metric("Completado", f"{stats['pct']}%")
    top[3].metric("Atrasados", stats["overdue"])
    tabs = st.tabs(["Hoy", "Semana", "Mes", "To-do", "Chat / Agentes", "Progreso", "Hábitos", "Memoria"])
    with tabs[0]:
        tab_today(store)
    with tabs[1]:
        tab_week(store)
    with tabs[2]:
        tab_month(store)
    with tabs[3]:
        tab_todo(store)
    with tabs[4]:
        tab_chat(store)
    with tabs[5]:
        tab_progress(store)
    with tabs[6]:
        tab_habits(store)
    with tabs[7]:
        tab_memory(store)
    save_store(store)


if __name__ == "__main__":
    main()



