import asyncio
import logging
import os
from typing import Callable

import discord
from discord.ext import commands

from bot.config import is_player_category
from bot.diplo_bot import DiploBot
from bot.perms import gm_only
from bot.utils import get_filtered_orders, get_player_by_channel, send_message_and_file

from diplomacy.adjudicator.utils import svg_to_png
from diplomacy.persistence.manager import Manager
from diplomacy.persistence.player import Player

logger = logging.getLogger(__name__)


# if possible save one svg slot for others
FOW_EXPORT_LIMIT = asyncio.Semaphore(
    max(int(os.getenv("simultaneous_svg_exports_limit")) - 1, 1)
)


async def map_publish_task(map_maker, channel, message):
    async with FOW_EXPORT_LIMIT:
        file, file_name = map_maker()
        file, file_name = await svg_to_png(file, file_name)
        await send_message_and_file(
            channel=channel,
            message=message,
            file=file,
            file_name=file_name,
            file_in_embed=False,
        )


class FogOfWarCog(commands.Cog):
    def __init__(self, bot: DiploBot):
        self.bot = bot
        self.manager = bot.manager

    async def publish_map(
        self,
        ctx: commands.Context,
        manager: Manager,
        name: str,
        map_caller: Callable[[Manager, int, Player], tuple[str, str]],
        filter_player=None,
    ):
        player_category = None

        guild = ctx.guild
        if not guild:
            return

        guild_id = guild.id
        board = manager.get_board(guild_id)

        for category in guild.categories:
            if is_player_category(category.name):
                player_category = category
                break

        if not player_category:
            # FIXME this shouldn't be an Error/this should propagate
            raise RuntimeError("No player category found")

        name_to_player: dict[str, Player] = {}
        for player in board.players:
            name_to_player[player.name.lower()] = player

        tasks = []

        for channel in player_category.channels:
            player = get_player_by_channel(channel, manager, guild.id)

            if not player or (filter_player and player != filter_player):
                continue

            message = (
                f"Here is the {name} for {board.get_year_str()} {board.phase.name}"
            )
            # capture local of player
            tasks.append(
                map_publish_task(
                    lambda player=player: map_caller(manager, guild_id, player),
                    channel,
                    message,
                )
            )

        await asyncio.gather(*tasks)

    async def publish_fow_current(self, ctx: commands.Context):
        await self.publish_map(
            ctx,
            self.manager,
            "starting map",
            lambda m, s, p: m.draw_fow_current_map(s, p),
        )

    @commands.command(
        brief="Sends fog of war maps",
        description="""
        * publish_fow_moves {Country|(None) - whether or not to send for a specific country}
        """,
    )
    @gm_only("publish fow moves")
    async def publish_fow_moves(self, ctx: commands.Context) -> None:
        board = self.manager.get_board(ctx.guild.id)

        if not board.fow:
            raise ValueError("This is not a fog of war game")

        filter_player = board.get_player(
            ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with).strip()
        )

        await publish_map(
            ctx,
            manager,
            "moves map",
            lambda m, s, p: m.draw_fow_moves_map(s, p),
            filter_player,
        )

    @commands.command(
        brief="Sends fog of war orders",
        description="""
        * publish_fow_orders {Country|(None) - whether or not to send for a specific country}
        """,
    )
    @gm_only("send fow order logs")
    async def publish_fow_order_logs(self, ctx: commands.Context):
        player_category = None

        guild = ctx.guild
        if not guild:
            return

        guild_id = guild.id
        board = self.manager.get_board(guild_id)

        if not board.fow:
            raise ValueError("This is not a fog of war game")

        filter_player = board.get_player(
            ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with).strip()
        )

        for category in guild.categories:
            if is_player_category(category.name):
                player_category = category
                break

        if not player_category:
            return "No player category found"

        name_to_player: dict[str, Player] = {}
        for player in board.players:
            name_to_player[player.name.lower()] = player

        for channel in player_category.channels:
            player = get_player_by_channel(channel, self.manager, guild.id)

            if not player or (filter_player and player != filter_player):
                continue

            message = get_filtered_orders(board, player)

            await send_message_and_file(channel=channel, message=message)

        return "Successful"


async def setup(bot: DiploBot):
    await bot.add_cog(FogOfWarCog(bot))

