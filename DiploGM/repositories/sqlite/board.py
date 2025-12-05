import sqlite3
from DiploGM.models.board.repository import BoardRepository

class SQLiteBoardRepository(BoardRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._initialise_schema(self.conn)

    def _initialise_schema(self, conn: sqlite3.Connection):
        SCHEMA = """
            CREATE TABLE IF NOT EXISTS boards (
                board_id int,
                phase text,
                data_file text,
                fish int,
                name text,
                PRIMARY KEY (board_id, phase)
            );

        """
        conn.execute(SCHEMA)
        conn.commit()
