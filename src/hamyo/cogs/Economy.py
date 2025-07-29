import discord
from discord.ext import commands
from balance_data_manager import balance_manager
import aiosqlite

GUILD_ID = [1368459027851509891, 1378632284068122685]

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id in GUILD_ID:
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

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

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
                "`*온 지급 @유저 금액 [횟수]` : 특정 유저에게 온을 지급합니다. (관리자 권한 필요)\n"
                "`*온 회수 @유저 금액` : 특정 유저의 온을 회수합니다. (관리자 권한 필요)\n"
                "`*온 인증 @유저 조건 [횟수]` : 인증 조건을 만족한 유저에게 온을 지급합니다. (권한 필요)\n"
                "예시: `*온 지급 @유저 1000 10` → 10000 지급, `*온 인증 @유저 업 10` → 업 인증 10회분 지급"
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
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=member.display_avatar.url)
        embed.timestamp = ctx.message.created_at
   
        await ctx.reply(embed=embed)

    @on.command(name="지급")
    @only_in_guild()
    @in_allowed_channel()
    @commands.has_permissions(administrator=True)
    async def give_coins(self, ctx, member: discord.Member, amount: int, count: int = 1):
        """Give a specific amount of coins to a user, multiplied by count."""
        if amount <= 0 or count <= 0:
            await ctx.reply("금액과 횟수는 0보다 커야 합니다.")
            return

        total = amount * count
        await balance_manager.give(str(member.id), total)
        unit = await self.get_currency_unit()
        new_balance = await balance_manager.get_balance(str(member.id))
        
        embed = discord.Embed(
            title=f"{unit}、온 지급 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}에게 **{total}**{unit} 줬다묘...✩
(⠀ ⠀ ⠀좋은 곳에 쓰라묘.........
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author} | 지급 후 잔액: {new_balance}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게 {total}({amount}*{count}) 지급.")

    @on.command(name="인증")
    @only_in_guild()
    @in_allowed_channel()
    @has_auth_role()
    async def certify(self, ctx, member: discord.Member, condition: str, count: int = 1):
        """Certify a user for meeting a condition and reward them, multiplied by count."""
        if count <= 0:
            await ctx.reply("횟수는 0보다 커야 합니다.")
            return

        reward_amount = await balance_manager.get_auth_reward_amount(condition)
        if reward_amount is None:
            await ctx.reply(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        total = reward_amount * count
        await balance_manager.give(str(member.id), total)

        unit = await self.get_currency_unit()
        new_balance = await balance_manager.get_balance(str(member.id))

        embed = discord.Embed(
            title=f"{unit}: 온 인증",
            description=f"{member.mention}님에게 `{condition} {count}회` 인증 보상으로 `{total}`{unit}을 지급했슴묘!",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author} | 지급 후 잔액: {new_balance}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at

        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게 인증 '{condition} {count}회'로 {total}({reward_amount}*{count}) {unit} 지급.")

async def setup(bot):
    
    await bot.add_cog(Economy(bot))