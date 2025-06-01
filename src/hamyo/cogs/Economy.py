import discord
from discord.ext import commands
from balance_data_manager import balance_manager

GUILD_ID = 1368459027851509891

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id == GUILD_ID:
            return True
        return False  # 메시지 없이 무반응
    return commands.check(predicate)

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

def in_allowed_channel():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        
        allowed_channels = await balance_manager.list_allowed_channels()
        
        # 허용 채널이 하나도 없으면 모든 채널 허용
        if not allowed_channels or ctx.channel.id in allowed_channels:
            return True
        return False
    return commands.check(predicate)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skylantern = None

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        # SkyLanternEvent Cog 참조
        self.skylantern = self.bot.get_cog("SkyLanternEvent")

    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def get_currency_unit(self):
        unit = await balance_manager.get_currency_unit()
        return unit['emoji'] if unit else "코인"

    @commands.group(name="온", invoke_without_command=True)
    @only_in_guild()
    @in_allowed_channel()
    async def on(self, ctx):
        """온(경제) 관련 명령어 그룹"""
        unit = await self.get_currency_unit()
        embed = discord.Embed(
            title=f"온(경제) 명령어 도움말",
            description=f"서버 내 화폐 단위: {unit}\n\n아래는 사용 가능한 온(경제) 명령어입니다.",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.add_field(
            name="일반 명령어",
            value="`*온 확인 [@유저]` : 자신의 또는 다른 유저의 잔액을 확인합니다.",
            inline=False
        )
        embed.add_field(
            name="관리자 전용 명령어",
            value=(
                "`*온 지급 @유저 금액` : 특정 유저에게 온을 지급합니다. (관리자 권한 필요)\n"
                "`*온 회수 @유저 금액` : 특정 유저의 온을 회수합니다. (관리자 권한 필요)\n"
                "`*온 인증 @유저 조건` : 인증 조건을 만족한 유저에게 온을 지급합니다. (권한 필요)"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)

    @on.command(name="확인")
    @only_in_guild()
    @in_allowed_channel()
    async def check_balance(self, ctx, member: discord.Member = None):
        """Check the current balance of a user."""
        member = member or ctx.author
        balance = await balance_manager.get_balance(str(member.id))
        unit = await self.get_currency_unit()
        embed = discord.Embed(
            title=f"{unit}、온 확인 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}에게는 **{balance}**{unit} 있다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )        
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.avatar.url)
        embed.timestamp = ctx.message.created_at
   
        await ctx.reply(embed=embed)

    @on.command(name="지급")
    @only_in_guild()
    @in_allowed_channel()
    @commands.has_permissions(administrator=True)
    async def give_coins(self, ctx, member: discord.Member, amount: int):
        """Give a specific amount of coins to a user."""
        if amount <= 0:
            await ctx.reply("금액은 0보다 커야 합니다.")
            return

        await balance_manager.give(str(member.id), amount)
        unit = await self.get_currency_unit()
        new_balance = await balance_manager.get_balance(str(member.id))
        
        embed = discord.Embed(
            title=f"{unit}、온 지급 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}에게 **{amount}**{unit} 줬다묘...✩
(⠀ ⠀ ⠀좋은 곳에 쓰라묘.........
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author} | 지급 후 잔액: {new_balance}",
            icon_url=ctx.author.avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게 {amount} 지급.")

    @on.command(name="인증")
    @only_in_guild()
    @in_allowed_channel()
    @has_auth_role()
    async def certify(self, ctx, member: discord.Member, condition: str):
        """Certify a user for meeting a condition and reward them."""
        reward_amount = await balance_manager.get_auth_reward_amount(condition)
        if reward_amount is None:
            await ctx.reply(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        await balance_manager.give(str(member.id), reward_amount)
        lantern_given = False
        lantern_type = None
        # 풍등 지급: 업/추천 조건일 때만
        if self.skylantern and await self.skylantern.is_event_period():
            if condition == "업":
                ok = await self.skylantern.give_lantern(member.id, "up")
                if ok:
                    lantern_given = True
                    lantern_type = "업"
            elif condition == "추천":
                ok = await self.skylantern.give_lantern(member.id, "recommend")
                if ok:
                    lantern_given = True
                    lantern_type = "추천"
        unit = await self.get_currency_unit()
        new_balance = await balance_manager.get_balance(str(member.id))
        
        embed = discord.Embed(
            title=f"{unit}: 온 인증",
            description=f"{member.mention}님에게 `{condition}` 인증 보상으로 `{reward_amount}`{unit}을 지급했슴묘!",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author} | 지급 후 잔액: {new_balance}",
            icon_url=ctx.author.avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게 인증 '{condition}'로 {reward_amount} {unit} 지급.")

        # 풍등 지급 안내 메시지 (embed와 별개로)
        if lantern_given:
            lantern_channel = ctx.guild.get_channel(1378353273194545162)
            mention = lantern_channel.mention if lantern_channel else "<#1378353273194545162>"
            lantern_count = 2 if lantern_type == "업" else 3
            await ctx.send(
                f"{member.mention}님, `{lantern_type}` 인증으로 풍등 {lantern_count}개가 지급되었습니다!\n"
                f"현재 보유 풍등 개수는 {mention} 채널에서 `/내풍등` 명령어로 확인할 수 있습니다."
            )

    @on.command(name="회수")
    @only_in_guild()
    @in_allowed_channel()
    @commands.has_permissions(administrator=True)
    async def take_coins(self, ctx, member: discord.Member, amount: int):
        """Take a specific amount of coins from a user."""
        if amount <= 0:
            await ctx.reply("금액은 0보다 커야 합니다.")
            return

        user_id = str(member.id)
        balance = await balance_manager.get_balance(user_id)
        if balance < amount:
            await ctx.reply(f"{member.display_name}은/는 잔액이 부족하여 `{amount}`{unit}을 회수할 수 없습니다.\n현재 {member.display_name}의 잔액: `{balance}`{unit}")
            return

        await balance_manager.take(user_id, amount)
        unit = await self.get_currency_unit()
        new_balance = await balance_manager.get_balance(user_id)
        
        embed = discord.Embed(
            title=f"{unit}、온 회수 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {member.mention}에게 **{amount}**{unit} 뺏었다묘...✩
(⠀ ⠀ ⠀이제 내 것이다묘.....!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author} | 회수 후 잔액: {new_balance}",
            icon_url=ctx.author.avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게서 {amount} {unit} 회수.")

async def setup(bot):
    
    await bot.add_cog(Economy(bot))