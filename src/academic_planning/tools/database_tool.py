import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


def read_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def create_json_backup(backup_dir, data, reason="manual", now=None):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    clean_reason = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(reason or "manual"),
    ).strip("_")[:40] or "manual"
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"academic_planning_{stamp}_{clean_reason}.json"
    write_json(backup_path, data)
    return backup_path
