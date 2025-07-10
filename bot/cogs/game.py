import logging
import re

import discord
from discord.ext import commands

from bot.command import color_options
from bot.config import ERROR_COLOUR, is_player_category, is_player_role
from bot.diplo_bot import DiploBot
from bot.parse_edit_state import parse_edit_state
from bot.perms import gm_only
from bot.utils import (
    get_orders,
    get_orders_log,
    get_player_by_channel,
    is_gm,
    log_command,
    send_message_and_file,
)

from diplomacy.persistence import phase
from diplomacy.persistence.db.database import get_connection
from diplomacy.persistence.player import Player
from diplomacy.persistence.order import Build, Disband

logger = logging.getLogger(__name__)


class GameCog(commands.Cog):
    def __init__(self, bot: DiploBot) -> None:
        self.bot = bot
        self.manager = bot.manager

    @commands.command(
        brief="Create a game of Imp Dip and output the map.",
        description="Create a game of Imp Dip and output the map. (there are no other variant options at this time)",
    )
    @gm_only("create a game")
    async def create_game(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        gametype = ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)
        if gametype == "":
            gametype = "impdip.json"
        else:
            gametype = gametype.removeprefix(" ") + ".json"

        message = self.manager.create_game(guild.id, gametype)
        log_command(logger, ctx, message=message)
        await send_message_and_file(channel=ctx.channel, message=message)

    @commands.command(brief="permanently deletes a game, cannot be undone")
    @gm_only("delete the game")
    async def delete_game(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        self.manager.total_delete(guild.id)
        log_command(logger, ctx, message=f"Deleted game")
        await send_message_and_file(channel=ctx.channel, title="Deleted game")

    @commands.command(
        brief="archives a category of the server",
        description="""Used after a game is done. Will make all channels in category viewable by all server members, but no messages allowed.
        * .archive [link to any channel in category]""",
    )
    @gm_only("archive")
    async def archive(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        categories = {}
        for channel in ctx.message.channel_mentions:
            if channel.category is None:
                continue

            categories[channel.category] = True

        if not categories:
            await send_message_and_file(
                channel=ctx.channel,
                message="This channel is not part of a category.",
                embed_colour=ERROR_COLOUR,
            )
            return

        for category in categories.keys():
            if category is None:
                continue

            for channel in category.channels:
                overwrites = channel.overwrites

                # Remove all permissions except for everyone
                overwrites.clear()
                overwrites[guild.default_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=False
                )

                # Apply the updated overwrites
                await channel.edit(overwrites=overwrites)

        message = f"The following catagories have been archived: {' '.join([catagory.name for catagory in categories])}"
        log_command(logger, ctx, message=f"Archived {len(categories)} Channels")
        await send_message_and_file(channel=ctx.channel, message=message)

    @commands.command(
        brief="blitz",
        description="Creates all possible channels between two players for blitz in available comms channels.",
    )
    @gm_only("create blitz comms channels")
    async def blitz(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)
        cs = []
        pla = sorted(board.players, key=lambda p: p.name)
        for p1 in pla:
            for p2 in pla:
                if p1.name < p2.name:
                    c = f"{p1.name}-{p2.name}"
                    cs.append((c, p1, p2))

        cos: list[discord.CategoryChannel] = []

        for category in guild.categories:
            if category.name.lower().startswith("comms"):
                cos.append(category)

        available = 0
        for cat in cos:
            available += 50 - len(cat.channels)

        # if available < len(cs):
        #     await send_message_and_file(channel=ctx.channel, message="Not enough available comms")
        #     return

        name_to_player: dict[str, Player] = dict()
        player_to_role: dict[Player | None, discord.Role] = dict()
        for player in board.players:
            name_to_player[player.name.lower()] = player

        spectator_role = None

        for role in guild.roles:
            if role.name.lower() == "spectator":
                spectator_role = role

            player = name_to_player.get(role.name.lower())
            if player:
                player_to_role[player] = role

        if spectator_role is None:
            await send_message_and_file(
                channel=ctx.channel, message=f"Missing spectator role"
            )
            return

        for player in board.players:
            if not player_to_role.get(player):
                await send_message_and_file(
                    channel=ctx.channel,
                    message=f"Missing player role for {player.name}",
                )
                return

        current_cat = cos.pop(0)
        available = 50 - len(current_cat.channels)
        while len(cs) > 0:
            while available == 0:
                current_cat = cos.pop(0)
                available = 50 - len(current_cat.channels)

            assert available > 0

            name, p1, p2 = cs.pop(0)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                spectator_role: discord.PermissionOverwrite(view_channel=True),
                player_to_role[p1]: discord.PermissionOverwrite(view_channel=True),
                player_to_role[p2]: discord.PermissionOverwrite(view_channel=True),
            }

            await current_cat.create_text_channel(name, overwrites=overwrites)

            available -= 1

    @commands.command(brief="Reloads the current board with what is in the DB")
    @gm_only("reload")
    async def reload(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        message = self.manager.reload(guild.id)
        log_command(logger, ctx, message=message["message"])
        await send_message_and_file(channel=ctx.channel, **message)

    @commands.command(brief="re-enables orders", aliases=["unlock"])
    @gm_only("unlock orders")
    async def enable_orders(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)
        board.orders_enabled = True
        log_command(logger, ctx, message="Unlocked orders")
        await send_message_and_file(
            channel=ctx.channel,
            title="Unlocked orders",
            message=f"{board.phase.name} {board.get_year_str()}",
        )

    @commands.command(
        brief="disables orders until .unlock_orders is run.",
        description="""disables orders until .enable_orders is run.
                 Note: Currently does not persist after the bot is restarted""",
        aliases=["lock"],
    )
    @gm_only("lock orders")
    async def disable_orders(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)
        board.orders_enabled = False
        log_command(logger, ctx, message="Locked orders")
        await send_message_and_file(
            channel=ctx.channel,
            title="Locked orders",
            message=f"{board.phase.name} {board.get_year_str()}",
        )

    @commands.command(brief="Clears all players orders.")
    @gm_only("remove all orders")
    async def remove_all(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)
        for unit in board.units:
            unit.order = None

        database = get_connection()
        database.save_order_for_units(board, board.units)
        log_command(logger, ctx, message="Removed all Orders")
        await send_message_and_file(channel=ctx.channel, title="Removed all Orders")

    @commands.command(
        brief="pings players who don't have the expected number of orders.",
        description="""Pings all players in their orders channl that satisfy the following constraints:
        1. They have too many build orders, or too little or too many disband orders. As of now, waiving builds doesn't lead to a ping.
        2. They are missing move orders or retreat orders.
        You may also specify a timestamp to send a deadline to the players.
        * .ping_players <timestamp>
        """,
    )
    @gm_only("ping players")
    async def ping_players(self, ctx: commands.Context) -> None:
        player_categories: list[discord.CategoryChannel] = []

        timestamp = re.match(
            r"<t:(\d+):[a-zA-Z]>",
            ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with).strip(),
        )
        if timestamp:
            timestamp = f"<t:{timestamp.group(1)}:R>"

        guild = ctx.guild
        if not guild:
            return

        guild_id = guild.id
        board = self.manager.get_board(guild_id)

        for category in guild.categories:
            # TODO hacky
            if is_player_category(category.name) or (
                board.is_chaos() and "Order" in category.name
            ):
                player_categories.append(category)

        if len(player_categories) == 0:
            log_command(logger, ctx, message=f"No player category found")
            await send_message_and_file(
                channel=ctx.channel,
                message="No player category found",
                embed_colour=ERROR_COLOUR,
            )
            return

        # find player roles
        if not board.is_chaos():
            name_to_player: dict[str, Player] = dict()
            player_to_role: dict[Player | None, discord.Role] = dict()
            for player in board.players:
                name_to_player[player.name.lower()] = player

            player_roles: set[discord.Role] = set()

            for role in guild.roles:
                if is_player_role(role.name):
                    player_roles.add(role)

                player = name_to_player.get(role.name.lower())
                if player:
                    player_to_role[player] = role

            if len(player_roles) == 0:
                log_command(logger, ctx, message=f"No player role found")
                await send_message_and_file(
                    channel=ctx.channel,
                    message="No player role found",
                    embed_colour=ERROR_COLOUR,
                )
                return

        response = None
        pinged_players = 0
        failed_players = []

        for player_category in player_categories:
            for channel in player_category.channels:
                player = get_player_by_channel(
                    channel, self.manager, guild.id, ignore_catagory=board.is_chaos()
                )

                if not player:
                    await send_message_and_file(
                        channel=ctx.channel, title=f"Couldn't find player for {channel}"
                    )
                    continue

                if not board.is_chaos():
                    role = player_to_role.get(player)
                    if not role:
                        log_command(
                            logger,
                            ctx,
                            message=f"Missing player role for player {player.name} in guild {guild_id}",
                            level=logging.WARN,
                        )
                        continue

                    # Find users which have a player role to not ping spectators
                    users = set(
                        filter(
                            lambda m: len(set(m.roles) & player_roles) > 0, role.members
                        )
                    )
                else:
                    users = set()
                    # Find users with access to this channel
                    for overwritter, permission in channel.overwrites.items():
                        if isinstance(overwritter, discord.Member):
                            if permission.view_channel:
                                users.add(overwritter)
                            pass

                if len(users) == 0:
                    failed_players.append(player)
                    continue

                if phase.is_builds(board.phase):
                    count = len(player.centers) - len(player.units)

                    current = 0
                    has_disbands = False
                    has_builds = False
                    for order in player.build_orders:
                        if isinstance(order, Disband):
                            current -= 1
                            has_disbands = True
                        elif isinstance(order, Build):
                            current += 1
                            has_builds = True

                    difference = abs(current - count)
                    if difference != 1:
                        order_text = "orders"
                    else:
                        order_text = "order"

                    if has_builds and has_disbands:
                        response = f"Hey {''.join([u.mention for u in users])}, you have both build and disband orders. Please get this looked at."
                    elif count >= 0:
                        available_centers = [
                            center
                            for center in player.centers
                            if center.unit is None
                            and (
                                center.core == player
                                or "build anywhere" in board.data.get("adju flags", [])
                            )
                        ]
                        available = min(len(available_centers), count)

                        difference = abs(current - available)
                        if current > available:
                            response = f"Hey {''.join([u.mention for u in users])}, you have {difference} more build {order_text} than possible. Please get this looked at."
                        elif current < available:
                            response = f"Hey {''.join([u.mention for u in users])}, you have {difference} less build {order_text} than necessary. Make sure that you want to waive."
                    elif count < 0:
                        if current < count:
                            response = f"Hey {''.join([u.mention for u in users])}, you have {difference} more disband {order_text} than necessary. Please get this looked at."
                        elif current > count:
                            response = f"Hey {''.join([u.mention for u in users])}, you have {difference} less disband {order_text} than required. Please get this looked at."
                else:
                    if phase.is_retreats(board.phase):
                        in_moves = lambda u: u == u.province.dislodged_unit
                    else:
                        in_moves = lambda _: True

                    missing = [
                        unit
                        for unit in player.units
                        if unit.order is None and in_moves(unit)
                    ]
                    if len(missing) != 1:
                        unit_text = "units"
                    else:
                        unit_text = "unit"

                    if missing:
                        response = f"Hey **{''.join([u.mention for u in users])}**, you are missing moves for the following {len(missing)} {unit_text}:"
                        for unit in sorted(
                            missing, key=lambda _unit: _unit.province.name
                        ):
                            response += f"\n{unit}"

                if response:
                    pinged_players += 1
                    if timestamp:
                        response += f"\n The orders deadline is {timestamp}."
                    await channel.send(response)
                    response = None

        log_command(logger, ctx, message=f"Pinged {pinged_players} players")
        await send_message_and_file(
            channel=ctx.channel, title=f"Pinged {pinged_players} players"
        )

        if len(failed_players) > 0:
            await send_message_and_file(
                channel=ctx.channel,
                title=f"Failed to find the following players: {','.join([player.name for player in failed_players])}",
            )

    @commands.command(
        brief="Sends all previous orders",
        description="For GM: Sends orders from previous phase to #orders-log",
    )
    @gm_only("publish orders")
    async def publish_orders(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_previous_board(guild.id)
        if not board:
            await send_message_and_file(
                channel=ctx.channel,
                title="Failed to get previous phase",
                embed_colour=ERROR_COLOUR,
            )
            return

        try:
            order_text = get_orders(board, None, ctx, fields=True)
        except RuntimeError as err:
            logger.error(err, exc_info=True)
            log_command(
                logger,
                ctx,
                message=f"Failed for an unknown reason",
                level=logging.ERROR,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Unknown Error: Please contact your local bot dev",
                embed_colour=ERROR_COLOUR,
            )
            return
        orders_log_channel = get_orders_log(guild)
        if not orders_log_channel:
            log_command(
                logger,
                ctx,
                message=f"Could not find orders log channel",
                level=logging.WARN,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Could not find orders log channel",
                embed_colour=ERROR_COLOUR,
            )
            return
        else:
            await send_message_and_file(
                channel=orders_log_channel,
                title=f"{board.phase.name} {board.get_year_str()}",
                fields=order_text,
            )
            log_command(logger, ctx, message=f"Successfully published orders")
            await send_message_and_file(
                channel=ctx.channel,
                title=f"Sent Orders to {orders_log_channel.mention}",
            )

    @commands.command(
        brief="Adjudicates the game and outputs the moves and results maps.",
        description="""
        GMs may append true as an argument to this command to instead get the base svg file.
        * adjudicate {arguments}
        Arguments: 
        * pass true|t|svg|s to return an svg
        * pass standard, dark, blue, or pink for different color modes if present
        """,
    )
    @gm_only("adjudicate")
    async def adjudicate(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)

        arguments = (
            ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)
            .strip()
            .lower()
            .split()
        )
        return_svg = not ({"true", "t", "svg", "s"} & set(arguments))
        color_arguments = list(color_options & set(arguments))
        color_mode = color_arguments[0] if color_arguments else None
        # await send_message_and_file(channel=ctx.channel, **await view_map(ctx, manager))
        # await send_message_and_file(channel=ctx.channel, **await view_orders(ctx, manager))
        self.manager.adjudicate(guild.id)

        file, file_name = self.manager.draw_current_map(guild.id, color_mode)

        log_command(
            logger,
            ctx,
            message=f"Adjudication Sucessful for {board.phase.name} {board.get_year_str()}",
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{board.phase.name} {board.get_year_str()}",
            message="Adjudication has completed successfully",
            file=file,
            file_name=file_name,
            convert_svg=return_svg,
            file_in_embed=False,
        )

    @commands.command(brief="Rolls back to the previous game state.")
    @gm_only("rollback")
    async def rollback(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        message = self.manager.rollback(guild.id)
        log_command(logger, ctx, message=message["message"])
        await send_message_and_file(channel=ctx.channel, **message)

    @commands.command(
        brief="Edits the game state and outputs the results map.",
        description="""Edits the game state and outputs the results map. 
        There must be one and only one command per line.
        Note: you cannot edit immalleable map state (eg. province adjacency).
        The following are the supported sub-commands:
        * set_phase {spring, fall, winter}_{moves, retreats, builds}
        * set_core <province_name> <player_name>
        * set_half_core <province_name> <player_name>
        * set_province_owner <province_name> <player_name>
        * set_player_color <player_name> <hex_code>
        * create_unit {A, F} <player_name> <province_name>
        * create_dislodged_unit {A, F} <player_name> <province_name> <retreat_option1> <retreat_option2>...
        * delete_dislodged_unit <province_name>
        * delete_unit <province_name>
        * move_unit <province_name> <province_name>
        * dislodge_unit <province_name> <retreat_option1> <retreat_option2>...
        * make_units_claim_provinces {True|(False) - whether or not to claim SCs}
        * set_player_points <player_name> <integer>
        * set_player_vassal <liege> <vassal>
        * remove_relationship <player1> <player2>
        """,
    )
    @gm_only("edit")
    async def edit(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        edit_commands = ctx.message.content.removeprefix(
            ctx.prefix + ctx.invoked_with
        ).strip()
        message = parse_edit_state(edit_commands, self.manager.get_board(guild.id))
        log_command(logger, ctx, message=message["title"])
        await send_message_and_file(channel=ctx.channel, **message)

    async def publicize(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        if not is_gm(ctx.message.author):
            raise PermissionError(
                f"You cannot publicize a void because you are not a GM."
            )

        channel = ctx.channel
        board = self.manager.get_board(guild.id)

        if not board.is_chaos():
            await send_message_and_file(
                channel=channel,
                message="This command only works for chaos games.",
                embed_colour=ERROR_COLOUR,
            )

        player = get_player_by_channel(
            channel, self.manager, guild.id, ignore_catagory=True
        )

        # TODO hacky
        users = []
        user_permissions: list[tuple[discord.Member, discord.PermissionOverwrite]] = []
        # Find users with access to this channel
        for overwritter, user_permission in channel.overwrites.items():
            if isinstance(overwritter, discord.Member):
                if user_permission.view_channel:
                    users.append(overwritter)
                    user_permissions.append((overwritter, user_permission))

        # TODO don't hardcode
        staff_role = None
        spectator_role = None
        for role in guild.roles:
            if role.name == "World Chaos Staff":
                staff_role = role
            elif role.name == "Spectators":
                spectator_role = role

        if not staff_role or not spectator_role:
            return

        if not player or len(users) == 0:
            await send_message_and_file(
                channel=ctx.channel,
                message="Can't find the applicable user.",
                embed_colour=ERROR_COLOUR,
            )
            return

        # Create Thread
        thread: discord.Thread = await channel.create_thread(
            name=f"{player.name.capitalize()} Orders",
            reason=f"Creating Orders for {player.name}",
            invitable=False,
        )
        await thread.send(
            f"{''.join([u.mention for u in users])} | {staff_role.mention}"
        )

        # Allow for sending messages in thread
        for user, permission in user_permissions:
            permission.send_messages_in_threads = True
            await channel.set_permissions(target=user, overwrite=permission)

        # Add spectators
        spectator_permissions = discord.PermissionOverwrite(
            view_channel=True, send_messages=False
        )
        await channel.set_permissions(
            target=spectator_role, overwrite=spectator_permissions
        )

        # Update name
        await channel.edit(name=channel.name.replace("orders", "void"))

        await send_message_and_file(
            channel=channel, message="Finished publicizing void."
        )


async def setup(bot: DiploBot):
    await bot.add_cog(GameCog(bot))
