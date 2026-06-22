import json
import math
import os
import re
from datetime import date, datetime, timedelta

from academic_planning.tools.calendar_tool import future_dates


def load_dotenv(project_root=None):
    root = project_root or os.getcwd()
    env_path = os.path.join(root, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_date_from_text(text, today=None):
    today = today or date.today()
    match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if match:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(match.group(1), fmt).date()
            except ValueError:
                pass
    lower = text.lower()
    weekdays = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    }
    for name, idx in weekdays.items():
        if name in lower:
            delta = (idx - today.weekday()) % 7
            if delta == 0 or "proximo" in lower or "próximo" in lower:
                delta = delta or 7
            return today + timedelta(days=delta)
    return None


def workload_score(day, context):
    weekday = day.weekday()
    day_key = day.isoformat()
    class_minutes = 0
    class_count = 0
    for block in (context or {}).get("availability", []):
        if int(block.get("day_index", -1)) != weekday:
            continue
        try:
            start_h, start_m = [int(part) for part in str(block.get("start_time", "0:0")).split(":")[:2]]
            end_h, end_m = [int(part) for part in str(block.get("end_time", "0:0")).split(":")[:2]]
        except ValueError:
            continue
        class_minutes += max(0, (end_h * 60 + end_m) - (start_h * 60 + start_m))
        class_count += 1
    todo_count = sum(1 for item in (context or {}).get("todo_items", []) if item.get("date") == day_key and not item.get("done"))
    return class_minutes + class_count * 20 + todo_count * 60


def prioritized_future_dates(today, deadline, context=None):
    days = future_dates(today, deadline)
    return sorted(days, key=lambda day: (workload_score(day, context or {}), day))


def infer_type(text):
    lower = text.lower()
    if any(word in lower for word in ["examen", "parcial", "quiz"]):
        return "Examen"
    if any(word in lower for word in ["ensayo", "redaccion", "redacción"]):
        return "Ensayo"
    if any(word in lower for word in ["proyecto", "presentacion", "presentación"]):
        return "Proyecto"
    if any(word in lower for word in ["leer", "lectura", "paginas", "páginas", "capitulos", "capítulos"]):
        return "Lectura"
    if any(word in lower for word in ["laboratorio", "lab", "practica", "práctica"]):
        return "Laboratorio"
    return "Tarea"


def clean_title(text):
    title = re.sub(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "", text)
    title = re.sub(r"\b(tengo|debo|necesito|hacer|realizar|entregar|para|el|la|los|las|que)\b", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" .,-")
    return title[:80] or "Actividad"


def page_or_chapter_count(text):
    lower = text.lower()
    page_match = re.search(r"(\d+)\s*(paginas|páginas|pages|pags)", lower)
    chapter_match = re.search(r"(\d+)\s*(capitulos|capítulos|chapters)", lower)
    if page_match:
        return "pages", int(page_match.group(1))
    if chapter_match:
        return "chapters", int(chapter_match.group(1))
    return None, None


def distribute_ranges(total, days):
    base = total // len(days)
    extra = total % len(days)
    ranges = []
    cursor = 1
    for idx, day in enumerate(days):
        amount = base + (1 if idx < extra else 0)
        start = cursor
        end = cursor + amount - 1
        ranges.append((day, start, end, amount))
        cursor = end + 1
    return ranges


def reading_plan(activity_id, title, total, unit, days):
    label = "paginas" if unit == "pages" else "capitulos"
    items = []
    for order, (day, start, end, amount) in enumerate(distribute_ranges(total, days)):
        item_title = f"Leer {label} {start}-{end}: {title}"
        items.append({
            "title": item_title,
            "date": day.isoformat(),
            "done": False,
            "order": order,
            "meta": {"kind": "reading", "unit": unit, "page_start": start, "page_end": end, "target_amount": amount},
        })
    return items


def redistribute_reading_plan(activity_id, title, start_page, total_pages, start_date, deadline):
    days = future_dates(start_date, deadline)
    if not days or start_page > total_pages:
        return []
    remaining = total_pages - start_page + 1
    ranges = distribute_ranges(remaining, days)
    items = []
    cursor = start_page
    for order, (day, _, _, amount) in enumerate(ranges):
        end = cursor + amount - 1
        items.append({
            "todo_id": f"todo_replan_{activity_id}_{order}",
            "activity_id": activity_id,
            "title": f"Leer paginas {cursor}-{end}: {title}",
            "date": day.isoformat(),
            "done": False,
            "order": order,
            "meta": {"kind": "reading", "unit": "pages", "page_start": cursor, "page_end": end, "target_amount": amount},
        })
        cursor = end + 1
    return items


