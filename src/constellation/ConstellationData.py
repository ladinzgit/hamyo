# src/constellation/ConstellationData.py
# ============================================================
# 비몽 별자리 수집 데이터 관리 모듈
# SQLite (유저 수집 데이터) + JSON (관리자 설정) 혼합 사용
# ============================================================

import os
import json
import aiosqlite
from datetime import datetime
import pytz

from src.constellation.ConstellationConstants import (
    CONSTELLATIONS,
    DEFAULT_OBSERVE_COST,
    DEFAULT_OBSERVE_COOLDOWN_HOURS,
    DEFAULT_EXCHANGE_FEE,
)

KST = pytz.timezone("Asia/Seoul")
DB_PATH = "data/constellation.db"
CONFIG_PATH = "config/constellation_config.json"

# ===========================================
# JSON Config 헬퍼 (설정값 저장)
# ===========================================

def _ensure_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        default = {
            "observe_cost": DEFAULT_OBSERVE_COST,
            "observe_cooldown_hours": DEFAULT_OBSERVE_COOLDOWN_HOURS,
            "exchange_fee": DEFAULT_EXCHANGE_FEE,
            "allowed_channels": [],
            "announce_channel_id": None,
            "completion_rewards": {}
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)


def _load_config() -> dict:
    _ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(data: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===========================================
# ConstellationData 클래스
# ===========================================

class ConstellationData:
    """별자리 수집 데이터 관리 (SQLite + JSON config)"""

    def __init__(self):
        self._initialized = False

    # ── DB 초기화 ──

    async def ensure_initialized(self):
        if self._initialized:
            return
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_stars (
                    user_id INTEGER,
                    constellation_id TEXT,
                    star_id TEXT,
                    collected_at TEXT,
                    PRIMARY KEY (user_id, constellation_id, star_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_observe_log (
                    user_id INTEGER PRIMARY KEY,
                    last_observe_at TEXT
                )
            """)
            await db.commit()
        self._initialized = True

    # ── 별 수집 ──

    async def add_star(self, user_id: int, constellation_id: str, star_id: str) -> bool:
        """별을 수집합니다. 이미 있으면 False, 새로 추가하면 True."""
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    "INSERT INTO user_stars (user_id, constellation_id, star_id, collected_at) VALUES (?, ?, ?, ?)",
                    (user_id, constellation_id, star_id, now)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def has_star(self, user_id: int, constellation_id: str, star_id: str) -> bool:
        """유저가 특정 별을 이미 가지고 있는지 확인합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM user_stars WHERE user_id = ? AND constellation_id = ? AND star_id = ?",
                (user_id, constellation_id, star_id)
            )
            return await cursor.fetchone() is not None

    async def get_user_stars(self, user_id: int) -> dict:
        """유저가 수집한 모든 별을 {constellation_id: [star_id, ...]} 형태로 반환합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT constellation_id, star_id FROM user_stars WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()

        result = {}
        for constellation_id, star_id in rows:
            if constellation_id not in result:
                result[constellation_id] = []
            result[constellation_id].append(star_id)
        return result

    async def get_user_constellation_stars(self, user_id: int, constellation_id: str) -> list:
        """유저가 특정 별자리에서 수집한 별 ID 목록을 반환합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT star_id FROM user_stars WHERE user_id = ? AND constellation_id = ?",
                (user_id, constellation_id)
            )
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def is_constellation_complete(self, user_id: int, constellation_id: str) -> bool:
        """별자리가 완성되었는지 확인합니다."""
        constellation = CONSTELLATIONS.get(constellation_id)
        if not constellation:
            return False
        collected = await self.get_user_constellation_stars(user_id, constellation_id)
        total_stars = len(constellation["stars"])
        return len(collected) >= total_stars

    async def get_completed_count(self, user_id: int) -> int:
        """유저가 완성한 별자리 개수를 반환합니다."""
        count = 0
        for cid in CONSTELLATIONS:
            if await self.is_constellation_complete(user_id, cid):
                count += 1
        return count

    async def remove_star(self, user_id: int, constellation_id: str, star_id: str) -> bool:
        """유저에게서 별을 제거합니다. (교환용)"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM user_stars WHERE user_id = ? AND constellation_id = ? AND star_id = ?",
                (user_id, constellation_id, star_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    # ── 관측 쿨타임 ──

    async def get_last_observe_time(self, user_id: int) -> str | None:
        """유저의 마지막 관측 시간을 반환합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT last_observe_at FROM user_observe_log WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_last_observe_time(self, user_id: int):
        """유저의 마지막 관측 시간을 현재로 설정합니다."""
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO user_observe_log (user_id, last_observe_at) VALUES (?, ?)",
                (user_id, now)
            )
            await db.commit()

    # ── DB 초기화 (관리자용) ──

    async def reset_all_data(self):
        """모든 유저의 별자리 수집 데이터를 초기화합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_stars")
            await db.execute("DELETE FROM user_observe_log")
            await db.commit()

    async def reset_user_data(self, user_id: int):
        """특정 유저의 별자리 수집 데이터를 초기화합니다."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_stars WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM user_observe_log WHERE user_id = ?", (user_id,))
            await db.commit()

    # ===========================================
    # JSON Config 기반 설정 관리
    # ===========================================

    # ── 관측 비용 ──
    def get_observe_cost(self) -> int:
        cfg = _load_config()
        return cfg.get("observe_cost", DEFAULT_OBSERVE_COST)

    def set_observe_cost(self, amount: int):
        cfg = _load_config()
        cfg["observe_cost"] = amount
        _save_config(cfg)

    # ── 관측 쿨타임 ──
    def get_observe_cooldown_hours(self) -> int:
        cfg = _load_config()
        return cfg.get("observe_cooldown_hours", DEFAULT_OBSERVE_COOLDOWN_HOURS)

    def set_observe_cooldown_hours(self, hours: int):
        cfg = _load_config()
        cfg["observe_cooldown_hours"] = hours
        _save_config(cfg)

    # ── 교환 수수료 ──
    def get_exchange_fee(self) -> int:
        cfg = _load_config()
        return cfg.get("exchange_fee", DEFAULT_EXCHANGE_FEE)

    def set_exchange_fee(self, fee: int):
        cfg = _load_config()
        cfg["exchange_fee"] = fee
        _save_config(cfg)

    # ── 허용 채널 (복수) ──
    def get_allowed_channels(self) -> list:
        cfg = _load_config()
        return cfg.get("allowed_channels", [])

    def add_allowed_channel(self, channel_id: int) -> bool:
        """허용 채널을 추가합니다. 이미 있으면 False."""
        cfg = _load_config()
        channels = cfg.setdefault("allowed_channels", [])
        if channel_id in channels:
            return False
        channels.append(channel_id)
        _save_config(cfg)
        return True

    def remove_allowed_channel(self, channel_id: int) -> bool:
        """허용 채널을 제거합니다. 없으면 False."""
        cfg = _load_config()
        channels = cfg.get("allowed_channels", [])
        if channel_id not in channels:
            return False
        channels.remove(channel_id)
        cfg["allowed_channels"] = channels
        _save_config(cfg)
        return True

    # ── 알림 채널 ──
    def get_announce_channel_id(self) -> int | None:
        cfg = _load_config()
        return cfg.get("announce_channel_id")

    def set_announce_channel_id(self, channel_id: int | None):
        cfg = _load_config()
        cfg["announce_channel_id"] = channel_id
        _save_config(cfg)

    # ── 완성 보상 마일스톤 ──
    def get_completion_rewards(self) -> dict:
        """
        {완성수(str): {"role_id": int|None, "bonus_on": int}} 형태로 반환합니다.
        JSON은 key가 문자열이므로 str으로 관리합니다.
        """
        cfg = _load_config()
        return cfg.get("completion_rewards", {})

    def set_completion_reward(self, required_count: int, role_id: int | None, bonus_on: int):
        cfg = _load_config()
        rewards = cfg.setdefault("completion_rewards", {})
        rewards[str(required_count)] = {
            "role_id": role_id,
            "bonus_on": bonus_on
        }
        _save_config(cfg)

    def remove_completion_reward(self, required_count: int) -> bool:
        cfg = _load_config()
        rewards = cfg.get("completion_rewards", {})
        key = str(required_count)
        if key in rewards:
            del rewards[key]
            _save_config(cfg)
            return True
        return False
