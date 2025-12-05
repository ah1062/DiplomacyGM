import sqlite3
from typing import Type, TypeVar

from DiploGM.models.board import Board
from DiploGM.repositories.base import Repository, RepositoryFactory
from DiploGM.repositories.sqlite.board import SQLiteBoardRepository

T = TypeVar("T")

class SQLiteRepositoryFactory(RepositoryFactory):
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.conn.commit()

    def create(self, model_type: Type[T]) -> Repository[T]:
        if model_type == Board:
            return SQLiteBoardRepository(self.conn)

        raise NotImplementedError()
