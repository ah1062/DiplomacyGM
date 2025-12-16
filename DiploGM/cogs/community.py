import datetime
import hashlib
import io
import logging
from DiploGM.utils.send_message import send_message_and_file
import matplotlib.pyplot as plt
import networkx as nx
from sqlite3 import IntegrityError

import discord
from discord.ext import commands

from DiploGM.models.community.community import Community, SQLiteCommunityRepository
from DiploGM.models.community.relationship import Relationship, RelationshipType, SQLiteRelationshipRepository
from DiploGM.models.community.server import SQLiteServerRepository, Server

logger = logging.getLogger(__name__)

class CommunityService:
    def __init__(self) -> None:
        self.community_repo = SQLiteCommunityRepository()
        self.server_repo = SQLiteServerRepository()
        self.relation_repo = SQLiteRelationshipRepository()

    def create_community(self, name: str, owner: discord.User):
        cid = string_to_u32(name)
        c = Community(id=cid, name=name, description="")
        
        try:
            self.community_repo.save(c)
        except IntegrityError:
            pass

        rel = Relationship(owner.id, cid, RelationshipType.COMMUNITY_OWNER)
        self.relation_repo.save(rel)

    def take_registration_server(self, guild: discord.Guild):
        server = Server(guild.id, guild.name)
        self.server_repo.save(server)

        current_member_ids = {member.id for member in guild.members}

        existing_rels = self.relation_repo.find_by(
            lambda rel: rel.object_id == guild.id and rel.type == RelationshipType.SERVER_MEMBER
        )
        existing_member_ids = {rel.subject_id for rel in existing_rels}

        attending = [
            Relationship(subject_id=member_id, object_id=guild.id, type=RelationshipType.SERVER_MEMBER)
            for member_id in current_member_ids - existing_member_ids
        ]
        self.relation_repo.save_many(attending)

        for rel in filter(lambda r: r.subject_id not in current_member_ids, existing_rels):
            if rel.id:
                self.relation_repo.delete(rel.id)

class CommunityCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.service = CommunityService()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.service.take_registration_server(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        rel = Relationship(member.id, member.guild.id, RelationshipType.SERVER_MEMBER)
        self.service.relation_repo.save(rel)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        rels = self.service.relation_repo.find_by(lambda r: r.subject_id == member.id and r.object_id == member.guild.id)
        for r in rels:
            if r.id:
                self.service.relation_repo.delete(r.id)

    @commands.group(name="community")
    async def community(self, ctx: commands.Context):
        pass

    @community.command(name="create")
    async def community_create(self, ctx: commands.Context, name: str):
        self.service.create_community(name, ctx.author)

    @community.command(name="graph")
    async def community_graph(self, ctx: commands.Context):
        G = nx.DiGraph()
        rels = self.service.relation_repo.find_by(lambda r: r.type == RelationshipType.SERVER_MEMBER)
        for r in rels:
            G.add_node(r.subject_id, type="user")

            server = self.service.server_repo.load(r.object_id)
            if server:
                G.add_node(r.object_id, type="server", label=server.name)
                G.add_edge(r.subject_id, r.object_id)


        plt.figure(figsize=(10, 10))
        pos = nx.spring_layout(G, seed=42)  # nice layout
        node_colors = ['lightblue' if G.nodes[n]['type']=='user' else 'orange' for n in G.nodes]

        def node_sizes_by_type(G):
            NODE_TYPE_SIZES = {
                "server": 3000,
                "community": 2200,
                "user": 400,
            }
            return [
                NODE_TYPE_SIZES.get(G.nodes[n].get("type"), 400)
                for n in G.nodes
            ]

        def layered_layout(G):
            pos = {}

            communities = [n for n in G if G.nodes[n]["type"] == "community"]
            servers = [n for n in G if G.nodes[n]["type"] == "server"]
            users = [n for n in G if G.nodes[n]["type"] == "user"]

            # Communities in center
            pos.update(nx.circular_layout(G.subgraph(communities), scale=1.5))

            # Servers around communities
            pos.update(nx.spring_layout(G.subgraph(servers), center=(0, 0), scale=2.5))

            # Users pushed outward
            pos.update(nx.spring_layout(G.subgraph(users), center=(0, 0), scale=6.0))

            return pos

        nx.draw(
            G,
            pos=layered_layout(G),    
            with_labels=True,
            labels={n: G.nodes[n].get("label", "") for n in G.nodes},
            font_size=8,
            node_color=node_colors,
            node_size=node_sizes_by_type(G),
            edge_color='gray',
        )

        # Save to BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        await ctx.send(file=discord.File(buf, filename="graph.png"))

    @commands.command()
    async def populate(self, ctx: commands.Context):
        assert ctx.guild is not None

        start = datetime.datetime.now()
        self.service.take_registration_server(ctx.guild)
        diff = datetime.datetime.now() - start

        await send_message_and_file(channel=ctx.channel, title="Populated server relationships!", message=f"Took: {diff}")

def string_to_u32(s: str) -> int:
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    code = int(digest, 16) % (10 ** 8)
    return code

async def setup(bot):
    cog = CommunityCog(bot)
    await bot.add_cog(cog)
