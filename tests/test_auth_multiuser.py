import json

from academic_planning.auth import UserRegistry, active_session_user, login_session, logout_session
from ui import shared


def test_registration_hashes_password(tmp_path):
    registry_path = tmp_path / "auth" / "users.json"
    registry = UserRegistry(registry_path)

    user, error = registry.register("Student@example.com", "strong-pass", "Ana")

    assert error == ""
    assert user["email"] == "student@example.com"
    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    password_record = raw["users"][0]["password"]
    assert password_record["algorithm"] == "pbkdf2_sha256"
    assert password_record["hash"] != "strong-pass"
    assert "strong-pass" not in registry_path.read_text(encoding="utf-8")


def test_correct_and_incorrect_login(tmp_path):
    registry = UserRegistry(tmp_path / "users.json")
    registered, _ = registry.register("ana@example.com", "strong-pass", "Ana")

    authenticated = registry.authenticate("ANA@example.com", "strong-pass")

    assert authenticated["user_id"] == registered["user_id"]
    assert registry.authenticate("ana@example.com", "wrong-pass") is None
    assert registry.authenticate("missing@example.com", "strong-pass") is None


def test_change_password_success_updates_hash_and_keeps_user(tmp_path):
    registry_path = tmp_path / "auth" / "users.json"
    registry = UserRegistry(registry_path)
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    before = json.loads(registry_path.read_text(encoding="utf-8"))["users"][0]["password"]["hash"]

    changed, error = registry.change_password_confirmed(
        user["user_id"],
        "strong-pass",
        "new-strong-pass",
        "new-strong-pass",
    )
    after = json.loads(registry_path.read_text(encoding="utf-8"))["users"][0]["password"]["hash"]

    assert error == ""
    assert changed["user_id"] == user["user_id"]
    assert after != before
    assert "new-strong-pass" not in registry_path.read_text(encoding="utf-8")


def test_change_password_rejects_wrong_current_password(tmp_path):
    registry_path = tmp_path / "auth" / "users.json"
    registry = UserRegistry(registry_path)
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    before = registry_path.read_text(encoding="utf-8")

    changed, error = registry.change_password_confirmed(
        user["user_id"],
        "wrong-pass",
        "new-strong-pass",
        "new-strong-pass",
    )

    assert changed is None
    assert "contrase" in error.lower()
    assert registry_path.read_text(encoding="utf-8") == before


def test_change_password_rejects_mismatched_confirmation(tmp_path):
    registry_path = tmp_path / "auth" / "users.json"
    registry = UserRegistry(registry_path)
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    before = registry_path.read_text(encoding="utf-8")

    changed, error = registry.change_password_confirmed(
        user["user_id"],
        "strong-pass",
        "new-strong-pass",
        "different-pass",
    )

    assert changed is None
    assert "coinciden" in error.lower()
    assert registry_path.read_text(encoding="utf-8") == before


def test_login_uses_new_password_and_rejects_old_password(tmp_path):
    registry = UserRegistry(tmp_path / "users.json")
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")

    changed, error = registry.change_password_confirmed(
        user["user_id"],
        "strong-pass",
        "new-strong-pass",
        "new-strong-pass",
    )

    assert error == ""
    assert changed["user_id"] == user["user_id"]
    assert registry.authenticate("ana@example.com", "new-strong-pass")["user_id"] == user["user_id"]
    assert registry.authenticate("ana@example.com", "strong-pass") is None


def test_change_password_does_not_clear_active_session(tmp_path):
    registry = UserRegistry(tmp_path / "users.json")
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    session = {}
    login_session(session, user)

    changed, error = registry.change_password_confirmed(
        user["user_id"],
        "strong-pass",
        "new-strong-pass",
        "new-strong-pass",
    )

    assert error == ""
    assert changed["user_id"] == user["user_id"]
    assert active_session_user(session)["user_id"] == user["user_id"]


def test_logout_only_clears_auth_session_keys():
    session = {"widget": "value", "preferred_display_mode": "Oscuro"}
    login_session(
        session,
        {"user_id": "a" * 32, "email": "a@example.com", "display_name": "A"},
    )

    logout_session(session)

    assert session == {"widget": "value", "preferred_display_mode": "Oscuro"}


def test_login_session_sets_stable_current_user_keys():
    session = {}
    user = {"user_id": "a" * 32, "email": "a@example.com", "display_name": "A"}

    login_session(session, user)

    assert session["auth_authenticated"] is True
    assert session["current_user_id"] == user["user_id"]
    assert session["current_user_email"] == user["email"]
    assert active_session_user(session)["user_id"] == user["user_id"]


def test_active_session_user_restores_auth_user_from_current_keys():
    session = {
        "auth_authenticated": True,
        "current_user_id": "a" * 32,
        "current_user_email": "a@example.com",
        "current_user_name": "A",
        "preferred_display_mode": "Claro",
    }

    user = active_session_user(session)

    assert user == {
        "user_id": "a" * 32,
        "email": "a@example.com",
        "display_name": "A",
    }
    assert session["auth_user"]["user_id"] == "a" * 32


