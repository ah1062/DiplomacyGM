"""A sample cog to demonstrate the structure of a cog."""
import logging

from discord.ext import commands

from DiploGM.manager import Manager

logger = logging.getLogger(__name__)
manager = Manager()


class SampleCog(commands.Cog):
    """A sample cog to demonstrate the structure of a cog."""
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    """Setup function for the Sample cog."""
    cog = SampleCog(bot)
    await bot.add_cog(cog)
