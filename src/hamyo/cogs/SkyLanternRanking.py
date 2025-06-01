import discord
from discord.ext import commands, tasks

CHANNEL_RANKING = 1378352416571002880

class SkyLanternRanking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skylantern = None

    async def cog_load(self):
        self.skylantern = self.bot.get_cog("SkyLanternEvent")
        self.update_ranking.start()

    @tasks.loop(hours=1)
    async def update_ranking(self):
        if not self.skylantern:
            return
        top = await self.skylantern.get_top_lanterns(5)
        channel = self.bot.get_channel(CHANNEL_RANKING)
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
