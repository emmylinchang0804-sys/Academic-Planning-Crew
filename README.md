# Academic Planning Crew

Aplicación local en Streamlit para organizar clases, pendientes, eventos, hábitos,
metas y progreso académico. Incluye un asistente de planificación que puede usar
CrewAI y OpenAI, además de un planificador local que funciona sin API key.

# Live Demo

Academic Planning Crew se encuentra disponible en línea mediante Streamlit Cloud:

[https://vqm65skzewzqz54alymg3c.streamlit.app/](https://vqm65skzewzqz54alymg3c.streamlit.app/)

Esta demostración permite explorar las funcionalidades principales de la plataforma directamente desde el navegador sin necesidad de instalación local.

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

- Python 3.10 o posterior (Python 3.13.14 es la versión validada)
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
streamlit run app.py
```

La aplicación estará disponible normalmente en
`http://localhost:8501`.

## Usuarios, registro e inicio de sesión

Al abrir la aplicación sin una sesión activa se muestran únicamente las
pantallas **Iniciar sesión** y **Crear cuenta**. Cada persona debe:

1. Crear una cuenta con nombre, correo y una contraseña de al menos 8 caracteres.
2. Iniciar sesión con ese correo y contraseña.
3. Usar **Cerrar sesión** en la barra lateral al terminar.

La sesión activa se mantiene en `st.session_state`. Las contraseñas nunca se
guardan en texto plano: se derivan con PBKDF2-HMAC-SHA256, salt aleatorio y
comparación segura del hash.

Antes de iniciar sesión se puede elegir **Modo claro** o **Modo oscuro** desde
la pantalla inicial. El cambio se aplica al instante y, al entrar, se guarda en
la memoria del usuario activo. Los campos de contraseña de login y registro
incluyen un botón con ojo para mostrar u ocultar el texto temporalmente.

## Uso rápido

1. Regístrate o inicia sesión.
2. Completa el perfil desde la barra lateral.
3. Agrega o importa tus clases en **Semana**.
4. Registra eventos en **Mes**.
5. Crea pendientes manualmente o usa **Chat / Agentes** para dividir una actividad.
6. Marca avances desde **Hoy**, **To-do**, **Progreso** o **Hábitos**.
7. Revisa métricas y tendencias en **Estadísticas**.

La apariencia y los widgets visibles se configuran desde **Apariencia** en la
barra lateral.

La sección **Cuenta** de la barra lateral concentra opciones personales:

- Tema claro u oscuro.
- **Descargar todos mis datos** en `academic_planning_backup.json`.
- **Importar todos mis datos** desde `academic_planning_backup.json`, con validación, advertencia de sobrescritura y respaldo automático previo.
- **Descargar horario** en `horario.json`.
- **Importar horario** desde `horario.json`, con validación y confirmación.
- **Borrar datos de demostración**, cuando la cuenta contiene datos de ejemplo.
- **Restaurar datos demo**, para volver a cargar ejemplos si fueron eliminados.
- **Cambiar contraseña**, validando la contraseña actual y guardando un hash
  PBKDF2-HMAC-SHA256 nuevo con salt aleatorio.
- **Eliminar cuenta**, con confirmación escrita, contraseña actual, cierre de
  sesión y respaldo final de la carpeta del usuario.

## Datos de demostración

Durante el registro, la app pregunta:

```text
¿Deseas comenzar con datos de demostración?
```

Si eliges **Sí**, se crea una cuenta con ejemplos realistas para mostrar todas
las secciones principales:

- Dashboard con próximas clases, eventos, pendientes, hábitos y avance del día.
- Horario semanal de lunes a viernes, de 07:00 a 13:00, con bloques de 40
  minutos y recesos libres de 09:00-09:20 y 11:20-11:40.
- Materias demo: Matemática, Física, Química, Ética, Biología, Literatura,
  Estadística, Computación, Liderazgo, Mate aplicada, Inglés, Robótica,
  Programación, Seminario y Laboratorio.
- Calendario con examen, entrega de proyecto, reunión de grupo y presentación.
- To-do con tareas pendientes, próximas y completadas.
- Hábitos como estudiar 1 hora, leer, repasar apuntes, dormir temprano y hacer ejercicio.
- Progreso, actividades académicas y una meta semanal coherente con esos datos.

Cada elemento de demostración se marca internamente como demo. Desde **Cuenta →
Datos de demostración → Borrar datos de demostración** se eliminan solo esos
elementos del usuario actual. Los datos creados manualmente se conservan.

Si borras los ejemplos y luego quieres verlos otra vez, usa **Cuenta -> Restaurar datos demo**.
La app crea un respaldo antes de restaurarlos y los carga solo en la cuenta actual.

## Chat / Agentes

Cuando el chat crea actividades, pendientes o eventos, la app resume la
intención del mensaje antes de guardar. El prompt literal no se usa como título:
se genera un título académico corto, máximo 50 caracteres, y la descripción
conserva el contexto útil. Si el mensaje menciona materia, fecha u hora, se
mantienen en el plan; si falta información esencial, el agente pide aclaración
antes de crear datos.

Ejemplos:

- “mañana tengo que estudiar para el examen de mate...” se guarda como
  **Estudiar funciones de Matemática**.
- “el viernes tengo entrega del proyecto de programación...” se guarda como
  **Entrega proyecto de Programación**.

## Cambiar contraseña

Desde **Cuenta → Cambiar contraseña**, el usuario puede actualizar su contraseña
sin cerrar la sesión. La app pide:

- Contraseña actual.
- Nueva contraseña.
- Confirmación de la nueva contraseña.

La contraseña actual debe ser correcta, la nueva contraseña debe tener al menos
8 caracteres y la confirmación debe coincidir. Si alguna validación falla, no se
modifica el registro. Si todo es correcto, se guarda un nuevo hash
PBKDF2-HMAC-SHA256 con salt aleatorio en `data/auth/users.json`; la contraseña
nunca se guarda en texto plano.

## Eliminar cuenta

Desde **Cuenta → Eliminar cuenta** se muestra la advertencia:

```text
Esta acción eliminará tu cuenta y todos tus datos. No se puede deshacer.
```

Para continuar, el usuario debe escribir `ELIMINAR` y confirmar su contraseña
actual. Con contraseña correcta se elimina el registro de `data/auth/users.json`,
se mueve `data/users/<user_id>/` a `data/deleted_accounts/`, se cierra la sesión
y se vuelve al login. Con contraseña incorrecta no se elimina nada.

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

## Exportar e importar horario JSON

Desde **Cuenta → Descargar horario** se exporta solo la información relacionada
con el horario del usuario actual. El archivo recomendado es:

```text
horario.json
```

Incluye cursos, disponibilidad/bloques de horario, estructuras de horario
compatibles y configuración visual relacionada con la vista semanal. No incluye
tareas, eventos, hábitos, chat, progreso ni datos de otros usuarios.

Para importar, usa **Cuenta → Importar horario**, selecciona un `horario.json`
compatible y marca la confirmación. Por defecto se agrega al horario actual; si
activas **Reemplazar mi horario actual**, la app crea un respaldo antes de
sustituirlo.

## Exportar e importar todos mis datos

Desde **Cuenta -> Descargar todos mis datos** se genera:

```text
academic_planning_backup.json
```

El respaldo incluye solo la información del usuario actual: tareas, eventos,
hábitos, horario, progreso, preferencias, metas, memoria, estadísticas derivadas
y configuración relevante. No incluye contraseñas, hashes, sales, tokens, API
keys, registros internos de autenticación ni datos de otros usuarios.

Para restaurar, usa **Cuenta -> Importar todos mis datos**, selecciona
`academic_planning_backup.json` y marca la confirmación. La app valida la
estructura antes de habilitar la importación, muestra una advertencia clara
porque se sobrescriben los datos de esa cuenta, crea un respaldo automático de
la cuenta actual y luego importa el contenido solo en el usuario conectado.

Esto es útil en Streamlit Cloud porque el almacenamiento local de la app puede
reiniciarse al redeployar o cambiar de entorno. Descargar este archivo permite
guardar una copia personal y restaurarla en la misma cuenta sin afectar a otras
personas.

## Tema y modo oscuro

El selector de tema está disponible antes de iniciar sesión y también en
**Apariencia** / **Cuenta** después de entrar. El modo oscuro conserva la paleta
morada de Academic Planning Crew y ajusta tarjetas, sidebar, botones, entradas,
selectbox, multiselect, calendario/date picker y menú superior de Streamlit para
evitar fondos blancos o textos sin contraste.

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

## Datos, usuarios y respaldos

El registro de cuentas se guarda localmente en:

```text
data/auth/users.json
```

Cada cuenta recibe un `user_id` aleatorio. El correo nunca se usa como nombre de
archivo o carpeta. Los datos de cada usuario se guardan en:

```text
data/users/<user_id>/academic_data.json
```

Sus respaldos automáticos se guardan en:

```text
data/users/<user_id>/backups/
```

La memoria contiene perfil, cursos, horario, actividades, pendientes, eventos,
hábitos, metas, chat, registros y configuración. Se crean respaldos antes de
reinicios, reemplazos de horario y limpiezas selectivas.

El respaldo completo descargable desde **Cuenta** es la forma recomendada de
copiar esa memoria fuera del servidor, especialmente en despliegues de
Streamlit Cloud.

El archivo anterior `data/academic_planning_store.json` no se elimina ni se
carga automáticamente en ninguna cuenta. Se conserva como información heredada
o demo y puede migrarse manualmente si se desea asignarlo a una persona.

La pestaña **Memoria** permite descargar una copia JSON y borrar secciones
específicas sin eliminar necesariamente el resto.

`sample_data.json` contiene datos ficticios y no se carga automáticamente.

### Limpieza local manual de usuarios

Para reiniciar un entorno local sin cuentas, se puede hacer una limpieza manual
moviendo estos datos a un respaldo:

```text
data/auth/users.json
data/users/
data/deleted_accounts/
```

Antes de limpiar, crea una carpeta como:

```text
data/backups/pre_clean_users_<timestamp>/
```

La limpieza debe hacerse manualmente en el entorno local. No hay código de la
aplicación que borre cuentas automáticamente al iniciar ni en producción.
`data/` permanece ignorado por Git.

## Pruebas

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest --basetemp .pytest-tmp
```

Las pruebas cubren registro, login, logout, aislamiento y persistencia por
usuario, además de planificación, hábitos, progreso, memoria, respaldos,
preferencias y validaciones de la experiencia.

## Estructura

```text
Academic-Planning-Crew/
├── app.py
├── ui/
│   ├── auth.py
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
│   ├── auth.py
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

La aplicación separa los datos por `user_id`: una sesión solo carga y modifica
su propio `academic_data.json`. Esto incluye perfil, horario, tareas, eventos,
hábitos, progreso, preferencias, memoria y estadísticas derivadas.

No publiques:

- `.env`
- `.streamlit/secrets.toml`
- el contenido de `data/`
- datos personales o respaldos

## Deployment

La aplicación desplegada puede consultarse en la [demo de Streamlit Cloud](https://vqm65skzewzqz54alymg3c.streamlit.app/).

### Preparación común

1. Publica el repositorio sin `.env`, `.streamlit/secrets.toml`, `data/`,
   respaldos, cachés ni logs.
2. Usa `requirements.txt` para producción. `requirements-dev.txt` agrega
   únicamente las herramientas de prueba.
3. Configura `OPENAI_API_KEY`, `OPENAI_MODEL` y `OPENAI_VISION_MODEL` como
   secretos o variables de entorno solo si utilizarás OpenAI/CrewAI.
4. Comprueba antes del despliegue:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

La aplicación usa `data/` de forma predeterminada para el registro de cuentas,
los archivos por usuario y los respaldos. Puedes cambiar el directorio sin
modificar código:

```bash
ACADEMIC_PLANNING_DATA_DIR=/ruta/persistente
```

El directorio debe existir o poder crearse y permitir escritura.

### Streamlit Community Cloud

1. Sube el proyecto a GitHub.
2. En Streamlit Community Cloud, crea una aplicación y selecciona `app.py`
   como archivo principal.
3. Selecciona una versión de Python compatible; se recomienda Python 3.13.
4. Agrega los valores opcionales de OpenAI en **Advanced settings → Secrets**:

   ```toml
   OPENAI_API_KEY = "..."
   OPENAI_MODEL = "gpt-4.1-mini"
   OPENAI_VISION_MODEL = "gpt-4o-mini"
   ```

5. Despliega y revisa los logs de instalación.

Community Cloud ejecuta desde la raíz del repositorio y detecta
`requirements.txt` y `.streamlit/config.toml`. Su sistema de archivos no debe
considerarse una base de datos durable: el JSON puede perderse tras reinicios o
redespliegues, incluyendo cuentas y hashes de contraseña. El aislamiento sí
funciona mientras la instancia conserva esos archivos, pero esta opción sigue
siendo adecuada únicamente para demostraciones o uso sin datos críticos.

### Render

El repositorio incluye `render.yaml`.

1. Crea un **Blueprint** o un **Web Service** desde el repositorio.
2. Si lo configuras manualmente, usa:

   - Build command: `pip install -r requirements.txt`
   - Start command:
     `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`
   - Health check: `/_stcore/health`

3. Agrega las variables opcionales de OpenAI como secretos.
4. Para conservar JSON entre reinicios, usa un disco persistente de pago
   montado, por ejemplo, en `/var/data`, y define:

   ```text
   ACADEMIC_PLANNING_DATA_DIR=/var/data
   ```

Sin disco persistente, el sistema de archivos de Render es efímero.

### Railway

El repositorio incluye `railway.toml` con el comando de inicio, health check y
política de reinicio.

1. Crea un proyecto y conecta el repositorio de GitHub.
2. Railway detectará Python y ejecutará la instalación de `requirements.txt`.
3. Genera un dominio público desde **Networking**.
4. Agrega las variables opcionales de OpenAI.
5. Para persistencia, adjunta un volumen, móntalo por ejemplo en `/data` y
   configura:

   ```text
   ACADEMIC_PLANNING_DATA_DIR=/data
   ```

El servidor escucha en `0.0.0.0` y en el puerto proporcionado por `$PORT`.

### Persistencia y uso multiusuario

El JSON se conserva por compatibilidad con la arquitectura actual. Cada usuario
tiene su propio archivo, pero todavía existen estas limitaciones:

- dos escrituras simultáneas de la misma cuenta pueden sobrescribir cambios;
- el registro local no ofrece recuperación de contraseña, verificación de
  correo, MFA, bloqueo por intentos ni administración de roles;
- un archivo local no permite escalar horizontalmente de forma segura;
- sin volumen o disco persistente, las cuentas y los datos pueden desaparecer.

Para uso institucional, muchos usuarios, múltiples réplicas o concurrencia real,
migra a PostgreSQL y conserva `user_id` como clave de separación en todas las
tablas.

### Mejoras futuras

- **Identidad institucional:** OpenID Connect/OAuth o SSO, verificación de
  correo, recuperación de cuenta, MFA, roles y sesiones con expiración.
- **SQLite:** repositorios para perfil, cursos, eventos, tareas y hábitos;
  migración controlada desde JSON; transacciones, índices y respaldos. Es
  apropiado para una sola instancia con volumen persistente.
- **PostgreSQL:** esquema multiusuario, migraciones, pool de conexiones,
  restricciones, índices, backups y variable `DATABASE_URL`.
- **Despliegue institucional:** SSO institucional, roles, protección de datos,
  auditoría, monitoreo, copias de seguridad, límites de uso de OpenAI,
  ambientes separados y pruebas de carga.

## Limitaciones actuales

- Persistencia en archivos JSON separados por usuario.
- Registro y login locales, sin recuperación de contraseña ni SSO.
- Riesgo de colisiones si la misma cuenta escribe desde dos sesiones a la vez.
- Streamlit Community Cloud no garantiza persistencia del sistema de archivos.
- Sin sincronización externa ni notificaciones.
- La lectura de imágenes y el flujo generativo requieren una API key válida.
- Parte de la interfaz continúa centralizada en `ui/shared.py`.

