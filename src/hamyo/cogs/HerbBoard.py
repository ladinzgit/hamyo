import discord
from discord.ext import commands, tasks
import json
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from DataManager import DataManager
from voice_utils import get_herb_expanded_tracked_channels

# 기본 설정
GUILD_ID = [1396829213100605580, 1378632284068122685]

# 데이터 저장을 위한 파일 경로
DATA_DIR = "event_data"
HERB_BOARD_SETTINGS_FILE = os.path.join(DATA_DIR, "herb_board_settings.json")

# KST (UTC+9) 시간대 객체
KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    """현재 시각을 KST 기준으로 반환합니다."""
    return datetime.now(tz=KST)

def has_admin_role():
    async def predicate(ctx):
        if ctx.guild.id not in GUILD_ID:
            return False
        if ctx.author.guild_permissions.administrator:
            return True
        await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        return False
    return commands.check(predicate)

class HerbBoard(commands.Cog):
    """허브 채널 사용 시간 기반 순위표를 관리하는 기능을 담당합니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.settings = {}
        self.data_manager = DataManager()

        # 데이터 디렉토리 및 파일 생성
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(HERB_BOARD_SETTINGS_FILE):
            with open(HERB_BOARD_SETTINGS_FILE, 'w') as f:
                json.dump({}, f)

        # 초기 데이터 로드
        self.load_settings()
        
        # 순위표 자동 게시 태스크 시작
        self.herb_board_poster.start()

    def cog_unload(self):
        """Cog 언로드 시 태스크를 중지합니다."""
        self.herb_board_poster.cancel()
        
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

    def load_settings(self):
        """설정 파일에서 정보를 불러옵니다."""
        with open(HERB_BOARD_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            self.settings = json.load(f)

    async def _save_settings(self):
        """설정 정보를 JSON 파일에 비동기적으로 저장합니다."""
        async with self._lock:
            with open(HERB_BOARD_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def calculate_points(self, seconds: int) -> int:
        """음성 채널 사용 시간을 점수로 변환 (1분당 2점, 초 단위 내림)"""
        minutes = seconds // 60
        return minutes * 2

    def format_duration(self, total_seconds: int) -> str:
        """시간을 포맷팅합니다."""
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}일 {hours}시간 {minutes}분 {seconds}초 ({self.calculate_points(total_seconds)}점)"

    @commands.group(name="허브순위설정", invoke_without_command=True)
    @has_admin_role()
    async def herb_board_settings(self, ctx: commands.Context):
        """허브 순위표 관련 설정을 관리합니다."""
        await ctx.reply("사용법: `*허브순위설정 순위채널 <채널>`")

    @herb_board_settings.command(name="순위채널")
    @has_admin_role()
    async def set_herb_board_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """허브 순위표가 게시될 채널을 설정합니다."""
        guild_id = str(ctx.guild.id)
        self.settings[guild_id] = {"herb_board_channel_id": channel.id}
        await self._save_settings()
        await ctx.reply(f"허브 순위표 게시 채널을 {channel.mention}으로 설정했습니다.")

    @tasks.loop(hours=1)
    async def herb_board_poster(self):
        """매 시간 정각에 설정된 채널로 허브 순위표를 전송합니다."""
        for guild_id_str, config in self.settings.items():
            channel_id = config.get("herb_board_channel_id")
            if not channel_id:
                continue

            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                await self.log(f"Guild {guild.name}의 채널(ID: {channel_id})을 찾을 수 없습니다.")
                continue

            # 채널의 기존 메시지 모두 삭제 (봇 권한 필요)
            try:
                async for msg in channel.history(limit=100):
                    await msg.delete()
            except Exception as e:
                await self.log(f"메시지 삭제 중 오류: {e}")

            # 허브 추적 채널 목록 가져오기
            try:
                tracked_channels = await get_herb_expanded_tracked_channels(self.bot, self.data_manager, "aginari")
                
                # 당일 데이터 가져오기
                from datetime import datetime
                import pytz
                tz = pytz.timezone('Asia/Seoul')
                today = datetime.now(tz)
                
                all_data, start_date, end_date = await self.data_manager.get_all_users_times("주간", today, tracked_channels)
                
                # 유저별 총 시간 계산 및 정렬
                user_totals = [(uid, sum(times.values())) for uid, times in all_data.items()]
                ranked = sorted(user_totals, key=lambda x: x[1], reverse=True)
                
                # 길드에 실제로 존재하는 멤버만 필터링
                filtered_ranked = []
                for uid, total_seconds in ranked:
                    member = guild.get_member(uid)
                    if member is not None and not member.bot:
                        filtered_ranked.append((uid, total_seconds))
                
                if not filtered_ranked:
                    await channel.send("이번 주 허브 채널 사용 기록이 없습니다.")
                    continue

                start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
                end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"
                 
                # 임베드 생성
                embed = discord.Embed(
                    title="🌿 허브 채널 사용 시간 순위",
                    description=f"주간({start_str} ~ {end_str}) 기준",
                    color=discord.Color.green()
                )

                # 순위 목록 구성 (상위 10명)
                rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
                
                for i, (uid, total_seconds) in enumerate(filtered_ranked[:10], 1):
                    member = guild.get_member(uid)
                    member_name = member.mention if member else f"ID: {uid}"
                    rank_emoji = rank_emojis.get(i, f"`{i}.`")
                    
                    embed.add_field(
                        name=f"{rank_emoji} {i}위",
                        value=f"{member_name}\n{self.format_duration(total_seconds)}",
                        inline=True if i <= 3 else False
                    )

                embed.set_footer(text=f"업데이트 시각: {now_kst().strftime('%Y-%m-%d %H:%M:%S KST')}")

                await channel.send(embed=embed)

            except Exception as e:
                await self.log(f"순위표 생성 중 오류: {e}")
                await channel.send("순위표 생성 중 오류가 발생했습니다.")

    @herb_board_poster.before_loop
    async def before_herb_board_poster(self):
        """루프가 시작되기 전, 다음 정시까지 대기합니다."""
        await self.bot.wait_until_ready()
        
        now = now_kst()
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        wait_seconds = (next_hour - now).total_seconds()
        
        await self.log(f"다음 허브 순위표 업데이트까지 {wait_seconds:.2f}초 대기합니다.")
        await asyncio.sleep(wait_seconds)

async def setup(bot: commands.Bot):
    """봇에 HerbBoard Cog를 추가합니다."""
    await bot.add_cog(HerbBoard(bot))
