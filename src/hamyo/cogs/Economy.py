import discord
from discord.ext import commands
from ..balance_data_manager import balance_manager

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        """Check your or another user's balance."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        await ctx.send(f"{member.mention} has {balance} coins.")

    @commands.command()
    async def earn(self, ctx, amount: int):
        """Earn a specified amount of coins."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        await balance_manager.give(str(ctx.author.id), amount)
        await ctx.send(f"{ctx.author.mention} earned {amount} coins!")

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
        await ctx.send(f"{ctx.author.mention} transferred {amount} coins to {member.mention}!")

    @commands.command(name="확인")
    async def check_balance(self, ctx, member: discord.Member = None):
        """Check the current balance of a user."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        await ctx.send(f"{member.mention} has {balance} coins.")

    @commands.command(name="지급")
    @commands.has_permissions(administrator=True)
    async def give_coins(self, ctx, member: discord.Member, amount: int):
        """Give a specific amount of coins to a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        await balance_manager.give(str(member.id), amount)
        await ctx.send(f"{amount} coins have been given to {member.mention}.")

    @commands.command(name="인증")
    async def certify(self, ctx, member: discord.Member, condition: str):
        """Certify a user for meeting a condition and reward them."""
        # 인증 항목(auth 테이블) 확인 후 지급
        is_authed = await balance_manager.is_item_authed(condition)
        if not is_authed:
            await ctx.send(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        reward_amount = 100  # 예시: 고정 지급량
        await balance_manager.give(str(member.id), reward_amount)
        await ctx.send(f"{member.mention} has been certified for {condition} and received {reward_amount} coins.")

    @commands.command(name="뺏기")
    @commands.has_permissions(administrator=True)
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
        await ctx.send(f"{amount} coins have been taken from {member.mention}.")

async def setup(bot):
    await bot.add_cog(Economy(bot))