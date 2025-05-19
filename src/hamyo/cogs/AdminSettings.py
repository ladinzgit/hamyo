import discord
from discord.ext import commands
from ..data_manager import load_data, save_data

class AdminSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="설정", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        """Base command for admin settings."""
        await ctx.send("사용 가능한 하위 명령어: 권한, 조건")

    @settings.command(name="권한")
    @commands.has_permissions(administrator=True)
    async def set_role_permission(self, ctx, role: discord.Role):
        """Set the role required for executing certain commands."""
        data = load_data()
        data["required_role"] = role.id
        save_data(data)
        await ctx.send(f"권한이 {role.name}(으)로 설정되었습니다.")

    @settings.command(name="조건")
    @commands.has_permissions(administrator=True)
    async def set_conditions(self, ctx, *, conditions: str):
        """Set the conditions for the 인증 command."""
        data = load_data()
        data["conditions"] = conditions.split(",")
        save_data(data)
        await ctx.send(f"조건이 다음과 같이 설정되었습니다: {', '.join(data['conditions'])}")

async def setup(bot):
    await bot.add_cog(AdminSettings(bot))