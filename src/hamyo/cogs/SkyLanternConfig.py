import discord
from discord.ext import commands
import aiosqlite

DB_PATH = "data/skylantern_event.db"

class SkyLanternConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="풍등설정", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def lantern_config(self, ctx):
        await ctx.send("하위 명령어: 기간, 지급량, 채널")

    @lantern_config.command(name="기간")
    @commands.has_permissions(administrator=True)
    async def set_period(self, ctx, start: str, end: str):
        """YYYY-MM-DD 형식"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE config SET start=?, end=? WHERE id=1", (start+"T00:00:00+09:00", end+"T23:59:59+09:00"))
            await db.commit()
        await ctx.send(f"이벤트 기간이 {start} ~ {end}로 설정되었습니다.")

    @lantern_config.command(name="지급량")
    @commands.has_permissions(administrator=True)
    async def set_reward(self, ctx, key: str, amount: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO reward_config (key, amount) VALUES (?, ?)", (key, amount))
            await db.commit()
        await ctx.send(f"{key} 지급량이 {amount}개로 설정되었습니다.")

    @lantern_config.group(name="채널", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def channel_config(self, ctx):
        await ctx.send("하위 명령어: 랭킹, 응원글, 내풍등")

    @channel_config.command(name="랭킹")
    @commands.has_permissions(administrator=True)
    async def set_ranking_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("ALTER TABLE config ADD COLUMN ranking_channel_id INTEGER")  # 무시: 이미 있으면 에러
            await db.execute("UPDATE config SET ranking_channel_id=? WHERE id=1", (channel.id,))
            await db.commit()
        await ctx.send(f"실시간_랭킹 채널이 {channel.mention}로 설정되었습니다.")

    @channel_config.command(name="응원글")
    @commands.has_permissions(administrator=True)
    async def set_celebration_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("ALTER TABLE config ADD COLUMN celebration_channel_id INTEGER")
            await db.execute("UPDATE config SET celebration_channel_id=? WHERE id=1", (channel.id,))
            await db.commit()
        await ctx.send(f"오픈_응원글 채널이 {channel.mention}로 설정되었습니다.")

    @channel_config.command(name="내풍등")
    @commands.has_permissions(administrator=True)
    async def set_my_lantern_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("ALTER TABLE config ADD COLUMN my_lantern_channel_id INTEGER")
            await db.execute("UPDATE config SET my_lantern_channel_id=? WHERE id=1", (channel.id,))
            await db.commit()
        await ctx.send(f"냬_풍등_확인 채널이 {channel.mention}로 설정되었습니다.")

async def setup(bot):
    await bot.add_cog(SkyLanternConfig(bot))
