import discord
from discord.ext import commands, tasks
from datetime import datetime
from DataManager import DataManager
from voice_utils import get_expanded_tracked_channels as expand_tracked 
import asyncio
import time
import pytz

KST = pytz.timezone("Asia/Seoul")

class VoiceTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.join_times = {}  # {user_id: {channel_id: join_time}}
        bot.loop.create_task(self.data_manager.initialize())
        self.track_voice_time.start()
        # --- 추가: 음성 퀘스트 지급 여부 메모리 관리 ---
        self.voice_quest_daily_given = set()  # (user_id, date)
        self.voice_quest_weekly_given = {}    # user_id: set([5, 10, 20])  # 시간 단위
        self.voice_1h_tracker = set() # user_id set for today
        self.current_date_str = datetime.now(KST).strftime("%Y-%m-%d")
        self._tracked_voice_cache = None
        self._tracked_voice_cache_at = 0  # epoch seconds

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
            
    async def _get_tracked_voice_ids_cached(self, ttl: int = 600) -> set[int]:
        now_ts = time.time()
        if self._tracked_voice_cache and (now_ts - self._tracked_voice_cache_at) < ttl:
            return self._tracked_voice_cache
        ids = set(await expand_tracked(self.bot, self.data_manager, "voice"))
        self._tracked_voice_cache = ids
        self._tracked_voice_cache_at = now_ts
        return ids

    def get_all_voice_channels(self):
        channels = []
        for guild in self.bot.guilds:
            channels.extend(getattr(guild, "voice_channels", []))
            channels.extend(getattr(guild, "stage_channels", []))  
        return channels
    
    def invalidate_tracked_voice_cache(self):
        self._tracked_voice_cache = None
        self._tracked_voice_cache_at = 0

    @tasks.loop(minutes=1)
    async def track_voice_time(self):
        now = datetime.now(KST)
        channels = self.get_all_voice_channels()

        for channel in channels:
            for member in channel.members:
                if member.bot:
                    continue

                user_id = member.id
                channel_id = channel.id

                if user_id not in self.join_times:
                    self.join_times[user_id] = {}

                if channel_id not in self.join_times[user_id]:
                    self.join_times[user_id][channel_id] = now
                    continue

                join_time = self.join_times[user_id][channel_id]

                if join_time.date() != now.date():
                    midnight = join_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    duration1 = int((midnight - join_time).total_seconds())
                    duration2 = int((now - next_day).total_seconds())

                    if duration1 > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration1)
                    if duration2 > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration2)

                    self.join_times[user_id][channel_id] = next_day
                else:
                    duration = int((now - join_time).total_seconds())
                    if duration > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration)
                        self.join_times[user_id][channel_id] = now

        await self.process_voice_quests()

    async def process_voice_quests(self):
        """
        음성방 30분(일일), 5/10/20시간(주간) 퀘스트 경험치 지급
        """
        level_checker = self.bot.get_cog('LevelChecker')
        if not level_checker:
            return

        # 추적 채널 목록 확보 (캐시가 있으면 사용, 없으면 유틸 함수로 확장)
        try:
            tracked_channel_ids = set(await self._get_tracked_voice_ids_cached())
        except AttributeError:
            # 캐시 헬퍼가 없는 경우 폴백
            from voice_utils import get_expanded_tracked_channels as expand_tracked
            tracked_channel_ids = set(await expand_tracked(self.bot, self.data_manager, "voice"))
            
        if not tracked_channel_ids:
            return

        now = datetime.now(KST)
        user_ids = list(self.join_times.keys())
        
        for uid in user_ids:
            try:
                # === 일간(오늘) 누적 초 ===
                day_map, _, _ = await self.data_manager.get_user_times(
                    user_id=uid,
                    period="일간",
                    base_date=now,
                    channel_filter=list(tracked_channel_ids)
                )
                daily_secs = sum(day_map.values()) if day_map else 0

                if daily_secs >= 30 * 60:
                    # 일일 30분 달성 → 중복 여부는 LevelChecker가 내부적으로 판단
                    await level_checker.process_voice_30min(uid)

                # 일일 1시간 달성
                now_str = now.strftime("%Y-%m-%d")
                if self.current_date_str != now_str:
                    self.voice_1h_tracker.clear()
                    self.current_date_str = now_str
                    
                if daily_secs >= 60 * 60 and uid not in self.voice_1h_tracker:
                    self.voice_1h_tracker.add(uid)
                    self.bot.dispatch('mission_completion', uid, 'voice_1h', None)

                # === 주간 누적 초 ===
                week_map, _, _ = await self.data_manager.get_user_times(
                    user_id=uid,
                    period="주간",
                    base_date=now,
                    channel_filter=list(tracked_channel_ids)
                )
                weekly_secs = sum(week_map.values()) if week_map else 0

                # 주간 5/10/20h 달성도 순차 검사 (중복 방지는 LevelChecker가 처리)
                for h in (5, 10, 20):
                    if weekly_secs >= h * 3600:
                        await level_checker.process_voice_weekly(uid, h)
            except Exception as e:
                # 한 유저에서 에러가 나도 다른 유저 진행은 계속
                try:
                    await self.log(f"음성방 퀘스트 처리에서 유저 - {uid} 처리 중 오류: {e}")
                except Exception:
                    pass
                        
    async def process_voice_quests_for_users(self, user_ids: set[int]):
        """
        음성방 30분(일일), 5/10/20시간(주간) 퀘스트 경험치 지급
        """
        if not user_ids:
            return
        
        level_checker = self.bot.get_cog('LevelChecker')
        if not level_checker:
            return

        # 추적 채널 목록 확보 (캐시가 있으면 사용, 없으면 유틸 함수로 확장)
        try:
            tracked_channel_ids = set(await self._get_tracked_voice_ids_cached())
        except AttributeError:
            # 캐시 헬퍼가 없는 경우 폴백
            from voice_utils import get_expanded_tracked_channels as expand_tracked
            tracked_channel_ids = set(await expand_tracked(self.bot, self.data_manager, "voice"))
            
        if not tracked_channel_ids:
            return

        now = datetime.now(KST)
        for uid in user_ids:
            try:
                # === 일간(오늘) 누적 초 ===
                day_map, _, _ = await self.data_manager.get_user_times(
                    user_id=uid,
                    period="일간",
                    base_date=now,
                    channel_filter=list(tracked_channel_ids)
                )
                daily_secs = sum(day_map.values()) if day_map else 0

                if daily_secs >= 30 * 60:
                    # 일일 30분 달성 → 중복 여부는 LevelChecker가 내부적으로 판단
                    await level_checker.process_voice_30min(uid)

                # === 주간 누적 초 ===
                week_map, _, _ = await self.data_manager.get_user_times(
                    user_id=uid,
                    period="주간",
                    base_date=now,
                    channel_filter=list(tracked_channel_ids)
                )
                weekly_secs = sum(week_map.values()) if week_map else 0

                # 주간 5/10/20h 달성도 순차 검사 (중복 방지는 LevelChecker가 처리)
                for h in (5, 10, 20):
                    if weekly_secs >= h * 3600:
                        await level_checker.process_voice_weekly(uid, h)
            except Exception as e:
                # 한 유저에서 에러가 나도 다른 유저 진행은 계속
                try:
                    await self.log(f"음성방 퀘스트 처리에서 유저 - {uid} 처리 중 오류: {e}")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)) and channel.category_id:
            await self.data_manager.register_deleted_channel(channel.id, channel.category_id)
            
            category_name = channel.category.name if channel.category else f"UnknownCategory({channel.category_id})"
            
            await self.log(
                f"추적된 카테고리 {category_name}의 음성/스테이지 채널 {channel.name}({channel.id})이 삭제되었습니다. [길드: {channel.guild.name}({channel.guild.id})] [시스템]"
            )
            # 추적 채널 캐시 무효화
            self.invalidate_tracked_voice_cache()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot or before.channel == after.channel:
                return

            now = datetime.now(KST)

            # 나간 채널 처리
            if before.channel:
                if member.id in self.join_times and before.channel.id in self.join_times[member.id]:
                    join_time = self.join_times[member.id][before.channel.id]

                    if join_time.date() != now.date():
                        midnight = join_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                        duration1 = int((midnight - join_time).total_seconds())
                        duration2 = int((now - next_day).total_seconds())

                        if duration1 > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration1)
                        if duration2 > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration2)
                    else:
                        duration = int((now - join_time).total_seconds())
                        if duration > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration)

                    del self.join_times[member.id][before.channel.id]

            # 입장한 채널 등록
            if after.channel:
                if member.id not in self.join_times:
                    self.join_times[member.id] = {}
                self.join_times[member.id][after.channel.id] = now
            else:
                await self.process_voice_quests_for_users({member.id}) # 나간 유저에 대해 음성 퀘스트 처리
        except Exception as e:
            print(e)
    @commands.command()
    async def check_all_time(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        data = await self.data_manager.get_user_times(user.id, "누적")
        times, start, end = data
        if not times:
            return await ctx.send(f"{user.display_name}님의 누적 기록이 없습니다.")

        total_seconds = sum(times.values())
        d, r = divmod(total_seconds, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        await ctx.send(f"{user.display_name}님의 전체 기록: {d}일 {h}시간 {m}분 {s}초")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceTracker(bot))