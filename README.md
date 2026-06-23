# Academic Planning Crew

Academic Planning Crew es una app local en Streamlit para organizar la vida academica: horarios, pendientes, entregas, eventos, habitos, progreso y un chat/agente que ayuda a dividir actividades grandes en pasos manejables.

La app esta pensada para estudiantes que quieren abrir una sola pantalla y saber rapidamente que sigue, que urge y que conviene hacer hoy.

## Descripción General

Academic Planning Crew centraliza la planeacion academica diaria y semanal en una sola interfaz local. Combina vistas visuales de calendario, administracion de pendientes, seguimiento de habitos, metricas de progreso y un sistema de agentes que interpreta solicitudes en lenguaje natural para convertirlas en planes accionables.

El proyecto funciona principalmente de forma local: guarda la informacion en archivos JSON dentro del repositorio, genera respaldos automaticos y puede usar OpenAI de manera opcional para enriquecer el analisis de actividades y la lectura de horarios desde imagenes.

## Objetivo

Ayudar a estudiantes a transformar carga academica dispersa en un plan claro, sostenible y revisable, evitando la sobrecarga de tareas, fechas pasadas y horarios saturados.

El sistema busca responder preguntas practicas como:

- Que tengo que hacer hoy?
- Que entrega o evento urge mas?
- Como divido una lectura, ensayo, examen, laboratorio o proyecto?
- Como se ve mi semana academica completa?
- Que tan constante he sido con mis habitos?
- Que actividades estan atrasadas y necesitan replanificacion?

## Características

| Modulo | Descripcion |
| --- | --- |
| Hoy | Dashboard inteligente con proxima clase, pendiente urgente, proximo evento, avance del dia y recomendacion principal. |
| Planear mi dia | Lista sugerida que combina clases, pendientes vencidos, pendientes de hoy y eventos proximos. |
| Semana | Vista tipo agenda por dia para que los horarios cargados no se vean saturados, con opcion de administrar/importar horario. |
| Mes | Calendario mensual visual con detalle del dia, edicion de eventos y colores por tipo. |
| To-do inteligente | Pendientes organizados por `Vencidos`, `Hoy`, `Esta semana` y `Completados`, con tarjetas limpias y editor plegable. |
| Chat / Agentes | Analiza actividades en lenguaje natural y puede dividirlas en pendientes diarios. |
| Estadisticas | Panel visual con tareas completadas vs pendientes, cumplimiento, carga por materia, proximas actividades y horas semanales estimadas. |
| Progreso | Resumen de actividades, avance, completados, pendientes y atrasos. |
| Habitos | Seguimiento semanal y calendario de rutinas academicas. |
| Memoria | Descarga, revision y reinicio controlado de la estructura local de datos. |
| Importacion | Carga de horarios desde CSV, TXT, Excel e imagenes cuando hay API key configurada para vision. |
| Respaldos | Copias automaticas antes de acciones sensibles como reinicios o replanificaciones. |

## Casos de Uso

- Organizar horarios de clases en una vista semanal legible.
- Registrar entregas, examenes, eventos academicos y tareas personales.
- Dividir una lectura por paginas o capitulos entre los dias disponibles.
- Convertir proyectos, laboratorios, ensayos o examenes en fases manejables.
- Replanificar pendientes atrasados sin perder el historial.
- Revisar avances diarios, semanales y mensuales.
- Mantener rutinas academicas mediante habitos y rachas.
- Importar horarios desde archivos existentes o imagenes.
- Descargar la memoria local para respaldo, auditoria o migracion.

## Arquitectura

El proyecto esta organizado como una aplicacion Streamlit con una capa principal de interfaz (`app.py`) y una capa de logica academica en `src/academic_planning`.

```text
Academic-Planning-Crew/
  app.py
  requirements.txt
  sample_horario.csv
  sample_rastreo.csv
  data/
    academic_planning_store.json
    backups/
  src/academic_planning/
    crew.py
    main.py
    config/
      agents.yaml
      tasks.yaml
    tools/
      calendar_tool.py
      google_calendar_integration.py
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

Arquitectura conceptual:

```text
+--------------------------+
|        Streamlit UI       |
| Hoy / Semana / Mes / Todo |
| Chat / Progreso / Habitos |
+------------+-------------+
             |
             v
+--------------------------+
|        app.py             |
| Estado, vistas, formularios|
| importacion y persistencia |
+------------+-------------+
             |
             v
+--------------------------+
| AcademicPlanningCrew      |
| crew.py                   |
+------------+-------------+
             |
             v
+--------------------------+
| CrewAI Agent / Task / Crew|
| YAML + tools + fallback   |
+------------+-------------+
             |
             v
