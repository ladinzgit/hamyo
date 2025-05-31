import discord
from discord.ext import commands
from balance_data_manager import balance_manager

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
                "`*온설정 인증역할추가 @역할` : 인증/지급/회수 명령어 사용 권한 역할을 추가합니다.\n"
                "`*온설정 인증역할제거 @역할` : 인증 명령어 사용 권한 역할을 제거합니다.\n"
                "`*온설정 인증역할목록` : 등록된 인증 명령어 사용 역할 목록을 확인합니다."
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
        await self.log(f"{ctx.author}({ctx.author.id})이 온설정 명령어 도움말을 조회함.")

    @settings.command(name="인증추가")
    @commands.has_permissions(administrator=True)
    async def add_auth_condition(self, ctx, condition: str, reward_amount: int):
        """Add an authentication condition (auth item) with reward amount."""
        await balance_manager.add_auth_item(condition, reward_amount)
        await ctx.send(f"인증 조건 '{condition}'(보상: {reward_amount})이(가) 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 '{condition}'(보상: {reward_amount}) 추가.")

    @settings.command(name="인증제거")
    @commands.has_permissions(administrator=True)
    async def remove_auth_condition(self, ctx, *, condition: str):
        """Remove an authentication condition (auth item)."""
        await balance_manager.remove_auth_item(condition)
        await ctx.send(f"인증 조건 '{condition}'이(가) 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 '{condition}' 제거.")

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
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 조건 목록을 조회함.")

    @settings.command(name="인증역할추가")
    @commands.has_permissions(administrator=True)
    async def add_auth_role(self, ctx, role: discord.Role):
        """Add a role that can use 인증/지급/회수 명령어."""
        await balance_manager.add_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할로 '{role.name}'이(가) 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 '{role.name}'({role.id}) 추가.")

    @settings.command(name="인증역할제거")
    @commands.has_permissions(administrator=True)
    async def remove_auth_role(self, ctx, role: discord.Role):
        """Remove a role from 인증 명령어 사용 역할."""
        await balance_manager.remove_auth_role(role.id)
        await ctx.send(f"인증 명령어 사용 역할에서 '{role.name}'이(가) 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 '{role.name}'({role.id}) 제거.")

    @settings.command(name="인증역할목록")
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
        await self.log(f"{ctx.author}({ctx.author.id})이 인증 명령어 사용 역할 목록을 조회함.")

    @settings.command(name="화폐단위등록")
    @commands.has_permissions(administrator=True)
    async def set_currency_unit(self, ctx, emoji: str):
        """Set the currency unit (emoji only)."""
        await balance_manager.set_currency_unit(emoji)
        await ctx.send(f"화폐 단위가 '{emoji}'로 설정되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 화폐 단위를 '{emoji}'로 설정.")

    @settings.command(name="온채널추가")
    @commands.has_permissions(administrator=True)
    async def add_economy_channel(self, ctx, channel: discord.TextChannel = None):
        """온(경제) 명령어를 사용할 수 있는 채널을 추가합니다."""
        channel = channel or ctx.channel
        await balance_manager.add_allowed_channel(channel.id)
        await ctx.send(f"{channel.mention} 채널이 온(경제) 명령어 허용 채널로 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 '{channel.name}'({channel.id}) 추가.")

    @settings.command(name="온채널제거")
    @commands.has_permissions(administrator=True)
    async def remove_economy_channel(self, ctx, channel: discord.TextChannel = None):
        """온(경제) 명령어 허용 채널에서 제거합니다."""
        channel = channel or ctx.channel
        await balance_manager.remove_allowed_channel(channel.id)
        await ctx.send(f"{channel.mention} 채널이 온(경제) 명령어 허용 채널에서 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 '{channel.name}'({channel.id}) 제거.")

    @settings.command(name="온채널목록")
    @commands.has_permissions(administrator=True)
    async def list_economy_channels(self, ctx):
        """온(경제) 명령어 허용 채널 목록을 확인합니다."""
        ids = await balance_manager.list_allowed_channels()
        if not ids:
            await ctx.send("등록된 온(경제) 명령어 허용 채널이 없습니다.")
        else:
            mentions = [f"<#{cid}>" for cid in ids]
            await ctx.send("온(경제) 명령어 허용 채널 목록:\n" + ", ".join(mentions))
        await self.log(f"{ctx.author}({ctx.author.id})이 온(경제) 명령어 허용 채널 목록을 조회함.")

    @settings.command(name="온초기화")
    @commands.has_permissions(administrator=True)
    async def reset_all_balances(self, ctx):
        """모든 유저의 온(화폐) 잔액을 초기화합니다. (설정은 유지)"""
        await balance_manager.reset_all_balances()
        await ctx.send("모든 유저의 온(화폐) 잔액이 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})이 모든 유저의 온(화폐) 잔액 초기화.")


async def setup(bot):
    await bot.add_cog(OnAdminSettings(bot))