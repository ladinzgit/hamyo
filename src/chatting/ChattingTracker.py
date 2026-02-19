"""
실시간 채팅 추적 모듈입니다.
on_message 이벤트를 통해 채팅을 필터링하고 점수를 DB에 기록합니다.
VoiceTracker와 유사한 패턴으로 동작합니다.
"""
import discord
from discord.ext import commands
import re
import json
import os
import time
from datetime import datetime
import pytz

from src.core.ChattingDataManager import ChattingDataManager

KST = pytz.timezone("Asia/Seoul")

# 설정 파일 경로
CONFIG_PATH = "config/chatting_config.json"

# 한글 정규식
KOREAN_PATTERN = re.compile(r'[가-힣]')

# 점수 설정
BASE_POINTS = 2
LONG_MESSAGE_POINTS = 3
LONG_MESSAGE_THRESHOLD = 30  # 전체 문자 30자 이상이면 3점
MIN_KOREAN_CHARS = 10  # 한글 최소 10글자

# 쿨타임 (초)
COOLDOWN_SECONDS = 60


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tracked_channels": [], "ignored_role_ids": []}


class ChattingTracker(commands.Cog):
    """실시간 채팅 추적 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.data_manager = ChattingDataManager()
        bot.loop.create_task(self.data_manager.initialize())
        # 유저별 마지막 점수 획득 시간 (메모리 캐시)
        # {user_id: last_scored_timestamp}
        self._cooldowns: dict[int, float] = {}

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    def _count_korean_chars(self, text: str) -> int:
        """텍스트에서 한글 글자 수를 카운트합니다."""
        return len(KOREAN_PATTERN.findall(text))

    def _calculate_points(self, text: str) -> int:
        """메시지 텍스트에 따른 점수를 계산합니다."""
        if len(text) >= LONG_MESSAGE_THRESHOLD:
            return LONG_MESSAGE_POINTS
        return BASE_POINTS

    def _is_on_cooldown(self, user_id: int) -> bool:
        """유저가 쿨타임 중인지 확인합니다."""
        last_time = self._cooldowns.get(user_id)
        if last_time is None:
            return False
        return (time.time() - last_time) < COOLDOWN_SECONDS

    def _has_ignored_role_mention(self, message: discord.Message, ignored_role_ids: list) -> bool:
        """메시지에 무시할 역할 멘션이 포함되어 있는지 확인합니다."""
        if not ignored_role_ids or not message.role_mentions:
            return False
        for role in message.role_mentions:
            if role.id in ignored_role_ids:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """메시지 이벤트를 감지하여 채팅 점수를 기록합니다."""
        # 봇 메시지 무시
        if message.author.bot:
            return

        # 시스템 메시지 무시
        if message.type != discord.MessageType.default:
            return

        # 설정 로드
        config = load_config()
        tracked_channels = config.get("tracked_channels", [])
        ignored_role_ids = config.get("ignored_role_ids", [])

        # 추적 채널 확인
        if message.channel.id not in tracked_channels:
            return

        content = message.content or ""

        # 무시할 역할 멘션 확인
        if self._has_ignored_role_mention(message, ignored_role_ids):
            return

        # 한글 10글자 이상 확인
        korean_count = self._count_korean_chars(content)
        if korean_count < MIN_KOREAN_CHARS:
            return

        # 쿨타임 확인
        user_id = message.author.id
        if self._is_on_cooldown(user_id):
            return

        # 점수 계산
        points = self._calculate_points(content)

        # DB에 기록
        now = datetime.now(KST)
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")

        success = await self.data_manager.add_chat_record(
            user_id=user_id,
            channel_id=message.channel.id,
            message_id=message.id,
            char_count=len(content),
            points=points,
            created_at=created_at
        )

        if success:
            # 쿨타임 갱신
            self._cooldowns[user_id] = time.time()


async def setup(bot: commands.Bot):
    await bot.add_cog(ChattingTracker(bot))
