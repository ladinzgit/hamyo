import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import pytz
import os

KST = pytz.timezone("Asia/Seoul")
db_path = "data/tree.db"

class TreeDataManager:
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()
    
    def __new__(cls, db_path: str = db_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = db_path
            cls._instance._db = None
        return cls._instance
    
    def __init__(self, db_path: str = db_path):
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
            self._db = None
        self.logger = logging.getLogger(__name__)
    
    async def ensure_initialized(self):
        if not TreeDataManager._initialized:
            async with TreeDataManager._init_lock:
                if not TreeDataManager._initialized:
                    await self.initialize_database()
                    TreeDataManager._initialized = True
    
    async def initialize_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        
        # 유저 눈송이 테이블
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS user_snowflakes (
                user_id INTEGER PRIMARY KEY,
                amount INTEGER DEFAULT 0,
                total_gathered INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 퀘스트 로그 테이블
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS quest_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quest_name TEXT,
                quest_subtype TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount_gained INTEGER DEFAULT 0,
                week_start DATE,
                FOREIGN KEY (user_id) REFERENCES user_snowflakes (user_id)
            )
        """)
        
        await self._db.commit()
    
    def db_connect(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        return aiosqlite.connect(self.db_path)
    
    def _get_week_start(self, date: datetime = None) -> str:
        """주의 시작일 계산 (월요일 기준, KST)"""
        if date is None:
            date = datetime.now(KST)
        else:
            date = date.astimezone(KST)
        days_since_monday = date.weekday()
        week_start = date - timedelta(days=days_since_monday)
        return week_start.strftime('%Y-%m-%d')
    
    async def add_snowflake(self, user_id: int, amount: int, quest_name: str = None, quest_subtype: str = None) -> bool:
        await self.ensure_initialized()
        """눈송이 지급"""
        try:
            # 유저 눈송이 업데이트 또는 생성
            await self._db.execute("""
                INSERT INTO user_snowflakes (user_id, amount, total_gathered) 
                VALUES (?, ?, ?) 
                ON CONFLICT(user_id) 
                DO UPDATE SET 
                    amount = amount + ?,
                    total_gathered = total_gathered + ?,
                    last_updated = CURRENT_TIMESTAMP
            """, (user_id, amount, amount, amount, amount))
            
            # 퀘스트 로그 기록
            if quest_name:
                week_start = self._get_week_start(datetime.now(KST))
                await self._db.execute("""
                    INSERT INTO quest_logs (user_id, quest_name, quest_subtype, amount_gained, week_start)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, quest_name, quest_subtype, amount, week_start))
            
            await self._db.commit()
            self.logger.info(f"Added {amount} snowflakes to user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error adding snowflakes: {e}")
            return False
            
    async def remove_snowflake(self, user_id: int, amount: int) -> bool:
        await self.ensure_initialized()
        try:
            await self._db.execute("""
                UPDATE user_snowflakes 
                SET amount = MAX(0, amount - ?),
                    total_gathered = MAX(0, total_gathered - ?),
                    last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (amount, amount, user_id))
            await self._db.commit()
            self.logger.info(f"Removed {amount} snowflakes from user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error removing snowflakes: {e}")
            return False

    async def get_user_snowflake(self, user_id: int) -> Dict[str, Any]:
        await self.ensure_initialized()
        """유저 눈송이 정보 조회"""
        try:
            cursor = await self._db.execute("""
                SELECT amount, total_gathered, last_updated 
                FROM user_snowflakes 
                WHERE user_id = ?
            """, (user_id,))
            result = await cursor.fetchone()
            
            if result:
                return {
                    'user_id': user_id,
                    'amount': result[0],
                    'total_gathered': result[1],
                    'last_updated': result[2]
                }
            else:
                return {
                    'user_id': user_id,
                    'amount': 0,
                    'total_gathered': 0,
                    'last_updated': None
                }
        except Exception as e:
            self.logger.error(f"Error getting user snowflake: {e}")
            return None

    async def check_mission_completion(self, user_id: int, quest_name: str, periodicity: str = 'daily') -> bool:
        await self.ensure_initialized()
        """미션 수행 여부 확인
           periodicity: 'one_time' (전체 기간 1회), 'daily' (하루 1회)
        """
        try:
            if periodicity == 'one_time':
                cursor = await self._db.execute("""
                    SELECT 1 FROM quest_logs 
                    WHERE user_id = ? AND quest_name = ?
                    LIMIT 1
                """, (user_id, quest_name))
                result = await cursor.fetchone()
                return result is not None
                
            elif periodicity == 'daily':
                today_kst = datetime.now(KST).strftime('%Y-%m-%d')
                cursor = await self._db.execute("""
                    SELECT 1 FROM quest_logs 
                    WHERE user_id = ? AND quest_name = ? 
                    AND DATE(completed_at, '+9 hours') = ?
                    LIMIT 1
                """, (user_id, quest_name, today_kst))
                result = await cursor.fetchone()
                return result is not None
            
            else:
                # Default to checking if any exist? Or False?
                # Instruction 52: "다회성이라면 해당 날짜에만... 일회성이라면 모든 기록..."
                # There are only these two types mentioned for specific logic.
                return False

        except Exception as e:
            self.logger.error(f"Error checking mission completion: {e}")
            return False

    async def get_tree_status(self) -> Dict[str, int]:
        await self.ensure_initialized()
        """트리 상태(전체 눈송이 합계) 조회"""
        try:
            # Using total_gathered to calculate tree growth
            cursor = await self._db.execute("""
                SELECT SUM(total_gathered) FROM user_snowflakes
            """)
            result = await cursor.fetchone()
            total_snowflakes = result[0] if result[0] else 0
            
            # Calculate Level
            # 0단계 : 0
            # 1단계 : 700
            # 2단계 : 1500
            # 3단계 : 2500
            # 4단계 : 4000
            level = 0
            next_level_exp = 700
            
            if total_snowflakes >= 4000:
                level = 4
                next_level_exp = 0 # Max level
            elif total_snowflakes >= 2500:
                level = 3
                next_level_exp = 4000
            elif total_snowflakes >= 1500:
                level = 2
                next_level_exp = 2500
            elif total_snowflakes >= 700:
                level = 1
                next_level_exp = 1500
            else:
                level = 0
                next_level_exp = 700
                
            return {
                'total_snowflakes': total_snowflakes,
                'level': level,
                'next_level_exp': next_level_exp
            }
        except Exception as e:
            self.logger.error(f"Error getting tree status: {e}")
            return {'total_snowflakes': 0, 'level': 0, 'next_level_exp': 500}

    async def get_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        await self.ensure_initialized()
        """눈송이 기여도 순위 조회"""
        try:
            cursor = await self._db.execute("""
                SELECT user_id, total_gathered
                FROM user_snowflakes 
                WHERE total_gathered > 0
                ORDER BY total_gathered DESC 
                LIMIT ?
            """, (limit,))
            results = await cursor.fetchall()
            
            rankings = []
            for row in results:
                rankings.append({
                    'user_id': row[0],
                    'total_gathered': row[1]
                })
            return rankings
        except Exception as e:
            self.logger.error(f"Error getting rankings: {e}")
            return []

    async def get_user_rank(self, user_id: int) -> int:
        await self.ensure_initialized()
        """유저 순위 조회"""
        try:
            cursor = await self._db.execute("""
                SELECT COUNT(*) + 1
                FROM user_snowflakes
                WHERE total_gathered > (
                    SELECT total_gathered FROM user_snowflakes WHERE user_id = ?
                )
            """, (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting user rank: {e}")
            return 0

    async def reset_database(self) -> bool:
        """데이터베이스 초기화 (모든 데이터 삭제)"""
        await self.ensure_initialized()
        try:
            await self._db.execute("DELETE FROM user_snowflakes")
            await self._db.execute("DELETE FROM quest_logs")
            await self._db.execute("DELETE FROM sqlite_sequence WHERE name='quest_logs'") # Reset autoincrement
            await self._db.commit()
            self.logger.info("Database reset complete.")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting database: {e}")
            return False
