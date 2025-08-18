import discord
from discord.ext import commands, tasks
import json
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# =====================================================================================
# I. 기본 설정 (사용자 수정 필요)
# =====================================================================================

# !인증 명령어를 사용할 수 있는 역할의 이름을 지정하세요.
# 서버에 해당 이름을 가진 역할이 반드시 존재해야 합니다.
AUTH_ROLE_ID = "1396829213218181262"
GUILD_ID = [1396829213100605580, 1378632284068122685]

# 데이터 저장을 위한 파일 경로
DATA_DIR = "event_data"
SETTINGS_FILE = os.path.join(DATA_DIR, "leaderboard_settings.json")
DATA_FILE = os.path.join(DATA_DIR, "leaderboard_data.json")

def has_auth_role():
    async def predicate(ctx):
        if ctx.guild.id not in GUILD_ID:
            return False
        if ctx.author.guild_permissions.administrator:
            return True
        if AUTH_ROLE_ID in ctx.author.roles:
            return True
        await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        return False
    return commands.check(predicate)


# =====================================================================================
# II. 시간대 설정 (KST)
# =====================================================================================

# KST (UTC+9) 시간대 객체
KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    """현재 시각을 KST 기준으로 반환합니다."""
    return datetime.now(tz=KST)


# =====================================================================================
# III. 메인 Cog 클래스
# =====================================================================================

