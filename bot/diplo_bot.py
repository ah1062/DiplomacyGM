import datetime
from dotenv.main import load_dotenv
import logging
import os
import random

import discord
from discord.ext import commands

from bot.bot import impdip_server, bot_status_channel, MESSAGES
from bot.config import ERROR_COLOUR
from bot.perms import CommandPermissionError
from bot.utils import send_message_and_file
from diplomacy.persistence.manager import Manager

load_dotenv()
logger = logging.getLogger(__name__)


class DiploBot(commands.Bot):
    def __init__(
        self,
        command_prefix: str = ".",
        intents: discord.Intents = discord.Intents.default(),
    ):
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.before_invoke(self.before_any_command)
        self.after_invoke(self.after_any_command)

        self.logger = logger
        self.manager = Manager()

    async def on_ready(self) -> None:
        try:
            await self.tree.sync()
        except discord.app_commands.CommandAlreadyRegistered:
            pass

        guild = self.get_guild(impdip_server)
        if guild:
            channel = self.get_channel(bot_status_channel)
            if channel:
                message = random.choice(MESSAGES)
                await channel.send(message)
            else:
                print(f"Imperial Diplomacy Guild (id={bot_status_channel}) not found.")

        else:
            print(f"Imperial Diplomacy Guild (id={impdip_server}) not found.")

        # Set bot's presence (optional)
        await self.change_presence(activity=discord.Game(name="Impdip 🔪"))

    async def before_any_command(self, ctx: commands.Context) -> None:
        if isinstance(ctx.channel, discord.DMChannel):
            return

        logger.debug(
            f"[{ctx.guild.name}][#{ctx.channel.name}]({ctx.message.author.name}) - '{ctx.message.content}'"
        )

        # People input apostrophes that don't match what the province names are, we can catch all of that here
        # ctx.message.content = re.sub(r"[‘’`´′‛]", "'", ctx.message.content)

        # mark the message as seen
        await ctx.message.add_reaction("👍")

    async def after_any_command(self, ctx: commands.Context) -> None:
        time_spent = datetime.datetime.now(datetime.UTC) - ctx.message.created_at

        if time_spent.total_seconds() < 10:
            level = logging.DEBUG
        else:
            level = logging.WARN

        logger.log(
            level,
            f"[{ctx.guild.name}][#{ctx.channel.name}]({ctx.message.author.name}) - '{ctx.message.content}' - "
            f"complete in {time_spent}s",
        )

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            # we shouldn't do anything if the user says something like "..."
            return

        if isinstance(
            error,
            (
                commands.CommandInvokeError,
                commands.ConversionError,
                commands.HybridCommandError,
            ),
        ):
            original = error.original
        else:
            original = error

        try:
            # mark the message as failed
            await ctx.message.add_reaction("❌")
            await ctx.message.remove_reaction("👍", self.user)
        except Exception:
            # if reactions fail, ignore and continue handling existing exception
            pass

        if isinstance(original, CommandPermissionError):
            await send_message_and_file(
                channel=ctx.channel, message=str(original), embed_colour=ERROR_COLOUR
            )
            return

        time_spent = datetime.datetime.now(datetime.UTC) - ctx.message.created_at
        logger.log(
            logging.ERROR,
            f"[{ctx.guild.name}][#{ctx.channel.name}]({ctx.message.author.name}) - '{ctx.message.content}' - "
            f"errored in {time_spent}s\n",
        )

        if isinstance(original, discord.Forbidden):
            await send_message_and_file(
                channel=ctx.channel,
                message=f"I do not have the correct permissions to do this.\n"
                f"I might not be setup correctly.\n"
                f"If this is unexpected please contact a GM or reach out in: "
                f"https://discord.com/channels/1201167737163104376/1286027175048253573"
                f" or "
                f"https://discord.com/channels/1201167737163104376/1280587781638459528",
                embed_colour=ERROR_COLOUR,
            )
        else:
            time_spent = datetime.datetime.now(datetime.UTC) - ctx.message.created_at

            try:
                # mark the message as failed
                await ctx.message.add_reaction("❌")
                await ctx.message.remove_reaction("👍", self.user)
            except Exception:
                # if reactions fail continue handling error
                pass

            if isinstance(original, CommandPermissionError):
                await send_message_and_file(
                    channel=ctx.channel,
                    message=str(original),
                    embed_colour=ERROR_COLOUR,
                )
            else:
                logger.error(
                    f"[{ctx.guild.name}][#{ctx.channel.name}]({ctx.message.author.name}) - '{ctx.message.content}' - "
                    f"errored in {time_spent}s\n"
                )
                logger.error(original)
                await send_message_and_file(
                    channel=ctx.channel,
                    message=str(original),
                    embed_colour=ERROR_COLOUR,
                )

    async def setup_hook(self) -> None:
        cog_dir = "./cogs"
        for filename in os.listdir(cog_dir):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            extension = f"cogs.{filename[:-3]}"
            await self.load_extension(extension)
            print(f"Loaded: {filename}")


def run():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("The DISCORD_TOKEN environment variable is not set.")

    command_prefix = os.getenv("command_prefix", default=".")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = DiploBot(command_prefix, intents)
    bot.run(token)


if __name__ == "__main__":
    run()
