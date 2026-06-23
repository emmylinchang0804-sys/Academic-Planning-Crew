# Academic Planning Crew

Academic Planning Crew es una aplicacion local en Streamlit para organizar horarios,
pendientes, eventos, actividades, habitos y progreso academico. Incluye un chat de
planificacion que puede usar CrewAI y OpenAI, con un planificador local como respaldo.

## Caracteristicas principales

- Dashboard diario con clases, tareas urgentes, eventos y avance.
- Horario semanal editable e importable desde CSV, TXT, Excel o imagen.
- Calendario mensual para entregas, examenes y eventos.
- Lista de pendientes con prioridades, duracion, energia y replanificacion.
- Division de lecturas, ensayos, proyectos, examenes y laboratorios en pasos.
- Seguimiento de actividades, progreso, habitos y rachas.
- Memoria local en JSON y respaldos antes de operaciones sensibles.
- Funcionamiento local sin API key mediante un fallback deterministico.

Google Calendar y Moodle no forman parte de las funcionalidades actuales. Sus
integraciones fueron removidas por ahora y solo se consideran mejoras futuras.

## Tecnologias usadas

- Python 3.10+
- Streamlit
- pandas
- CrewAI
- OpenAI SDK
- PyYAML
- openpyxl y xlrd
- pytest
- JSON para almacenamiento local

## Instalacion

```powershell
cd Academic-Planning-Crew
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

La API key es opcional. Para habilitar OpenAI, crea un archivo `.env`:

```env
OPENAI_API_KEY=tu_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_VISION_MODEL=gpt-4o-mini
```

El archivo `.env` esta ignorado por Git.

## Ejecucion

```powershell
streamlit run app.py
```

La aplicacion queda disponible normalmente en `http://localhost:8501`.

## Pruebas

```powershell
pytest
```

Las pruebas basicas cubren planificacion local, memoria, respaldos, habitos y
estadisticas de progreso.

## Estructura del proyecto

```text
Academic-Planning-Crew/
|-- app.py
|-- ui/
|   |-- dashboard.py
|   |-- planner.py
|   |-- calendar.py
|   |-- habits.py
|   |-- progress.py
|   |-- memory.py
|   `-- shared.py
|-- src/academic_planning/
|   |-- crew.py
|   |-- config/
|   |-- memory/
|   |-- models/
|   |-- profile/
|   |-- tools/
|   `-- workflows/
|-- tests/
|-- data/
|   |-- academic_planning_store.json
|   `-- backups/
|-- requirements.txt
`-- README.md
```

`app.py` configura Streamlit, carga el almacenamiento y compone las pantallas.
Los modulos de `ui/` exponen las vistas. `ui/shared.py` conserva widgets y helpers
compartidos para evitar cambios de comportamiento durante la modularizacion.
La logica academica y de agentes vive en `src/academic_planning/`.

## Arquitectura general

```text
Streamlit app.py
      |
      v
Pantallas ui/ ----> almacenamiento JSON + backups
      |
      v
AcademicPlanningCrew
      |
      +----> CrewAI / OpenAI cuando hay API key
      |
      `----> fallback local deterministico
```

Las pantallas modifican una estructura de datos comun. Al finalizar cada ciclo de
Streamlit, la app guarda el estado en el archivo JSON existente.

## CrewAI, OpenAI y fallback local

`AcademicPlanningCrew` coordina agentes configurados en YAML para analizar una
solicitud, revisar el perfil, crear un plan y evaluar progreso. Cuando CrewAI y
`OPENAI_API_KEY` estan disponibles, la app intenta generar el plan con el modelo.

Si falta la API key, CrewAI no esta disponible o la respuesta no es valida, se usa
automaticamente la logica local de `planning_flow.py`. Este fallback:

- identifica el tipo de actividad;
- solicita fecha o cantidad cuando faltan;
- evita fechas pasadas;
- distribuye lecturas y fases entre dias disponibles;
- considera clases, pendientes y horas de estudio.

## Memoria y respaldos

El almacenamiento actual se mantiene en:

```text
data/academic_planning_store.json
```

Los respaldos se crean en:

```text
data/backups/
```

La memoria incluye perfil, cursos, horario, actividades, pendientes, eventos,
habitos, historial de chat, registros de agentes y configuracion. La app crea
respaldos antes de reinicios, reemplazos de horario y limpiezas selectivas. La
pantalla Memoria permite descargar una copia JSON.

No se migra a SQLite en esta version. SQLite queda como recomendacion futura para
mejorar consultas, integridad y crecimiento del almacenamiento.

## Limitaciones actuales

- Aplicacion local y de un solo usuario, sin autenticacion.
- Persistencia basada en un unico archivo JSON.
- Las funciones generativas y lectura de imagenes requieren una API key valida.
- El fallback local es deterministico y puede pedir datos adicionales.
- No hay sincronizacion con Google Calendar.
- No hay conexion con Moodle.
- No hay notificaciones del sistema ni sincronizacion entre dispositivos.
- Parte de los helpers visuales compartidos sigue centralizada en `ui/shared.py`.

## Roadmap

- Continuar separando helpers de `ui/shared.py` por dominio.
- Migrar opcionalmente el almacenamiento a SQLite.
- Mejorar la replanificacion segun avance real y carga futura.
- Agregar mas pruebas de formularios, importacion y flujos de agentes.
- Incorporar exportacion de calendario y recordatorios locales.
- Evaluar nuevamente integraciones con Google Calendar y Moodle.
- Agregar autenticacion y sincronizacion multiusuario si el proyecto lo requiere.

## Archivos de ejemplo

- `sample_horario.csv`: ejemplo para importar un horario.
- `sample_rastreo.csv`: ejemplo de datos de seguimiento.

No subas `.env`, datos personales ni el contenido local de `data/` al repositorio.
