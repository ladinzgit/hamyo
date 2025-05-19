import discord
from discord.ext import commands
from .data_manager import load_data, save_data

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        """Check your or another user's balance."""
        member = member or ctx.author
        data = load_data()
        balance = data.get(str(member.id), 0)
        await ctx.send(f"{member.mention} has {balance} coins.")

    @commands.command()
    async def earn(self, ctx, amount: int):
        """Earn a specified amount of coins."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        data = load_data()
        user_id = str(ctx.author.id)
        data[user_id] = data.get(user_id, 0) + amount
        save_data(data)

        await ctx.send(f"{ctx.author.mention} earned {amount} coins!")

    @commands.command()
    async def transfer(self, ctx, member: discord.Member, amount: int):
        """Transfer coins to another user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        data = load_data()
        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)

        if data.get(sender_id, 0) < amount:
            await ctx.send("You don't have enough coins to transfer.")
            return

        data[sender_id] = data.get(sender_id, 0) - amount
        data[receiver_id] = data.get(receiver_id, 0) + amount
        save_data(data)

        await ctx.send(f"{ctx.author.mention} transferred {amount} coins to {member.mention}!")

    @commands.command(name="확인")
    async def check_balance(self, ctx, member: discord.Member = None):
        """Check the current balance of a user."""
        member = member or ctx.author
        data = load_data()
        balance = data.get(str(member.id), 0)
        await ctx.send(f"{member.mention} has {balance} coins.")

    @commands.command(name="지급")
    @commands.has_permissions(administrator=True)
    async def give_coins(self, ctx, member: discord.Member, amount: int):
        """Give a specific amount of coins to a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        data = load_data()
        user_id = str(member.id)
        data[user_id] = data.get(user_id, 0) + amount
        save_data(data)

        await ctx.send(f"{amount} coins have been given to {member.mention}.")

    @commands.command(name="인증")
    async def certify(self, ctx, member: discord.Member, condition: str):
        """Certify a user for meeting a condition and reward them."""
        data = load_data()

        # Check if the user has the required role
        required_role_id = data.get("required_role")
        if required_role_id is None:
            await ctx.send("권한이 설정되지 않았습니다. 관리자에게 문의하세요.")
            return

        required_role = discord.utils.get(ctx.guild.roles, id=required_role_id)
        if required_role not in ctx.author.roles:
            await ctx.send("이 명령어를 실행할 권한이 없습니다.")
            return

        # Validate the condition
        valid_conditions = data.get("conditions", [])
        if condition not in valid_conditions:
            await ctx.send(f"유효하지 않은 조건입니다. 설정된 조건: {', '.join(valid_conditions)}")
            return

        # Reward the user
        reward_amount = 100  # Example fixed reward amount
        user_id = str(member.id)
        data[user_id] = data.get(user_id, 0) + reward_amount
        save_data(data)

        await ctx.send(f"{member.mention} has been certified for {condition} and received {reward_amount} coins.")

    @commands.command(name="뺏기")
    @commands.has_permissions(administrator=True)
    async def take_coins(self, ctx, member: discord.Member, amount: int):
        """Take a specific amount of coins from a user."""
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        data = load_data()
        user_id = str(member.id)
        if data.get(user_id, 0) < amount:
            await ctx.send(f"{member.mention} does not have enough coins to take.")
            return

        data[user_id] = data.get(user_id, 0) - amount
        save_data(data)

        await ctx.send(f"{amount} coins have been taken from {member.mention}.")

async def setup(bot):
    await bot.add_cog(Economy(bot))