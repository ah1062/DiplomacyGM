import logging
import sys
import numpy as np
import pandas as pd
import re
from scipy.optimize import linear_sum_assignment

FILEDIR = "b2.2"
FILENAME = "Player List _ Beta 2.2 Signup - Form responses 1.csv"
ALLOCATION_OUT_FILENAME = f"{FILEDIR}/allocations.txt"
DNP_OUT_FILENAME = f"{FILEDIR}/donotplaylists.txt"
PUBLICATION_OUT_FILENAME = f"{FILEDIR}/publications.txt"
PLAYERS_OUT_FILENAME = f"{FILEDIR}/players.txt"

# LOGGING
STDOUT_LOGGER = True
logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=ALLOCATION_OUT_FILENAME, filemode="w", format="%(message)s", level=logging.INFO
)

if STDOUT_LOGGER:
    formatter = logging.Formatter("%(asctime)s:%(levelname)s | %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# CONSTANTS
REPUTATION_FILE = "Imperial Diplomacy Reputation - Master Sheet.csv"
df = pd.read_csv(f"{REPUTATION_FILE}", skipinitialspace=True)

# create dict of player name to "Current Reputation" column value (as int)
PLAYER_REP_VALUES = {name.lower(): int(val) for name, val in list(df.iloc[:, :2].itertuples(index=False, name=None)) if not pd.isna(name) and not pd.isna(val)}

DISCORD_USERNAME_TEXT = "Discord Username"
COUNTRY_RANK_PREFIX = "Rank Your Country Choices "
DNP_ROW_TEXT = "Are there any people you refuse to play with? (This will be shared with the Admins and your GM Team.)"
NO_PREFERENCE_TEXT = "Select Here If You Have No Power Preferences"

RANK_TO_WEIGHTS = {"1st": 36, "2nd": 25, "3rd": 16, "4th": 9, "5th": 4}
WEIGHT_TO_RANKS = {v: k for k, v in RANK_TO_WEIGHTS.items()}
CONSIDER_DNP = True

# seeding (for reproduction of allocations)
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

logger.info(f"Results for signups file: {FILENAME}")
logger.info(f"- Random Seed was: {RANDOM_SEED}\n")
logger.info("=== STARTING PROCESSING OF SIGNUPS ===")

# === TODO ===
# TODO: Consideration for Do Not Play Lists
# Probably has to be manually done without standardising list formats

# HACK: The whole thing is a bit of a mess

# TODO: Break out into functions

# TODO: Cleanup behaviour for potential bot integration if required
# Create alternative method for fetching signup responses (Google Forms API Request?)

# Clean CSV Structure
df = pd.read_csv(f"{FILEDIR or '.'}/{FILENAME}", skipinitialspace=True)
df = df.drop(
    "Timestamp", axis=1
)  # .drop("Anything else the Admin should know?", axis=1)
df = df.rename(columns=lambda c: re.sub(COUNTRY_RANK_PREFIX, "", c))

df[DISCORD_USERNAME_TEXT] = df[DISCORD_USERNAME_TEXT].str.lower()

for col in df.columns:
    try:
        df[col] = df[col].str.replace("@", "")
        df[col] = df[col].str.replace("\n", ", ")
        df[col] = df[col].str.strip()
    except Exception:
        continue

logger.info("Parsed Signups CSV")

# Extract Preferences
dnp_lists = {}
player_rankings = {}
no_preference_players = []
for _, row in df.iterrows():
    username = row.get(DISCORD_USERNAME_TEXT)
    if not username:
        continue
    username = username.lower()

    rep_value = PLAYER_REP_VALUES.get(username)
    if not rep_value:
       logger.warning(f"Could not find a reputation value for player '{username}' , assuming 10")
    #    continue
    elif rep_value < 0:
        logger.warning(f"Skipping player '{username}' for having a reputation value of: {rep_value}")
        continue


    rankings = {}

    # do not play list
    dnp = row.get(DNP_ROW_TEXT, default="")
    if dnp and not pd.isna(dnp):
        dnp_lists[username] = dnp.lower()

    # check for scrapper
    if row.get(NO_PREFERENCE_TEXT) == "No Preferences":
        if username in player_rankings:
            del player_rankings[username]

        if username not in no_preference_players:
            no_preference_players.append(username)

        continue

    # map preferences to weights
    for idx, val in enumerate(row):
        if val not in RANK_TO_WEIGHTS:
            continue

        power = df.columns[idx]
        rankings[power] = RANK_TO_WEIGHTS[val]

    # sort for readability
    player_rankings[username] = {
        k: v
        for k, v in sorted(rankings.items(), key=lambda pair: pair[1], reverse=True)
    }

logger.info("Processed preferences from signups")
logger.info(f"No Preference Players: {no_preference_players}")

# check for duplicate preferences in player_rankings
# HACK: Really messy
for user, rankings in player_rankings.items():
    for weight in np.unique(rankings.values()):
        items = list(filter(lambda p: p[1] == weight, rankings.items()))
        if len(items) > 1:
            selection = np.random.choice(items)
            items.remove(selection)

            for exile, _ in items:
                del rankings[exile]
logger.info("Randomly filtered out any duplicate preferences within form submissions")

# complete list of player_names
all_players = list(player_rankings.keys()) + list(no_preference_players)

# Allocate Powers
powers = list(df.columns[1:26])
num_games = (len(player_rankings) + len(no_preference_players)) / len(powers)
num_games = int(round(num_games, 0))

logger.info(f"Decided on {num_games} games to be run for {len(all_players)} players.")

# Initialise cost matrix for each possible game that can be run
score_matrix = np.zeros((len(player_rankings), len(powers) * num_games))
for i, (player, ranking) in enumerate(player_rankings.items()):
    for j, power in enumerate(powers * num_games):
        score_matrix[i, j] = ranking.get(power, 0)

power_to_players = {}
ranked_names = list(player_rankings.keys())
logger.info("Initialised Hungarian Method cost matrix")

# scipy.optimize Hungarian Method implementation
player_idx, power_idx = linear_sum_assignment(-score_matrix)
for i, (player, power) in enumerate(zip(player_idx, power_idx)):
    player_name = list(player_rankings.items())[player][0]
    game_id = power // len(powers)
    power_name = powers[power % len(powers)]

    # assigned power is not one the player originally requested
    if (
        power_name not in player_rankings[player_name]
        and player_name not in no_preference_players
    ):
        logger.warning(
            f"COULD NOT FULFILL ANY PREFERENCES OF PLAYER [{player_name}] | MAKING SCRAP"
        )
        no_preference_players.append(player_name)
        continue

    if power_name not in power_to_players:
        power_to_players[power_name] = []

    power_to_players[power_name].append(player_name)
logger.info("Assigned players their preferred powers!")

# randomly allocate assigned players to each game for rough balance (and avoid alphabetical -> numerical game ordering)
games = {k: {"SCRAP": []} for k in range(num_games)}
for power, player in power_to_players.items():
    assert len(player) <= len(games)

    x = np.random.choice(range(num_games), len(player), replace=False)
    for i, game in enumerate(x):
        games[game][power] = player[i]

logger.info("Randomly distributed assigned players between game(s)")

# fill-in no-preference (scrap) players
empty_spaces = {k: len(powers) - (len(games[k]) - 1) for k in games}
logger.info(empty_spaces)
np.random.shuffle(no_preference_players)
for player in no_preference_players.copy():
    valid_games = [i for i in empty_spaces.keys() if empty_spaces[i] > 0]
    if len(valid_games) == 0:
        break

    chosen = np.random.choice(valid_games)

    games[chosen]["SCRAP"].append(player)
    no_preference_players.remove(player)
    empty_spaces[chosen] -= 1

logger.info("Randomly assigned remaining players to available Scrap positions")
# for game, powers in games.items():
#    for power, player in powers.items():
#        print(f"\t{power}: {player}")


def validate_game_dnp(num, game) -> tuple[bool, list]:
    conflicts = []
    total_players = []
    for power, players in game.items():
        if power == "SCRAP":
            total_players.extend(list(map(lambda p: (p, power), players)))
        else:
            total_players.append((players, power))

    for player, power in total_players:
        dnp = dnp_lists.get(player, np.nan)
        if pd.isna(dnp):
            continue

        for other, other_power in total_players:
            if other == player:
                continue

            if other in dnp:
                conflicts.append(
                    {
                        "game": num,
                        "concerned": (
                            {"username": player, "power": power},
                            {"username": other, "power": other_power},
                        ),
                    }
                )

    return len(conflicts) == 0, conflicts


dnp_check_limit = 25
logger.info(f"=== STARTING DO NOT PLAY VALIDATION ({dnp_check_limit} Attempts) === ")

dnp_check_count = 1
validated = True if not CONSIDER_DNP else False
total_conflicts = []
while (not validated and dnp_check_count <= dnp_check_limit) and CONSIDER_DNP:
    logger.info(f"Do not play validation: Attempt {abs(dnp_check_count)}")

    valid_games = []
    total_conflicts = []
    for i, game in games.items():
        valid, conflicts = validate_game_dnp(i, game)
        valid_games.append(valid)

        conflict_reprs = map(
            lambda c2: f"({c2[0]['username']} and {c2[1]['username']})",
            list(map(lambda c: c["concerned"], conflicts)),
        )
        logger.info(
            f"Game {i}: {valid} | Num of Conflicts: {len(conflicts)} = {', '.join(conflict_reprs)}"
        )
        total_conflicts.extend(conflicts)

    validated = all(valid_games)
    logger.info(f"Result: {validated}")
    if validated:
        break

    logger.info("Attempting to resolve errors within allocations...")
    for conflict in total_conflicts:
        game = conflict["game"]
        orig_game = games[game]

        a = conflict["concerned"][0]
        b = conflict["concerned"][1]

        if b["power"] == "SCRAP":
            tmp = a
            a = b
            b = tmp

        if a["power"] == "SCRAP":
            others = [g for g in games if g != game and len(games[g]["SCRAP"]) > 0]

            swap_game_id = np.random.choice(others)
            swap_game = games[swap_game_id]

            swap_scrapper = np.random.choice(swap_game["SCRAP"])
            swap_game["SCRAP"].remove(swap_scrapper)

            if a["username"] in orig_game["SCRAP"]:
                orig_game["SCRAP"].remove(a["username"])
            orig_game["SCRAP"].append(swap_scrapper)

            continue

        others = [g for g in games if g != game and a["power"] in games[g]]
        if len(others) == 0:
            logger.error(
                f"No other games with an assigned {a['power']} to swap {a['username']} with."
            )

        swap_power = a["power"]
        swap_game_id = np.random.choice(others)
        swap_game = games[swap_game_id]

        tmp = swap_game[swap_power]
        swap_game[swap_power] = orig_game[swap_power]
        orig_game[swap_power] = tmp

        logger.info(
            f"Swapped {orig_game[swap_power]} in {game} with {swap_game[swap_power]} from {swap_game_id}: Power = {swap_power}"
        )

    dnp_check_count += 1

if not validated:
    logger.error(
        "Failed to validate do not playlists after {dnp_check_count} attempts..."
    )
    conc_conflict = "\n" + "\n".join(map(str, total_conflicts))
    logger.error(f"Remaining conflicts: {conc_conflict}")
else:
    logger.info(
        "Successfully validated Do not play requests (where possible, manual checking is advised)"
    )

logger.info("=== BEGINNING RESULTS OUTPUT ===")

for game, powers in games.items():
    logger.info(f"=== GAME {game} PLAYER ALLOCATIONS LIST ===")
    for power, player in sorted(powers.items(), key=lambda p: p[0]):
        if isinstance(player, list):
            for p in sorted(player):
                out = f"{p}"
                out += f" got their random allocation: {power}"
                #out += f" | Do not play =  [{dnp_lists.get(p, '')}]"

                logger.info(out)
            continue

        preference = WEIGHT_TO_RANKS[player_rankings[player][power]]
        out = f"{player}"
        out += f" got their {preference} choice: {power}"
        #out += f" | Do not play = [{dnp_lists.get(player, '')}]"

        logger.info(out)

logger.info("=== Failed to Allocate ===")
for player in no_preference_players:
    logger.info(f"{player} did not get allocated")
logger.info("=== Games missing full attendance ===")
for id, count in empty_spaces.items():
    if count == 0:
        continue

    logger.info(f"Game {id} - Missing {count}")

publish = open(PUBLICATION_OUT_FILENAME, "w")
donotplay = open(DNP_OUT_FILENAME, "w")
playerlist = open(PLAYERS_OUT_FILENAME, "w")

for game, powers in games.items():
    publish.write(f"=== GAME {game} ANNOUNCEMENT LIST ===\n")
    donotplay.write(f"=== GAME {game} DO NOT PLAY LIST ===\n")

    players = []
    for _, player in powers.items():
        if isinstance(player, list):
            players.extend(player)
            continue

        players.append(player)
    np.random.shuffle(players)

    game_dnp_list = set()
    for p in players:
        publish.write(f"{p}\n")
        playerlist.write(f"{p}\n")

        if p in dnp_lists:
            dnp = dnp_lists[p]
            for user in map(str.strip, dnp.split(",")):
                game_dnp_list.add(user.lower())

    dnpout = "\n".join(game_dnp_list)
    donotplay.write(f"{dnpout}\n")

publish.close()
donotplay.close()
playerlist.close()

print(f"Results outputted to: {ALLOCATION_OUT_FILENAME}")
print("Results outputted to: publications.txt")
print("Results outputted to: donotplay.txt")
