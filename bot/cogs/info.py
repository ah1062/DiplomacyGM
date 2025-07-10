from black.trans import defaultdict
import logging

from discord.ext import commands

from bot.diplo_bot import DiploBot
import bot.perms as perms
from bot.perms import assert_gm_only, require_player_by_context
from bot.utils import get_role_by_player, log_command, send_message_and_file

from diplomacy.persistence.player import Player

logger = logging.getLogger(__name__)


class InfoCog(commands.Cog):
    def __init__(self, bot: DiploBot):
        self.bot = bot
        self.manager = bot.manager

    @commands.command(brief="outputs information about the current game", aliases=["i"])
    async def info(self, ctx: commands.Context) -> None:
        try:
            board = self.manager.get_board(ctx.guild.id)
        except RuntimeError:
            log_command(logger, ctx, message="No game this this server.")
            await send_message_and_file(
                channel=ctx.channel, title="There is no game this this server."
            )
            return

        log_command(
            logger,
            ctx,
            message=f"Displayed info - {board.get_year_str()}|"
            f"{str(board.phase)}|{str(board.datafile)}|"
            f"{'Open' if board.orders_enabled else 'Locked'}",
        )

        await send_message_and_file(
            channel=ctx.channel,
            message=(
                f"Year: {board.get_year_str()}\n"
                f"Phase: {str(board.phase)}\n"
                f"Orders are {'Open' if board.orders_enabled else 'Locked'}\n"
                f"Game Type: {str(board.datafile)}\n"
                f"Chaos: {':white_check_mark:' if board.is_chaos() else ':x:'}\n"
                f"Fog of War: {':white_check_mark:' if board.fow else ':x:'}"
            ),
        )

    @commands.command(
        brief="Outputs the scoreboard.",
        description="""Outputs the scoreboard.
        In Chaos, is shortened and sorted by points, unless "standard" is an argument""",
        aliases=["leaderboard"],
    )
    async def scoreboard(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)

        if board.fow:
            perms.assert_gm_only(ctx, "get scoreboard")

        the_player = perms.get_player_by_context(ctx, self.manager)

        response = ""
        if board.is_chaos() and "standard" not in ctx.message.content:
            scoreboard_rows = []

            latest_index = -1
            latest_points = float("inf")

            for i, player in enumerate(board.get_players_by_points()):
                points = player.points

                if points < latest_points:
                    latest_index = i
                    latest_points = points

                if i <= 25 or player == the_player:
                    scoreboard_rows.append((latest_index + 1, player))
                elif the_player is None:
                    break
                elif the_player == player:
                    scoreboard_rows.append((latest_index + 1, player))
                    break

            index_length = len(str(scoreboard_rows[-1][0]))
            points_length = len(str(scoreboard_rows[0][1]))

            for index, player in scoreboard_rows:
                response += (
                    f"\n\\#{index: >{index_length}} | {player.points: <{points_length}} | **{player.name}**: "
                    f"{len(player.centers)} ({'+' if len(player.centers) - len(player.units) >= 0 else ''}"
                    f"{len(player.centers) - len(player.units)})"
                )
        else:
            response = ""
            for player in board.get_players_by_score():
                if (player_role := get_role_by_player(player, guild.roles)) is not None:
                    player_name = player_role.mention
                else:
                    player_name = player.name

                response += (
                    f"\n**{player_name}**: "
                    f"{len(player.centers)} ({'+' if len(player.centers) - len(player.units) >= 0 else ''}"
                    f"{len(player.centers) - len(player.units)}) [{round(player.score() * 100, 1)}%]"
                )

        log_command(logger, ctx, message="Generated scoreboard")
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{board.phase.name}" + " " + f"{board.get_year_str()}",
            message=response,
        )

    @commands.command(
        brief="outputs information about a specific player",
        aliases=["player"],
    )
    async def player_info(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(ctx.guild.id)

        if not board.orders_enabled:
            assert_gm_only(
                ctx,
                "You cannot use .province_info in a non-GM channel while orders are locked.",
                non_gm_alt="Orders locked! If you think this is an error, contact a GM.",
            )
            return

        player_name = ctx.message.content.removeprefix(
            ctx.prefix + ctx.invoked_with
        ).strip()
        if not player_name:
            log_command(logger, ctx, message=f"No province given")
            await send_message_and_file(
                channel=ctx.channel,
                title="No province given",
                message="Usage: .province_info <player>",
            )
            return

        # HACK: chaos has same name of players as provinces so we exploit that
        province, _ = board.get_province_and_coast(player_name)
        player: Player = board.get_player(province.name.lower())
        if player is None:
            log_command(logger, ctx, message=f"Player `{player}` not found")
            await send_message_and_file(
                channel=ctx.channel, title=f"Could not find player {player_name}"
            )
            return

        # FOW permissions
        if not board.is_chaos():
            await send_message_and_file(
                channel=ctx.channel, title=f"This command only works for chaos"
            )
            return

        # f"Initial/Current/Victory SC Count [Score]: {player.iscc}/{len(player.centers)}/{player.vscc} [{player.score()}%]\n" + \

        # fmt: off
        bullet = "\n- "
        out = f"Color: #{player.render_color}\n" + \
            f"Points: {player.points}\n" + \
            f"Vassals: {', '.join(map(str, player.vassals))}\n" + \
            f"Liege: {player.liege if player.liege else 'None'}\n" + \
            f"Units: {(bullet + bullet.join([unit.location().name for unit in player.units])) if len(player.units) > 0 else 'None'}\n" + \
            f"Centers ({len(player.centers)}): {(bullet + bullet.join([center.name for center in player.centers])) if len(player.centers) > 0 else 'None'}\n"
        # fmt: on
        log_command(logger, ctx, message=f"Got info for player {player}")

        # FIXME title should probably include what coast it is.
        await send_message_and_file(channel=ctx.channel, title=player.name, message=out)

    @commands.command(
        brief="outputs information about a specific province",
        aliases=["province"],
    )
    async def province_info(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)

        if not board.orders_enabled:
            assert_gm_only(
                ctx,
                "You cannot use .province_info in a non-GM channel while orders are locked.",
                non_gm_alt="Orders locked! If you think this is an error, contact a GM.",
            )
            return

        province_name = ctx.message.content.removeprefix(
            ctx.prefix + ctx.invoked_with
        ).strip()
        if not province_name:
            log_command(logger, ctx, message=f"No province given")
            await send_message_and_file(
                channel=ctx.channel,
                title="No province given",
                message="Usage: .province_info <province>",
            )
            return
        province, coast = board.get_province_and_coast(province_name)
        if province is None:
            log_command(logger, ctx, message=f"Province `{province_name}` not found")
            await send_message_and_file(
                channel=ctx.channel, title=f"Could not find province {province_name}"
            )
            return

        # FOW permissions
        if board.fow:
            player = require_player_by_context(ctx, self.manager, "get province info")
            if player and province not in board.get_visible_provinces(player):
                log_command(
                    logger,
                    ctx,
                    message=f"Province `{province_name}` hidden by fow to player",
                )
                await send_message_and_file(
                    channel=ctx.channel,
                    title=f"Province {province.name} is not visible to you",
                )
                return

        # fmt: off
        if not coast:
            out = f"Type: {province.type.name}\n" + \
                f"Coasts: {len(province.coasts)}\n" + \
                f"Owner: {province.owner.name if province.owner else 'None'}\n" + \
                f"Unit: {(province.unit.player.name + ' ' + province.unit.unit_type.name) if province.unit else 'None'}\n" + \
                f"Center: {province.has_supply_center}\n" + \
                f"Core: {province.core.name if province.core else 'None'}\n" + \
                f"Half-Core: {province.half_core.name if province.half_core else 'None'}\n" + \
                f"Adjacent Provinces:\n- " + "\n- ".join(sorted([adjacent.name for adjacent in province.adjacent | province.impassible_adjacent])) + "\n"
        else:
            coast_unit = None
            if province.unit and province.unit.coast == coast:
                coast_unit = province.unit

            out = "Type: COAST\n" + \
                f"Coast Unit: {(coast_unit.player.name + ' ' + coast_unit.unit_type.name) if coast_unit else 'None'}\n" + \
                f"Province Unit: {(province.unit.player.name + ' ' + province.unit.unit_type.name) if province.unit else 'None'}\n" + \
                "Adjacent Provinces:\n" + \
                "- " + \
                "\n- ".join(sorted([adjacent.name for adjacent in coast.get_adjacent_locations()])) + "\n"
        # fmt: on
        log_command(logger, ctx, message=f"Got info for {province_name}")

        # FIXME title should probably include what coast it is.
        await send_message_and_file(
            channel=ctx.channel, title=province.name, message=out
        )

    @commands.command(brief="outputs all provinces per owner")
    async def all_province_data(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)

        if not board.orders_enabled:
            assert_gm_only(ctx, "call .all_province_data while orders are locked")

        province_by_owner = defaultdict(list)
        for province in board.provinces:
            owner = province.owner
            if not owner:
                owner = None
            province_by_owner[owner].append(province.name)

        message = ""
        for owner, provinces in province_by_owner.items():
            if owner is None:
                player_name = "None"
            elif (player_role := get_role_by_player(owner, guild.roles)) is not None:
                player_name = player_role.mention
            else:
                player_name = owner

            message += f"{player_name}: "
            for province in provinces:
                message += f"{province}, "
            message += "\n\n"

        log_command(
            logger,
            ctx,
            message=f"Found {sum(map(len, province_by_owner.values()))} provinces",
        )
        await send_message_and_file(channel=ctx.channel, message=message)


async def setup(bot: DiploBot):
    await bot.add_cog(InfoCog(bot))
