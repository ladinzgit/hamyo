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
        # 생일 정보 테이블 (edit_count 제거)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS birthdays (
                user_id TEXT PRIMARY KEY,
                year INTEGER,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 수정 횟수 관리 테이블 (별도 테이블로 분리)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_edit_count (
                user_id TEXT PRIMARY KEY,
                edit_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 기존 birthdays 테이블에서 edit_count 데이터를 user_edit_count로 마이그레이션
        try:
            # edit_count 컬럼이 있는지 확인
            async with db.execute("PRAGMA table_info(birthdays)") as cursor:
                columns = await cursor.fetchall()
                has_edit_count = any(col[1] == 'edit_count' for col in columns)
            
            if has_edit_count:
                # 기존 데이터 마이그레이션
                await db.execute("""
                    INSERT OR REPLACE INTO user_edit_count (user_id, edit_count, last_updated)
                    SELECT user_id, edit_count, updated_at FROM birthdays WHERE edit_count > 0
                """)
                
                # birthdays 테이블에서 edit_count 컬럼 제거
                # SQLite는 컬럼 삭제를 직접 지원하지 않으므로 테이블 재생성
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS birthdays_new (
                        user_id TEXT PRIMARY KEY,
                        year INTEGER,
                        month INTEGER NOT NULL,
                        day INTEGER NOT NULL,
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.execute("""
                    INSERT INTO birthdays_new (user_id, year, month, day, registered_at, updated_at)
                    SELECT user_id, year, month, day, registered_at, updated_at FROM birthdays
                """)
                
                await db.execute("DROP TABLE birthdays")
                await db.execute("ALTER TABLE birthdays_new RENAME TO birthdays")
                
                print("✅ Migration completed: edit_count moved to user_edit_count table")
        except Exception as e:
            print(f"⚠️ Migration warning (can be ignored if fresh install): {e}")
        
        await db.commit()
    print(f"✅ Birthday DB initialized at {DB_PATH}")


async def get_db():
    """데이터베이스 연결 반환 (Row factory 설정)"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def get_user_edit_count(user_id: str) -> int:
    """
    유저의 수정 횟수 조회
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        int: 수정 횟수 (0-2)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT edit_count FROM user_edit_count WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def increment_edit_count(user_id: str) -> int:
    """
    유저의 수정 횟수 증가
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        int: 증가된 수정 횟수
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 현재 수정 횟수 조회
        current_count = await get_user_edit_count(user_id)
        new_count = current_count + 1
        
        await db.execute("""
            INSERT INTO user_edit_count (user_id, edit_count, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                edit_count = excluded.edit_count,
                last_updated = CURRENT_TIMESTAMP
        """, (user_id, new_count))
        await db.commit()
        
        return new_count


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
            # 기존 수정 횟수 확인
            current_edit_count = await get_user_edit_count(user_id)
            
            # 수정 횟수가 2 이상이면 실패
            if current_edit_count >= 2:
                return False
            
            # 생일 정보 저장/업데이트
            await db.execute("""
                INSERT INTO birthdays (user_id, year, month, day, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    year = excluded.year,
                    month = excluded.month,
                    day = excluded.day,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, year, month, day))
            await db.commit()
            
            # 수정 횟수 증가
            await increment_edit_count(user_id)
        
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
            # 생일 정보만 업데이트 (edit_count는 건드리지 않음)
            await db.execute("""
                INSERT INTO birthdays (user_id, year, month, day, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                # 수정 횟수는 별도 테이블에서 조회
                edit_count = await get_user_edit_count(user_id)
                
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
    생일 정보 삭제 (수정 횟수는 유지됨)
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        bool: 성공 여부
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # birthdays 테이블에서만 삭제, user_edit_count는 유지
            await db.execute("DELETE FROM birthdays WHERE user_id = ?", (user_id,))
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 생일 삭제 오류: {e}")
        return False


async def reset_edit_count(user_id: str) -> bool:
    """
    관리자 전용: 특정 유저의 수정 횟수 초기화
    
    Args:
        user_id: 디스코드 유저 ID (문자열)
    
    Returns:
        bool: 성공 여부
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM user_edit_count WHERE user_id = ?", (user_id,)
            )
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 수정 횟수 초기화 오류: {e}")
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


async def swap_user_birthday_data(old_user_id: str, new_user_id: str) -> bool:
    """
    생일 데이터에서 old_user_id의 정보를 new_user_id로 통합합니다.
    본계정(new_user_id)에 생일 정보가 이미 있다면 부계정 정보는 무시(삭제)됩니다.
    없다면 부계정 정보를 본계정으로 이동합니다.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 1. 본계정 존재 여부 확인
            async with db.execute("SELECT 1 FROM birthdays WHERE user_id = ?", (new_user_id,)) as cursor:
                main_exists = await cursor.fetchone()
            
            if main_exists:
                # 본계정이 이미 있으면 부계정 데이터는 그냥 삭제 (본계정 유지)
                await db.execute("DELETE FROM birthdays WHERE user_id = ?", (old_user_id,))
                await db.execute("DELETE FROM user_edit_count WHERE user_id = ?", (old_user_id,))
            else:
                # 본계정이 없으면 부계정 -> 본계정 이동
                await db.execute("UPDATE birthdays SET user_id = ? WHERE user_id = ?", (new_user_id, old_user_id))
                await db.execute("UPDATE user_edit_count SET user_id = ? WHERE user_id = ?", (new_user_id, old_user_id))
            
            await db.commit()
        return True
    except Exception as e:
        print(f"❌ 생일 데이터 스왑 오류: {e}")
        return False