+--------------------------+
| Herramientas y Dominio    |
| models / tools / memory   |
+------------+-------------+
             |
             v
+--------------------------+
| data/academic_planning... |
| JSON local + backups      |
+--------------------------+
```

## Agentes

La configuracion de agentes vive en `src/academic_planning/config/agents.yaml`.

| Agente | Rol | Responsabilidad |
| --- | --- | --- |
| `academic_coordinator` | Coordinador principal del sistema de planificacion academica | Entender la solicitud, clasificarla y delegar solo a los agentes necesarios. |
| `student_profile_manager` | Administrador del perfil academico y personal | Mantener disponibilidad, horarios fijos, actividades recurrentes y restricciones temporales. |
| `task_analyzer` | Analizador academico de actividades | Convertir tareas, lecturas, examenes, ensayos y proyectos en objetos estructurados y divisibles. |
| `academic_planner` | Planificador academico inteligente | Distribuir subtareas en dias disponibles sin usar fechas pasadas y sin sobrecargar al estudiante. |
| `progress_monitor` | Monitor de progreso academico | Comparar avance real contra planificado y activar redistribucion cuando hay retrasos. |

Tareas configuradas:

| Tarea | Agente | Salida esperada |
| --- | --- | --- |
| `classify_student_request` | `academic_coordinator` | `request_type`, `workflow`, `required_agents` |
| `analyze_academic_activity` | `task_analyzer` | Tipo de actividad, fecha limite, horas estimadas, complejidad, prioridad y datos faltantes |
| `review_student_profile` | `student_profile_manager` | Disponibilidad, habitos, preferencias, pendientes abiertos y carga semanal |
| `build_weekly_todo_plan` | `academic_planner` | Pendientes distribuidos solo en fechas de hoy o futuras |
| `monitor_progress` | `progress_monitor` | Avance, trabajo restante y recomendacion de replanificacion |
| `coordinate_final_response` | `academic_coordinator` | JSON final compatible con Streamlit |

## Flujo de Trabajo

Flujo general de uso:

```text
1. Completa tu perfil en la barra lateral
2. Carga o crea tu horario en Semana
3. Agrega entregas y eventos importantes en Mes
4. Usa Chat / Agentes para dividir actividades grandes
5. Revisa Hoy cada dia para decidir que hacer primero
6. Usa To-do para editar, completar o replanificar pendientes
7. Revisa Progreso y Habitos para mantener constancia
```

Flujo interno del sistema de agentes:

```text
Usuario escribe una actividad
          |
          v
+----------------------+
| Academic Coordinator |
+----------+-----------+
           |
           v
+----------------------+
| Task Analyzer        |
| tipo, fecha, esfuerzo|
+----------+-----------+
           |
           v
+----------------------+
| Student Profile      |
| disponibilidad/carga |
+----------+-----------+
           |
           v
+----------------------+
| Academic Planner     |
| distribucion futura  |
+----------+-----------+
           |
           v
+----------------------+
| Todo Items + Log     |
| memoria local JSON   |
+----------+-----------+
           |
           v