def phase_plan(title, activity_type, days):
    if activity_type == "Ensayo":
        phases = ["Definir tema y tesis", "Investigar fuentes", "Bosquejo", "Redactar desarrollo", "Redactar introduccion y conclusion", "Revision final"]
    elif activity_type == "Laboratorio":
        phases = ["Parte 1", "Parte 2", "Parte 3", "Analisis de resultados", "Revision final"]
    elif activity_type == "Examen":
        phases = ["Repasar temas principales", "Practicar ejercicios", "Resolver dudas", "Simulacro", "Repaso final"]
    else:
        phases = ["Parte 1", "Parte 2", "Parte 3", "Revision final"]
    items = []
    for index, phase in enumerate(phases):
        day = days[min(index, len(days) - 1)]
        items.append({"title": f"{phase}: {title}", "date": day.isoformat(), "done": False, "order": index, "meta": {"kind": "phase", "phase": phase}})
    return items


def fallback_plan(message, today=None, context=None):
    today = today or date.today()
    context = context or {}
    deadline = parse_date_from_text(message, today)
    activity_type = infer_type(message)
    title = clean_title(message)
    if not deadline:
        return {
            "needs_clarification": True,
            "question": "¿Para que fecha necesitas tener lista esta actividad?",
            "agent_log": [{"agent": "Task Analyzer", "action": "Falta fecha limite", "payload": {"message": message}}],
        }
    days = prioritized_future_dates(today, deadline, context)
    if not days:
        return {
            "needs_clarification": True,
            "question": "La fecha ya paso. ¿Para que nueva fecha quieres replanificarla?",
            "agent_log": [{"agent": "Academic Planner", "action": "Fecha pasada detectada", "payload": {"deadline": deadline.isoformat()}}],
        }
    unit, total = page_or_chapter_count(message)
    if activity_type == "Lectura" and not total:
        return {
            "needs_clarification": True,
            "question": "¿Cuantas paginas o capitulos tienes que leer?",
            "agent_log": [{"agent": "Task Analyzer", "action": "Falta cantidad de lectura", "payload": {}}],
        }
    if activity_type == "Lectura":
        todo_items = reading_plan("", title, total, unit, days)
        estimated_hours = round(total / 35, 1) if unit == "pages" else round(total * 0.75, 1)
        metadata = {"total_pages": total if unit == "pages" else 0, "unit": unit}
    else:
        todo_items = phase_plan(title, activity_type, days)
        estimated_hours = {"Ensayo": 6, "Proyecto": 8, "Laboratorio": 4, "Examen": 5}.get(activity_type, 2)
        metadata = {}
    activity = {
        "title": title,
        "activity_type": activity_type,
        "course": "General",
        "deadline": deadline.isoformat(),
        "estimated_hours": estimated_hours,
        "priority": "Alta" if (deadline - today).days <= 3 else "Media",
        "metadata": metadata,
    }
    return {
        "needs_clarification": False,
        "activity": activity,
        "todo_items": todo_items,
        "summary": f"Dividi {title} en {len(todo_items)} pendientes hasta {deadline.strftime('%d/%m/%Y')}.",
        "agent_log": [
            {"agent": "Academic Coordinator", "action": "Solicitud clasificada", "payload": {"type": activity_type}},
            {"agent": "Task Analyzer", "action": "Actividad analizada", "payload": {"estimated_hours": estimated_hours}},
            {"agent": "Academic Planner", "action": "To-do semanal generado", "payload": {"items": len(todo_items)}},
        ],
    }


def llm_plan(message, context, today):
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI()
        prompt = {
            "today": today.isoformat(),
            "message": message,
            "context": context,
            "instructions": (
                "Actua como Academic Planning Crew con Academic Coordinator, Task Analyzer, Academic Planner y Progress Monitor. "
                "Devuelve JSON estricto. Si falta fecha, cantidad, paginas/capitulos o duración necesaria, pide aclaracion. "
                "No planifiques en fechas pasadas. Para lecturas divide paginas/capitulos entre dias restantes. "
                "Para ensayos divide en tema/tesis, investigacion, bosquejo, desarrollo, conclusion y revisión. "
                "Para laboratorios divide en partes y revisión."
            ),
            "schema": {
                "needs_clarification": "bool",
                "question": "string optional",
                "activity": {"title": "string", "activity_type": "string", "course": "string", "deadline": "YYYY-MM-DD", "estimated_hours": "number", "priority": "string", "metadata": {}},
                "todo_items": [{"title": "string", "date": "YYYY-MM-DD", "order": "number", "meta": {}}],
                "summary": "string",
            },
        }
        response = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
        )
        text = response.output_text.strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        data.setdefault("agent_log", [{"agent": "Academic Planning Crew", "action": "Plan generado por LLM", "payload": {}}])
        return data
    except Exception:
        return None


def plan_activity(message, context=None, today=None):
    today = today or date.today()
    llm = llm_plan(message, context or {}, today)
    if llm:
        return llm
    return fallback_plan(message, today, context or {})

