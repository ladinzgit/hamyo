import discord
from discord.ext import commands, tasks
import aiosqlite

async def get_ranking_channel_id():
    async with aiosqlite.connect("data/skylantern_event.db") as db:
        async with db.execute("SELECT ranking_channel_id FROM config WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else 1378352416571002880

class SkyLanternRanking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skylantern = None

    async def cog_load(self):
        self.update_ranking.start()

    @tasks.loop(hours=1)
    async def update_ranking(self):
        skylantern = self.bot.get_cog("SkyLanternEvent")
        if not skylantern:
            return
        top = await skylantern.get_top_lanterns(5)
        channel_id = await get_ranking_channel_id()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        desc = ""
        for i, (user_id, count) in enumerate(top, 1):
            desc += f"{i}위 <@{user_id}>: {count}개\n"
        embed = discord.Embed(
            title="풍등 랭킹 TOP 5",
            description=desc or "아직 풍등을 날린 사람이 없습니다.",
            colour=discord.Colour.orange()
        )
        async for msg in channel.history(limit=10):
            if msg.author == self.bot.user:
                await msg.delete()
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SkyLanternRanking(bot))
