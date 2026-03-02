import logging

import discord
from discord.ext import commands

from DiploGM import config
from DiploGM import perms
from DiploGM.parse_order import parse_order, parse_remove_order
from DiploGM.utils import get_orders, log_command, parse_season, send_message_and_file
from DiploGM.manager import Manager, SEVERENCE_A_ID, SEVERENCE_B_ID
from DiploGM.models.player import Player

logger = logging.getLogger(__name__)
manager = Manager()


class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        brief="Submits orders; there must be one and only one order per line.",
        description="""Submits orders: 
    There must be one and only one order per line.
    A variety of keywords are supported: e.g. '-', '->', 'move', and 'm' are all supported for a move command.
    Supplying the unit type is fine but not required: e.g. 'A Ghent -> Normandy' and 'Ghent -> Normandy' are the same
    If anything in the command errors, we recommend resubmitting the whole order message.
    *During Build phases only*, you have to specify multi-word provinces with underscores; e.g. Somali Basin would be Somali_Basin (we use a different parser during build phases)
    If you would like to use something that is not currently supported please inform your GM and we can add it.""",
        aliases=["o", "orders"],
    )
    @perms.player("order")
    async def order(
        self,
        ctx: commands.Context,
        player: Player | None,
    ) -> None:
        assert ctx.guild is not None
        board = manager.get_board(ctx.guild.id)

        if player and not board.orders_enabled:
            log_command(logger, ctx, "Orders locked - not processing")
            await send_message_and_file(
                channel=ctx.channel,
                title="Orders locked!",
                message="If you think this is an error, contact a GM.",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        message = parse_order(ctx.message.content, player, board)
        if "title" in message:
            log_command(logger, ctx, message=message["title"], level=logging.DEBUG)
        elif "message" in message:
            log_command(
                logger, ctx, message=message["message"][:100], level=logging.DEBUG
            )
        elif "messages" in message and len(message["messages"]) > 0:
            log_command(
                logger, ctx, message=message["messages"][0][:100], level=logging.DEBUG
            )
        await send_message_and_file(channel=ctx.channel, **message)

    @commands.command(
        brief="Removes orders for given units.",
        description="Removes orders for given units (required for removing builds/disbands). "
        "There must be one and only one order per line.",
        aliases=["remove", "rm", "removeorders"],
    )
    @perms.player("remove orders")
    async def remove_order(self, ctx: commands.Context, player: Player | None) -> None:
        assert ctx.guild is not None
        board = manager.get_board(ctx.guild.id)

        if player and not board.orders_enabled:
            log_command(logger, ctx, "Orders locked - not processing")
            await send_message_and_file(
                channel=ctx.channel,
                title="Orders locked!",
                message="If you think this is an error, contact a GM.",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        content = ctx.message.content.removeprefix(f"{ctx.prefix}{ctx.invoked_with}")

        message = parse_remove_order(content, player, board)
        log_command(logger, ctx, message=message["message"])
        await send_message_and_file(channel=ctx.channel, **message)

    @commands.command(
        brief="Outputs your current submitted orders.",
        description="Outputs your current submitted orders. "
        "Use .view_map to view a sample moves map of your orders. "
        "Use the 'missing' or 'submitted' argument to view only units without orders or only submitted orders. "
        "Use the 'blind' argument to view only the number of orders submitted.",
        aliases=["v", "view", "vieworders", "view-orders"],
    )
    @perms.player("view orders")
    async def view_orders(self, ctx: commands.Context, player: Player | None) -> None:
        assert ctx.guild is not None
        arguments = (
            ctx.message.content.removeprefix(f"{ctx.prefix}{ctx.invoked_with}")
            .strip()
            .lower()
            .split()
        )
        subset = "missing" if {"missing", "miss", "m"} & set(arguments) else None
        subset = (
            "submitted"
            if {"submitted", "submit", "sub", "s"} & set(arguments)
            else subset
        )

        try:
            board = manager.get_board(ctx.guild.id)

            blind = "blind" in arguments
            order_text = get_orders(board, player, ctx, subset=subset, blind=blind)

        except RuntimeError as err:
            logger.error(err, exc_info=True)
            log_command(
                logger,
                ctx,
                message="Failed for an unknown reason",
                level=logging.ERROR,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Unknown Error: Please contact your local bot dev",
                embed_colour=config.ERROR_COLOUR,
            )
            return
        log_command(
            logger,
            ctx,
            message=f"Success - generated orders for {board.turn}",
        )
        assert isinstance(order_text, str)
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{board.turn}",
            message=order_text,
        )

    @commands.command(
        brief="Outputs the current map with submitted orders.",
        description="""
        For GMs, all submitted orders are displayed. For a player, only their own orders are displayed.
        GMs may append true as an argument to this to instead get the svg.
        * view_map {arguments}
        Arguments: 
        * pass true|t|svg|s to return an svg
        * pass standard, dark, blue, or pink for different color modes if present
        * pass season and optionally year for older maps
        """,
        aliases=["viewmap", "vm"],
    )
    @perms.player("view map")
    async def view_map(self, ctx: commands.Context, player: Player | None):
        assert ctx.guild is not None
        arguments = (
            ctx.message.content.removeprefix(f"{ctx.prefix}{ctx.invoked_with}")
            .strip()
            .lower()
            .split()
        )
        convert_svg = (player is not None) or not (
            {"true", "t", "svg", "s"} & set(arguments)
        )
        color_arguments = list(config.color_options & set(arguments))
        color_mode = color_arguments[0] if color_arguments else None
        movement_only = "movement" in arguments
        board = manager.get_board(ctx.guild.id)
        turn = parse_season(arguments, board.turn)
        
        if player and not board.orders_enabled:
            log_command(logger, ctx, "Orders locked - not processing")
            await send_message_and_file(
                channel=ctx.channel,
                title="Orders locked!",
                message="If you think this is an error, contact a GM.",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        try:
            if not board.fow:
                file, file_name = manager.draw_map(
                    ctx.guild.id,
                    draw_moves=True,
                    player_restriction=player,
                    color_mode=color_mode,
                    turn=turn,
                    movement_only=movement_only,
                    is_severance=ctx.guild.id in [SEVERENCE_A_ID, SEVERENCE_B_ID],
                )
            else:
                file, file_name = manager.draw_fow_players_moves_map(
                    ctx.guild.id, player, color_mode
                )
        except Exception as err:
            logger.error(err, exc_info=True)
            log_command(
                logger,
                ctx,
                message="Failed to generate map for an unknown reason",
                level=logging.ERROR,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Unknown Error: Please contact your local bot dev",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        message = None
        if {"true", "t"} & set(arguments):
            message = ("`.vm true` and `.vm t` have been deprecated and will soon be disabled.\n"
                       "Please use `.vm svg` instead")

        log_command(
            logger,
            ctx,
            message=f"Generated moves map for {turn}",
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{turn}",
            message=message,
            file=file,
            file_name=file_name,
            convert_svg=convert_svg,
            file_in_embed=False,
        )

    @commands.command(
        brief="Outputs the current map without any orders.",
        description="""
        * view_current {arguments}
        Arguments: 
        * pass true|t|svg|s to return an svg
        * pass standard, dark, blue, or pink for different color modes if present
        """,
        aliases=["viewcurrent", "vc"],
    )
    @perms.player("view current")
    async def view_current(self, ctx: commands.Context, player: Player | None) -> None:
        assert ctx.guild is not None
        arguments = (
            ctx.message.content.removeprefix(f"{ctx.prefix}{ctx.invoked_with}")
            .strip()
            .lower()
            .split()
        )
        convert_svg = not ({"true", "t", "svg", "s"} & set(arguments))
        color_arguments = list(config.color_options & set(arguments))
        color_mode = color_arguments[0] if color_arguments else None
        board = manager.get_board(ctx.guild.id)
        turn = parse_season(arguments, board.turn)
        
        try:
            if not board.fow:
                file, file_name = manager.draw_map(
                    ctx.guild.id,
                    player_restriction=player,
                    color_mode=color_mode,
                    turn=turn,
                    is_severance=ctx.guild.id in [SEVERENCE_A_ID, SEVERENCE_B_ID],
                )
            else:
                file, file_name = manager.draw_fow_players_moves_map(
                    ctx.guild.id, player, color_mode
                )
        except Exception as err:
            logger.error(err, exc_info=True)
            log_command(
                logger,
                ctx,
                message="Failed to generate map for an unknown reason",
                level=logging.ERROR,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Unknown Error: Please contact your local bot dev",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        message = None
        if {"true", "t"} & set(arguments):
            message = ("`.vc true` and `.vc t` have been deprecated and will soon be disabled.\n"
                       "Please use `.vm svg` instead")


        log_command(
            logger,
            ctx,
            message=f"Generated current map for {turn}",
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{turn}",
            message=message,
            file=file,
            file_name=file_name,
            convert_svg=convert_svg,
            file_in_embed=False,
        )

    @commands.command(
        brief="Outputs a interactive svg that you can issue orders in",
        aliases=["g"],
    )
    @perms.player("view gui")
    async def view_gui(self, ctx: commands.Context, player: Player | None) -> None:
        assert ctx.guild is not None
        arguments = (
            ctx.message.content.removeprefix(f"{ctx.prefix}{ctx.invoked_with}")
            .strip()
            .lower()
            .split()
        )
        color_arguments = list(config.color_options & set(arguments))
        color_mode = color_arguments[0] if color_arguments else None
        board = manager.get_board(ctx.guild.id)

        if player and not board.orders_enabled:
            log_command(logger, ctx, "Orders locked - not processing")
            await send_message_and_file(
                channel=ctx.channel,
                title="Orders locked!",
                message="If you think this is an error, contact a GM.",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        try:
            if not board.fow:
                file, file_name = manager.draw_gui_map(
                    ctx.guild.id, color_mode=color_mode
                )
            else:
                file, file_name = manager.draw_fow_gui_map(
                    ctx.guild.id, player_restriction=player, color_mode=color_mode
                )
        except Exception as err:
            log_command(
                logger,
                ctx,
                message="Failed to generate map for an unknown reason",
                level=logging.ERROR,
            )
            await send_message_and_file(
                channel=ctx.channel,
                title="Unknown Error: Please contact your local bot dev",
                embed_colour=config.ERROR_COLOUR,
            )
            raise err
            return
        log_command(
            logger,
            ctx,
            message=f"Generated current map for {board.turn}",
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{board.turn}",
            file=file,
            file_name=file_name,
            convert_svg=False,
            file_in_embed=False,
        )

    @commands.command(brief="outputs the provinces you can see")
    @perms.player("view visible provinces")
    async def visible_provinces(
        self, ctx: commands.Context, player: Player | None
    ) -> None:
        assert ctx.guild is not None
        board = manager.get_board(ctx.guild.id)

        if not player or not board.fow:
            log_command(logger, ctx, message="No fog of war game")
            await send_message_and_file(
                channel=ctx.channel,
                message="This command only works for players in fog of war games.",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        visible_provinces = board.get_visible_provinces(player)
        log_command(
            logger, ctx, message=f"There are {len(visible_provinces)} visible provinces"
        )
        await send_message_and_file(
            channel=ctx.channel, message=", ".join([p.name for p in visible_provinces])
        )

    @commands.command(name="press_directory", brief="outputs a list of press channels")
    @perms.player("generate a press directory")
    async def press_directory(self, ctx: commands.Context, player: Player | None) -> None:
        assert ctx.guild is not None
        board = manager.get_board(ctx.guild.id)
        power_roles = set(map(lambda p: p.find_discord_role(ctx.guild.roles), board.players))

        if player is None:
            await send_message_and_file(
                channel=ctx.channel,
                message="Due to the number of potential channels, global press directories are not currently permitted for GMs, instead create them in player orders channels",
                embed_colour=config.PARTIAL_ERROR_COLOUR,
            )
            return

        void_channels = [] # channels where the only perms are the calling country
        direct_channels = [] # channels where the only perms are the calling country +1
        group_channels = [] # channels where the only perms are the calling country + >1

        player_role = player.find_discord_role(ctx.guild.roles)
        if player_role is None:
            await send_message_and_file(
                channel=ctx.channel,
                message=f"Could not find the role for {player.name}",
                embed_colour=config.ERROR_COLOUR,
            )
            return

        for ch in ctx.guild.text_channels:
            # evaluate player access to channels
            allowed_roles = []
            for target, overwrite in ch.overwrites.items():
                if isinstance(target, discord.Role):
                    if overwrite.view_channel:
                        allowed_roles.append(target)

            if player_role not in allowed_roles:
                continue

            # remove non-player roles
            allowed_roles = list(set(allowed_roles) & power_roles)
            allowed_roles.remove(player_role)
            if len(allowed_roles) == 0:
                info = (ch, None)
                void_channels.append(info)
            elif len(allowed_roles) == 1:
                info = (ch, f"{allowed_roles[0].mention}")
                direct_channels.append(info)
            elif len(allowed_roles) > 1:
                info = (ch, " ".join(map(lambda r: r.mention, sorted(allowed_roles, key=lambda r: r.name))))
                group_channels.append(info)
            else:
                continue

        void_out = "\n".join([f"- {c.mention}" for c, _ in void_channels])
        direct_out = "\n".join([f"- {c.mention} - {r_mentions}" for c, r_mentions in direct_channels]) if len(direct_channels) > 0 else ""
        group_out = "\n".join([f"- {c.mention} - {r_mentions}" for c, r_mentions in group_channels]) if len(group_channels) > 0 else ""
        out = (
            "Void\n"
            f"{void_out}\n"
            "Press\n"
            f"{direct_out}\n"
            "Group\n"
            f"{group_out}"
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"{player_role.name} Press Channel Directory",
            message=out
        )

async def setup(bot):
    cog = PlayerCog(bot)
    await bot.add_cog(cog)
