"""
서버의 모든 멤버에게 DM을 일괄 전송하는 관리자 전용 모듈입니다.
"""
import discord
from discord.ext import commands
import asyncio
from src.core.admin_utils import is_guild_admin


class BulkDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}  # {(user_id, channel_id): True}

    async def cog_load(self):
        try:
            print(f"✅ {self.__class__.__name__} loaded successfully!")
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로드 중 오류 발생: {e}")

    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        logger = self.bot.get_cog('Logger')
        if logger:
            await logger.log(message, title="⚙️ 관리자 시스템 로그", color=discord.Color.dark_red())

    def create_progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """진행률 바를 생성합니다."""
        if total == 0:
            return "░" * length
        filled = int(length * current / total)
        return "█" * filled + "░" * (length - filled)

    def build_initial_embed(self, guild: discord.Guild, target_count: int) -> discord.Embed:
        """초기 안내 embed를 생성합니다."""
        embed = discord.Embed(
            title="📤 DM 일괄전송 모드",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="서버",
            value=guild.name,
            inline=True
        )
        embed.add_field(
            name="대상",
            value=f"{target_count}명 (봇 제외)",
            inline=True
        )
        embed.add_field(
            name="━━━━━━━━━━━━━━━━",
            value="💡 보낼 메시지를 입력해주세요.\n⚠️ `취소`를 입력하면 명령어가 종료됩니다.",
            inline=False
        )
        return embed

    def build_progress_embed(self, current: int, total: int, success: int, failed: int) -> discord.Embed:
        """진행 상태 embed를 생성합니다."""
        percentage = int(current / total * 100) if total > 0 else 0
        progress_bar = self.create_progress_bar(current, total)
        
        embed = discord.Embed(
            title="📤 DM 전송 중...",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="진행률",
            value=f"{progress_bar} {percentage}% ({current}/{total})",
            inline=False
        )
        embed.add_field(
            name="현재 상태",
            value=f"✅ 성공: {success}명 | ❌ 실패: {failed}명",
            inline=False
        )
        return embed

    def build_complete_embed(self, guild_name: str, success: int, failed: int) -> discord.Embed:
        """완료 embed를 생성합니다."""
        embed = discord.Embed(
            title="✅ DM 전송 완료",
            color=discord.Color.green()
        )
        embed.add_field(
            name="서버",
            value=guild_name,
            inline=False
        )
        embed.add_field(
            name="전송 결과",
            value=f"✅ 성공: {success}명\n❌ 실패: {failed}명",
            inline=False
        )
        return embed

    def build_cancel_embed(self) -> discord.Embed:
        """취소 embed를 생성합니다."""
        embed = discord.Embed(
            title="❌ DM 전송 취소됨",
            description="명령어가 취소되었습니다.",
            color=discord.Color.red()
        )
        return embed

    @commands.command(name="DM일괄전송")
    @is_guild_admin()
    async def bulk_dm(self, ctx):
        """서버의 모든 멤버에게 DM을 일괄 전송합니다."""
        session_key = (ctx.author.id, ctx.channel.id)
        
        # 이미 세션이 진행 중인지 확인
        if session_key in self.active_sessions:
            await ctx.send("❌ 이미 DM 전송 세션이 진행 중입니다.")
            return

        # 봇이 아닌 멤버 목록
        members = [m for m in ctx.guild.members if not m.bot]
        target_count = len(members)

        if target_count == 0:
            await ctx.send("❌ 전송 대상이 없습니다.")
            return

        self.active_sessions[session_key] = True

        try:
            # 초기 안내 embed 전송
            initial_embed = self.build_initial_embed(ctx.guild, target_count)
            status_msg = await ctx.send(embed=initial_embed)

            await self.log(
                f"DM 일괄전송 모드 시작 - {ctx.author}({ctx.author.id}) "
                f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id}), 대상: {target_count}명]"
            )

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                # 사용자 메시지 대기 (5분 타임아웃)
                msg = await self.bot.wait_for('message', check=check, timeout=300.0)
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ 시간 초과",
                    description="5분 동안 입력이 없어 명령어가 종료되었습니다.",
                    color=discord.Color.red()
                )
                await status_msg.edit(embed=timeout_embed)
                await self.log(
                    f"DM 일괄전송 시간 초과 - {ctx.author}({ctx.author.id}) "
                    f"[길드: {ctx.guild.name}({ctx.guild.id})]"
                )
                return

            # 취소 처리
            if msg.content == "취소":
                cancel_embed = self.build_cancel_embed()
                await status_msg.edit(embed=cancel_embed)
                await self.log(
                    f"DM 일괄전송 취소됨 - {ctx.author}({ctx.author.id}) "
                    f"[길드: {ctx.guild.name}({ctx.guild.id})]"
                )
                return

            # DM 전송 시작
            dm_content = msg.content
            success_count = 0
            failed_count = 0

            # 진행률 업데이트 간격 (10% 또는 최소 1명)
            update_interval = max(1, target_count // 10)

            for i, member in enumerate(members, 1):
                try:
                    await member.send(dm_content)
                    success_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    failed_count += 1

                # 진행률 업데이트
                if i % update_interval == 0 or i == target_count:
                    progress_embed = self.build_progress_embed(i, target_count, success_count, failed_count)
                    await status_msg.edit(embed=progress_embed)

                # Rate limit 방지를 위한 딜레이
                await asyncio.sleep(0.5)

            # 완료 embed
            complete_embed = self.build_complete_embed(ctx.guild.name, success_count, failed_count)
            await status_msg.edit(embed=complete_embed)

            await self.log(
                f"DM 일괄전송 완료 - {ctx.author}({ctx.author.id}) "
                f"[길드: {ctx.guild.name}({ctx.guild.id}), 성공: {success_count}명, 실패: {failed_count}명]"
            )

        finally:
            # 세션 정리
            self.active_sessions.pop(session_key, None)

    async def cog_command_error(self, ctx, error):
        print(f"{self.__class__.__name__} cog에서 오류 발생: {error}")
        await self.log(
            f"{self.__class__.__name__} cog에서 오류 발생: {error} "
            f"[길드: {ctx.guild.name if ctx.guild else 'DM'}, 채널: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'}({ctx.channel.id})]"
        )


async def setup(bot):
    await bot.add_cog(BulkDM(bot))