+----------------------+
| Progress Monitor     |
| avance y replanteo   |
+----------------------+
```

## Integracion Real con CrewAI

El chat academico entra por `app.py` y llama a `AcademicPlanningCrew` en `src/academic_planning/crew.py`.
Esa clase carga `config/agents.yaml` y `config/tasks.yaml`, crea agentes reales con `Agent`, tareas reales con `Task` y ejecuta un `Crew` secuencial cuando existe `OPENAI_API_KEY` y CrewAI esta instalado.

El workflow usa cinco agentes:

1. `academic_coordinator`: clasifica la solicitud y organiza la respuesta final.
2. `task_analyzer`: interpreta tipo, fecha, prioridad, carga y datos faltantes.
3. `student_profile_manager`: revisa disponibilidad, habitos, preferencias y carga semanal.
4. `academic_planner`: crea el plan de pendientes.
5. `progress_monitor`: revisa progreso, atrasos y estado actual.

Para no romper la app, las funciones actuales de `planning_flow.py` se conservan y se exponen como herramientas:

- `analizar_actividad_academica`
- `revisar_perfil_estudiante`
- `crear_plan_local`
- `revisar_progreso_actual`

Si CrewAI no esta disponible, falta la API key o el modelo devuelve una salida no valida, el sistema usa automaticamente el planificador local anterior. Por eso Streamlit mantiene el mismo comportamiento y la misma estructura de respuesta: `needs_clarification`, `question`, `activity`, `todo_items`, `summary` y `agent_log`.

## Entidades de Dominio

| Entidad | Archivo | Campos principales | Uso |
| --- | --- | --- | --- |
| `Student` | `models/student.py` | `name`, `career`, `semester` | Perfil academico del estudiante. |
| `Course` | `models/course.py` | `name`, `color` | Materias y codificacion visual. |
| `Activity` | `models/activity.py` | `title`, `activity_type`, `deadline`, `estimated_hours`, `metadata` | Actividades academicas estructuradas. |
| `Progress` | `models/progress.py` | `completed`, `actual_amount` | Seguimiento basico de avance. |
| Horario | `app.py` / memoria JSON | Dia, hora de inicio, hora de fin, nombre, tipo, color | Bloques de clases y disponibilidad. |
| Pendiente | `app.py` / memoria JSON | Titulo, fecha, estado, prioridad, energia, duracion estimada, metadata | Unidad accionable del plan diario/semanal. |
| Habito | `app.py` / memoria JSON | Titulo, categoria, meta semanal, historial, racha, color | Rutinas academicas recurrentes. |
| Evento | `app.py` / memoria JSON | Fecha, titulo, tipo, color y detalles | Calendario mensual y recordatorios academicos. |

## Sistema de Memoria

La app guarda la informacion en:

```text
data/academic_planning_store.json
```

Tambien crea respaldos automaticos en:

```text
data/backups/
```

La memoria local incluye, entre otros datos:

- Perfil del estudiante.
- Cursos y colores asociados.
- Bloques de horario y disponibilidad.
- Actividades academicas.
- Pendientes generados manualmente o por agentes.
- Eventos del calendario.
- Habitos, historial y rachas.
- Estadisticas calculadas desde pendientes, eventos, habitos y registros de progreso.
- Historial de chat.
- Log de acciones de agentes.
- Configuraciones visuales y preferencias de planificacion.

No se cambia el formato de importacion existente para CSV, Excel, TXT, PDF o imagen.

## Tecnologías Utilizadas

| Tecnologia | Uso |
| --- | --- |
| Python 3.10+ | Lenguaje principal del proyecto. |
| Streamlit | Interfaz web local e interactiva. |
| pandas | Lectura, transformacion y visualizacion tabular de datos. |
| openpyxl / xlrd | Importacion de hojas de calculo `.xlsx` y `.xls`. |
| OpenAI SDK | Planificacion con modelo y lectura de horarios desde imagen cuando hay API key. |
| CrewAI | Orquestacion real de agentes `Agent`, `Task` y `Crew` para el chat academico. |
| PyYAML | Lectura de `agents.yaml` y `tasks.yaml`. |
| JSON | Persistencia local de memoria y respaldos. |
| YAML | Configuracion declarativa de agentes y tareas. |

## Instalación

Requisitos:

- Python 3.10 o superior.
- Streamlit.
- pandas.
- openpyxl / xlrd para importar hojas de calculo.
- OpenAI SDK si se usa lectura de imagen o funciones del agente con modelo.

Clona o descarga el proyecto y entra a la carpeta:

```powershell
cd Academic-Planning-Crew
```

Instala dependencias:

```powershell
python -m pip install -r requirements.txt
```

Ejecuta la app:

```powershell
streamlit run app.py
```

Luego abre:

```text
http://localhost:8501
```

## Variables de Entorno

La app no pide ni guarda la API key en pantalla. Para usar funciones con OpenAI, crea un archivo `.env` local en la raiz del proyecto:

```env
OPENAI_API_KEY=tu_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_VISION_MODEL=gpt-4o-mini
```

| Variable | Requerida | Descripcion |
| --- | --- | --- |
| `OPENAI_API_KEY` | No, pero necesaria para funciones con modelo | Habilita el uso del OpenAI SDK para planificacion asistida y lectura de imagenes. |
| `OPENAI_MODEL` | No | Modelo usado para planificacion por lenguaje natural. Si no se define, se usa un valor por defecto. |
| `OPENAI_VISION_MODEL` | No | Modelo usado para interpretar horarios desde imagenes. Si no se define, se usa `OPENAI_MODEL` o un valor por defecto. |

`.env` esta ignorado por Git.

## Ejemplo de Uso

Ejemplo de horario importable:

```text
dia,inicio,fin,nombre,tipo,color
Lunes,07:00,08:20,Matematica,Clase,#93c5fd
```

Tambien se aceptan archivos `.csv`, `.txt`, `.xlsx`, `.xls` e imagenes (`.png`, `.jpg`, `.jpeg`, `.webp`) cuando hay API key configurada para vision.

Ejemplo de solicitud para `Chat / Agentes`:

```text
Tengo que leer 120 paginas de Historia para el 28/06/2026
```

Resultado esperado:

```text
1. El sistema detecta que es una lectura.
2. Identifica fecha limite y cantidad de paginas.
3. Calcula los dias disponibles desde hoy hasta la fecha limite.
4. Revisa carga de clases y pendientes existentes.
5. Divide la lectura en pendientes diarios.
6. Guarda actividad, pendientes y log de agentes en la memoria local.
```

## Diseño

La interfaz usa una estetica pastel con acentos lila y detalles de estrellas. Las materias, eventos, tareas y habitos usan colores suaves para que el calendario y el horario se lean mejor sin sentirse pesados.

## Limitaciones

- La app esta pensada para uso local; no incluye autenticacion multiusuario.
- La persistencia se basa en JSON local, no en una base de datos remota.
- Las funciones con OpenAI dependen de `OPENAI_API_KEY`.
- La lectura de imagenes requiere un modelo con capacidades de vision.
- El planificador local funciona como respaldo deterministico, pero puede requerir aclaraciones cuando faltan datos como fecha limite, paginas o duracion.
- No se planifican actividades en fechas pasadas.
- La vista mensual no muestra habitos ni pendientes por defecto para evitar sobreestimular el calendario.
- El historial del chat puede limpiarse desde `Chat / Agentes`.
- Los pendientes existentes reciben valores por defecto seguros: prioridad media, energia normal y 30 minutos estimados.

## Roadmap

- Mejorar el motor de replanificacion automatica segun avance real.
- Agregar filtros avanzados por materia, prioridad, energia y tipo de actividad.
- Permitir exportar calendario a formatos externos.
- Incorporar notificaciones locales o recordatorios programados.
- Crear pruebas automatizadas para los flujos criticos.
- Mejorar la edicion masiva de horarios, eventos y pendientes.
- Agregar analiticas historicas de carga academica y consistencia.
- Documentar ejemplos adicionales de importacion y uso de agentes.

## Integraciones Futuras

| Integracion | Posible uso |
| --- | --- |
| Google Calendar | Sincronizar clases, entregas y eventos. |
| Microsoft Outlook Calendar | Integrar calendario academico con cuentas institucionales. |
| Notion | Exportar planes semanales o tableros de pendientes. |
| Google Sheets | Mantener rastreos academicos compartidos. |
| LMS institucional | Importar entregas desde plataformas academicas. |
| Base de datos remota | Habilitar sincronizacion entre dispositivos. |
| Notificaciones | Recordatorios de pendientes, eventos y habitos. |

### Preparacion para Google Calendar

La estructura base ya existe en:

```text
src/academic_planning/tools/google_calendar_integration.py
```

Funciones disponibles como placeholders:

- `export_event_to_google_calendar(event)`
- `import_google_calendar_events()`
- `sync_calendar_events()`

Para activar Google Calendar real todavia falta:

- Crear un proyecto en Google Cloud y habilitar Google Calendar API.
- Configurar pantalla de consentimiento OAuth.
- Descargar credenciales OAuth y guardarlas fuera del repositorio.
- Agregar dependencias oficiales de Google si se usara el SDK.
- Implementar almacenamiento seguro de tokens.
- Mapear eventos locales de `store["events"]` al formato de Google Calendar.
- Decidir reglas de sincronizacion: solo exportar, solo importar o sincronizacion bidireccional.

## Screenshots

> Placeholders para capturas futuras.

| Vista | Screenshot |
| --- | --- |
| Hoy | `docs/screenshots/hoy.png` |
| Semana | `docs/screenshots/semana.png` |
| Mes | `docs/screenshots/mes.png` |
| To-do | `docs/screenshots/todo.png` |
| Chat / Agentes | `docs/screenshots/chat-agentes.png` |
| Progreso | `docs/screenshots/progreso.png` |
| Habitos | `docs/screenshots/habitos.png` |
| Memoria | `docs/screenshots/memoria.png` |

## Contribuciones

Las contribuciones son bienvenidas. Para mantener el proyecto ordenado:

1. Crea una rama descriptiva para tu cambio.
2. Mantén los cambios enfocados en una mejora o correccion concreta.
3. Actualiza el README si agregas una funcionalidad visible.
4. Verifica que la app ejecute correctamente con `streamlit run app.py`.
5. Evita subir archivos locales sensibles como `.env` o datos personales.

Sugerencias de contribucion:

- Mejoras de interfaz y accesibilidad.
- Nuevos importadores de horarios.
- Pruebas para `planning_flow.py`.
- Mejor documentacion de entidades y memoria.
- Integraciones con calendarios externos.

## Notas

- La app es local y mantiene tus datos en tu carpeta del proyecto.
- El historial del chat puede limpiarse desde `Chat / Agentes`.
- Los pendientes existentes reciben valores por defecto seguros: prioridad media, energia normal y 30 minutos estimados.
- La vista mensual no muestra habitos ni pendientes por defecto para evitar sobreestimular el calendario.
