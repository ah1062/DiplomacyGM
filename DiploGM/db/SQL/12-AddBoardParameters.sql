BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS board_parameters (
    board_id INTEGER NOT NULL,
    parameter_key TEXT NOT NULL,
    parameter_value TEXT NOT NULL,
    PRIMARY KEY (board_id, parameter_key)
)

COMMIT;