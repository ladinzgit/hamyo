import discord
from discord.ext import commands
from src.core.balance_data_manager import balance_manager
import aiosqlite

from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin


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
            value=(
                "`*온 확인 [@유저]` : 자신의 또는 다른 유저의 잔액을 확인합니다.\n"
                "`*온 송금 @유저 금액` : 다른 유저에게 온을 송금합니다. (수수료: 500온, 50,000온 이상 1,000온)\n"
                "`*온 수수료` : 송금 수수료를 확인합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="관리자 전용 명령어",
            value=(
                "`*온 지급 @유저 금액 [횟수]` : 특정 유저에게 온을 지급합니다. (권한 필요)\n"
                "`*온 회수 @유저 금액` : 특정 유저의 온을 회수합니다. (권한 필요)\n"
                "`*온 인증 @유저 조건 [횟수]` : 인증 조건을 만족한 유저에게 온을 지급합니다. (권한 필요)\n"
                "`*온 채널일괄지급 금액 [#채널]` : 해당 채널에 채팅을 한 모든 유저에게 온을 지급합니다. (권한 필요)\n"
                "예시: `*온 지급 @유저 1000 10` → 10000 지급, `*온 인증 @유저 업 10` → 업 인증 10회분 지급"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)

    @on.command(name="확인")
    @only_in_guild()
    @in_allowed_channel()
    async def check_balance(self, ctx, member: discord.Member = None):
        """유저의 현재 잔액을 확인합니다."""
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
        
    @on.command(name="송금")
    @only_in_guild()
    @in_allowed_channel()
    async def transfer_money(self, ctx, member: discord.Member, amount: int):
        """다른 유저에게 특정 금액을 송금합니다."""
        unit = await self.get_currency_unit()
        if member.bot:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ 기몽한테 {unit}을 보내는 것은
(⠀⠀⠀⠀ ⠀⠀⠀⠀ 안 된다묘.....!!!!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            return
            
        if member.id == ctx.author.id:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}한테 {unit}을 보내는 것은
(⠀⠀⠀⠀ ⠀⠀⠀⠀ 안 된다묘.....!!!!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            return

        if amount <= 0:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}은 바보냐묘..!!!
(⠀⠀⠀⠀ ⠀⠀⠀⠀ 1{unit}부터 보낼 수 있다묘...!!!!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            return

        # 송금 수수료 계산
        try:
            fee = await balance_manager.get_fee_for_amount(amount)
        except Exception:

            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘..... 
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            await self.log(f"{ctx.author}({ctx.author.id}) 송금 수수료 계산 중 오류 발생\n(송금: {amount}, 수수료: '계산 실패')")
            return
            
        total_cost = amount + fee

        # 잔액 확인
        balance = await balance_manager.get_balance(str(ctx.author.id))
        unit = await self.get_currency_unit()
        if balance < total_cost:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {ctx.author.mention}은 그지다묘.....
(⠀⠀⠀{amount}{unit}을 보내려면 {total_cost}{unit}이 필요한데
(⠀⠀⠀⠀ ⠀ {balance}{unit} 밖에 없어서 못 보낸다묘.......
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            return

        # 일일 송금/수취 횟수 확인
        send_limit, receive_limit = await balance_manager.get_daily_limits()
        sent_count = await balance_manager.get_daily_transfer_count(str(ctx.author.id), True)
        if sent_count >= send_limit:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {ctx.author.mention}은 기부천사냐묘..?!!
(⠀⠀⠀⠀ 오늘은 {sent_count}번이나 보내서
(⠀⠀⠀⠀ 더 이상 못 보낸다묘.......
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )

            sender_balance = await balance_manager.get_balance(str(ctx.author.id))

            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at

            await ctx.reply(embed=embed)
            return

        # 일일 수취 횟수 확인
        received_count = await balance_manager.get_daily_transfer_count(str(member.id), False)
        if received_count >= receive_limit:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {member.id}은 인기쟁이다묘..!!!!
(⠀⠀⠀⠀ 오늘은 {received_count}번이나 받아서
(⠀⠀⠀⠀ 더 이상 못 받는다묘.......
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )

            sender_balance = await balance_manager.get_balance(str(ctx.author.id))

            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at

            await ctx.reply(embed=embed)
            return

        # 송금 실행
        success = await balance_manager.transfer(str(ctx.author.id), str(member.id), amount, fee)
        
        if success:
            embed = discord.Embed(
                title=f"{unit}、온 송금 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {ctx.author.mention}님이 {member.mention}에게
(⠀ ⠀ ⠀**{amount}**{unit} 보냈다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
            
            embed.set_footer(
                text=f"요청자: {ctx.author} | 회수 후 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게 {amount} 송금 (수수료: {fee})")
        else:
            embed = discord.Embed(
                title=f"{unit}、온 송금 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘..... 
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            
            sender_balance = await balance_manager.get_balance(str(ctx.author.id))
                        
            embed.set_footer(
                text=f"요청자: {ctx.author} | 현재 잔액: {sender_balance}", 
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)

    @on.command(name="수수료")
    @only_in_guild()
    @in_allowed_channel()
    async def check_transfer_fee(self, ctx):
        """송금 수수료 구조를 확인합니다."""
        fee_tiers = await balance_manager.get_fee_tiers()
        unit = await self.get_currency_unit()
        
        embed = discord.Embed(
            title="온 송금 수수료 안내 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 현재 수수료 설정이다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯

""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        if fee_tiers:
            tiers_text = "\n".join([f"• {tier['min_amount']:,}{unit} 이상: {tier['fee']:,}{unit}" for tier in sorted(fee_tiers, key=lambda x: x['min_amount'])])
            embed.add_field(name="현재 수수료 구간", value=tiers_text, inline=False)
        else:
            embed.add_field(name="현재 수수료 구간", value="설정된 수수료 구간이 없습니다.", inline=False)
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 수수료 목록을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @on.command(name="지급")
    @only_in_guild()
    @has_auth_role()
    async def give_coins(self, ctx, member: discord.Member, amount: int, count: int = 1):
        """특정 유저에게 온을 지급합니다 (횟수 적용 가능)."""
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
    @has_auth_role()
    async def certify(self, ctx, member: discord.Member, condition: str, count: int = 1):
        """유저의 인증 조건을 처리하고 보상을 지급합니다 (횟수 적용 가능)."""
        if count <= 0:
            await ctx.reply("횟수는 0보다 커야 합니다.")
            return

        reward_amount = await balance_manager.get_auth_reward_amount(condition)
        if reward_amount is None:
            await ctx.reply(f"유효하지 않은 조건입니다. 인증 가능한 조건을 확인하세요.")
            return

        total = reward_amount * count
        await balance_manager.give(str(member.id), total)

        # --- 추천 인증 시 LevelChecker에 주간 퀘스트 트리거 ---
        # --- 추천/업/지인초대 인증 시 이벤트를 방출하여 퀘스트 트리거 ---
        if condition == "추천":
            self.bot.dispatch("quest_recommend", member.id, count)

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

    @on.command(name="회수")
    @only_in_guild()
    @has_auth_role()
    async def take_coins(self, ctx, member: discord.Member, amount: int):
        """특정 유저에게서 온을 회수합니다."""
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
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})에게서 {amount} {unit} 회수.")

    @on.command(name="채널일괄지급")
    @only_in_guild()
    @has_auth_role()
    async def bulk_give_channel(self, ctx, amount: int, channel: discord.TextChannel = None):
        """지정된 채널에서 채팅한 모든 유저에게 온을 지급합니다."""
        if amount <= 0:
            await ctx.reply("금액은 0보다 커야 합니다.")
            return

        target_channel = channel or ctx.channel
        unit = await self.get_currency_unit()

        # 처리 중 메시지 전송
        processing_embed = discord.Embed(
            title=f"{unit}: 채널 일괄 지급 처리 중...",
            description=f"{target_channel.mention}에서 채팅한 유저들을 찾고 있다묘...",
            colour=discord.Colour.from_rgb(255, 255, 0)
        )
        processing_msg = await ctx.reply(embed=processing_embed)

        # 채널에서 메시지를 보낸 유저들 수집 (중복 제거)
        unique_users = set()
        try:
            async for message in target_channel.history(limit=None):
                if not message.author.bot:  # 봇 제외
                    unique_users.add(message.author)
        except discord.Forbidden:
            await processing_msg.edit(embed=discord.Embed(
                title="❌ 오류",
                description=f"{target_channel.mention}의 메시지 기록에 접근할 수 없습니다.",
                colour=discord.Colour.red()
            ))
            return
        except Exception as e:
            await processing_msg.edit(embed=discord.Embed(
                title="❌ 오류",
                description=f"메시지 기록을 읽는 중 오류가 발생했습니다: {str(e)}",
                colour=discord.Colour.red()
            ))
            return

        if not unique_users:
            await processing_msg.edit(embed=discord.Embed(
                title="ℹ️ 알림",
                description=f"{target_channel.mention}에서 채팅한 유저가 없습니다.",
                colour=discord.Colour.blue()
            ))
            return

        # 각 유저에게 지급
        successful_users = []
        failed_users = []
        
        for user in unique_users:
            try:
                await balance_manager.give(str(user.id), amount)
                successful_users.append(user)
            except Exception as e:
                failed_users.append(f"{user.display_name}: {str(e)}")

        # 결과 임베드 생성
        total_given = len(successful_users) * amount
        
        embed = discord.Embed(
            title=f"{unit}: 채널 일괄 지급 완료 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {target_channel.mention}에서 채팅한 **{len(successful_users)}명**에게
(⠀ ⠀ ⠀각각 **{amount}**{unit}씩 줬다묘...✩
(⠀ ⠀ ⠀총 **{total_given}**{unit} 지급했다묘!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        
        # 지급받은 유저 목록 (최대 25개 필드 제한)
        user_mentions = [user.mention for user in successful_users]
        
        # 유저 목록을 여러 필드로 나누어 표시 (필드당 최대 1024자)
        field_count = 0
        current_field_value = ""
        
        for mention in user_mentions:
            # 새로운 멘션을 추가했을 때 1024자를 넘는지 확인
            test_value = current_field_value + mention + ", "
            if len(test_value) > 1024 or field_count >= 24:  # 필드 제한 고려
                # 현재 필드 추가
                if current_field_value:
                    embed.add_field(
                        name=f"지급받은 유저 목록 ({field_count + 1})",
                        value=current_field_value.rstrip(", "),
                        inline=False
                    )
                    field_count += 1
                current_field_value = mention + ", "
            else:
                current_field_value = test_value
        
        # 마지막 필드 추가
        if current_field_value and field_count < 25:
            embed.add_field(
                name=f"지급받은 유저 목록 ({field_count + 1})" if field_count > 0 else "지급받은 유저 목록",
                value=current_field_value.rstrip(", "),
                inline=False
            )

        # 실패한 유저가 있다면 표시
        if failed_users:
            failure_text = "\n".join(failed_users[:10])  # 최대 10개만 표시
            if len(failed_users) > 10:
                failure_text += f"\n... 및 {len(failed_users) - 10}명 더"
            embed.add_field(
                name="지급 실패",
                value=failure_text,
                inline=False
            )

        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at

        await processing_msg.edit(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 {target_channel.name}({target_channel.id}) 채널에서 {len(successful_users)}명에게 각각 {amount} {unit} 일괄 지급.")


async def setup(bot):
    await bot.add_cog(Economy(bot))