from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from .config import get_settings


@dataclass(frozen=True)
class NoteRecord:
    id: int
    content: str
    created_at: str


@dataclass(frozen=True)
class ActionItemRecord:
    id: int
    note_id: Optional[int]
    text: str
    done: bool
    created_at: str


class Database:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def ensure_data_directory_exists(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.ensure_data_directory_exists()
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS action_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER,
                    text TEXT NOT NULL,
                    done INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (note_id) REFERENCES notes(id)
                );
                """
            )

    def create_note(self, content: str) -> NoteRecord:
        with self.connection() as connection:
            note_id = self._insert_note(connection, content)
            row = self._fetch_note_row(connection, note_id)
            if row is None:  # pragma: no cover - defensive guard
                raise RuntimeError("Inserted note could not be reloaded")
            return self._note_from_row(row)

    def list_notes(self) -> list[NoteRecord]:
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC")
            return [self._note_from_row(row) for row in cursor.fetchall()]

    def get_note(self, note_id: int) -> Optional[NoteRecord]:
        with self.connection() as connection:
            row = self._fetch_note_row(connection, note_id)
            if row is None:
                return None
            return self._note_from_row(row)

    def create_action_items(
        self, items: list[str], note_id: Optional[int] = None
    ) -> list[ActionItemRecord]:
        with self.connection() as connection:
            return self._insert_action_items(connection, items, note_id=note_id)

    def create_note_with_action_items(
        self, content: str, items: list[str]
    ) -> tuple[NoteRecord, list[ActionItemRecord]]:
        with self.connection() as connection:
            note_id = self._insert_note(connection, content)
            note_row = self._fetch_note_row(connection, note_id)
            if note_row is None:  # pragma: no cover - defensive guard
                raise RuntimeError("Inserted note could not be reloaded")
            action_items = self._insert_action_items(connection, items, note_id=note_id)
            return self._note_from_row(note_row), action_items

    def list_action_items(self, note_id: Optional[int] = None) -> list[ActionItemRecord]:
        with self.connection() as connection:
            cursor = connection.cursor()
            if note_id is None:
                cursor.execute(
                    """
                    SELECT id, note_id, text, done, created_at
                    FROM action_items
                    ORDER BY id DESC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id, note_id, text, done, created_at
                    FROM action_items
                    WHERE note_id = ?
                    ORDER BY id DESC
                    """,
                    (note_id,),
                )
            return [self._action_item_from_row(row) for row in cursor.fetchall()]

    def get_action_item(self, action_item_id: int) -> Optional[ActionItemRecord]:
        with self.connection() as connection:
            row = self._fetch_action_item_row(connection, action_item_id)
            if row is None:
                return None
            return self._action_item_from_row(row)

    def set_action_item_done(
        self, action_item_id: int, done: bool
    ) -> Optional[ActionItemRecord]:
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE action_items SET done = ? WHERE id = ?",
                (1 if done else 0, action_item_id),
            )
            if cursor.rowcount == 0:
                return None
            row = self._fetch_action_item_row(connection, action_item_id)
            if row is None:  # pragma: no cover - defensive guard
                return None
            return self._action_item_from_row(row)

    def _fetch_note_row(
        self, connection: sqlite3.Connection, note_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, content, created_at FROM notes WHERE id = ?",
            (note_id,),
        )
        return cursor.fetchone()

    def _insert_note(self, connection: sqlite3.Connection, content: str) -> int:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notes (content) VALUES (?)", (content,))
        return int(cursor.lastrowid)

    def _insert_action_items(
        self,
        connection: sqlite3.Connection,
        items: list[str],
        *,
        note_id: Optional[int],
    ) -> list[ActionItemRecord]:
        cursor = connection.cursor()
        created: list[ActionItemRecord] = []
        for item in items:
            cursor.execute(
                "INSERT INTO action_items (note_id, text) VALUES (?, ?)",
                (note_id, item),
            )
            action_item_id = int(cursor.lastrowid)
            row = self._fetch_action_item_row(connection, action_item_id)
            if row is None:  # pragma: no cover - defensive guard
                raise RuntimeError("Inserted action item could not be reloaded")
            created.append(self._action_item_from_row(row))
        return created

    def _fetch_action_item_row(
        self, connection: sqlite3.Connection, action_item_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, note_id, text, done, created_at
            FROM action_items
            WHERE id = ?
            """,
            (action_item_id,),
        )
        return cursor.fetchone()

    @staticmethod
    def _note_from_row(row: sqlite3.Row) -> NoteRecord:
        return NoteRecord(
            id=int(row["id"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _action_item_from_row(row: sqlite3.Row) -> ActionItemRecord:
        return ActionItemRecord(
            id=int(row["id"]),
            note_id=row["note_id"],
            text=str(row["text"]),
            done=bool(row["done"]),
            created_at=str(row["created_at"]),
        )


def get_default_database() -> Database:
    settings = get_settings()
    return Database(settings.database_path)


def init_db() -> None:
    get_default_database().initialize()


def insert_note(content: str) -> int:
    return get_default_database().create_note(content).id


def list_notes() -> list[NoteRecord]:
    return get_default_database().list_notes()


def get_note(note_id: int) -> Optional[NoteRecord]:
    return get_default_database().get_note(note_id)


def insert_action_items(items: list[str], note_id: Optional[int] = None) -> list[int]:
    created_items = get_default_database().create_action_items(items, note_id=note_id)
    return [item.id for item in created_items]


def list_action_items(note_id: Optional[int] = None) -> list[ActionItemRecord]:
    return get_default_database().list_action_items(note_id=note_id)


def mark_action_item_done(action_item_id: int, done: bool) -> None:
    get_default_database().set_action_item_done(action_item_id, done)
