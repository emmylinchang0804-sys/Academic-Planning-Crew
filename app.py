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
COURSE_PALETTE = ["#2563eb", "#0f766e", "#9333ea", "#dc6803", "#c11574", "#087443", "#175cd3", "#b42318"]
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
    if not value:
        return None
    for fmt in ("%H:%M", "%H"):
        try:
            return datetime.strptime(str(value), fmt).time()
        except ValueError:
            pass
    return None


def week_start(selected):
    return selected - timedelta(days=selected.weekday())


def minutes(t):
    return t.hour * 60 + t.minute


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
    cols = st.columns(7)
    for idx, day in enumerate(days):
        blocks = [b for b in store["availability"] if int(b.get("day_index", -1)) == idx]
        blocks.sort(key=lambda b: b.get("start_time", ""))
        html = f"<div class='week-day'><div class='day-title'>{DAYS_ES[idx]}</div><div class='day-date'>{day.strftime('%d/%m')}</div>"
        if not blocks:
            html += "<div class='subtle'>Sin horario fijo</div>"
        for block in blocks:
            color = block.get("color", "#2563eb")
            html += (
                f"<div class='schedule-card' style='border-left-color:{color}; background:{pastel(color)}'>"
                f"<div class='schedule-title'>{block.get('title', 'Horario')}</div>"
                f"<div class='subtle'>{block.get('start_time')} - {block.get('end_time')} Â· {block.get('availability_type', 'Fijo')}</div>"
                f"</div>"
            )
        html += "</div>"
        cols[idx].markdown(html, unsafe_allow_html=True)


def manual_schedule_form(store):
    st.divider()
    st.subheader("Agregar horario manual")
    with st.form("manual_schedule", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([1.2, .8, .8, .8, .8])
        title = c1.text_input("Nombre", placeholder="Clase, gimnasio, trabajo...")
        day = c2.selectbox("Dia", DAYS_ES)
        start = c3.time_input("Inicio", value=time(8, 0))
        end = c4.time_input("Fin", value=time(9, 0))
        color = c5.color_picker("Color", "#2563eb")
        typ = st.selectbox("Tipo", ["Clase", "Extracurricular", "Personal", "Descanso", "Bloqueado"])
        if st.form_submit_button("Guardar horario", use_container_width=True):
            store["availability"].append({
                "availability_id": make_id("av"),
                "title": title or typ,
                "day_index": DAYS_ES.index(day),
                "day_of_week": day,
                "start_time": start.strftime("%H:%M"),
                "end_time": end.strftime("%H:%M"),
                "availability_type": typ,
                "color": color,
            })
            add_log(store, "Student Profile Manager", "Horario fijo creado", {"title": title or typ})
            save_store(store)
            st.rerun()
    if store["availability"]:
        st.subheader("Horarios guardados")
        for block in sorted(store["availability"], key=lambda b: (b.get("day_index", 0), b.get("start_time", ""))):
            cols = st.columns([2, 1, 1, .7])
            cols[0].write(f"{DAYS_ES[int(block.get('day_index', 0))]} Â· {block.get('title')}")
            cols[1].write(f"{block.get('start_time')} - {block.get('end_time')}")
            cols[2].write(block.get("availability_type", "Fijo"))
            if cols[3].button("Eliminar", key=f"del_av_{block['availability_id']}"):
                store["availability"] = [item for item in store["availability"] if item.get("availability_id") != block["availability_id"]]
                save_store(store)
                st.rerun()


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



