import aiosqlite
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

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
        
    def __init__(self, db_path: str = "src/florence/data/voice_logs.db"):
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
        now = datetime.now().strftime("%Y-%m-%d")
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
            base_date = datetime.now()

        result: Dict[int, int] = {}
        start_date, end_date = await self.get_period_range(period, base_date)
        if not start_date or not end_date:
            return result, None, None

        # 삭제된 채널을 자동으로 포함하고, 빈 리스트인 경우 바로 리턴
        if channel_filter is not None:
            async with self._db.execute(
                "SELECT channel_id FROM deleted_channels"
            ) as cursor:
                deleted_ids = [row[0] async for row in cursor]
            channel_filter = channel_filter + deleted_ids
            if not channel_filter:
                return {}, start_date, end_date

        sql = """
            SELECT date, channel_id, seconds
              FROM voice_times
             WHERE user_id = ?
               AND date BETWEEN ? AND ?
        """
        params = [
            user_id,
            start_date.strftime("%Y-%m-%d"),
            (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        ]

        # None이 아닌 경우만 IN 절 추가
        if channel_filter is not None:
            placeholders = ",".join("?" for _ in channel_filter)
            sql += f" AND channel_id IN ({placeholders})"
            params.extend(channel_filter)

        async with self._db.execute(sql, params) as cursor:
            async for _date, cid, secs in cursor:
                result[cid] = result.get(cid, 0) + secs

        return result, start_date, end_date


    async def get_all_users_times(
        self,
        period: str,
        base_date: datetime,
        channel_filter: Optional[List[int]] = None
    ) -> Tuple[Dict[int, Dict[str, int]], Optional[datetime], Optional[datetime]]:
        await self.ensure_initialized()
        result: Dict[int, Dict[str, int]] = {}
        start_date, end_date = await self.get_period_range(period, base_date)
        if not start_date or not end_date:
            return result, start_date, end_date

        # 삭제된 채널을 자동으로 포함하고, 빈 리스트인 경우 바로 리턴
        if channel_filter is not None:
            async with self._db.execute(
                "SELECT channel_id FROM deleted_channels"
            ) as cursor:
                deleted_ids = [row[0] async for row in cursor]
            channel_filter = channel_filter + deleted_ids
            if not channel_filter:
                return {}, start_date, end_date

        sql = """
            SELECT date, user_id, channel_id, seconds
              FROM voice_times
             WHERE date BETWEEN ? AND ?
        """
        params = [
            start_date.strftime("%Y-%m-%d"),
            (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        ]

        # None이 아닌 경우만 IN 절 추가
        if channel_filter is not None:
            placeholders = ",".join("?" for _ in channel_filter)
            sql += f" AND channel_id IN ({placeholders})"
            params.extend(channel_filter)

        async with self._db.execute(sql, params) as cursor:
            async for dstr, uid, cid, secs in cursor:
                user_map = result.setdefault(uid, {})
                user_map[dstr] = user_map.get(dstr, 0) + secs

        return result, start_date, end_date

    
    async def get_period_range(self, period: str, base_datetime: datetime) -> Tuple[Optional[datetime], Optional[datetime]]:
        await self.ensure_initialized()
        if period == '일간':
            start = base_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == '주간':
            start = base_datetime - timedelta(days=base_datetime.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == '월간':
            start = base_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif period == '누적':
            async with self._db.execute("SELECT date FROM voice_times ORDER BY date ASC") as cursor:
                dates = [datetime.strptime(row[0], "%Y-%m-%d") async for row in cursor]
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
        for path in user_times_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    user_times = json.load(f)
                for date_str, users in user_times.items():
                    for user_id, channels in users.items():
                        for channel_id, seconds in channels.items():
                            await self._db.execute("""
                                INSERT INTO voice_times (date, user_id, channel_id, seconds)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(date, user_id, channel_id) DO NOTHING
                            """, (date_str, int(user_id), int(channel_id), int(seconds)))
        if os.path.exists(deleted_channels_path):
            with open(deleted_channels_path, 'r', encoding='utf-8') as f:
                deleted_channels = json.load(f)
            for channel_id, data in deleted_channels.items():
                category_id = data.get("category_id")
                if category_id is not None:
                    await self._db.execute("""
                        INSERT OR REPLACE INTO deleted_channels (channel_id, category_id)
                        VALUES (?, ?)
                    """, (int(channel_id), int(category_id)))
        await self._db.commit()
