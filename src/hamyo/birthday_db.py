"""
생일 데이터베이스 관리 모듈
유저의 생일 정보를 SQLite에 저장하고 관리합니다.
"""

import aiosqlite
from pathlib import Path
from typing import Optional, Dict

DB_PATH = Path("data/birthday.db")


async def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # 생일 정보 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS birthdays (
                user_id TEXT PRIMARY KEY,
                year INTEGER,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                edit_count INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 기존 테이블에 edit_count 컬럼 추가 (마이그레이션)
        try:
            await db.execute("ALTER TABLE birthdays ADD COLUMN edit_count INTEGER DEFAULT 0")
        except Exception:
            pass  # 이미 컬럼이 있으면 무시
        
        await db.commit()
    print(f"✅ Birthday DB initialized at {DB_PATH}")


async def get_db():
    """데이터베이스 연결 반환 (Row factory 설정)"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def register_birthday(user_id: str, year: Optional[int], month: int, day: int) -> bool:
    """
    생일 등록 또는 업데이트
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
        year: 생년 (선택사항, None 가능)
        month: 월 (1-12)
        day: 일 (1-31)
    
    Returns:
        bool: 성공 여부
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 기존 데이터 확인
            async with db.execute(
                "SELECT edit_count FROM birthdays WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                current_edit_count = row[0] if row else 0
            
            # 수정 횟수가 2 이상이면 실패
            if current_edit_count >= 2:
                return False
            
            # 새로운 수정 횟수 계산
            new_edit_count = current_edit_count + 1
            
            await db.execute("""
                INSERT INTO birthdays (user_id, year, month, day, edit_count, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    year = excluded.year,
                    month = excluded.month,
                    day = excluded.day,
                    edit_count = ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, year, month, day, new_edit_count, new_edit_count))
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 생일 등록 오류: {e}")
        return False


async def admin_update_birthday(user_id: str, year: Optional[int], month: int, day: int) -> bool:
    """
    관리자 전용: 생일 강제 업데이트 (수정 횟수 무시)
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
        year: 생년 (선택사항, None 가능)
        month: 월 (1-12)
        day: 일 (1-31)
    
    Returns:
        bool: 성공 여부
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 기존 edit_count 유지하면서 생일만 업데이트
            await db.execute("""
                INSERT INTO birthdays (user_id, year, month, day, edit_count, updated_at)
                VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    year = excluded.year,
                    month = excluded.month,
                    day = excluded.day,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, year, month, day))
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 관리자 생일 업데이트 오류: {e}")
        return False


async def get_birthday(user_id: str) -> Optional[Dict]:
    """
    특정 유저의 생일 정보 조회
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        Dict 또는 None: {'user_id', 'year', 'month', 'day', 'edit_count', 'registered_at', 'updated_at'}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM birthdays WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # sqlite3.Row는 get() 메서드가 없으므로 키 존재 여부 확인 후 접근
                try:
                    edit_count = row["edit_count"]
                except (KeyError, IndexError):
                    edit_count = 0
                
                return {
                    "user_id": row["user_id"],
                    "year": row["year"],
                    "month": row["month"],
                    "day": row["day"],
                    "edit_count": edit_count,
                    "registered_at": row["registered_at"],
                    "updated_at": row["updated_at"]
                }
            return None


async def delete_birthday(user_id: str) -> bool:
    """
    생일 정보 삭제
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        bool: 성공 여부
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM birthdays WHERE user_id = ?", (user_id,))
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 생일 삭제 오류: {e}")
        return False


async def get_all_birthdays() -> list:
    """
    모든 유저의 생일 정보 조회
    
    Returns:
        list: 생일 정보 딕셔너리 리스트
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM birthdays") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "user_id": row["user_id"],
                    "year": row["year"],
                    "month": row["month"],
                    "day": row["day"],
                    "registered_at": row["registered_at"],
                    "updated_at": row["updated_at"]
                }
                for row in rows
            ]


async def get_birthdays_by_date(month: int, day: int) -> list:
    """
    특정 날짜(월/일)에 해당하는 생일 조회
    
    Args:
        month: 월 (1-12)
        day: 일 (1-31)
    
    Returns:
        list: 해당 날짜가 생일인 유저 정보 리스트
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM birthdays WHERE month = ? AND day = ?", (month, day)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "user_id": row["user_id"],
                    "year": row["year"],
                    "month": row["month"],
                    "day": row["day"],
                    "registered_at": row["registered_at"],
                    "updated_at": row["updated_at"]
                }
                for row in rows
            ]
