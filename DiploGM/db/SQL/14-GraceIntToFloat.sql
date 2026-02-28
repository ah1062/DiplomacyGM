BEGIN TRANSACTION;
ALTER TABLE extension_events RENAME TO extension_events_old;


CREATE TABLE IF NOT EXISTS extension_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    server_id INTEGER NOT NULL,
    hours REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL);

INSERT INTO extension_events (user_id, server_id, hours, reason, created_at)
SELECT user_id, server_id, hours, reason, created_at FROM extension_events_old;

DROP TABLE extension_events_old;
COMMIT;