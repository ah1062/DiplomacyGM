if board.turn.is_builds():
    board.get_province("North Africa").owner = board.get_player("Italy")

for player in board.players:
    player.dp_max = len(player.name)