import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import pytz

KST = pytz.timezone("Asia/Seoul")

db_path = "data/level_system.db"

class LevelDataManager:
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()
    
    def __new__(cls, db_path: str = db_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, db_path: str = db_path):
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    async def ensure_initialized(self):
        if not LevelDataManager._initialized:
            async with LevelDataManager._init_lock:
                if not LevelDataManager._initialized:
                    await self.initialize_database()
                    LevelDataManager._initialized = True
    
    async def initialize_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        async with aiosqlite.connect(self.db_path) as db:
            # 유저 경험치 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_exp (
                    user_id INTEGER PRIMARY KEY,
                    total_exp INTEGER DEFAULT 0,
                    current_role TEXT DEFAULT 'hub',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 퀘스트 로그 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS quest_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    quest_type TEXT,
                    quest_subtype TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exp_gained INTEGER DEFAULT 0,
                    week_start DATE,
                    FOREIGN KEY (user_id) REFERENCES user_exp (user_id)
                )
            """)
            
            # 일회성 퀘스트 완료 기록
            await db.execute("""
                CREATE TABLE IF NOT EXISTS one_time_quests (
                    user_id INTEGER,
                    quest_type TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, quest_type),
                    FOREIGN KEY (user_id) REFERENCES user_exp (user_id)
                )
            """)
            
            # 랭크 인증 테이블
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rank_certifications (
                    user_id INTEGER,
                    rank_type TEXT,
                    certified_level INTEGER,
                    certified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, rank_type),
                    FOREIGN KEY (user_id) REFERENCES user_exp (user_id)
                )
            """)
            
            await db.commit()
    
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
    
    async def add_exp(self, user_id: int, exp_amount: int, quest_type: str = None, quest_subtype: str = None) -> bool:
        await self.ensure_initialized()
        """다공 지급"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 유저 다공 업데이트 또는 생성
                await db.execute("""
                    INSERT INTO user_exp (user_id, total_exp) 
                    VALUES (?, ?) 
                    ON CONFLICT(user_id) 
                    DO UPDATE SET 
                        total_exp = total_exp + ?,
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id, exp_amount, exp_amount))
                
                # 퀘스트 로그 기록
                if quest_type:
                    week_start = self._get_week_start(datetime.now(KST))
                    await db.execute("""
                        INSERT INTO quest_logs (user_id, quest_type, quest_subtype, exp_gained, week_start)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, quest_type, quest_subtype, exp_amount, week_start))
                
                await db.commit()
                self.logger.info(f"Added {exp_amount} 다공 to user {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error adding 다공: {e}")
            return False
    
    async def get_user_exp(self, user_id: int) -> Dict[str, Any]:
        await self.ensure_initialized()
        """유저 다공 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT total_exp, current_role, last_updated 
                    FROM user_exp 
                    WHERE user_id = ?
                """, (user_id,))
                result = await cursor.fetchone()
                
                if result:
                    return {
                        'user_id': user_id,
                        'total_exp': result[0],
                        'current_role': result[1],
                        'last_updated': result[2]
                    }
                else:
                    return {
                        'user_id': user_id,
                        'total_exp': 0,
                        'current_role': 'hub',
                        'last_updated': None
                    }
        except Exception as e:
            self.logger.error(f"Error getting user exp: {e}")
            return None
    
    async def remove_exp(self, user_id: int, exp_amount: int) -> bool:
        await self.ensure_initialized()
        """다공 회수"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE user_exp 
                    SET total_exp = MAX(0, total_exp - ?),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (exp_amount, user_id))
                await db.commit()
                self.logger.info(f"Removed {exp_amount} 다공 from user {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error removing 다공: {e}")
            return False
    
    async def reset_all_users(self) -> bool:
        await self.ensure_initialized()
        """전체 유저 초기화"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM user_exp")
                await db.execute("DELETE FROM quest_logs")
                await db.execute("DELETE FROM one_time_quests")
                await db.commit()
                self.logger.info("Reset all users")
                return True
        except Exception as e:
            self.logger.error(f"Error resetting all users: {e}")
            return False
    
    async def reset_user(self, user_id: int) -> bool:
        await self.ensure_initialized()
        """특정 유저 초기화"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM user_exp WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM quest_logs WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM one_time_quests WHERE user_id = ?", (user_id,))
                await db.commit()
                self.logger.info(f"Reset user {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error resetting user: {e}")
            return False
    
    async def get_quest_count(self, user_id: int, quest_type: str, quest_subtype: str = None, timeframe: str = 'week') -> int:
        await self.ensure_initialized()
        """퀘스트 완료 횟수 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if timeframe == 'week':
                    week_start = self._get_week_start()
                    if quest_subtype:
                        cursor = await db.execute("""
                            SELECT COUNT(*) FROM quest_logs 
                            WHERE user_id = ? AND quest_type = ? AND quest_subtype = ? AND week_start = ?
                        """, (user_id, quest_type, quest_subtype, week_start))
                    else:
                        cursor = await db.execute("""
                            SELECT COUNT(*) FROM quest_logs 
                            WHERE user_id = ? AND quest_type = ? AND week_start = ?
                        """, (user_id, quest_type, week_start))
                else:  # all time
                    if quest_subtype:
                        cursor = await db.execute("""
                            SELECT COUNT(*) FROM quest_logs 
                            WHERE user_id = ? AND quest_type = ? AND quest_subtype = ?
                        """, (user_id, quest_type, quest_subtype))
                    else:
                        cursor = await db.execute("""
                            SELECT COUNT(*) FROM quest_logs 
                            WHERE user_id = ? AND quest_type = ?
                        """, (user_id, quest_type))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting quest count: {e}")
            return 0
    
    async def is_one_time_quest_completed(self, user_id: int, quest_type: str) -> bool:
        await self.ensure_initialized()
        """일회성 퀘스트 완료 여부 확인"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 1 FROM one_time_quests 
                    WHERE user_id = ? AND quest_type = ?
                """, (user_id, quest_type))
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            self.logger.error(f"Error checking one-time quest: {e}")
            return False
    
    async def mark_one_time_quest_completed(self, user_id: int, quest_type: str) -> bool:
        await self.ensure_initialized()
        """일회성 퀘스트 완료 표시"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO one_time_quests (user_id, quest_type)
                    VALUES (?, ?)
                """, (user_id, quest_type))
                await db.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error marking one-time quest: {e}")
            return False
    
    async def update_user_role(self, user_id: int, new_role: str) -> bool:
        await self.ensure_initialized()
        """유저 역할 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE user_exp 
                    SET current_role = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (new_role, user_id))
                await db.commit()
                self.logger.info(f"Updated user {user_id} role to {new_role}")
                return True
        except Exception as e:
            self.logger.error(f"Error updating user role: {e}")
            return False

    async def get_period_rankings(self, period_type: str, limit: int = 20) -> list:
        await self.ensure_initialized()
        """기간별 순위 데이터 가져오기"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if period_type == 'total':
                    # 누적 순위
                    cursor = await db.execute("""
                        SELECT user_id, total_exp, current_role
                        FROM user_exp 
                        WHERE total_exp > 0
                        ORDER BY total_exp DESC 
                        LIMIT ?
                    """, (limit,))
                elif period_type == 'daily':
                    # 일간 순위 (오늘 획득한 경험치, KST 기준)
                    today_kst = datetime.now(KST).strftime('%Y-%m-%d')
                    cursor = await db.execute("""
                        SELECT ql.user_id, SUM(ql.exp_gained) as period_exp, 
                               COALESCE(ue.current_role, 'hub') as current_role
                        FROM quest_logs ql
                        LEFT JOIN user_exp ue ON ql.user_id = ue.user_id
                        WHERE DATE(ql.completed_at, 'localtime') = ?
                        GROUP BY ql.user_id
                        HAVING period_exp > 0
                        ORDER BY period_exp DESC
                        LIMIT ?
                    """, (today_kst, limit))
                elif period_type == 'weekly':
                    # 주간 순위 (이번 주 획득한 경험치)
                    week_start = self._get_week_start(datetime.now(KST))
                    cursor = await db.execute("""
                        SELECT ql.user_id, SUM(ql.exp_gained) as period_exp,
                               COALESCE(ue.current_role, 'hub') as current_role
                        FROM quest_logs ql
                        LEFT JOIN user_exp ue ON ql.user_id = ue.user_id
                        WHERE ql.week_start = ?
                        GROUP BY ql.user_id
                        HAVING period_exp > 0
                        ORDER BY period_exp DESC
                        LIMIT ?
                    """, (week_start, limit))
                elif period_type == 'monthly':
                    # 월간 순위 (이번 달 획득한 경험치)
                    month_kst = datetime.now(KST).strftime('%Y-%m')
                    cursor = await db.execute("""
                        SELECT ql.user_id, SUM(ql.exp_gained) as period_exp,
                               COALESCE(ue.current_role, 'hub') as current_role
                        FROM quest_logs ql
                        LEFT JOIN user_exp ue ON ql.user_id = ue.user_id
                        WHERE strftime('%Y-%m', ql.completed_at, 'localtime') = ?
                        GROUP BY ql.user_id
                        HAVING period_exp > 0
                        ORDER BY period_exp DESC
                        LIMIT ?
                    """, (month_kst, limit))
                else:
                    return []
                
                results = await cursor.fetchall()
                return results if results else []
                
        except Exception as e:
            self.logger.error(f"Error getting period rankings for {period_type}: {e}")
            return []
    
    async def get_user_period_exp(self, user_id: int, period_type: str) -> int:
        await self.ensure_initialized()
        """특정 유저의 기간별 경험치 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if period_type == 'total':
                    # 누적 경험치
                    cursor = await db.execute("""
                        SELECT total_exp FROM user_exp WHERE user_id = ?
                    """, (user_id,))
                elif period_type == 'daily':
                    # 오늘 획득한 경험치
                    today_kst = datetime.now(KST).strftime('%Y-%m-%d')
                    cursor = await db.execute("""
                        SELECT COALESCE(SUM(exp_gained), 0) as daily_exp
                        FROM quest_logs 
                        WHERE user_id = ? AND DATE(completed_at, 'localtime') = ?
                    """, (user_id, today_kst))
                elif period_type == 'weekly':
                    # 이번 주 획득한 경험치
                    week_start = self._get_week_start(datetime.now(KST))
                    cursor = await db.execute("""
                        SELECT COALESCE(SUM(exp_gained), 0) as weekly_exp
                        FROM quest_logs 
                        WHERE user_id = ? AND week_start = ?
                    """, (user_id, week_start))
                elif period_type == 'monthly':
                    # 이번 달 획득한 경험치
                    month_kst = datetime.now(KST).strftime('%Y-%m')
                    cursor = await db.execute("""
                        SELECT COALESCE(SUM(exp_gained), 0) as monthly_exp
                        FROM quest_logs 
                        WHERE user_id = ? AND strftime('%Y-%m', completed_at, 'localtime') = ?
                    """, (user_id, month_kst))
                else:
                    return 0
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            self.logger.error(f"Error getting user period exp for {period_type}: {e}")
            return 0
    
    async def get_user_period_rank(self, user_id: int, period_type: str) -> int:
        await self.ensure_initialized()
        """특정 유저의 기간별 순위 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if period_type == 'total':
                    # 누적 순위
                    cursor = await db.execute("""
                        SELECT COUNT(*) + 1 as rank
                        FROM user_exp u1
                        WHERE u1.total_exp > (
                            SELECT COALESCE(total_exp, 0) FROM user_exp WHERE user_id = ?
                        )
                    """, (user_id,))
                elif period_type == 'daily':
                    # 일간 순위
                    today_kst = datetime.now(KST).strftime('%Y-%m-%d')
                    cursor = await db.execute("""
                        SELECT COUNT(*) + 1 as rank
                        FROM (
                            SELECT user_id, SUM(exp_gained) as daily_exp
                            FROM quest_logs 
                            WHERE DATE(completed_at, 'localtime') = ?
                            GROUP BY user_id
                        ) daily_ranks
                        WHERE daily_exp > (
                            SELECT COALESCE(SUM(exp_gained), 0)
                            FROM quest_logs 
                            WHERE user_id = ? AND DATE(completed_at, 'localtime') = ?
                        )
                    """, (today_kst, user_id, today_kst))
                elif period_type == 'weekly':
                    # 주간 순위
                    week_start = self._get_week_start(datetime.now(KST))
                    cursor = await db.execute("""
                        SELECT COUNT(*) + 1 as rank
                        FROM (
                            SELECT user_id, SUM(exp_gained) as weekly_exp
                            FROM quest_logs 
                            WHERE week_start = ?
                            GROUP BY user_id
                        ) weekly_ranks
                        WHERE weekly_exp > (
                            SELECT COALESCE(SUM(exp_gained), 0)
                            FROM quest_logs 
                            WHERE user_id = ? AND week_start = ?
                        )
                    """, (week_start, user_id, week_start))
                elif period_type == 'monthly':
                    # 월간 순위
                    month_kst = datetime.now(KST).strftime('%Y-%m')
                    cursor = await db.execute("""
                        SELECT COUNT(*) + 1 as rank
                        FROM (
                            SELECT user_id, SUM(exp_gained) as monthly_exp
                            FROM quest_logs 
                            WHERE strftime('%Y-%m', completed_at, 'localtime') = ?
                            GROUP BY user_id
                        ) monthly_ranks
                        WHERE monthly_exp > (
                            SELECT COALESCE(SUM(exp_gained), 0)
                            FROM quest_logs 
                            WHERE user_id = ? AND strftime('%Y-%m', completed_at, 'localtime') = ?
                        )
                    """, (month_kst, user_id, month_kst))
                else:
                    return 1
                
                result = await cursor.fetchone()
                return result[0] if result else 1
                
        except Exception as e:
            self.logger.error(f"Error getting user period rank for {period_type}: {e}")
            return 1
    
    async def get_period_summary(self, user_id: int) -> Dict[str, int]:
        await self.ensure_initialized()
        """유저의 모든 기간별 경험치 요약"""
        try:
            summary = {}
            for period in ['daily', 'weekly', 'monthly', 'total']:
                summary[period] = await self.get_user_period_exp(user_id, period)
            return summary
        except Exception as e:
            self.logger.error(f"Error getting period summary: {e}")
            return {'daily': 0, 'weekly': 0, 'monthly': 0, 'total': 0}
        
    async def get_certified_rank_level(self, user_id: int, rank_type: str) -> int:
        """유저의 인증된 랭크 레벨 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT certified_level FROM rank_certifications 
                    WHERE user_id = ? AND rank_type = ?
                """, (user_id, rank_type))
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting certified rank level: {e}")
            return 0

    async def update_certified_rank_level(self, user_id: int, rank_type: str, new_level: int) -> bool:
        """유저의 인증된 랭크 레벨 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO rank_certifications (user_id, rank_type, certified_level)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, rank_type)
                    DO UPDATE SET 
                        certified_level = ?,
                        certified_at = CURRENT_TIMESTAMP
                """, (user_id, rank_type, new_level, new_level))
                await db.commit()
                self.logger.info(f"Updated {rank_type} rank level for user {user_id} to {new_level}")
                return True
        except Exception as e:
            self.logger.error(f"Error updating certified rank level: {e}")
            return False

    async def get_all_certified_ranks(self, user_id: int) -> Dict[str, int]:
        """유저의 모든 인증된 랭크 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT rank_type, certified_level FROM rank_certifications 
                    WHERE user_id = ?
                """, (user_id,))
                results = await cursor.fetchall()
                return {rank_type: level for rank_type, level in results}
        except Exception as e:
            self.logger.error(f"Error getting all certified ranks: {e}")
            return {}

