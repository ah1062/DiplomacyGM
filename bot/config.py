from discord import TextChannel

from diplomacy.persistence.board import Board

IMPDIP_HUB_SERVER = 1201167737163104376
IMPDIP_HUB_STATUS_CHANNEL = 1284336328657600572
BOT_DEV_SERVER = 1262215477237645314

ERROR_COLOUR = "#FF0000"
PARTIAL_ERROR_COLOUR = "#FF7700"


class ServerConfig:
    def __init__(self) -> None:
        # Discord roles which are allowed full access to bot commands
        self.gm_categories: set[str] = {"gm channels"}
        self.gm_channels: set[str] = {"admin-chat"}

        self.gm_roles: set[str] = {
            "admin",
            "gm",
            "heavenly angel",
            "emergency gm",
            "bot manager",
        }

        self.player_roles: set[str] = {"player"}

        # Discord categories in which player channels must be
        # (so that you can't create a fake player channel with the right name)
        self.player_categories: set[str] = {"orders"}

    def is_gm_role(self, role: str) -> bool:
        return _is_member(role, self.gm_roles)

    def is_gm_channel(self, channel: str) -> bool:
        return _is_member(channel, self.gm_channels)

    def is_gm_category(self, category: str) -> bool:
        return _is_member(category, self.gm_categories)

    def is_player_role(self, role: str) -> bool:
        return _is_member(role, self.player_roles)

    def is_player_category(self, category: str) -> bool:
        return _is_member(category, self.player_categories)

    def is_player_channel(self, player_role: str, channel: TextChannel) -> bool:
        player_channel = player_role.lower() + player_channel_suffix
        return player_channel == channel and self.is_player_category(
            channel.category.name
        )


# Capitalization is ignored in all definitions.
# Please only insert lowercase names.
def _is_member(string: str, group: set) -> bool:
    return string.lower() in group


# Channel suffix for player orders channels.
# E.g. if the player is "france" and the suffix is "-orders", the channel is "france-orders"
player_channel_suffix: str = "-orders"

# Temporary bumbleship holds until the server restarts or until you fish too much
temporary_bumbles: set[str] = set()


def is_bumble(name: str) -> bool:
    return name == "_bumble" or name in temporary_bumbles
