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
        await ctx.send("사용 가능한 하위 명령어: 인증추가, 인증제거, 인증목록, 인증역할추가, 인증역할제거, 인증역할목록, 화폐단위등록")

    @settings.command(name="인증추가")
    @commands.has_permissions(administrator=True)
    async def add_auth_condition(self, ctx, condition: str, reward_amount: int):
        """Add an authentication condition (auth item) with reward amount."""
        await balance_manager.add_auth_item(condition, reward_amount)
        await ctx.send(f"인증 조건 '{condition}'(보상: {reward_amount})이(가) 추가되었습니다.")

    @settings.command(name="인증제거")
    @commands.has_permissions(administrator=True)
    async def remove_auth_condition(self, ctx, *, condition: str):
        """Remove an authentication condition (auth item)."""
        await balance_manager.remove_auth_item(condition)
        await ctx.send(f"인증 조건 '{condition}'이(가) 제거되었습니다.")

    @settings.command(name="인증목록")
    @commands.has_permissions(administrator=True)
    async def list_auth_conditions(self, ctx):
        """List all authentication conditions."""
        items = await balance_manager.list_auth_items()
        if not items:
            await ctx.send("등록된 인증 조건이 없습니다.")
        else:
            msg = "\n".join([f"{item['item']} (보상: {item['reward_amount']})" for item in items])
            await ctx.send(f"인증 조건 목록:\n{msg}")

    @settings.command(name="인증역할추가")
    @commands.has_permissions(administrator=True)
    async def add_auth_role(self, ctx, role: discord.Role):
        """Add a role that can use 인증/지급/뺏기 명령어."""
        await balance_manager.add_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할로 '{role.name}'이(가) 추가되었습니다.")

    @settings.command(name="인증역할제거")
    @commands.has_permissions(administrator=True)
    async def remove_auth_role(self, ctx, role: discord.Role):
        """Remove a role from 인증 명령어 사용 역할."""
        await balance_manager.remove_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할에서 '{role.name}'이(가) 제거되었습니다.")

    @settings.command(name="인증역할목록")
    @commands.has_permissions(administrator=True)
    async def list_auth_roles(self, ctx):
        """List all roles that can use 인증/지급/뺏기 명령어."""
        role_ids = await balance_manager.list_auth_roles()
        if not role_ids:
            await ctx.send("등록된 인증 명령어 사용 역할이 없습니다.")
        else:
            roles = [discord.utils.get(ctx.guild.roles, id=rid) for rid in role_ids]
            msg = "\n".join([role.name if role else f"ID:{rid}" for role, rid in zip(roles, role_ids)])
            await ctx.send(f"인증 명령어 사용 역할 목록:\n{msg}")

    @settings.command(name="화폐단위등록")
    @commands.has_permissions(administrator=True)
    async def set_currency_unit(self, ctx, name: str, emoji: str):
        """Set the currency unit (name and emoji)."""
        await balance_manager.set_currency_unit(name, emoji)
        await ctx.send(f"화폐 단위가 '{name} {emoji}'로 설정되었습니다.")

async def setup(bot):
    await bot.add_cog(AdminSettings(bot))