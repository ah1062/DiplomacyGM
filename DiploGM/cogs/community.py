import copy
from dataclasses import dataclass, field
import datetime
import hashlib
import json
import logging
import os
from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands

from DiploGM.config import ERROR_COLOUR
from DiploGM.manager import Manager
from DiploGM.perms import is_superuser, superuser_only
from DiploGM.utils import send_message_and_file

logger = logging.getLogger(__name__)
manager = Manager()


@dataclass
class User:
    id: int
    name: str
    servers: set[int] = field(default_factory=set)
    communities: set[int] = field(default_factory=set)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, User):
            return False

        return self.id == value.id

    def __str__(self) -> str:
        return f"User(id={self.id}, name='{self.name}', in {len(self.servers)} servers)"

    def to_json(self) -> Dict:
        return {
            "type": "user",
            "id": self.id,
            "name": self.name,
            "servers": list(self.servers),
            "communities": list(self.communities),
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_json(cls, data: dict):
        return User(
            id=data["id"],
            name=data["name"],
            servers=set(data["servers"]),
            communities=set(data["communities"]),
            created_at=datetime.datetime.fromisoformat(data["created_at"])
        )

    
    def display(self) -> str:
        return ""

@dataclass
class Server:
    id: int
    name: str
    users: set[int] = field(default_factory=set)
    community: Optional[int] = None
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, Server):
            return False

        return self.id == value.id

    def __str__(self) -> str:
        return f"Server(id={self.id}, name='{self.name}', has {len(self.users)} users)"

    def to_json(self) -> Dict:
        return {
            "type": "server",
            "id": self.id,
            "name": self.name,
            "users": list(self.users),
            "community": self.community,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_json(cls, data: dict):
        return Server(
            id=data["id"],
            name=data["name"],
            users=set(data["users"]),
            community=data["communities"],
            created_at=datetime.datetime.fromisoformat(data["created_at"])
        )

    def display(self) -> str:
        return ""

@dataclass
class Community:
    id: int 
    owner: int
    name: str
    users: set[int] = field(default_factory=set)
    servers: set[int] = field(default_factory=set)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, Community):
            return False

        return self.id == value.id

    def __str__(self) -> str:
        return f"Community(id={self.id}, name='{self.name}', has {len(self.users)} users in {len(self.servers)} servers)"

    def to_json(self) -> Dict:
        return {
            "type": "community",
            "id": self.id,
            "owner": self.owner,
            "name": self.name,
            "users": list(self.users),
            "servers": list(self.servers),
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_json(cls, data: dict):
        return Community(
            id=data["id"],
            name=data["name"],
            owner=data["owner"],
            users=set(data["users"]),
            servers=set(data["servers"]),
            created_at=datetime.datetime.fromisoformat(data["created_at"])
        )

    def display(self) -> str:
        return f"Name: {self.name}\nOwned by: <@{self.owner}>\nNo. Servers: {len(self.servers)}\nNo. Members: {len(self.users)}"


class Repository:
    def save_community(self, community: Community) -> None: ...
    def load_community(self, id: int) -> Optional[Community]: ...
    def delete_community(self, id: int) -> None: ...
        
    def save_server(self, server: Server) -> None: ...
    def load_server(self, id: int) -> Optional[Server]: ...
    def delete_server(self, id: int) -> None: ...

    def save_user(self, user: User) -> None: ...
    def load_user(self, id: int) -> Optional[User]: ...
    def delete_user(self, id: int) -> None: ...

class JSONRepository(Repository):
    def __init__(self, storage_dir: str):
        self.storage = storage_dir

    def save_community(self, community: Community) -> None:
        file_path = f"{self.storage}/community_{community.id}.json"
        
        output = json.dumps(community, indent=4, default=lambda c: c.to_json())
        with open(file_path, "w") as f:
            f.write(output)

    def load_community(self, id: int) -> Optional[Community]:
        file_path = f"{self.storage}/community_{id}.json"
        if not os.path.exists(file_path):
            return None

        with open(file_path) as f:
            data = json.load(f)
            community = Community(
                id=data["id"], 
                name=data["name"],
                owner=data["owner"], 
                users=set(data["users"]),
                servers=set(data["servers"]),
                created_at=datetime.datetime.fromisoformat(data["created_at"])
            )

        return community

    def delete_community(self, id: int) -> None:
        file_path = f"{self.storage}/community_{id}.json"
        if os.path.exists(file_path):
            os.remove(file_path)

    def save_server(self, server: Server) -> None:
        file_path = f"{self.storage}/server_{server.id}.json"
        
        output = json.dumps(server, indent=4, default=lambda c: c.to_json())
        with open(file_path, "w") as f:
            f.write(output)

    def load_server(self, id: int) -> Optional[Server]:
        file_path = f"{self.storage}/server_{id}.json"
        if not os.path.exists(file_path):
            return None

        with open(file_path) as f:
            data = json.load(f)
            server = Server(
                id=data["id"], 
                name=data["name"],
                users=set(data["users"]),
                community=data["community"],
                created_at=datetime.datetime.fromisoformat(data["created_at"])
            )

        return server

    def delete_server(self, id: int) -> None:
        file_path = f"{self.storage}/server_{id}.json"
        if os.path.exists(file_path):
            os.remove(file_path)

    def save_user(self, user: User) -> None:
        file_path = f"{self.storage}/user_{user.id}.json"
        
        output = json.dumps(user, indent=4, default=lambda c: c.to_json())
        with open(file_path, "w") as f:
            f.write(output)

    def load_user(self, id: int) -> Optional[User]:
        file_path = f"{self.storage}/user_{id}.json"
        if not os.path.exists(file_path):
            return None

        with open(file_path) as f:
            data = json.load(f)
            user = User(
                id=data["id"], 
                name=data["name"],
                servers=set(data["servers"]),
                communities=set(data["communities"]),
                created_at=datetime.datetime.fromisoformat(data["created_at"])
            )

        return user

    def delete_user(self, id: int) -> None:
        file_path = f"{self.storage}/user_{id}.json"
        if os.path.exists(file_path):
            os.remove(file_path)

class CommunityManager:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.communities: Dict[int, Community] = {}
        self.names_to_community_id: Dict[str, int] = {}

        self.servers: Dict[int, Server] = {}
        self.names_to_server_id: Dict[str, int] = {}

        self.users: Dict[int, User] = {}
        self.names_to_user_id: Dict[str, int] = {}

        self.load_existing_data()

    def load_existing_data(self):
        if isinstance(self.repo, JSONRepository):
            for filename in os.listdir(self.repo.storage):
                path = os.path.join(self.repo.storage, filename)

                data = {}
                with open(path) as f:
                    data = json.load(f)

                try:
                    match data["type"]:
                        case "user":
                            user = User.from_json(data)
                            self.users[user.id] = user
                            self.names_to_user_id[user.name] = user.id
                        case "server":
                            server = Server.from_json(data)
                            self.servers[server.id] = server
                            self.names_to_server_id[server.name] = server.id
                        case "community":
                            community = Community.from_json(data)
                            self.communities[community.id] = community
                            self.names_to_community_id[community.name] = community.id
                except KeyError:
                    continue

    # === Manager Community Methods
    def get_communities(self, object: Union[User, Server]) -> List[Community]:
        communities = []
        
        if isinstance(object, User):
            communities = [community for cid in object.communities if (community := self.get_community(cid))]
        if isinstance(object, Server):
            if not object.community:
                return []

            if (community := self.get_community(object.community)):
                communities.append(community)

        return communities

    def get_community(self, id: Union[int, str]) -> Optional[Community]: 
        if isinstance(id, str):
            id = self.names_to_community_id.get(id, -1)

            if id == -1:
                return None

        try:
            return self.communities[id]
        except KeyError:
            community = self.repo.load_community(id)
            if community:
                self.save_community(community)
                return community
                
        return None

    def save_community(self, community: Community) -> None:
        self.communities[community.id] = community
        self.names_to_community_id[community.name] = community.id

        self.repo.save_community(community)

    def load_community(self, id: int) -> Optional[Community]:
        community = self.repo.load_community(id)
        if community:
            self.communities[id] = community
            self.names_to_community_id[community.name] = community.id

        return community

    def delete_community(self, id: int) -> None:
        community = self.get_community(id)
        if not community:
            return

        for sid in copy.deepcopy(community.users):
            user = self.get_user(sid)
            if user:
                self.unlink_user_to_community(user, community)
                self.save_user(user)

        for sid in copy.deepcopy(community.servers):
            server = self.get_server(sid)
            if server:
                self.unlink_server_to_community(server, community)
                self.save_server(server)

        del self.servers[id]
        self.repo.delete_server(id)

    def display_community(self, community: Community) -> str:
        out = ""
        out += f"Name: {community.name}\n"
        out += f"Owned by: <@{community.owner}>\n"
        out += f"No. of Members: {len(community.users)}\n" 
        out += f"No. of Servers: {len(community.servers)}\n" 
        out += f"Registered on: {community.created_at}\n" 

        servers = self.get_servers(community)
        if len(servers) > 0:
            out += "Registered Servers:\n"
            servers = self.get_servers(community)
            for server in sorted(servers, key=lambda s: s.name):
                out += f"- {server.name}\n"

        return out

    # === Manager Server Methods
    def get_servers(self, object: Union[User, Community]) -> List[Server]:
        servers = []
        
        if isinstance(object, User):
            servers = [server for sid in object.servers if (server := self.get_server(sid))]
        if isinstance(object, Community):
            servers = [server for sid in object.servers if (server := self.get_server(sid))]

        return servers

    def get_server(self, id: Union[int, str]) -> Optional[Server]: 
        if isinstance(id, str):
            id = self.names_to_server_id.get(id, -1)

            if id == -1:
                return None

        try:
            return self.servers[id]
        except KeyError:
            server = self.repo.load_server(id)
            if server:
                self.save_server(server)
                return server
                
        return None

    def save_server(self, server: Server) -> None:
        self.servers[server.id] = server
        self.names_to_server_id[server.name] = server.id
        self.repo.save_server(server)

    def load_server(self, id: int) -> Optional[Server]:
        server = self.repo.load_server(id)
        if server:
            self.servers[id] = server
            self.names_to_server_id[server.name] = server.id

        return server

    def delete_server(self, id: int) -> None:
        server = self.get_server(id)
        if not server:
            return

        for uid in copy.deepcopy(server.users):
            user = self.get_user(uid)
            if user:
                self.unlink_user_to_server(user, server)
                self.save_user(user)

        if server.community:
            community = self.get_community(server.community)
            if community:
                self.unlink_server_to_community(server, community)

        del self.servers[id]
        self.repo.delete_server(id)

    def display_server(self, server: Server) -> str:
        out = ""
        out += f"Name: {server.name}\n"
        out += f"Community: {c.name if server.community and (c := self.get_community(server.community)) else 'None'}\n" 
        out += f"No. of Members: {len(server.users)}\n" 
        out += f"Registered on: {server.created_at}\n" 

        return out

    # === Manager User Methods
    def get_users(self, object: Union[Server, Community]) -> List[User]:
        users = []
        
        if isinstance(object, Server):
            users = [user for uid in object.users if (user := self.get_user(uid))]
        if isinstance(object, Community):
            users = [user for sid in object.users if (user := self.get_user(sid))]

        return users

    def get_user(self, id: Union[int, str]) -> Optional[User]:
        if isinstance(id, str):
            id = self.names_to_user_id.get(id, -1)

            if id == -1:
                return None

        try:
            return self.users[id]
        except KeyError:
            user = self.repo.load_user(id)
            if user:
                self.save_user(user)
                return user
                
        return None

    def save_user(self, user: User) -> None:
        self.users[user.id] = user
        self.names_to_user_id[user.name] = user.id
        self.repo.save_user(user)

    def load_user(self, id: int) -> Optional[User]:
        user = self.repo.load_user(id)
        if user:
            self.users[id] = user
            self.names_to_user_id[user.name] = user.id

        return user

    def delete_user(self, id: int) -> None:
        user = self.get_user(id)
        if not user:
            return

        for cid in user.servers:
            community = self.get_server(cid)
            if community:
                self.unlink_user_to_server(user, community)

        for cid in user.communities:
            community = self.get_community(cid)
            if community:
                self.unlink_user_to_community(user, community)

        del self.users[id]
        self.repo.delete_user(id)

    def display_user(self, user: User) -> str:
        out = ""
        out += f"Name: {user.name}\n"
        out += f"Registered on: {user.created_at}\n"
        
        communities = self.get_communities(user)
        if len(communities) > 0:
            out += "Communities:\n"
            for community in sorted(communities, key=lambda c: c.name):
                out += f"- {community.name}\n"

        servers = self.get_servers(user)
        if len(servers) > 0:
            out += "Servers:\n"
            for server in sorted(servers, key=lambda c: c.created_at, reverse=True):
                out += f"- {server.name}\n"

        return out

    # === Object Linking Methods
    def link_user_to_server(self, user: User, server: Server) -> None:
        user.servers.add(server.id)
        server.users.add(user.id)

        self.repo.save_user(user)
        self.repo.save_server(server)

    def unlink_user_to_server(self, user: User, server: Server) -> None:
        user.servers.remove(server.id)
        server.users.remove(user.id)

        self.repo.save_user(user)
        self.repo.save_server(server)

    def link_user_to_community(self, user: User, community: Community) -> None:
        user.communities.add(community.id)
        community.users.add(user.id)

        self.repo.save_user(user)
        self.repo.save_community(community)

    def unlink_user_to_community(self, user: User, community: Community) -> None:
        user.communities.remove(community.id)
        community.users.remove(user.id)

        self.repo.save_user(user)
        self.repo.save_community(community)

    def link_server_to_community(self, server: Server, community: Community) -> None:
        server.community = community.id
        community.servers.add(server.id)

        for user in self.get_users(server):
            self.link_user_to_community(user, community)

        self.repo.save_server(server)
        self.repo.save_community(community)

    def unlink_server_to_community(self, server: Server, community: Community) -> None:
        server.community = None
        community.servers.remove(server.id)

        self.repo.save_server(server)
        self.repo.save_community(community)

    def change_community_ownership(self, user: User, community: Community) -> None:
        community.owner = user.id
        self.repo.save_community(community)

class CommunityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        repo = JSONRepository("assets/community")
        self.comms = CommunityManager(repo)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        server = self.comms.get_server(guild.id)
        if not server:
            process_server(self.comms, guild)
            server = self.comms.get_server(guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        server = self.comms.get_server(before.id)
        if server:
            server.name = after.name
            self.comms.save_server(server)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        user = self.comms.get_user(member.id)
        if not user:
            user = User(member.id, member.name)
            self.comms.save_user(user)
        
        guild = member.guild
        server = self.comms.get_server(guild.id)
        if server:
            self.comms.link_user_to_server(user, server)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        user = self.comms.get_user(member.id)
        if not user:
            user = User(member.id, member.name)
            self.comms.save_user(user)
        
        guild = member.guild
        server = self.comms.get_server(guild.id)
        if server:
            self.comms.unlink_user_to_server(user, server)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        user = self.comms.get_user(before.id)
        if user:
            user.name = after.name
            self.comms.save_user(user)

    @commands.command(hidden=True)
    @superuser_only("populate the community manager")
    async def populate(self, ctx: commands.Context, *args):
        """Populate data with an existing server
            
        """

        guild = ctx.guild
        if not guild:
            return


        servers = []
        if "all" in args:
            for guild in self.bot.guilds:
                process_server(self.comms, guild)
                servers.append(guild.name)
        else:
            process_server(self.comms, guild)
            servers.append(guild.name)

        output = ", ".join(servers)
        await send_message_and_file(channel=ctx.channel, title="Community Manager Populated", message=f"Servers: {output}")

    @commands.group(name="community", invoke_without_command=True)
    async def community(self, ctx: commands.Context) -> None:
        await ctx.send("**Options:** create, register, unregister, inspect")

    @community.command(name="create")
    async def community_create(self, ctx: commands.Context, name: str) -> None: 
        uid = string_to_u8(name.lower())
        
        community = self.comms.get_community(uid)
        if community:
            await send_message_and_file(channel=ctx.channel, message=f"A community named: '{name}' already exists!", embed_colour=ERROR_COLOUR)
            return

        community = Community(id=uid, name=name, owner=ctx.author.id)
        self.comms.save_community(community)
        await send_message_and_file(channel=ctx.channel, message=f"Created community: {name} ({uid})")

    @community.command(name="delete")
    async def community_delete(self, ctx: commands.Context, id: Union[int, str]) -> None: 
        community = self.comms.get_community(id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message=f"Could not find community attached to: '{id}'", embed_colour=ERROR_COLOUR)
            return

        if ctx.author.id != community.owner and not is_superuser(ctx.author):
            await send_message_and_file(channel=ctx.channel, message="You are not permitted to delete that community.", embed_colour=ERROR_COLOUR)
            return

        self.comms.delete_community(community.id)
        await send_message_and_file(channel=ctx.channel, message=f"Deleted community: {id}")

    @community.command(name="transfer")
    @superuser_only("transfer community ownership")
    async def community_transfer(self, ctx: commands.Context, id: Union[int, str], user: discord.User) -> None: 
        community = self.comms.get_community(id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message=f"Could not find community attached to: '{id}'", embed_colour=ERROR_COLOUR)
            return

        user = self.comms.get_user(id)
        if not user:
            await send_message_and_file(channel=ctx.channel, message=f"Could not find a user record attached to: '{id}'", embed_colour=ERROR_COLOUR)
            return

        self.comms.change_community_ownership(user, community)


    @community.command(name="join")
    async def community_join(self, ctx: commands.Context, id: Union[int, str]) -> None: 
        community = self.comms.get_community(id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message=f"Could not find community attached to: '{id}'", embed_colour=ERROR_COLOUR)
            return

        user = self.comms.get_user(ctx.author.id)
        if user:
            self.comms.link_user_to_community(user, community)
            await send_message_and_file(channel=ctx.channel, message=f"Joined Community: {community.name} ({community.id})")

    @community.command(name="leave")
    async def community_leave(self, ctx: commands.Context, id: Union[int, str]) -> None: 
        community = self.comms.get_community(id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message=f"Could not find community attached to: '{id}'", embed_colour=ERROR_COLOUR)
            return

        user = self.comms.get_user(ctx.author.id)
        if not user:
            return

        if user.id == community.owner:
            await send_message_and_file(channel=ctx.channel, message="You can't leave the community you own!", embed_colour=ERROR_COLOUR)
            return


        self.comms.unlink_user_to_community(user, community)
        await send_message_and_file(channel=ctx.channel, message=f"Left Community: {community.name} ({community.id})")

    @community.group(name="register", invoke_without_command=True)
    async def community_register(self, ctx: commands.Context) -> None: 
        await ctx.send("**Options:** server, user*")

    @community_register.command(name="server")
    async def community_register_server(self, ctx: commands.Context, community_id: Union[int, str]) -> None:
        guild = ctx.guild
        if not guild:
            return

        community = self.comms.get_community(community_id)
        server = self.comms.get_server(guild.id)

        if server and community:
            self.comms.link_server_to_community(server, community)
            await send_message_and_file(channel=ctx.channel, message=f"Registered {server.name} to {community.name}")

    @community_unregister.command(name="user")
    @superuser_only("register a user to a community")
    async def community_register_user(self, ctx: commands.Context, user: discord.User, community_id: Union[int, str]) -> None:
        community = self.comms.get_community(community_id)
        user = self.comms.get_user(user.id)

        if user and community:
            self.comms.link_user_to_community(user, community)
            await send_message_and_file(channel=ctx.channel, message=f"Registered {user.name} to {community.name}")

    @community.group(name="unregister", invoke_without_command=True)
    async def community_unregister(self, ctx: commands.Context) -> None: 
        await ctx.send("**Options:** server, user")

    @community_unregister.command(name="server")
    async def community_unregister_server(self, ctx: commands.Context, community_id: Union[int, str]) -> None:
        guild = ctx.guild
        if not guild:
            return

        community = self.comms.get_community(community_id)
        server = self.comms.get_server(guild.id)

        if server and community:
            self.comms.unlink_server_to_community(server, community)
            await send_message_and_file(channel=ctx.channel, message=f"Unregistered {server.name} from {community.name}")

    @community_unregister.command(name="user")
    @superuser_only("unregister a user from a community")
    async def community_unregister_user(self, ctx: commands.Context, user: discord.User, community_id: Union[int, str]) -> None:
        community = self.comms.get_community(community_id)
        user = self.comms.get_user(user.id)

        if user and community:
            self.comms.unlink_user_to_community(user, community)
            await send_message_and_file(channel=ctx.channel, message=f"Unregistered {user.name} from {community.name}")

    @community.group(name="list", invoke_without_command=True)
    async def community_list(self, ctx:commands.Context) -> None:
        await ctx.send("**Options:** community, server")

    @community_list.command(name="communities")
    async def community_list_communities(self, ctx: commands.Context) -> None:
        out = ""
        for name, id in sorted(self.comms.names_to_community_id.items(), key=lambda p: p[0]):
            out += f"- {name} ({id})\n"

        await send_message_and_file(channel=ctx.channel, title="Currently Tracked Communities", message=out)

    @community_list.command(name="servers")
    async def community_list_servers(self, ctx: commands.Context, community_id: Union[int, str]) -> None:
        community = self.comms.get_community(community_id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message="Could not find that Community!", embed_colour=ERROR_COLOUR)
            return
        
        out = ""
        servers = self.comms.get_servers(community)
        for server in sorted(servers, key=lambda s: s.name):
            out += f"- {server.name}\n"

        await send_message_and_file(channel=ctx.channel, title=f"{community.name} - Servers", message=out)

    @community.group(name="inspect", invoke_without_command=True)
    async def community_inspect(self, ctx:commands.Context) -> None:
        await ctx.send("**Options:** community, server, user")

    @community_inspect.command(name="community")
    async def community_inspect_community(self, ctx: commands.Context, id: Union[int, str]) -> None:
        community = self.comms.get_community(id)
        if not community:
            await send_message_and_file(channel=ctx.channel, message="Could not find that Community!", embed_colour=ERROR_COLOUR)
            return

        out = self.comms.display_community(community)
        await send_message_and_file(channel=ctx.channel, title = f"Community: {id}", message=out)

    @community_inspect.command(name="server")
    async def community_inspect_server(self, ctx: commands.Context, id: Union[int, str]) -> None:
        server = self.comms.get_server(id)
        if not server:
            await send_message_and_file(channel=ctx.channel, message="Could not find Server!", embed_colour=ERROR_COLOUR)
            return

        out = self.comms.display_server(server)
        await send_message_and_file(channel=ctx.channel, title = f"Server: {id}", message=out)

    @community_inspect.command(name="user")
    async def community_inspect_user(self, ctx: commands.Context, user: discord.User) -> None:
        user = self.comms.get_user(user.id)
        if not user:
            await send_message_and_file(channel=ctx.channel, message="Could not find User!", embed_colour=ERROR_COLOUR)
            return

        out = self.comms.display_user(user)
        await send_message_and_file(channel=ctx.channel, title = f"User: {id}", message=out)

def string_to_u8(s: str) -> int:
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    code = int(digest, 16) % (10 ** 8)
    return code

def process_server(comms: CommunityManager, guild: discord.Guild) -> None:
    start = datetime.datetime.now(datetime.timezone.utc)
    server = comms.get_server(guild.id)
    if not server:
        server = Server(guild.id, guild.name)
        comms.save_server(server)

    member: Optional[discord.Member] = None
    for member in guild.members:
        if member is None or member.bot:
            continue

        user = comms.get_user(member.id)
        if not user:
            user = User(member.id, member.name)
            logger.info(f"Creating new tracked object for user: {member.id}")
            comms.save_user(user)

        comms.link_user_to_server(user, server)        

    now = datetime.datetime.now(datetime.timezone.utc)
    logger.info(f"Processed server {guild.id} for the Community Manager: took {start - now}")
    comms.save_server(server)

async def setup(bot):
    cog = CommunityCog(bot)
    await bot.add_cog(cog)
