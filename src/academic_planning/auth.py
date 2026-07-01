"""Local JSON authentication with PBKDF2 password hashing."""

import base64
import hashlib
import hmac
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from academic_planning.tools.database_tool import read_json, write_json


PBKDF2_ITERATIONS = 310_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_registry_lock = threading.RLock()


def normalize_email(email):
    return str(email or "").strip().casefold()


def hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": base64.b64encode(salt_bytes).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password, password_record):
    try:
        iterations = int(password_record["iterations"])
        salt = base64.b64decode(password_record["salt"], validate=True)
        expected = base64.b64decode(password_record["hash"], validate=True)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            iterations,
        )
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate, expected)


class UserRegistry:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        registry = read_json(self.path, {"version": 1, "users": []})
        if not isinstance(registry, dict) or not isinstance(registry.get("users"), list):
            return {"version": 1, "users": []}
        return registry

    def register(self, email, password, display_name=""):
        normalized_email = normalize_email(email)
        clean_name = str(display_name or "").strip()
        if not EMAIL_PATTERN.fullmatch(normalized_email):
            return None, "Ingresa un correo electrónico válido."
        if len(str(password)) < 8:
            return None, "La contraseña debe tener al menos 8 caracteres."

        with _registry_lock:
            registry = self._load()
            if any(
                normalize_email(user.get("email")) == normalized_email
                for user in registry["users"]
            ):
                return None, "Ya existe una cuenta con ese correo."

            user = {
                "user_id": uuid.uuid4().hex,
                "email": normalized_email,
                "display_name": clean_name or normalized_email.split("@", 1)[0],
                "password": hash_password(password),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            registry["users"].append(user)
            write_json(self.path, registry)
        return public_user(user), ""

    def authenticate(self, email, password):
        normalized_email = normalize_email(email)
        with _registry_lock:
            registry = self._load()
        user = next(
            (
                item
                for item in registry["users"]
                if normalize_email(item.get("email")) == normalized_email
            ),
            None,
        )
        if not user or not verify_password(password, user.get("password", {})):
            return None
        return public_user(user)

    def change_password(self, user_id, current_password, new_password):
        clean_user_id = str(user_id or "").strip()
        if len(str(new_password)) < 8:
            return None, "La contraseÃ±a nueva debe tener al menos 8 caracteres."
        with _registry_lock:
            registry = self._load()
            user = next(
                (
                    item
                    for item in registry["users"]
                    if str(item.get("user_id", "")) == clean_user_id
                ),
                None,
            )
            if not user:
                return None, "La cuenta no existe."
            if not verify_password(current_password, user.get("password", {})):
                return None, "La contraseÃ±a actual no es correcta."
            user["password"] = hash_password(new_password)
            user["password_updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            write_json(self.path, registry)
        return public_user(user), ""

    def change_password_confirmed(self, user_id, current_password, new_password, confirmation):
        if new_password != confirmation:
            return None, "La nueva contraseÃ±a y la confirmaciÃ³n no coinciden."
        return self.change_password(user_id, current_password, new_password)

    def delete_account(self, user_id, password):
        clean_user_id = str(user_id or "").strip()
        with _registry_lock:
            registry = self._load()
            user = next(
                (
                    item
                    for item in registry["users"]
                    if str(item.get("user_id", "")) == clean_user_id
                ),
                None,
            )
            if not user:
                return None, "La cuenta no existe."
            if not verify_password(password, user.get("password", {})):
                return None, "La contraseÃ±a actual no es correcta."
            registry["users"] = [
                item
                for item in registry["users"]
                if str(item.get("user_id", "")) != clean_user_id
            ]
            write_json(self.path, registry)
        return public_user(user), ""


def public_user(user):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user.get("display_name") or user["email"],
    }


def login_session(session, user):
    session["auth_user"] = dict(user)


def logout_session(session):
    session.clear()