class Leaderboard(commands.Cog):
    """인증 횟수를 집계하고 순위표를 게시하는 기능을 담당합니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.settings = {}
        self.data = {}

        # 데이터 디렉토리 및 파일 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({}, f)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w') as f:
                json.dump({}, f)

        # 초기 데이터 로드
        self.load_data()
        
        # 순위표 자동 게시 태스크 시작
        self.leaderboard_poster.start()

    def cog_unload(self):
        """Cog 언로드 시 태스크를 중지합니다."""
        self.leaderboard_poster.cancel()
        
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

    # -----------------------------------------------------------------
    # 데이터 관리 (JSON)
    # -----------------------------------------------------------------

    def load_data(self):
        """설정 및 데이터 파일에서 정보를 불러옵니다."""
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            self.settings = json.load(f)
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    async def _save_settings(self):
        """설정 정보를 JSON 파일에 비동기적으로 저장합니다."""
        async with self._lock:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)

    async def _save_data(self):
        """유저 점수 정보를 JSON 파일에 비동기적으로 저장합니다."""
        async with self._lock:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)

    # -----------------------------------------------------------------
    # 사용자 명령어 (!인증)
    # -----------------------------------------------------------------

    @commands.command(name="인증")
    @has_auth_role()
    async def certify_user(self, ctx: commands.Context, member: discord.Member):
        """특정 유저의 인증 횟수를 1 증가시킵니다. (지정된 역할만 사용 가능)"""

        if member.bot:
            return await ctx.reply("봇은 인증할 수 없습니다.", ephemeral=True)

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        # 데이터베이스에 길드 및 유저 정보 초기화
        if guild_id not in self.data:
            self.data[guild_id] = {}
        if user_id not in self.data[guild_id]:
            self.data[guild_id][user_id] = 0

        # 인증 횟수 증가 및 저장
        self.data[guild_id][user_id] += 1
        await self._save_data()

        await ctx.reply(f"{member.mention} 님의 인증 횟수가 1 증가했습니다. (현재: {self.data[guild_id][user_id]}회)")

    # -----------------------------------------------------------------
    # 관리자 명령어 (!인증설정)
    # -----------------------------------------------------------------

    @commands.group(name="인증설정", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def leaderboard_settings(self, ctx: commands.Context):
        """인증 시스템 관련 설정을 관리합니다."""
        await ctx.reply("사용법: `*인증설정 지급 <유저> <횟수>`, `*인증설정 회수 <유저> <횟수>`, `*인증설정 순위채널 <채널>`")

    @leaderboard_settings.command(name="지급")
    @commands.has_permissions(administrator=True)
    async def grant_points(self, ctx: commands.Context, member: discord.Member, amount: int):
        """특정 유저에게 인증 횟수를 수동으로 지급합니다."""
        if amount <= 0:
            return await ctx.reply("지급할 횟수는 1 이상이어야 합니다.")

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in self.data:
            self.data[guild_id] = {}
        if user_id not in self.data[guild_id]:
            self.data[guild_id][user_id] = 0
        
        self.data[guild_id][user_id] += amount
        await self._save_data()
        await ctx.reply(f"{member.mention} 님에게 {amount}회의 인증 횟수를 지급했습니다. (현재: {self.data[guild_id][user_id]}회)")

    @leaderboard_settings.command(name="회수")
    @commands.has_permissions(administrator=True)
    async def revoke_points(self, ctx: commands.Context, member: discord.Member, amount: int):
        """특정 유저의 인증 횟수를 수동으로 회수합니다."""
        if amount <= 0:
            return await ctx.reply("회수할 횟수는 1 이상이어야 합니다.")

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        current_points = self.data.get(guild_id, {}).get(user_id, 0)
        
        final_points = max(0, current_points - amount)
        self.data[guild_id][user_id] = final_points
        await self._save_data()
        
        await ctx.reply(f"{member.mention} 님의 인증 횟수를 {amount}회 회수했습니다. (현재: {final_points}회)")

    @leaderboard_settings.command(name="순위채널")
    @commands.has_permissions(administrator=True)
    async def set_leaderboard_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """순위표가 게시될 채널을 설정합니다."""
        guild_id = str(ctx.guild.id)
        self.settings[guild_id] = {"leaderboard_channel_id": channel.id}
        await self._save_settings()
        await ctx.reply(f"순위표 게시 채널을 {channel.mention}으로 설정했습니다.")

    # -----------------------------------------------------------------
    # 순위표 자동 게시 (Task)
    # -----------------------------------------------------------------

    @tasks.loop(hours=1)
    async def leaderboard_poster(self):
        """매 시간 정각에 설정된 채널로 순위표를 전송합니다."""
        for guild_id_str, config in self.settings.items():
            channel_id = config.get("leaderboard_channel_id")
            if not channel_id:
                continue

            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                print(f"[Leaderboard] Guild {guild.name}의 채널(ID: {channel_id})을 찾을 수 없습니다.")
                continue

            # 채널의 기존 메시지 모두 삭제 (봇 권한 필요)
            try:
                async for msg in channel.history(limit=100):
                    await msg.delete()
            except Exception as e:
                print(f"[Leaderboard] 메시지 삭제 중 오류: {e}")

            # 길드의 점수 데이터 가져오기
            guild_data = self.data.get(guild_id_str, {})
            # 길드에 실제로 존재하는 멤버만 필터링
            filtered_users = []
            for user_id_str, points in guild_data.items():
                member = guild.get_member(int(user_id_str))
                if member is not None and not member.bot:
                    filtered_users.append((user_id_str, points))
            if not filtered_users:
                await channel.send("아직 인증 기록이 없습니다.")
                continue

            # 점수를 기준으로 내림차순 정렬
            sorted_users = sorted(filtered_users, key=lambda item: item[1], reverse=True)

            # 임베드 생성
            embed = discord.Embed(
                title="🍵 、찻자리 랭킹",
                description=f"{now_kst().strftime('%Y년 %m월 %d일 %H:%M')} 기준",
                color=discord.Color.green()
            )

            # 순위 목록 구성 (상위 10명)
            leaderboard_text = []
            rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            
            for i, (user_id_str, points) in enumerate(sorted_users[:10], 1):
                member = guild.get_member(int(user_id_str))
                member_name = member.mention if member else f"ID: {user_id_str}"
                rank_emoji = rank_emojis.get(i, f"`{i}.`")
                leaderboard_text.append(f"{rank_emoji} {member_name} - **{points}회**")

            embed.description += "\n\n" + "\n".join(leaderboard_text)
            embed.set_footer(text=f"요청 시각: {now_kst().strftime('%Y-%m-%d %H:%M:%S KST')}")

            await channel.send(embed=embed)

    @leaderboard_poster.before_loop
    async def before_leaderboard_poster(self):
        """루프가 시작되기 전, 다음 정시까지 대기합니다."""
        await self.bot.wait_until_ready()
        
        now = now_kst()
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        wait_seconds = (next_hour - now).total_seconds()
        
        print(f"다음 순위표 업데이트까지 {wait_seconds:.2f}초 대기합니다.")
        await asyncio.sleep(wait_seconds)


# =====================================================================================
# IV. Cog 등록 함수
# =====================================================================================

async def setup(bot: commands.Bot):
    """봇에 Leaderboard Cog를 추가합니다."""
    await bot.add_cog(Leaderboard(bot))