"""
티어 기반 경험치 레벨 계산 모듈입니다.
음성/채팅 각각의 누적 점수를 레벨과 진행률로 변환합니다.

경험치 티어 시스템:
  - 10레벨마다 티어가 증가하며, 레벨업에 필요한 XP가 50%씩 늘어남
  - 음성: 기본 XP = (레벨 * 139) + 70
  - 채팅: 기본 XP = (레벨 * 69.5) + 35
  - 최종 XP = 기본 XP * (1 + (레벨 // 10) * 0.5)
"""

import math
from dataclasses import dataclass


@dataclass
class LevelInfo:
    """레벨 계산 결과를 담는 데이터 클래스"""
    level: int            # 현재 레벨
    current_xp: int       # 현재 레벨에서의 누적 XP
    required_xp: int      # 다음 레벨까지 필요한 총 XP
    progress_pct: float   # 진행률 (0.0 ~ 100.0)


class TieredLevelManager:
    """티어 기반 경험치 계산기"""

    # 음성 레벨 상수
    VOICE_GROWTH = 139
    VOICE_BASE = 70

    # 채팅 레벨 상수
    CHAT_GROWTH = 69.5
    CHAT_BASE = 35

    @staticmethod
    def get_tier_multiplier(level: int) -> float:
        """10레벨마다 0.5씩 증가하는 티어 배수를 반환합니다."""
        tier = level // 10
        return 1 + (tier * 0.5)

    @classmethod
    def get_next_voice_xp(cls, level: int) -> int:
        """해당 레벨에서 다음 음성 레벨로 올라가기 위한 XP를 반환합니다."""
        standard_xp = (level * cls.VOICE_GROWTH) + cls.VOICE_BASE
        return int(standard_xp * cls.get_tier_multiplier(level))

    @classmethod
    def get_next_chat_xp(cls, level: int) -> int:
        """해당 레벨에서 다음 채팅 레벨로 올라가기 위한 XP를 반환합니다."""
        standard_xp = (level * cls.CHAT_GROWTH) + cls.CHAT_BASE
        return int(standard_xp * cls.get_tier_multiplier(level))

    @classmethod
    def calculate_level(cls, total_xp: int, xp_type: str) -> LevelInfo:
        """
        누적 XP를 레벨, 잔여 XP, 진행률로 변환합니다.

        누적 XP에서 각 레벨에 필요한 XP를 순차적으로 차감하여
        현재 레벨과 진행률을 계산합니다.

        Args:
            total_xp: 누적 총 XP (음성: 초 단위, 채팅: 메시지 수)
            xp_type: 'voice' 또는 'chat'

        Returns:
            LevelInfo: 레벨, 현재 XP, 필요 XP, 진행률
        """
        # XP 타입에 따라 계산 함수 선택
        if xp_type == 'voice':
            get_next_xp = cls.get_next_voice_xp
        elif xp_type == 'chat':
            get_next_xp = cls.get_next_chat_xp
        else:
            raise ValueError(f"알 수 없는 XP 타입: {xp_type}")

        level = 0
        remaining_xp = total_xp

        # 누적 XP에서 레벨업 비용을 순차 차감
        while True:
            required = get_next_xp(level)
            if remaining_xp < required:
                break
            remaining_xp -= required
            level += 1

        # 현재 레벨의 필요 XP와 진행률 계산
        current_required = get_next_xp(level)
        progress = (remaining_xp / current_required * 100) if current_required > 0 else 0.0

        return LevelInfo(
            level=level,
            current_xp=remaining_xp,
            required_xp=current_required,
            progress_pct=min(progress, 100.0)
        )


async def setup(bot):
    pass  # 유틸리티 모듈 — Cog 없음
