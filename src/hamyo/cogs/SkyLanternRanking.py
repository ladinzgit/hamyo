import discord
from discord.ext import commands, tasks
import aiosqlite
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone("Asia/Seoul")

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

    @tasks.loop(minutes=1)
    async def update_ranking(self):
        now = datetime.now(KST)
        if now.minute != 0:
            return  # 정각이 아니면 아무것도 하지 않음

        skylantern = self.bot.get_cog("SkyLanternEvent")
        if not skylantern:
            return
        top = await skylantern.get_top_lanterns(20)  # 넉넉히 받아서 동점자 처리
        # 동점자 처리 및 상위 10위까지 추출
        ranking = []
        prev_count = None
        rank = 0
        real_rank = 0
        for user_id, count in top:
            real_rank += 1
            if prev_count != count:
                rank = real_rank
            if rank > 10:
                break
            ranking.append((rank, user_id, count))
            prev_count = count

        channel_id = await get_ranking_channel_id()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        desc = ""
        for rank, user_id, count in ranking:
            desc += f"{rank}위 <@{user_id}>: {count}개\n"
        embed = discord.Embed(
            title="풍등 랭킹 TOP 10",
            description=desc or "아직 풍등을 날린 사람이 없다묘,,",
            colour=discord.Colour.orange()
        )
        embed.set_footer(text="매시 정각마다 자동 갱신")
        embed.timestamp = now
        embed.set_image(url="https://media.discordapp.net/attachments/1378305048429330502/1378740945448599632/0a000aa455f55f22.gif?ex=683db411&is=683c6291&hm=d784f4509417aa0d0848c3d47a159218b64a0c207790cd39bf9ad577c57a31cc&=")
        async for msg in channel.history(limit=10):
            if msg.author == self.bot.user:
                await msg.delete()
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SkyLanternRanking(bot))
