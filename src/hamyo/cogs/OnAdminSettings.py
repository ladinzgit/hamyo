import discord
from discord.ext import commands
from balance_data_manager import balance_manager

GUILD_ID = [1396829213100605580, 1378632284068122685]

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id in GUILD_ID:
            return True
        return False  # 메시지 없이 무반응
    return commands.check(predicate)

class OnAdminSettings(commands.Cog):
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

    @commands.group(name="온설정", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        """관리자 설정 명령어 그룹"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("관리자 권한이 필요합니다.")
            return

        embed = discord.Embed(
            title="온 설정(관리자) 명령어 도움말",
            description="아래는 사용 가능한 관리자 설정 명령어입니다.",
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        embed.add_field(
            name="인증 조건 관리",
            value=(
                "`*온설정 인증추가 <조건> <보상>` : 인증 조건과 보상 금액을 추가합니다.\n"
                "`*온설정 인증제거 <조건>` : 인증 조건을 제거합니다.\n"
                "`*온설정 인증목록` : 등록된 인증 조건 목록을 확인합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="인증 역할 관리",
            value=(
                "`*온설정 인증역할추가 @역할` : 인증 명령어 사용 권한 역할을 추가합니다.\n"
                "`*온설정 인증역할제거 @역할` : 인증 명령어 사용 권한 역할을 제거합니다.\n"
                "`*온설정 인증역할목록` : 등록된 인증 명령어 사용 역할 목록을 확인합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="수수료 관리",
            value=(
                "`*온설정 수수료` : 현재 수수료 구간을 확인합니다.\n"
                "`*온설정 수수료 설정 <최소금액> <수수료>` : 새로운 수수료 구간을 추가합니다.\n"
                "`*온설정 수수료 삭제 <최소금액>` : 수수료 구간을 삭제합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="일일 제한 관리",
            value=(
                "`*온설정 제한` : 현재 일일 제한을 확인합니다.\n"
                "`*온설정 제한 설정 송금 <횟수>` : 일일 송금 횟수 제한을 설정합니다.\n"
                "`*온설정 제한 설정 수취 <횟수>` : 일일 수취 횟수 제한을 설정합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="화폐 단위 설정",
            value="`*온설정 화폐단위등록 <이모지>` : 서버 내 화폐 단위를 설정합니다.",
            inline=False
        )
        embed.add_field(
            name="온(경제) 명령어 허용 채널 관리",
            value=(
                "`*온설정 온채널추가 <채널>` : 온(경제) 명령어를 사용할 수 있는 채널을 추가합니다.\n"
                "`*온설정 온채널제거 <채널>` : 온(경제) 명령어 허용 채널에서 제거합니다.\n"
                "`*온설정 온채널목록` : 온(경제) 명령어 허용 채널 목록을 확인합니다."
            ),
            inline=False
        )
        embed.add_field(
            name="모든 유저 화폐 초기화",
            value="`*온설정 온초기화` : 모든 유저의 온(화폐) 잔액을 초기화합니다.",
            inline=False
        )
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 온설정 명령어 도움말을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_auth_condition(self, ctx, condition: str, reward_amount: int):
        """Add an authentication condition (auth item) with reward amount."""
        await balance_manager.add_auth_item(condition, reward_amount)
        await ctx.send(f"인증 조건 '{condition}'(보상: {reward_amount})이(가) 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 '{condition}'(보상: {reward_amount}) 추가. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_auth_condition(self, ctx, *, condition: str):
        """Remove an authentication condition (auth item)."""
        await balance_manager.remove_auth_item(condition)
        await ctx.send(f"인증 조건 '{condition}'이(가) 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 '{condition}' 제거. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증목록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def list_auth_conditions(self, ctx):
        """List all authentication conditions."""
        items = await balance_manager.list_auth_items()
        if not items:
            await ctx.send("등록된 인증 조건이 없습니다.")
        else:
            msg = "\n".join([f"{item['item']} (보상: {item['reward_amount']})" for item in items])
            await ctx.send(f"인증 조건 목록:\n{msg}")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 목록을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증역할추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_auth_role(self, ctx, role: discord.Role):
        """Add a role that can use 인증/지급/회수 명령어."""
        await balance_manager.add_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할로 '{role.name}'이(가) 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 '{role.name}'({role.id}) 추가. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증역할제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_auth_role(self, ctx, role: discord.Role):
        """Remove a role from 인증 명령어 사용 역할."""
        await balance_manager.remove_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할에서 '{role.name}'이(가) 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 '{role.name}'({role.id}) 제거. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="인증역할목록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def list_auth_roles(self, ctx):
        """List all roles that can use 인증/지급/회수 명령어."""
        role_ids = await balance_manager.list_auth_roles()
        if not role_ids:
            await ctx.send("등록된 인증 명령어 사용 역할이 없습니다.")
        else:
            roles = [discord.utils.get(ctx.guild.roles, id=rid) for rid in role_ids]
            msg = "\n".join([role.name if role else f"ID:{rid}" for role, rid in zip(roles, role_ids)])
            await ctx.send(f"인증 명령어 사용 역할 목록:\n{msg}")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 목록을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="화폐단위등록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_currency_unit(self, ctx, emoji: str):
        """Set the currency unit (emoji only)."""
        await balance_manager.set_currency_unit(emoji)
        await ctx.send(f"화폐 단위가 '{emoji}'로 설정되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 화폐 단위를 '{emoji}'로 설정. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="온채널추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_economy_channel(self, ctx, channel: discord.TextChannel = None):
        """온(경제) 명령어를 사용할 수 있는 채널을 추가합니다."""
        channel = channel or ctx.channel
        await balance_manager.add_allowed_channel(channel.id)
        await ctx.send(f"{channel.mention} 채널이 온(경제) 명령어 허용 채널로 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 '{channel.name}'({channel.id}) 추가. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="온채널제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_economy_channel(self, ctx, channel: discord.TextChannel = None):
        """온(경제) 명령어 허용 채널에서 제거합니다."""
        channel = channel or ctx.channel
        await balance_manager.remove_allowed_channel(channel.id)
        await ctx.send(f"{channel.mention} 채널이 온(경제) 명령어 허용 채널에서 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 '{channel.name}'({channel.id}) 제거. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="온채널목록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def list_economy_channels(self, ctx):
        """온(경제) 명령어 허용 채널 목록을 확인합니다."""
        ids = await balance_manager.list_allowed_channels()
        if not ids:
            await ctx.send("등록된 온(경제) 명령어 허용 채널이 없습니다.")
        else:
            mentions = [f"<#{cid}>" for cid in ids]
            await ctx.send("온(경제) 명령어 허용 채널 목록:\n" + ", ".join(mentions))
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 목록을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.command(name="온초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_all_balances(self, ctx):
        """모든 유저의 온(화폐) 잔액을 초기화합니다. (설정은 유지)"""
        await balance_manager.reset_all_balances()
        await ctx.send("모든 유저의 온(화폐) 잔액이 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 모든 유저의 온(화폐) 잔액 초기화. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @settings.group(name="수수료", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def fee(self, ctx):
        """수수료 설정 관련 명령어 출력 및 현재 수수료 구간 확인"""
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        fee_tiers = await balance_manager.get_fee_tiers()
        
        embed = discord.Embed(
            title="온 송금 수수료 명령어",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 현재 수수료 설정이다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯

사용 가능한 명령어:
`*온설정 수수료 설정 <최소금액> <수수료>` : 새로운 수수료 구간 추가
`*온설정 수수료 삭제 <최소금액>` : 수수료 구간 삭제
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )

        if fee_tiers:
            tiers_text = "\n".join([f"• {tier['min_amount']:,}{unit} 이상: {tier['fee']:,}{unit}" for tier in sorted(fee_tiers, key=lambda x: x['min_amount'])])
            embed.add_field(name="현재 수수료 구간", value=tiers_text, inline=False)
        else:
            embed.add_field(name="현재 수수료 구간", value="설정된 수수료 구간이 없습니다.", inline=False)
        
        await ctx.reply(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})이 수수료 목록을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @fee.command(name="설정")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_fee(self, ctx, min_amount: int, fee: int):
        """수수료 구간 설정"""
        if min_amount < 0 or fee < 0:
            await ctx.reply("최소 금액과 수수료는 0 이상이어야 합니다.")
            return
        
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        await balance_manager.set_fee_tier(min_amount, fee)
        
        await ctx.send(f"수수료 구간이 {min_amount:,}{unit} 이상 → {fee:,}{unit}로 설정되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 수수료 구간 설정: {min_amount:,}{unit} 이상 → {fee:,}{unit}")

    @fee.command(name="삭제")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def delete_fee(self, ctx, min_amount: int):
        """수수료 구간 삭제"""
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        success = await balance_manager.delete_fee_tier(min_amount)
        
        if success:
            await ctx.send(f"수수료 구간 {min_amount:,}{unit} 이상이 삭제되었습니다.")  
            await self.log(f"{ctx.author}({ctx.author.id})이 수수료 구간 삭제: {min_amount:,}{unit} 이상")
        else:
            await ctx.send(f"수수료 구간 {min_amount:,}{unit} 이상이 존재하지 않습니다.")
            await self.log(f"{ctx.author}({ctx.author.id})이 수수료 구간 삭제 시도: {min_amount:,}{unit} 이상")

    @settings.group(name="제한설정", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def limit(self, ctx):
        """일일 송금/수취 제한 설정 관련 명령어 그룹"""
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        send_limit, receive_limit = await balance_manager.get_daily_limits()
        
        embed = discord.Embed(
            title=f"{unit}、온 일일 제한 설정 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 현재 일일 제한 설정이다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯

사용 가능한 명령어:
`*온설정 제한설정 송금 <횟수>` : 일일 송금 횟수 제한 설정
`*온설정 제한설정 수취 <횟수>` : 일일 수취 횟수 제한 설정

현재 설정:
• 일일 송금 제한: {send_limit}회
• 일일 수취 제한: {receive_limit}회
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        await ctx.reply(embed=embed)

    @limit.command(name="송금")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_send_limit(self, ctx, limit: int):
        """일일 송금 횟수 제한 설정"""
        if limit <= 0:
            await ctx.reply("제한 횟수는 0보다 커야 합니다.")
            return
        
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        current_send, current_receive = await balance_manager.get_daily_limits()
        await balance_manager.set_daily_limits(limit, current_receive)
        
        await ctx.send(f"일일 송금 제한이 {limit}회로 설정되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 일일 송금 제한 설정: {limit}회")

    @limit.command(name="수취")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_receive_limit(self, ctx, limit: int):
        """일일 수취 횟수 제한 설정"""
        if limit <= 0:
            await ctx.reply("제한 횟수는 0보다 커야 합니다.")
            return
        
        unit = await balance_manager.get_currency_unit()
        unit = unit['emoji'] if unit else "코인"
        current_send, current_receive = await balance_manager.get_daily_limits()
        await balance_manager.set_daily_limits(current_send, limit)
        
        await ctx.send(f"일일 수취 제한이 {limit}회로 설정되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 일일 수취 제한 설정: {limit}회")


async def setup(bot):
    await bot.add_cog(OnAdminSettings(bot))