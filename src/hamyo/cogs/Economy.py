import discord
from discord.ext import commands
from ..balance_data_manager import balance_manager

def has_auth_role():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        role_ids = await balance_manager.list_auth_roles()
        if any(role.id in role_ids for role in ctx.author.roles):
            return True
        await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        return False
    return commands.check(predicate)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_currency_unit(self):
        unit = await balance_manager.get_currency_unit()
        return f"{unit['name']} {unit['emoji']}" if unit else "코인"

    @commands.group(name="온", invoke_without_command=True)
    async def on(self, ctx):
        """온(경제) 관련 명령어 그룹"""
        unit = await self.get_currency_unit()
        embed = discord.Embed(
            title=f"온(경제) 명령어 도움말",
            description=f"서버 내 화폐 단위: {unit}\n\n아래는 사용 가능한 온(경제) 명령어입니다.",
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        embed.add_field(
            name="일반 명령어",
            value="`*온 확인 [@유저]` : 자신의 또는 다른 유저의 잔액을 확인합니다.",
            inline=False
        )
        embed.add_field(
            name="관리자 전용 명령어",
            value=(
                "`*온 지급 @유저 금액` : 특정 유저에게 온을 지급합니다. (권한 필요)\n"
                "`*온 회수 @유저 금액` : 특정 유저의 온을 회수합니다. (권한 필요)\n"
                "`*온 인증 @유저 조건` : 인증 조건을 만족한 유저에게 온을 지급합니다. (권한 필요)"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)

    @on.command(name="확인")
    async def check_balance(self, ctx, member: discord.Member = None):
        """Check the current balance of a user."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        unit = await self.get_currency_unit()
        await ctx.send(f"{member.mention} has {balance} {unit}.")

    @on.command(name="지급")
    @has_auth_role()
    async def give_coins(self, ctx, member: discord.Member, amount: int):
        """Give a specific amount of coins to a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        await balance_manager.give(str(member.id), amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{amount} {unit} have been given to {member.mention}.")

    @on.command(name="인증")
    @has_auth_role()
    async def certify(self, ctx, member: discord.Member, condition: str):
        """Certify a user for meeting a condition and reward them."""
        reward_amount = await balance_manager.get_auth_reward_amount(condition)
        if reward_amount is None:
            await ctx.send(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        await balance_manager.give(str(member.id), reward_amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{member.mention} has been certified for {condition} and received {reward_amount} {unit}.")

    @on.command(name="회수")
    @has_auth_role()
    async def take_coins(self, ctx, member: discord.Member, amount: int):
        """Take a specific amount of coins from a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        user_id = str(member.id)
        balance = await balance_manager.get_balance(user_id)
        if balance < amount:
            await ctx.send(f"{member.mention} does not have enough coins to take.")
            return

        await balance_manager.take(user_id, amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{amount} {unit} have been taken from {member.mention}.")

async def setup(bot):
    await bot.add_cog(Economy(bot))