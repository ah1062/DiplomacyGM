BEGIN TRANSACTION;
ALTER TABLE builds RENAME TO builds_old;


CREATE TABLE IF NOT EXISTS builds (
    board_id int,
    phase text,
    player text,
    location text,
    order_type text,
    is_army boolean,
    PRIMARY KEY (board_id, phase, player, location),
    FOREIGN KEY (board_id, phase) REFERENCES boards (board_id, phase),
    FOREIGN KEY (board_id, player) REFERENCES players (board_id, player_name),
    FOREIGN KEY (board_id, phase, location) REFERENCES provinces (board_id, phase, province_name)
);

INSERT INTO builds (board_id, phase, player, location, order_type, is_army)
SELECT board_id, phase, player, location, is_build, is_army FROM builds_old;
UPDATE builds SET order_type = 'Build' WHERE order_type = 1;
UPDATE builds SET order_type = 'Disband' WHERE order_type = 0;

DROP TABLE builds_old;
COMMIT;