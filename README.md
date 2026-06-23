# Academic Planning Crew

Aplicación local en Streamlit para organizar clases, pendientes, eventos, hábitos,
metas y progreso académico. Incluye un asistente de planificación que puede usar
CrewAI y OpenAI, además de un planificador local que funciona sin API key.

## Funciones principales

- Vista **Hoy** con clases, pendientes, eventos, hábitos, metas y actividad reciente.
- Horario semanal en formato agenda o cuadrícula.
- Creación, edición e importación de horarios desde CSV, TXT, XLSX o XLS.
- Lectura opcional de horarios desde PNG, JPG, JPEG o WEBP mediante OpenAI.
- Calendario mensual para entregas, exámenes y eventos personales.
- Lista de pendientes con prioridad, duración, energía y replanificación.
- División de lecturas, ensayos, proyectos, exámenes y laboratorios en pasos.
- Seguimiento de actividades, estadísticas, progreso, hábitos y rachas.
- Metas semanales basadas en horas de estudio, tareas o hábitos.
- Perfil del estudiante y preferencias visuales persistentes.
- Temas Lila, Azul, Verde, Rosa, Naranja y Gris.
- Modos Claro, Oscuro y Automático.
- Memoria local en JSON y respaldos antes de operaciones sensibles.

Google Calendar, Moodle, notificaciones y sincronización entre dispositivos no
forman parte de la versión actual.

## Requisitos

- Python 3.10 o posterior
- Dependencias incluidas en `requirements.txt`
- API key de OpenAI únicamente para CrewAI y lectura de horarios desde imágenes

## Instalación

En PowerShell:

```powershell
cd Academic-Planning-Crew
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuración opcional de OpenAI

La aplicación funciona sin API key mediante el planificador local.

Para habilitar las funciones de OpenAI, copia `.env.example` como `.env`:

```powershell
Copy-Item .env.example .env
```

Después completa:

```env
OPENAI_API_KEY=tu_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_VISION_MODEL=gpt-4o-mini
```

También puedes copiar `.streamlit/secrets.toml.example` como
`.streamlit/secrets.toml`. Los archivos reales de secretos están ignorados por
Git y no deben publicarse.

## Ejecución

```powershell
python -m streamlit run app.py
```

La aplicación estará disponible normalmente en
`http://localhost:8501`.

## Uso rápido

1. Completa el perfil desde la barra lateral.
2. Agrega o importa tus clases en **Semana**.
3. Registra eventos en **Mes**.
4. Crea pendientes manualmente o usa **Chat / Agentes** para dividir una actividad.
5. Marca avances desde **Hoy**, **To-do**, **Progreso** o **Hábitos**.
6. Revisa métricas y tendencias en **Estadísticas**.

La apariencia y los widgets visibles se configuran desde **Apariencia** en la
barra lateral.

## Importación de horarios

La vista **Semana** acepta:

- Tablas CSV, TXT, XLSX y XLS.
- Imágenes PNG, JPG, JPEG y WEBP cuando existe una API key válida.
- Pegado manual de una tabla con día, inicio, fin, nombre y tipo.

Ejemplo:

```text
| día   | inicio | fin   | nombre     | tipo  |
|-------|--------|-------|------------|-------|
| Lunes | 07:00  | 07:40 | Matemática | Clase |
```

`sample_horario.csv` contiene un horario de ejemplo listo para importar.

## CrewAI y planificador local

`AcademicPlanningCrew` coordina agentes definidos en archivos YAML. Cuando CrewAI
y `OPENAI_API_KEY` están disponibles, la aplicación intenta generar el plan con
el modelo configurado.

Si la API no está configurada, CrewAI no está disponible o la respuesta no es
válida, se utiliza automáticamente el flujo local de
`src/academic_planning/workflows/planning_flow.py`.

El planificador local:

- identifica el tipo de actividad;
- valida fechas y datos necesarios;
- divide el trabajo en pasos;
- distribuye lecturas y fases entre días disponibles;
- considera clases, pendientes y horario de estudio.

## Datos y respaldos

Los datos locales se guardan en:

```text
data/academic_planning_store.json
```

Los respaldos automáticos se guardan en:

```text
data/backups/
```

La memoria contiene perfil, cursos, horario, actividades, pendientes, eventos,
hábitos, metas, chat, registros y configuración. Se crean respaldos antes de
reinicios, reemplazos de horario y limpiezas selectivas.

La pestaña **Memoria** permite descargar una copia JSON y borrar secciones
específicas sin eliminar necesariamente el resto.

`sample_data.json` contiene datos ficticios y no se carga automáticamente.

## Pruebas

```powershell
python -m pytest
```

Las pruebas cubren planificación, hábitos, progreso, memoria, respaldos,
preferencias y validaciones de la experiencia.

## Estructura

```text
Academic-Planning-Crew/
├── app.py
├── ui/
│   ├── dashboard.py
│   ├── planner.py
│   ├── calendar.py
│   ├── habits.py
│   ├── progress.py
│   ├── memory.py
│   └── shared.py
├── src/academic_planning/
│   ├── config/
│   ├── memory/
│   ├── models/
│   ├── profile/
│   ├── tools/
│   ├── workflows/
│   ├── crew.py
│   ├── habits.py
│   ├── progress_metrics.py
│   └── weekly_goals.py
├── tests/
├── sample_data.json
├── sample_horario.csv
├── requirements.txt
└── README.md
```

`app.py` configura Streamlit y conecta las pantallas. Los módulos de `ui/`
contienen las vistas, mientras que la lógica académica, el perfil, las
herramientas y los flujos de planificación viven en `src/academic_planning/`.

## Privacidad

La aplicación está diseñada para uso local y de una sola persona. El archivo
JSON no separa usuarios: si varias personas usan la misma instancia, compartirán
perfil, horario, tareas y hábitos.

No publiques:

- `.env`
- `.streamlit/secrets.toml`
- el contenido de `data/`
- datos personales o respaldos

## Despliegue

Para Streamlit Community Cloud:

1. Publica el repositorio sin datos ni secretos reales.
2. Selecciona `app.py` como archivo principal.
3. Configura los secretos de OpenAI solo si usarás sus funciones.
4. Verifica la instalación de `requirements.txt`.

La persistencia del sistema de archivos puede ser temporal en servicios
alojados. Para uso multiusuario se necesita autenticación y almacenamiento
externo con separación por usuario.

## Limitaciones actuales

- Persistencia en un único archivo JSON.
- Sin autenticación ni aislamiento multiusuario.
- Sin sincronización externa ni notificaciones.
- La lectura de imágenes y el flujo generativo requieren una API key válida.
- Parte de la interfaz continúa centralizada en `ui/shared.py`.
