"""Storage backend selection."""

import os
import warnings
from pathlib import Path

from academic_planning.storage.json_storage import JSONStorage


def default_data_dir():
    app_dir = Path(__file__).resolve().parents[3]
    configured_data_dir = os.environ.get("ACADEMIC_PLANNING_DATA_DIR", "").strip()
    data_dir = Path(configured_data_dir).expanduser() if configured_data_dir else app_dir / "data"
    if not data_dir.is_absolute():
        data_dir = app_dir / data_dir
    return data_dir


def get_storage(data_dir=None, auth_users_path=None):
    """Return the configured storage backend.

    JSONStorage is the safe default. DATABASE_URL is detected but PostgreSQL is
    intentionally not activated in this phase.
    """

    configured_backend = os.environ.get("STORAGE_BACKEND", "").strip().casefold()
    backend = configured_backend or "json"
    selected_data_dir = Path(data_dir) if data_dir is not None else default_data_dir()

    if backend == "json" and (configured_backend or not os.environ.get("DATABASE_URL")):
        return JSONStorage(selected_data_dir, auth_users_path=auth_users_path)

    if os.environ.get("DATABASE_URL"):
        warnings.warn(
            "DATABASE_URL esta configurado, pero PostgreSQLStorage todavia no "
            "esta implementado. Se usara JSONStorage para no romper la app.",
            RuntimeWarning,
            stacklevel=2,
        )
        return JSONStorage(selected_data_dir, auth_users_path=auth_users_path)

    warnings.warn(
        f"STORAGE_BACKEND={backend!r} no esta soportado en esta fase. "
        "Se usara JSONStorage.",
        RuntimeWarning,
        stacklevel=2,
    )
    return JSONStorage(selected_data_dir, auth_users_path=auth_users_path)
