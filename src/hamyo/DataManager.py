import aiosqlite
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    import pytz
    KST = pytz.timezone("Asia/Seoul")

class DataManager:
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()

    def __new__(cls, db_path: str = "data/voice_logs.db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = db_path
            cls._instance._db = None
        return cls._instance
        
    def __init__(self, db_path: str = "data/voice_logs.db"):
        # Only set the db_path if this is a new instance
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
            self._db = None

    async def ensure_initialized(self):
        """Ensures the database is initialized before executing operations."""
        if not DataManager._initialized:
            async with self._init_lock:
                # Check again in case another task initialized while we were waiting
                if not DataManager._initialized:
                    await self.initialize()

    async def initialize(self):
        """Initialize the database connection and create tables if they don't exist."""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS voice_times (
                    date TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    seconds INTEGER NOT NULL,
                    PRIMARY KEY (date, user_id, channel_id)
                )
            """)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS deleted_channels (
                    channel_id INTEGER PRIMARY KEY,
                    category_id INTEGER NOT NULL
                )
            """)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS tracked_channels (
                    channel_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (channel_id, source)
                )
            """)
            await self._db.commit()
            DataManager._initialized = True

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
            DataManager._initialized = False
            
    async def register_tracked_channel(self, channel_id: int, source: str):
        await self.ensure_initialized()
        await self._db.execute("""
            INSERT OR IGNORE INTO tracked_channels (channel_id, source)
            VALUES (?, ?)
        """, (channel_id, source))
        await self._db.commit()

    async def unregister_tracked_channel(self, channel_id: int, source: str):
        await self.ensure_initialized()
        await self._db.execute("""
            DELETE FROM tracked_channels WHERE channel_id = ? AND source = ?
        """, (channel_id, source))
        await self._db.commit()

    async def get_tracked_channels(self, source: str) -> List[int]:
        await self.ensure_initialized()
        async with self._db.execute("SELECT channel_id FROM tracked_channels WHERE source = ?", (source,)) as cursor:
            return [row[0] async for row in cursor]

    async def get_all_tracked_sources(self) -> List[str]:
        await self.ensure_initialized()
        async with self._db.execute("SELECT DISTINCT source FROM tracked_channels") as cursor:
            return [row[0] async for row in cursor]

    async def add_voice_time(self, user_id: int, channel_id: int, seconds: int):
        await self.ensure_initialized()
        now = datetime.now(KST).strftime("%Y-%m-%d")
        await self._db.execute("""
            INSERT INTO voice_times (date, user_id, channel_id, seconds)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date, user_id, channel_id)
            DO UPDATE SET seconds = seconds + excluded.seconds
        """, (now, user_id, channel_id, seconds))
        await self._db.commit()

    async def register_deleted_channel(self, channel_id: int, category_id: int):
        await self.ensure_initialized()
        await self._db.execute("""
            INSERT OR REPLACE INTO deleted_channels (channel_id, category_id)
            VALUES (?, ?)
        """, (channel_id, category_id))
        await self._db.commit()

    async def get_deleted_channel_category(self, channel_id: int) -> Optional[int]:
        await self.ensure_initialized()
        async with self._db.execute("""
            SELECT category_id FROM deleted_channels WHERE channel_id = ?
        """, (channel_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_user_times(
        self,
        user_id: int,
        period: str,
        base_date: Optional[datetime] = None,
        channel_filter: Optional[List[int]] = None
    ) -> Tuple[Dict[int, int], Optional[datetime], Optional[datetime]]:
        await self.ensure_initialized()
        if base_date is None:
            base_date = datetime.now(KST)

        result: Dict[int, int] = {}
        start_date, end_date = await self.get_period_range(period, base_date)
        if not start_date or not end_date:
            return result, None, None

        # 빈 리스트면 바로 빈 결과 반환
        if channel_filter is None:
            return {}, start_date, end_date

        sql = """
            SELECT channel_id, SUM(seconds)
              FROM voice_times
             WHERE user_id = ?
               AND date BETWEEN ? AND ?
        """
        params = [
            user_id,
            start_date.strftime("%Y-%m-%d"),
            (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        ]

        if channel_filter is not None:
            placeholders = ",".join("?" for _ in channel_filter)
            sql += f" AND channel_id IN ({placeholders})"
            params.extend(channel_filter)

        sql += " GROUP BY channel_id"

        async with self._db.execute(sql, params) as cursor:
            async for cid, secs in cursor:
                result[cid] = secs

        return result, start_date, end_date

    async def get_all_users_times(
        self,
        period: str,
        base_date: datetime,
        channel_filter: Optional[List[int]] = None
    ) -> Tuple[Dict[int, Dict[int, int]], Optional[datetime], Optional[datetime]]:
        await self.ensure_initialized()
        result: Dict[int, Dict[int, int]] = {}
        start_date, end_date = await self.get_period_range(period, base_date)
        if not start_date or not end_date:
            return result, start_date, end_date

        # 빈 리스트면 바로 빈 결과 반환
        if channel_filter is not None and not channel_filter:
            return {}, start_date, end_date

        sql = """
            SELECT user_id, channel_id, SUM(seconds)
              FROM voice_times
             WHERE date BETWEEN ? AND ?
        """
        params = [
            start_date.strftime("%Y-%m-%d"),
            (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        ]

        if channel_filter is not None:
            placeholders = ",".join("?" for _ in channel_filter)
            sql += f" AND channel_id IN ({placeholders})"
            params.extend(channel_filter)

        sql += " GROUP BY user_id, channel_id"

        async with self._db.execute(sql, params) as cursor:
            async for uid, cid, secs in cursor:
                user_map = result.setdefault(uid, {})
                user_map[cid] = secs

        return result, start_date, end_date

    
    async def get_period_range(self, period: str, base_datetime: datetime) -> Tuple[Optional[datetime], Optional[datetime]]:
        await self.ensure_initialized()
        # base_datetime은 항상 KST로 전달되어야 함
        if period == '일간':
            start = base_datetime.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == '주간':
            base_datetime = base_datetime.astimezone(KST)
            start = base_datetime - timedelta(days=base_datetime.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == '월간':
            base_datetime = base_datetime.astimezone(KST)
            start = base_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif period == '누적':
            async with self._db.execute("SELECT date FROM voice_times ORDER BY date ASC") as cursor:
                dates = [datetime.strptime(row[0], "%Y-%m-%d").replace(tzinfo=KST) async for row in cursor]
                if not dates:
                    return None, None
                return dates[0], dates[-1] + timedelta(days=1)
        else:
            return None, None

        return start, end

    async def reset_data(self):
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM voice_times")
        await self._db.execute("DELETE FROM deleted_channels")
        await self._db.commit()
        
    async def reset_tracked_channels(self, source: str):
        """
        트래킹된 채널 목록(tracked_channels)만 모두 삭제합니다.
        voice_times, deleted_channels 테이블은 건드리지 않습니다.
        """
        await self.ensure_initialized()
        await self._db.execute(
            "DELETE FROM tracked_channels WHERE source = ?",
            (source,)
        )
        await self._db.commit()

    async def migrate_multiple_user_times(self, user_times_paths: List[str], deleted_channels_path: str):
        await self.ensure_initialized()
        # ① 매번 깨끗한 상태에서 시작하기 위해 이전 삭제채널 기록을 모두 지웁니다.
        await self._db.execute("DELETE FROM deleted_channels")

        # ② user_times 마이그레이션
        for path in user_times_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    user_times = json.load(f)
                for date_str, users in user_times.items():
                    for user_id, channels in users.items():
                        for channel_id, seconds in channels.items():
                            await self._db.execute(
                                """
                                INSERT INTO voice_times (date, user_id, channel_id, seconds)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(date, user_id, channel_id) DO NOTHING
                                """,
                                (date_str, int(user_id), int(channel_id), int(seconds))
                            )

        # ③ deleted_channels 로드
        if os.path.exists(deleted_channels_path):
            with open(deleted_channels_path, 'r', encoding='utf-8') as f:
                deleted_channels = json.load(f)
            for channel_id, payload in deleted_channels.items():
                # JSON 구조가 { "채널ID": { "category_id": 숫자 } } 이므로 payload에서 꺼냅니다.
                category_id = payload.get("category_id")
                if category_id is None:
                    continue
                await self._db.execute(
                    """
                    INSERT OR REPLACE INTO deleted_channels (channel_id, category_id)
                    VALUES (?, ?)
                    """,
                    (int(channel_id), int(category_id))
                )

        # ④ 최종 커밋
        await self._db.commit()
        

    async def migrate_deleted_channels(self, deleted_channels_paths: List[str]):
        """
        deleted_channels 테이블을 비우고, 여러 JSON 파일에서
        삭제된 채널 정보를 중복 없이 한 번에 삽입합니다.
        """
        # DB 초기화 및 준비
        await self.ensure_initialized()
        # 1) 기존 레코드 삭제
        await self._db.execute("DELETE FROM deleted_channels")

        # 프로젝트 루트를 기준으로 경로 재해석
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent

        # 2) 각 JSON 파일을 순회하며 데이터 병합
        for fp in deleted_channels_paths:
            path = Path(fp)
            # 상대 경로가 없으면 data 디렉터리에서 찾기
            if not path.exists():
                path = base_dir / "data" / fp
            if not path.exists():
                continue

            # JSON 로드
            with open(path, 'r', encoding='utf-8') as f:
                deleted = json.load(f)

            # 중복 없이 INSERT OR REPLACE
            for channel_id, payload in deleted.items():
                category_id = payload.get("category_id")
                if category_id is None:
                    continue
                await self._db.execute(
                    "INSERT OR REPLACE INTO deleted_channels (channel_id, category_id) VALUES (?, ?)",
                    (int(channel_id), int(category_id))
                )

        # 3) 커밋
        await self._db.commit()

    async def get_deleted_channels_by_categories(self, category_ids: List[int]) -> List[int]:
        """주어진 카테고리ID 목록에 속한 삭제된 채널ID들을 반환합니다."""
        if not category_ids:
            return []
        placeholders = ",".join("?" for _ in category_ids)
        sql = f"SELECT channel_id FROM deleted_channels WHERE category_id IN ({placeholders})"
        await self.ensure_initialized()
        result = []
        async with self._db.execute(sql, tuple(category_ids)) as cursor:
            async for (channel_id,) in cursor:
                result.append(channel_id)
        return result

    async def get_user_voice_seconds(self, user_id: int, period: str, base_date: Optional[datetime] = None) -> int:
        """
        주어진 기간(period: '일간', '주간') 동안 유저가 음성 채널에서 활동한 총 시간을 초 단위로 반환합니다.
        """
        await self.ensure_initialized()
        if base_date is None:
            base_date = datetime.now(KST)
        start_date, end_date = await self.get_period_range(period, base_date)
        if not start_date or not end_date:
            return 0

        sql = """
            SELECT SUM(seconds)
              FROM voice_times
             WHERE user_id = ?
               AND date BETWEEN ? AND ?
        """
        params = [
            user_id,
            start_date.strftime("%Y-%m-%d"),
            (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        ]
        async with self._db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 0

    async def get_user_voice_seconds_daily(self, user_id: int, base_date: Optional[datetime] = None) -> int:
        """오늘 하루 동안 유저가 음성 채널에서 활동한 총 시간을 초 단위로 반환합니다."""
        return await self.get_user_voice_seconds(user_id, '일간', base_date or datetime.now(KST))

    async def get_user_voice_seconds_weekly(self, user_id: int, base_date: Optional[datetime] = None) -> int:
        """이번 주 동안 유저가 음성 채널에서 활동한 총 시간을 초 단위로 반환합니다."""
        return await self.get_user_voice_seconds(user_id, '주간', base_date or datetime.now(KST))
