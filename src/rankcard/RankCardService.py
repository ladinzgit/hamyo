"""
랭크 카드에 필요한 데이터를 수집·가공하는 서비스 모듈입니다.
음성/채팅/레벨 데이터를 각 모듈에서 읽어와 XPFormulas로 레벨을 계산합니다.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

import discord
from discord.ext import commands
import pytz

from src.core.DataManager import DataManager
from src.core.LevelDataManager import LevelDataManager
from src.rankcard.XPFormulas import TieredLevelManager, LevelInfo

KST = pytz.timezone("Asia/Seoul")

# 채팅 설정 파일 경로
CHATTING_CONFIG_PATH = "config/chatting_config.json"

# 채팅 채널당 최대 조회 메시지 수
MAX_MESSAGES_PER_CHANNEL = 1000000

# 역할 승급 기준 (LevelSystem과 동일)
ROLE_THRESHOLDS = {
    'hub': 0,
    'dado': 400,
    'daho': 1800,
    'dakyung': 6000,
    'dahyang': 12000
}

# 역할 순서
ROLE_ORDER = ['hub', 'dado', 'daho', 'dakyung', 'dahyang']

# 역할 한글 표시명
ROLE_DISPLAY = {
    'hub': '허브',
    'dado': '다도',
    'daho': '다호',
    'dakyung': '다경',
    'dahyang': '다향'
}

# 역할별 이모지
ROLE_EMOJI = {
    'hub': '🌱',
    'dado': '🍵',
    'daho': '🌸',
    'dakyung': '⭐',
    'dahyang': '🔮'
}


@dataclass
class RankCardData:
    """랭크 카드에 표시할 모든 데이터"""
    # 기본 정보
    user_name: str
    avatar_url: str

    # 메인 레벨 (몽경 시스템)
    current_role: str         # 역할 키 (hub, dado, ...)
    role_display: str         # 한글 표시명
    role_emoji: str           # 역할 이모지
    total_exp: int            # 총 다공

    # 다음 경지 진행률
    next_role: Optional[str]         # 다음 역할 키
    next_role_display: Optional[str] # 다음 역할 한글명
    role_progress_pct: float         # 다음 경지까지 진행률

    # 음성 레벨
    voice_level_info: LevelInfo
    voice_total_xp: int       # 총 음성 XP (초 단위)
    voice_rank: Optional[int]         # 음성 순위 (1부터)
    voice_total_users: int            # 음성 전체 유저 수

    # 채팅 레벨
    chat_level_info: LevelInfo
    chat_total_xp: int        # 총 채팅 XP (메시지 수)
    chat_rank: Optional[int]          # 채팅 순위 (1부터)
    chat_total_users: int             # 채팅 전체 유저 수


def _load_chatting_config() -> list:
    """채팅 추적 채널 목록을 설정 파일에서 로드합니다."""
    try:
        with open(CHATTING_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("tracked_channels", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


class RankCardService:
    """랭크 카드 데이터 수집 및 레벨 계산 서비스"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_dm = DataManager()
        self.level_dm = LevelDataManager()

    async def get_rank_card_data(
        self,
        user: discord.Member
    ) -> RankCardData:
        """
        유저의 랭크 카드 데이터를 수집합니다.

        1. 레벨 시스템에서 다공/역할 정보 조회
        2. 음성 데이터에서 누적 시간(초) 조회
        3. 채팅 데이터에서 누적 메시지 수 조회
        4. XPFormulas로 각각의 레벨/진행률 계산
        """
        # ── 1. 메인 레벨 데이터 (다공 & 경지) ──
        level_data = await self.level_dm.get_user_exp(user.id)
        if level_data:
            total_exp = level_data['total_exp']
            current_role = level_data['current_role']
        else:
            total_exp = 0
            current_role = 'hub'

        # 다음 경지 계산
        next_role, next_role_display, role_progress = self._calc_role_progress(
            current_role, total_exp
        )

        # ── 2. 음성 데이터 (누적 초 + 순위) ──
        voice_total = await self._get_voice_total(user.id)
        voice_rank, voice_total_users = await self._get_voice_rank(user.id)

        # ── 3. 채팅 데이터 (누적 메시지 수 + 순위) ──
        chat_total, chat_rank, chat_total_users = await self._get_chat_total_with_rank(user)

        # ── 4. 티어 레벨 계산 ──
        voice_level_info = TieredLevelManager.calculate_level(voice_total, 'voice')
        chat_level_info = TieredLevelManager.calculate_level(chat_total, 'chat')

        # 아바타 URL (없으면 기본 아바타)
        avatar_url = str(user.display_avatar.replace(size=256, format="png"))

        # 표시 이름 추출 (닉네임에서 칭호 제거)
        display_name = self._extract_name(user.display_name)

        return RankCardData(
            user_name=display_name,
            avatar_url=avatar_url,
            current_role=current_role,
            role_display=ROLE_DISPLAY.get(current_role, '허브'),
            role_emoji=ROLE_EMOJI.get(current_role, '🌱'),
            total_exp=total_exp,
            next_role=next_role,
            next_role_display=next_role_display,
            role_progress_pct=role_progress,
            voice_level_info=voice_level_info,
            voice_total_xp=voice_total,
            voice_rank=voice_rank,
            voice_total_users=voice_total_users,
            chat_level_info=chat_level_info,
            chat_total_xp=chat_total,
            chat_rank=chat_rank,
            chat_total_users=chat_total_users,
        )

    def _calc_role_progress(self, current_role: str, total_exp: int):
        """현재 역할에서 다음 역할까지의 진행률을 계산합니다."""
        try:
            current_idx = ROLE_ORDER.index(current_role)
        except ValueError:
            current_idx = 0

        # 최고 랭크인 경우
        if current_idx >= len(ROLE_ORDER) - 1:
            return None, None, 100.0

        next_role_key = ROLE_ORDER[current_idx + 1]
        next_role_display = ROLE_DISPLAY.get(next_role_key, '???')

        current_threshold = ROLE_THRESHOLDS.get(current_role, 0)
        next_threshold = ROLE_THRESHOLDS.get(next_role_key, 0)

        # 현재 구간 내 진행률
        range_size = next_threshold - current_threshold
        if range_size <= 0:
            return next_role_key, next_role_display, 100.0

        progress_in_range = total_exp - current_threshold
        pct = (progress_in_range / range_size) * 100
        return next_role_key, next_role_display, min(max(pct, 0.0), 100.0)

    async def _get_voice_total(self, user_id: int) -> int:
        """유저의 누적 음성 시간(초)을 반환합니다."""
        try:
            await self.voice_dm.ensure_initialized()
            base_date = datetime.now(KST)
            times, _, _ = await self.voice_dm.get_user_times(
                user_id, '누적', base_date
            )
            return sum(times.values()) if times else 0
        except Exception:
            return 0

    async def _get_voice_rank(self, user_id: int) -> Tuple[Optional[int], int]:
        """유저의 누적 음성 순위를 반환합니다. (순위, 전체 유저 수)"""
        try:
            await self.voice_dm.ensure_initialized()
            base_date = datetime.now(KST)
            rank, total_users, _, _, _ = await self.voice_dm.get_user_rank(
                user_id, '누적', base_date
            )
            return rank, total_users
        except Exception:
            return None, 0

    async def _get_chat_total_with_rank(
        self, user: discord.Member
    ) -> Tuple[int, Optional[int], int]:
        """
        유저의 누적 채팅 메시지 수와 순위를 반환합니다.
        모든 유저의 메시지를 카운트하여 순위를 계산합니다.

        Returns:
            (유저 메시지 수, 순위, 전체 유저 수)
        """
        tracked_ids = _load_chatting_config()
        if not tracked_ids:
            return 0, None, 0

        # 전체 기간: 서버 오픈일부터 현재까지
        start = datetime(2025, 8, 1, tzinfo=KST)
        end = datetime.now(KST) + timedelta(days=1)

        # 모든 유저의 메시지 수 집계
        user_counts: Dict[int, int] = {}

        for channel_id in tracked_ids:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    continue

            if not isinstance(channel, discord.TextChannel):
                continue

            try:
                async for message in channel.history(
                    after=start,
                    before=end,
                    limit=MAX_MESSAGES_PER_CHANNEL,
                    oldest_first=True
                ):
                    # 봇 메시지 제외
                    if not message.author.bot:
                        user_counts[message.author.id] = (
                            user_counts.get(message.author.id, 0) + 1
                        )
            except discord.Forbidden:
                pass
            except Exception:
                pass

        # 유저의 메시지 수
        user_total = user_counts.get(user.id, 0)

        if not user_counts:
            return user_total, None, 0

        # 순위 계산 (내림차순 정렬)
        ranked = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        total_users = len(ranked)
        chat_rank = None
        for idx, (uid, _) in enumerate(ranked, start=1):
            if uid == user.id:
                chat_rank = idx
                break

        return user_total, chat_rank, total_users

    @staticmethod
    def _extract_name(text: str) -> str:
        """닉네임에서 칭호를 제거하고 순수 이름만 추출합니다."""
        import re
        # "칭호 | 이름" 패턴에서 이름 부분 추출
        match = re.search(r'[|｜]\s*(.+)', text)
        if match:
            return match.group(1).strip()
        return text.strip()


async def setup(bot):
    pass  # 유틸리티 모듈 — Cog 없음
