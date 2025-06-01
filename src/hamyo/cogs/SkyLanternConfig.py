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
        await ctx.send("하위 명령어: 기간, 지급량")

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

async def setup(bot):
    await bot.add_cog(SkyLanternConfig(bot))
