# Academic Planning Crew

App de Streamlit para planificacion academica con estructura tipo crew.

## Estructura

```text
src/academic_planning/
  crew.py
  main.py
  config/
    agents.yaml
    tasks.yaml
  tools/
    calendar_tool.py
    pdf_tool.py
    ocr_tool.py
    database_tool.py
  memory/
    short_term.py
    long_term.py
  models/
    student.py
    course.py
    activity.py
    progress.py
  workflows/
    planning_flow.py
```

## Flujo

- **Semana:** horarios fijos agregados manualmente.
- **Mes:** eventos y entregas con iconos y colores.
- **To-do:** lista semanal por dia con checkbox, editar, mover y eliminar.
- **Chat / Agentes:** analiza actividades y las divide en pendientes diarios.
- **Progreso:** muestra avance, pendientes y atrasos.

## API key

La app no pide ni guarda la API key en pantalla. Crea un `.env` local:

```env
OPENAI_API_KEY=tu_api_key
OPENAI_MODEL=gpt-4.1-mini
```

`.env` esta ignorado por Git.

## Correr

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```
