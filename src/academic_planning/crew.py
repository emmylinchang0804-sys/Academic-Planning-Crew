import json
import os
from datetime import date
from pathlib import Path

from .workflows.planning_flow import (
    analyze_activity_payload,
    build_plan_payload,
    load_dotenv,
    plan_activity,
    progress_payload,
    student_profile_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(__file__).resolve().parent / "config"


def _load_yaml(path):
    """Load simple YAML config without making Streamlit depend on CrewAI."""
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except Exception:
        return _load_simple_yaml(path)


def _load_simple_yaml(path):
    data = {}
    current_key = None
    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" ") and line.endswith(":"):
                current_key = line[:-1].strip()
                data[current_key] = {}
                continue
            if current_key and ":" in line:
                key, value = line.strip().split(":", 1)
                data[current_key][key.strip()] = value.strip().strip('"').strip("'")
    return data


def _json_dumps(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_json(text):
    if not text:
        return None
    if not isinstance(text, str):
        text = str(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


class AcademicPlanningCrew:
    def __init__(self, today=None):
        self.today = today or date.today()
        self.agents_config = _load_yaml(CONFIG_DIR / "agents.yaml")
        self.tasks_config = _load_yaml(CONFIG_DIR / "tasks.yaml")

    def plan_from_message(self, message, context=None):
        context = context or {}
        crew_result = self._run_crewai(message, context)
        if crew_result:
            return crew_result
        fallback = plan_activity(message, context, today=self.today)
        fallback.setdefault("agent_log", []).insert(
            0,
            {
                "agent": "Academic Planning Crew",
                "action": "Fallback local usado",
                "payload": {"reason": "CrewAI no disponible, sin API key o salida no valida"},
            },
        )
        return fallback

    def _run_crewai(self, message, context):
        load_dotenv(PROJECT_ROOT)
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        try:
            from crewai import Agent, Crew, Process, Task
            from crewai.tools import tool as crew_tool
        except Exception:
            return None

        try:
            tools = self._build_tools(crew_tool, message, context)
            agents = self._build_agents(Agent, tools)
            tasks = self._build_tasks(Task, agents, message, context)
            crew = Crew(
                agents=list(agents.values()),
                tasks=tasks,
                process=Process.sequential,
                verbose=False,
            )
            output = crew.kickoff(
                inputs={
                    "today": self.today.isoformat(),
                    "message": message,
                    "context_json": _json_dumps(context),
                }
            )
            result = _extract_json(getattr(output, "raw", None) or str(output))
            if not result:
                return None
            return self._normalize_crewai_result(result)
        except Exception as exc:
            return {
                **plan_activity(message, context, today=self.today),
                "agent_log": [
                    {
                        "agent": "Academic Planning Crew",
                        "action": "CrewAI fallo; se uso fallback local",
                        "payload": {"error": str(exc)[:180]},
                    }
                ],
            }

    def _build_tools(self, crew_tool, message, context):
        @crew_tool("analizar_actividad_academica")
        def analyze_activity_tool() -> str:
            """Analiza tipo, fecha, prioridad, carga y datos faltantes."""
            return _json_dumps(analyze_activity_payload(message, self.today))

        @crew_tool("revisar_perfil_estudiante")
        def student_profile_tool() -> str:
            """Resume disponibilidad, preferencias, habitos y carga semanal."""
            return _json_dumps(student_profile_payload(context, self.today))

        @crew_tool("crear_plan_local")
        def local_planning_tool() -> str:
            """Crea un plan usando la logica deterministica actual de la app."""
            return _json_dumps(build_plan_payload(message, context, self.today))

        @crew_tool("revisar_progreso_actual")
        def progress_tool() -> str:
            """Resume avance, pendientes y atrasos actuales."""
            return _json_dumps(progress_payload(context, self.today))

        return {
            "analyze_activity": analyze_activity_tool,
            "student_profile": student_profile_tool,
            "local_planning": local_planning_tool,
            "progress": progress_tool,
        }

    def _build_agents(self, Agent, tools):
        tool_map = {
            "student_profile_manager": [tools["student_profile"]],
            "task_analyzer": [tools["analyze_activity"]],
            "academic_planner": [tools["local_planning"], tools["student_profile"]],
            "progress_monitor": [tools["progress"]],
            "academic_coordinator": [tools["analyze_activity"], tools["local_planning"], tools["progress"]],
        }
        agents = {}
        for name, config in self.agents_config.items():
            agents[name] = Agent(
                role=config.get("role", name),
                goal=config.get("goal", ""),
                backstory=config.get("backstory", ""),
                tools=tool_map.get(name, []),
                allow_delegation=False,
                verbose=False,
            )
        return agents

    def _build_tasks(self, Task, agents, message, context):
        tasks = []
        ordered_configs = sorted(
            self.tasks_config.items(),
            key=lambda item: int(item[1].get("order", 99) or 99),
        )
        for name, config in ordered_configs:
            agent_name = config.get("agent")
            agent = agents.get(agent_name)
            if not agent:
                continue
            description = config.get("description", "")
            description = description.format(
                today=self.today.isoformat(),
                message=message,
                context_json=_json_dumps(context),
            )
            tasks.append(
                Task(
                    description=description,
                    expected_output=config.get("expected_output", "Resultado claro y estructurado."),
                    agent=agent,
                )
            )
        return tasks

    def _normalize_crewai_result(self, result):
        result.setdefault("needs_clarification", False)
        result.setdefault("todo_items", [])
        result.setdefault("agent_log", [])
        result["agent_log"].insert(
            0,
            {
                "agent": "Academic Planning Crew",
                "action": "Workflow CrewAI ejecutado",
                "payload": {"agents": list(self.agents_config.keys())},
            },
        )
        return result
