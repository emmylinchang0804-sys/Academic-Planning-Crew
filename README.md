# Academic Planning Crew

Repositorio base para un asistente de planificacion academica organizado como un flujo de agentes. La estructura apunta a una aplicacion Python con configuracion declarativa de agentes y tareas, mas herramientas especializadas para lectura de PDF y generacion o manejo de calendario.

## Estado actual

El proyecto esta en fase inicial. Los archivos principales ya existen, pero todavia no tienen implementacion:

- `src/academic_planning/main.py`: punto de entrada previsto para ejecutar el flujo.
- `src/academic_planning/crew.py`: modulo previsto para definir y orquestar la crew de agentes.
- `src/academic_planning/config/agents.yaml`: configuracion prevista de agentes.
- `src/academic_planning/config/tasks.yaml`: configuracion prevista de tareas.
- `src/academic_planning/tools/pdf_tool.py`: herramienta prevista para procesar documentos PDF.
- `src/academic_planning/tools/calendar_tool.py`: herramienta prevista para crear o administrar informacion de calendario.

## Estructura

```text
src/
└── academic_planning/
    ├── main.py
    ├── crew.py
    ├── config/
    │   ├── agents.yaml
    │   └── tasks.yaml
    └── tools/
        ├── calendar_tool.py
        └── pdf_tool.py
```

## Objetivo del proyecto

La intencion del proyecto es construir un flujo que ayude a transformar informacion academica en una planificacion util. Un caso de uso esperado seria:

1. Recibir documentos academicos, como programas de curso, calendarios institucionales o PDFs con fechas importantes.
2. Extraer fechas, evaluaciones, actividades y requisitos.
3. Organizar esa informacion en tareas academicas.
4. Generar una planificacion o calendario para el estudiante, docente o equipo academico.

## Instalacion

Todavia no existe un archivo de dependencias como `requirements.txt` o `pyproject.toml`. Cuando se agregue la implementacion, se recomienda crear un entorno virtual e instalar las dependencias declaradas por el proyecto.

Ejemplo base:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En macOS/Linux:

```bash
source .venv/bin/activate
```

## Uso

El punto de entrada previsto es:

```bash
python -m academic_planning.main
```

Actualmente este comando no ejecuta funcionalidad porque `main.py` esta vacio.

## Desarrollo pendiente

Para convertir este esqueleto en una aplicacion funcional, faltan al menos estos pasos:

1. Definir dependencias del proyecto en `pyproject.toml` o `requirements.txt`.
2. Implementar `main.py` como punto de entrada.
3. Implementar `crew.py` con la orquestacion de agentes y tareas.
4. Completar `config/agents.yaml` con roles, objetivos y contexto de cada agente.
5. Completar `config/tasks.yaml` con las tareas del flujo academico.
6. Implementar `pdf_tool.py` para extraer texto o datos estructurados de PDFs.
7. Implementar `calendar_tool.py` para generar eventos, archivos `.ics` o salidas equivalentes.
8. Agregar pruebas para las herramientas y el flujo principal.

## Notas

Este README refleja el contenido real del repositorio en su estado actual. A medida que se agregue codigo, comandos de instalacion, variables de entorno y ejemplos de uso, este documento debe actualizarse para mantenerse alineado con la aplicacion.
