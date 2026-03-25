BEGIN TRANSACTION;
ALTER TABLE builds RENAME TO builds_old;


CREATE TABLE IF NOT EXISTS builds (
    board_id int,
    phase text,
    player text,
    location text,
    order_type text,
    unit_type text,
    PRIMARY KEY (board_id, phase, player, location),
    FOREIGN KEY (board_id, phase) REFERENCES boards (board_id, phase),
    FOREIGN KEY (board_id, player) REFERENCES players (board_id, player_name),
    FOREIGN KEY (board_id, phase, location) REFERENCES provinces (board_id, phase, province_name)
);

INSERT INTO builds (board_id, phase, player, location, order_type, unit_type)
SELECT board_id, phase, player, location, order_type, "A" FROM builds_old WHERE is_army = 1;

INSERT INTO builds (board_id, phase, player, location, order_type, unit_type)
SELECT board_id, phase, player, location, order_type, "F" FROM builds_old WHERE is_army = 0 AND order_type = "Build" AND location NOT LIKE "% _c";

INSERT INTO builds (board_id, phase, player, location, order_type, unit_type)
SELECT board_id, phase, player, location, order_type, "" FROM builds_old WHERE is_army = 0 AND order_type = "Disband";

INSERT INTO builds (board_id, phase, player, location, order_type, unit_type)
SELECT board_id, phase, player, SUBSTR(location, 1, LENGTH(location) - 3), order_type, "F " || SUBSTR(location, -2, 2) FROM builds_old WHERE is_army = 0 AND location LIKE "% _c";

DROP TABLE builds_old;
COMMIT;