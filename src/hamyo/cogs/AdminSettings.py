import discord
from discord.ext import commands
from ..balance_data_manager import balance_manager

class AdminSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="설정", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        """Base command for admin settings."""
        await ctx.send("사용 가능한 하위 명령어: 인증추가, 인증제거")

    @settings.command(name="인증추가")
    @commands.has_permissions(administrator=True)
    async def add_auth_condition(self, ctx, *, condition: str):
        """Add an authentication condition (auth item)."""
        await balance_manager.add_auth_item(condition)
        await ctx.send(f"인증 조건 '{condition}'이(가) 추가되었습니다.")

    @settings.command(name="인증제거")
    @commands.has_permissions(administrator=True)
    async def remove_auth_condition(self, ctx, *, condition: str):
        """Remove an authentication condition (auth item)."""
        await balance_manager.remove_auth_item(condition)
        await ctx.send(f"인증 조건 '{condition}'이(가) 제거되었습니다.")

async def setup(bot):
    await bot.add_cog(AdminSettings(bot))