def test_normal_session_operations_do_not_logout_user(monkeypatch):
    fake_session = {}
    monkeypatch.setattr(shared, "st", type("FakeStreamlit", (), {"session_state": fake_session}))
    user = {"user_id": "a" * 32, "email": "a@example.com", "display_name": "A"}
    login_session(fake_session, user)
    store = shared.default_store()

    shared.set_session_display_mode("Oscuro")
    shared.apply_pending_session_theme(store)
    shared.apply_sample_data(store)
    shared.remove_sample_data(store, create_backup_first=False)

    assert active_session_user(fake_session)["user_id"] == user["user_id"]


def test_user_data_is_isolated_and_persists(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    first_id = "a" * 32
    second_id = "b" * 32

    first = shared.default_store()
    first["todo_items"].append({"title": "Tarea privada", "date": "2099-01-01"})
    first["events"].append({"title": "Evento privado", "date": "2099-01-02"})
    first["habits"].append({"title": "Hábito privado", "history": {}})
    assert shared.save_store(first, first_id)

    second = shared.load_store(second_id)
    second["todo_items"].append({"title": "Otra tarea", "date": "2099-02-01"})
    assert shared.save_store(second, second_id)

    reloaded_first = shared.load_store(first_id)
    reloaded_second = shared.load_store(second_id)

    assert [item["title"] for item in reloaded_first["todo_items"]] == [
        "Tarea privada"
    ]
    assert [item["title"] for item in reloaded_first["events"]] == [
        "Evento privado"
    ]
    assert [item["title"] for item in reloaded_first["habits"]] == [
        "Hábito privado"
    ]
    assert [item["title"] for item in reloaded_second["todo_items"]] == [
        "Otra tarea"
    ]
    assert reloaded_second["events"] == []
    assert reloaded_second["habits"] == []
    assert (data_dir / "users" / first_id / "academic_data.json").exists()
    assert (data_dir / "users" / second_id / "academic_data.json").exists()


def test_email_is_never_used_as_data_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    user_id = "c" * 32

    shared.save_store(shared.default_store(), user_id)

    assert not (data_dir / "users" / "student@example.com").exists()
    assert shared.store_path_for_user(user_id).parent.name == user_id


def test_delete_account_with_correct_password_archives_user_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    registry = UserRegistry(data_dir / "auth" / "users.json")
    user, error = registry.register("ana@example.com", "strong-pass", "Ana")
    assert error == ""
    store = shared.default_store()
    store["todo_items"].append({"title": "Privada", "date": "2099-01-01"})
    shared.save_store(store, user["user_id"])

    deleted, error = registry.delete_account(user["user_id"], "strong-pass")
    archived_path = shared.archive_user_data(user["user_id"])

    assert error == ""
    assert deleted["user_id"] == user["user_id"]
    assert registry.authenticate("ana@example.com", "strong-pass") is None
    assert not (data_dir / "users" / user["user_id"]).exists()
    assert archived_path.exists()
    assert (archived_path / "academic_data.json").exists()
    assert shared.load_store(user["user_id"])["todo_items"] == []


def test_delete_account_rejects_wrong_password_without_data_loss(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    registry = UserRegistry(data_dir / "auth" / "users.json")
    user, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    store = shared.default_store()
    store["events"].append({"title": "Evento privado", "date": "2099-01-02"})
    shared.save_store(store, user["user_id"])

    deleted, error = registry.delete_account(user["user_id"], "wrong-pass")

    assert deleted is None
    assert "contraseña" in error.lower() or "contrase" in error.lower()
    assert registry.authenticate("ana@example.com", "strong-pass") is not None
    assert (data_dir / "users" / user["user_id"] / "academic_data.json").exists()
    assert shared.load_store(user["user_id"])["events"][0]["title"] == "Evento privado"


def test_delete_account_does_not_affect_other_users(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(shared, "DATA_DIR", data_dir)
    monkeypatch.setattr(shared, "USERS_DIR", data_dir / "users")
    registry = UserRegistry(data_dir / "auth" / "users.json")
    first, _ = registry.register("ana@example.com", "strong-pass", "Ana")
    second, _ = registry.register("bea@example.com", "strong-pass", "Bea")
    first_store = shared.default_store()
    second_store = shared.default_store()
    first_store["todo_items"].append({"title": "Ana", "date": "2099-01-01"})
    second_store["todo_items"].append({"title": "Bea", "date": "2099-01-01"})
    shared.save_store(first_store, first["user_id"])
    shared.save_store(second_store, second["user_id"])

    deleted, error = registry.delete_account(first["user_id"], "strong-pass")
    shared.archive_user_data(first["user_id"])

    assert error == ""
    assert deleted["user_id"] == first["user_id"]
    assert registry.authenticate("ana@example.com", "strong-pass") is None
    assert registry.authenticate("bea@example.com", "strong-pass") is not None
    assert shared.load_store(first["user_id"])["todo_items"] == []
    assert shared.load_store(second["user_id"])["todo_items"][0]["title"] == "Bea"
