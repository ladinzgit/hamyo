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

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        """Check your or another user's balance."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        unit = await self.get_currency_unit()
        await ctx.send(f"{member.mention} has {balance} {unit}.")

    @commands.command()
    async def earn(self, ctx, amount: int):
        """Earn a specified amount of coins."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        await balance_manager.give(str(ctx.author.id), amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{ctx.author.mention} earned {amount} {unit}!")

    @commands.command()
    async def transfer(self, ctx, member: discord.Member, amount: int):
        """Transfer coins to another user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)
        sender_balance = await balance_manager.get_balance(sender_id)
        if sender_balance < amount:
            await ctx.send("You don't have enough coins to transfer.")
            return

        await balance_manager.take(sender_id, amount)
        await balance_manager.give(receiver_id, amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{ctx.author.mention} transferred {amount} {unit} to {member.mention}!")

    @commands.command(name="확인")
    async def check_balance(self, ctx, member: discord.Member = None):
        """Check the current balance of a user."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        unit = await self.get_currency_unit()
        await ctx.send(f"{member.mention} has {balance} {unit}.")

    @commands.command(name="지급")
    @has_auth_role()
    async def give_coins(self, ctx, member: discord.Member, amount: int):
        """Give a specific amount of coins to a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        await balance_manager.give(str(member.id), amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{amount} {unit} have been given to {member.mention}.")

    @commands.command(name="인증")
    @has_auth_role()
    async def certify(self, ctx, member: discord.Member, condition: str):
        """Certify a user for meeting a condition and reward them."""
        # 인증 항목(auth 테이블) 확인 후 지급
        reward_amount = await balance_manager.get_auth_reward_amount(condition)
        if reward_amount is None:
            await ctx.send(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        await balance_manager.give(str(member.id), reward_amount)
        unit = await self.get_currency_unit()
        await ctx.send(f"{member.mention} has been certified for {condition} and received {reward_amount} {unit}.")

    @commands.command(name="뺏기")
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