import logging

import discord
from discord.ext import commands

from DiploGM.models.rep_delta import ReputationDelta, SQLiteReputationDeltaRepository
from DiploGM.utils.send_message import send_message_and_file

logger = logging.getLogger(__name__)


class ReputationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rep_repo = SQLiteReputationDeltaRepository()

    @commands.group(name="rep")
    async def rep(self, ctx: commands.Context):
        pass

    @rep.command(name="add")
    async def rep_add(self, ctx: commands.Context, user: discord.User, amount: int, *, reason: str = "unspecified"):
        delta = ReputationDelta(user.id, amount, reason=reason)
        self.rep_repo.save(delta)

        out = (
            f"ID: {delta.id}\n"
            f"User: {user.mention}\n"
            f"Change: {amount}\n"
        )
        await send_message_and_file(channel=ctx.channel, title="Reputation Logged!", message=out)

    @rep.command(name="delete")
    async def rep_delete(self, ctx: commands.Context, id: int):
        self.rep_repo.delete(id)
        await send_message_and_file(channel=ctx.channel, message=f"Deleted Reputation Delta with ID of {id}")

    @rep.command(name="view")
    async def rep_view(self, ctx: commands.Context, user: discord.User):
        history = list(self.rep_repo.find_by(lambda d: d.user_id == user.id))
    
        out = ""
        for delta in history:
            out += f"({delta.id}): {delta.created_at}\n"
            out += f"- Change: {delta.delta}\n"
            out += f"- Reason: {delta.reason}\n"

        await send_message_and_file(channel=ctx.channel, title=f"{user.name} reputation history", message=out)


async def setup(bot):
    cog = ReputationCog(bot)
    await bot.add_cog(cog)
