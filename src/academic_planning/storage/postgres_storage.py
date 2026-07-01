"""Future PostgreSQL storage backend.

Planned tables:
- users: authentication records and public account metadata.
- user_data: JSONB document per user for the first migration step.
- user_backups: timestamped JSONB snapshots per user.
- deleted_accounts: archived account metadata and deletion timestamps.

Later migrations can normalize courses, availability, activities, todo_items,
events, habits, weekly_goals, progress, chat, agent_log and settings into
separate tables keyed by user_id.
"""

from academic_planning.storage.base import StorageBackend


class PostgreSQLStorage(StorageBackend):
    """Placeholder for the future DATABASE_URL-backed implementation."""

    MESSAGE = (
        "PostgreSQLStorage todavia no esta implementado. "
        "Usa JSONStorage en esta fase."
    )

    def __init__(self, database_url=None):
        self.database_url = database_url

    def load_user_data(self, user_id):
        raise NotImplementedError(self.MESSAGE)

    def save_user_data(self, user_id, data):
        raise NotImplementedError(self.MESSAGE)

    def backup_user_data(self, user_id, data=None, reason="manual"):
        raise NotImplementedError(self.MESSAGE)

    def export_user_data(self, user_id):
        raise NotImplementedError(self.MESSAGE)

    def import_user_data(self, user_id, data):
        raise NotImplementedError(self.MESSAGE)

    def delete_user_data(self, user_id):
        raise NotImplementedError(self.MESSAGE)

    def load_auth_users(self):
        raise NotImplementedError(self.MESSAGE)

    def save_auth_users(self, users):
        raise NotImplementedError(self.MESSAGE)
