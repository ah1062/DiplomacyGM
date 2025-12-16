from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from typing import Iterable, Optional

from DiploGM.db.database import get_connection
from DiploGM.utils.repository import Repository

@dataclass
class Community:
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    active: bool = True
    deactivated_at: Optional[datetime.datetime] = None

class SQLiteCommunityRepository(Repository):
    def __init__(self) -> None:
        self.conn = get_connection()._connection
        self._initialise_schema()

    def _initialise_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS communities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,

                created_at TEXT NOT NULL,
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                deactivated_at TEXT
            );
        """)
        self.conn.commit()

    def save(self, entity: Community) -> Community:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO communities (id, name, description, active, created_at, deactivated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                active = excluded.active,
                deactivated_at = excluded.deactivated_at
            """,
            (
                entity.id,
                entity.name,
                entity.description,
                int(entity.active),
                entity.created_at,
                entity.deactivated_at,
            ),
        )
        self.conn.commit()
        return entity

    def load(self, id: int) -> Optional[Community]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM communities WHERE id = ?", (id,))
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def delete(self, id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM communities WHERE id = ?", (id,))
        self.conn.commit()

    def soft_delete(self, id: int) -> None:
        self.conn.execute("""
            UPDATE communities
            SET active = 0,
                deactivated_at = ?
            WHERE id = ?
        """, (datetime.datetime.now().isoformat(), id,))

    def clear(self) -> None:
        self.conn.execute("DELETE FROM communities")
        self.conn.commit()

    def all(self) -> Iterable[Community]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM communities")
        rows = cur.fetchall()
        return [self._row_to_model(r) for r in rows]

    def _row_to_model(self, row) -> Community:
        return Community(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            deactivated_at=row["deactivated_at"],
        )

