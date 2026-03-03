import discord
from discord.ext import commands
from src.core.LevelDataManager import LevelDataManager
from src.level.LevelConstants import ROLE_IDS, ROLE_THRESHOLDS, ROLE_ORDER, ROLE_DISPLAY, VOICE_WEEKLY_THRESHOLDS, get_role_info
from src.core.DataManager import DataManager
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import json, os
import pytz
from src.core.voice_utils import get_filtered_tracked_channels 
import time

CONFIG_PATH = "config/level_config.json"
KST = pytz.timezone("Asia/Seoul")
import re

from src.core.admin_utils import GUILD_IDS

    
def extract_name(text: str) -> str:
    if not text: return ""
    name = re.sub(r"^[《『][^》』]+[》』]\s*", "", text)
    name = re.sub(r"^[&!]\s*", "", name)
    return name.strip() or text
    
def _load_levelcfg():
    if not os.path.exists(CONFIG_PATH):
        return {"guilds": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def in_myinfo_allowed_channel():
    def check():
        async def predicate(ctx: commands.Context):
            # DM이나 길드 없는 곳에서는 막음
            if not ctx.guild:
                return False
            
            if ctx.guild.id not in GUILD_IDS:
                return False

            # 관리자 무시
            if ctx.author.guild_permissions.administrator:
                return True

            cfg = _load_levelcfg()
            allowed = cfg.get("guilds", {}).get(str(ctx.guild.id), {}).get("my_info_channels", [])

            # 설정이 비어 있으면 전체 허용
            if not allowed:
                return True

            return ctx.channel.id in allowed
        return commands.check(predicate)
    return check()

class LevelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        self.voice_data_manager = DataManager()
        self.logger = logging.getLogger(__name__)
        self._tracked_voice_cache = None
        self._tracked_voice_cache_at = 0  # epoch seconds

        self.role_info = get_role_info()
        self.role_order = ROLE_ORDER
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.initialize_database()
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
            
    async def _get_tracked_voice_ids_cached(self, ttl: int = 600) -> set[int]:
        now_ts = time.time()
        if self._tracked_voice_cache and (now_ts - self._tracked_voice_cache_at) < ttl:
            return self._tracked_voice_cache
        ids = set(await get_filtered_tracked_channels(self.bot, self.voice_data_manager, "voice"))
        self._tracked_voice_cache = ids
        self._tracked_voice_cache_at = now_ts
        return ids
    
    def _get_progress_info(self, total_exp: int, current_role_key: str) -> tuple:
        """현재 역할에 따른 진행률, 다음 마일스톤 등 계산"""
        role_thresholds = ROLE_THRESHOLDS
        role_order = ROLE_ORDER
        
        current_idx = role_order.index(current_role_key) if current_role_key in role_order else 0
        current_floor = role_thresholds.get(role_order[current_idx], 0)
        next_idx = min(current_idx + 1, len(role_order) - 1)
        next_key = role_order[next_idx]
        next_floor = role_thresholds.get(next_key, current_floor)

        if next_floor == current_floor:
            percent = 100
            need_to_next = 0
        else:
            gained_in_tier = max(0, total_exp - current_floor)
            tier_span = max(1, next_floor - current_floor)
            percent = int((gained_in_tier / tier_span) * 100)
            need_to_next = max(0, next_floor - total_exp)

        bar_len = 5
        filled = min(bar_len, max(0, int(percent / (100 / bar_len))))
        bar = "▫️" * filled + "◾️" * (bar_len - filled)
        
        return percent, need_to_next, bar

    async def _get_quest_stats(self, user_id: int, tracked_channel_ids: set) -> dict:
        """유저의 일일/주간 퀘스트, 음성 활동 정보를 집계하여 반환"""
        level_checker = self.bot.get_cog("LevelChecker")
        data_manager = getattr(self, "data_manager", None) or getattr(level_checker, "data_manager", None)
        
        async def _safe_get_quest(qtype, subtype, scope):
            if hasattr(data_manager, "get_quest_count"):
                return await data_manager.get_quest_count(user_id, qtype, subtype, scope)
            return 0

        stats = {}
        # 일일 퀘스트
        stats['att_daily'] = await _safe_get_quest('daily', 'attendance', 'day')
        stats['diary_daily'] = await _safe_get_quest('daily', 'diary', 'day')
        stats['call_daily'] = await _safe_get_quest('daily', 'call', 'day')
        stats['friend_daily'] = await _safe_get_quest('daily', 'friend', 'day')
        stats['first_sentence_daily'] = await _safe_get_quest('daily', 'first_sentence', 'day')
        
        # 주간 퀘스트
        stats['att_week'] = await _safe_get_quest('daily', 'attendance', 'week')
        stats['diary_week'] = await _safe_get_quest('daily', 'diary', 'week')
        stats['recommend_week'] = await _safe_get_quest('weekly', 'recommend', 'week')
        stats['board_week'] = await _safe_get_quest('weekly', 'board_participate', 'week')
        stats['shop_week'] = await _safe_get_quest('weekly', 'shop_purchase', 'week')
        
        # 음성 활동
        voice_sec_day = 0
        voice_sec_week = 0
        now = datetime.now(KST)
        if hasattr(self.voice_data_manager, "get_user_times") and tracked_channel_ids:
            day_result, _, _ = await self.voice_data_manager.get_user_times(
                user_id = user_id, period='일간', base_date=now, channel_filter=list(tracked_channel_ids))
            voice_sec_day = sum(day_result.values()) if day_result else 0
            
            week_result, _, _ = await self.voice_data_manager.get_user_times(
                user_id = user_id, period='주간', base_date=now, channel_filter=list(tracked_channel_ids))
            voice_sec_week = sum(week_result.values()) if week_result else 0
            
        stats['voice_sec_day'] = voice_sec_day
        stats['voice_sec_week'] = voice_sec_week
        stats['voice_min_daily'] = voice_sec_day // 60
        stats['voice_min_week'] = voice_sec_week // 60
        stats['voice_hour_week'] = stats['voice_min_week'] // 60
        stats['voice_rem_min_week'] = stats['voice_min_week'] % 60
        
        # 주간 랭킹 / 획득
        stats['weekly_total'] = await data_manager.get_user_period_exp(user_id, 'weekly')
        stats['weekly_rank'] = await data_manager.get_user_period_rank(user_id, 'weekly')
        
        return stats

    async def _build_myinfo_embed(self, ctx, member, user_data, ranks, stats, progress) -> discord.Embed:
        """내정보 임베드 생성"""
        total_exp = int(user_data.get("total_exp", 0)) if user_data else 0
        current_role_key = user_data.get("current_role", "yeobaek") if user_data else "yeobaek"
        
        level_checker = self.bot.get_cog("LevelChecker")
        role_obj = ctx.guild.get_role(ROLE_IDS.get(current_role_key, ROLE_IDS['yeobaek']))
        current_role_mention = role_obj.mention if role_obj else ROLE_DISPLAY.get(current_role_key, current_role_key)
        
        percent, need_to_next, bar = progress
        voice_lv, chat_lv = ranks
        
        next_voice_lv = ((voice_lv // 5) + 1) * 5 if voice_lv % 5 != 0 else voice_lv + 5
        next_chat_lv = ((chat_lv // 5) + 1) * 5 if chat_lv % 5 != 0 else chat_lv + 5
        
        embed_color = await level_checker._get_role_color(current_role_key, ctx.guild) if hasattr(level_checker, "_get_role_color") else discord.Color.blue()
        embed = discord.Embed(
            title=f"🌙 、{extract_name(member.display_name)} 님의 집필 현황⠀",
            color=embed_color
        )
        
        embed.add_field(
            name="🪵◝. 엮여가는 당신의 책갈피",
            value=(
                f"> {current_role_mention} ( {total_exp:,} 쪽 ) \n"
                f"> ⠀{bar}: {percent:02d}%\n"
                f"> -# ⠀◟. 다음 이야기가 펼쳐지기까지 {need_to_next:,} 쪽"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⠀\n📜◝. 지난 발자취\n\n˚‧ 📔: 목소리와 활자의 깊이",
            value=(
                f"> 음성 : {voice_lv} Lv  \n"
                f"> 채팅 : {chat_lv} Lv \n"
                f"> -# ◟. 한 단계 더 깊어지기까지 보이스 {next_voice_lv - voice_lv} Lv / 채팅 {next_chat_lv - chat_lv} Lv "
            ),
            inline=False
        )
        
        ox = lambda done: ":o:" if done else ":x:"
        
        embed.add_field(
            name="˚‧ 📆 : 오늘 그려낸 구절들",
            value=(
                f"> 출석체크 : {ox(stats['att_daily'] >= 1)} \n"
                f"> 첫 문장 작성 : {ox(stats.get('first_sentence_daily', 0) >= 1)} \n"
                f"> 책방일지 : {ox(stats['diary_daily'] >= 1)} \n"
                f"> 통화할래 : {ox(stats['call_daily'] >= 1)}\n"
                f"> 친구할래 : {ox(stats['friend_daily'] >= 1)}\n"
                f"> 음성활동 : {stats['voice_min_daily']}분 / 30분 ({ox(stats['voice_min_daily'] >= 30)})"
            ),
            inline=False
        )
        
        next_step = "모든 퀘스트를 달성했습니다!"
        for threshold_sec, threshold_label in VOICE_WEEKLY_THRESHOLDS:
            if stats['voice_sec_week'] < threshold_sec:
                next_step = threshold_label
                break
                
        weekly_lines = [
            f"> 출석체크 : {stats['att_week']} / 7",
            f"> 책방추천 : {stats['recommend_week']} / 3",
            f"> 책방일지 : {stats['diary_week']} / 7",
            f"> 음성활동 : {stats['voice_hour_week']}시간 {stats['voice_rem_min_week']}분 / {next_step}",
            f"> 상점구매 : {stats['shop_week']} / 1",
            f"> 게시판이용 : {stats['board_week']} / 3"
        ]
        
        embed.add_field(
            name="˚‧ 🗓️ : 이번 주 엮어낸 페이지",
            value="\n".join(weekly_lines) + f"\n\n이번 주 쓰인 이야기: **{stats['weekly_total']:,} 쪽** • 마음의 온기 **{stats['weekly_rank']}위** ",
            inline=False
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = ctx.message.created_at
        
        return embed

    @commands.command(name='내정보', aliases=['myinfo', '정보'])
    @in_myinfo_allowed_channel()
    async def my_info(self, ctx, member: discord.Member = None):
        """내 경험치 및 퀘스트 정보 조회 (또는 @유저로 타인 조회)"""
        try:
            member = member or ctx.author
            user_id = member.id

            level_checker = ctx.bot.get_cog("LevelChecker")
            data_manager = getattr(self, "data_manager", None) or getattr(level_checker, "data_manager", None)
            if data_manager is None or level_checker is None:
                return await ctx.reply("설정이 아직 준비되지 않았어요. 잠시 후 다시 시도해 주세요.")

            user_data = await data_manager.get_user_exp(user_id) if hasattr(data_manager, "get_user_exp") else None
            total_exp = int(user_data.get("total_exp", 0)) if user_data else 0
            current_role_key = user_data.get("current_role", "yeobaek") if user_data else "yeobaek"

            progress = self._get_progress_info(total_exp, current_role_key)

            voice_lv, chat_lv = 0, 0
            if hasattr(data_manager, "get_all_certified_ranks"):
                try:
                    cert = await data_manager.get_all_certified_ranks(user_id)
                    voice_lv = int(cert.get("voice", 0))
                    chat_lv = int(cert.get("chat", 0))
                except Exception:
                    pass
            ranks = (voice_lv, chat_lv)

            try:
                tracked_channel_ids = set(await self._get_tracked_voice_ids_cached())
            except AttributeError:
                from src.core.voice_utils import get_filtered_tracked_channels
                tracked_channel_ids = set(await get_filtered_tracked_channels(self.bot, self.data_manager, "voice"))

            stats = await self._get_quest_stats(user_id, tracked_channel_ids)
            embed = await self._build_myinfo_embed(ctx, member, user_data, ranks, stats, progress)
            
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply("명령어 처리 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
            await self.log(f"{ctx.author}({ctx.author.id}) 님의 내정보 명령어 처리 중 오류 발생: {e}")
            return
    
    @commands.command(name='순위', aliases=['ranking', 'leaderboard'])
    async def ranking(self, ctx, period: str = '누적'):
        """경험치 순위 조회"""
        valid_periods = ['일간', 'daily', '주간', 'weekly', '월간', 'monthly', '누적', 'total', 'all']
        
        if period not in valid_periods:
            embed = discord.Embed(
                title="❌ 잘못된 기간",
                description="사용 가능한 기간: `일간`, `주간`, `월간`, `누적`",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # 기간 정규화
        if period in ['일간', 'daily']:
            period_type = 'daily'
            period_name = '일간'
            emoji = '📅'
        elif period in ['주간', 'weekly']:
            period_type = 'weekly'
            period_name = '주간'
            emoji = '📊'
        elif period in ['월간', 'monthly']:
            period_type = 'monthly'
            period_name = '월간'
            emoji = '📈'
        else:
            period_type = 'total'
            period_name = '누적'
            emoji = '🏆'
        
        # 순위 데이터 가져오기
        rankings = await self.data_manager.get_period_rankings(period_type)
        
        if not rankings:
            embed = discord.Embed(
                title=f"{emoji} {period_name} 순위",
                description="아직 순위 데이터가 없습니다.",
                color=0x999999
            )
            await ctx.send(embed=embed)
            return
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"{emoji} {period_name} 경험치 순위",
            color=0xffd700
        )
        
        rank_emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 17
        
        # 사용자의 순위 찾기
        user_rank = None
        user_exp = None
        for i, (user_id, exp, role) in enumerate(rankings, 1):
            if user_id == ctx.author.id:
                user_rank = i
                user_exp = exp
                break
        
        # 상위 10명 표시
        leaderboard_text = ""
        for i, (user_id, exp, role) in enumerate(rankings[:10], 1):
            try:
                user = self.bot.get_user(user_id)
                username = user.display_name if user else f"Unknown User"
                role_emoji = self.role_info.get(role, {'emoji': '❓'})['emoji']
                role_name = self.role_info.get(role, {'name': role})['name']
                
                # 현재 사용자 강조
                if user_id == ctx.author.id:
                    leaderboard_text += f"{rank_emojis[i-1]} **{i}.** **{username}** ⭐\n"
                else:
                    leaderboard_text += f"{rank_emojis[i-1]} **{i}.** {username}\n"
                
                leaderboard_text += f"   └ {exp:,} 쪽 ({role_emoji} {role_name})\n\n"
            except:
                continue
        
        embed.description = leaderboard_text
        
        # 사용자가 10위 밖이면 자신의 순위 표시
        if user_rank and user_rank > 10:
            embed.add_field(
                name="📍 내 순위",
                value=f"**{user_rank}위** - {ctx.author.display_name} ({user_exp:,} 쪽)",
                inline=False
            )
        
        # 기간별 설명 추가
        if period_type != 'total':
            period_descriptions = {
                'daily': '오늘 획득한 경험치 기준',
                'weekly': '이번 주 획득한 경험치 기준',
                'monthly': '이번 달 획득한 경험치 기준'
            }
            embed.set_footer(text=period_descriptions[period_type])
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelCommands(bot))
