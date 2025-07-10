import logging
import random
import re

import discord
from discord.ext import commands

from bot.command import ping_text_choices
from bot.diplo_bot import DiploBot
from bot.perms import admin_only
from bot.utils import is_gm_channel, log_command, send_message_and_file


logger = logging.getLogger(__name__)


class ContainedPrinter:
    def __init__(self):
        self.text = ""

    def __call__(self, *args):
        self.text += " ".join(map(str, args)) + "\n"


class AdminCog(commands.Cog):
    def __init__(self, bot: DiploBot) -> None:
        self.bot = bot
        self.manager = bot.manager

    @commands.command(help="Checks bot listens and responds.")
    async def ping(self, ctx: commands.Context) -> None:
        response = "Beep Boop"
        if random.random() < 0.1:
            author = ctx.message.author
            content = ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)
            if content == "":
                content = " nothing"
            name = author.nick
            if not name:
                name = author.name
            response = name + " " + random.choice(ping_text_choices) + content
        await send_message_and_file(channel=ctx.channel, title=response)

    @commands.command(hidden=True)
    @admin_only("send a GM announcement")
    async def announce(self, ctx: commands.Context) -> None:
        guilds_with_games = self.manager.list_servers()
        content = ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)
        content = re.sub(r"<@&[0-9]{16,20}>", r"{}", content)
        roles = list(map(lambda role: role.name, ctx.message.role_mentions))
        message = ""
        for server in ctx.bot.guilds:
            if server is None:
                continue
            admin_chat_channel = next(
                channel for channel in server.channels if is_gm_channel(channel)
            )
            if admin_chat_channel is None:
                message += f"\n- ~~{server.name}~~ Couldn't find admin channel"

            message += f"\n- {server.name}"
            if server.id in guilds_with_games:
                board = self.manager.get_board(server.id)
                message += f" - {board.phase.name} {board.get_year_str()}"
            else:
                message += f" - no active game"

            server_roles = []
            for role_name in roles:
                for role in server.roles:
                    if role.name == role_name:
                        server_roles.append(role.mention)
                        break
                else:
                    server_roles.append(role_name)

            if len(server_roles) > 0:
                await admin_chat_channel.send(
                    ("||" + "{}" * len(server_roles) + "||").format(*server_roles)
                )
            await send_message_and_file(
                channel=admin_chat_channel,
                title="Admin Announcement",
                message=content.format(*server_roles),
            )
        log_command(
            logger, ctx, f"Sent Announcement into {len(ctx.bot.guilds)} servers"
        )
        await send_message_and_file(
            channel=ctx.channel,
            title=f"Announcement sent to {len(ctx.bot.guilds)} servers:",
            message=message,
        )

    @commands.command(hidden=True)
    @admin_only("list servers")
    async def servers(self, ctx: commands.Context) -> None:
        servers_with_games = self.manager.list_servers()
        message = ""
        for server in ctx.bot.guilds:
            if server is None:
                continue

            channels = server.channels
            for channel in channels:
                if isinstance(channel, discord.TextChannel):
                    break
            else:
                message += f"\n- {server.name} - Could not find a channel for invite"
                continue

            if server.id in servers_with_games:
                servers_with_games.remove(server.id)
                board = self.manager.get_board(server.id)
                board_state = f" - {board.phase.name} {board.get_year_str()}"
            else:
                board_state = f" - no active game"

            try:
                invite = await channel.create_invite(max_age=300)
            except (discord.HTTPException, discord.NotFound):
                message += f"\n- {server.name} - Could not create invite"
            else:
                message += f"\n- [{server.name}](<{invite.url}>)"

            message += board_state

        # Servers with games the bot is not in
        if servers_with_games:
            message += f"\n There is a further {len(servers_with_games)} games in servers I am no longer in"

        log_command(logger, ctx, f"Found {len(ctx.bot.guilds)} servers")
        await send_message_and_file(
            channel=ctx.channel, title=f"{len(ctx.bot.guilds)} Servers", message=message
        )

    @commands.command(hidden=True)
    @admin_only("allocate roles to user(s)")
    async def bulk_allocate_role(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if guild is None:
            return

        # extract roles to be allocated based off of mentions
        # .bulk_allocate_role <@B1.4 Player> <@B1.4 GM Team> ...
        roles = ctx.message.role_mentions
        role_names = list(map(lambda r: r.name, roles))
        if len(roles) == 0:
            await send_message_and_file(
                channel=ctx.channel,
                title="Error",
                message="No roles were supplied to allocate. Please include a role mention in the command.",
            )
            return

        # parse usernames from trailing contents
        # .bulk_allocate_role <@B1.4 Player> elisha thisisflare kingofprussia ...
        content = ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)

        usernames = []
        components = content.split(" ")
        for comp in components:
            if comp == "":
                continue

            match = re.match(r"<@&\d+>", comp)
            if match:
                continue

            usernames.append(comp)

        success_count = 0
        failed = []
        skipped = []
        for user in usernames:
            # FIND USER FROM USERNAME
            member = discord.utils.find(
                lambda m: m.name == user,
                guild.members,
            )

            if not member or member is None:
                failed.append((user, "Member not Found"))
                continue

            for role in roles:
                if role in member.roles:
                    skipped.append((user, f"already had role @{role.name}"))
                    continue

                try:
                    await member.add_roles(role)
                    success_count += 1
                except Exception as e:
                    failed.append((user, f"Error Adding Role- {e}"))

        failed_out = "\n".join([f"{u}: {m}" for u, m in failed])
        skipped_out = "\n".join([f"{u}: {m}" for u, m in skipped])
        out = (
            f"Allocated Roles {', '.join(role_names)} to {len(usernames)} users.\n"
            + f"Succeeded in applying a role {success_count} times.\n"
            + f"Failed {len(failed)} times.\n"
            + f"Skipped {len(skipped)} times for already having the role.\n"
            + "----\n"
            + f"Failed Reasons:\n{failed_out}\n"
            + "----\n"
            + f"Skipped Reasons:\n{skipped_out}\n"
            + "----\n"
        )

        await send_message_and_file(
            channel=ctx.channel, title="Wave Allocation Info", message=out
        )

    @commands.command(hidden=True)
    @admin_only("Execute arbitrary code")
    async def exec_py(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if not guild:
            return

        board = self.manager.get_board(guild.id)
        code = (
            ctx.message.content.removeprefix(ctx.prefix + ctx.invoked_with)
            .strip()
            .strip("`")
        )

        embed_print = ContainedPrinter()

        try:
            exec(code, {"print": embed_print, "board": board})
        except Exception as e:
            embed_print("\n" + repr(e))

        if embed_print.text:
            await send_message_and_file(channel=ctx.channel, message=embed_print.text)
        self.manager._database.delete_board(board)

        self.manager._database.save_board(guild.id, board)


async def setup(bot: DiploBot):
    await bot.add_cog(AdminCog(bot))
