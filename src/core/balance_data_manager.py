import aiosqlite
import asyncio
import os
from datetime import datetime
import pytz
KST = pytz.timezone("Asia/Seoul")
DB_FILE = "data/balance.db"

class BalanceDataManager:
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()

    def __new__(cls, db_path: str = DB_FILE):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = db_path
            cls._instance._db = None
        return cls._instance

    def __init__(self, db_path: str = DB_FILE):
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
            self._db = None

    async def ensure_initialized(self):
        if not BalanceDataManager._initialized:
            async with self._init_lock:
                if not BalanceDataManager._initialized:
                    await self.init_db()
                    BalanceDataManager._initialized = True

    async def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)

        await self._db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS auth (
                item TEXT PRIMARY KEY,
                reward_amount INTEGER DEFAULT 100
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS auth_roles (
                role_id INTEGER PRIMARY KEY
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS currency_unit (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                emoji TEXT
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_channels (
                channel_id INTEGER
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS transfers (          -- 송금 테이블
                id INTEGER PRIMARY KEY AUTOINCREMENT,       -- 당일 송금 내역 확인을 위한 Key값 (자동증가, 중복방지)
                sender_id TEXT NOT NULL,                    -- 보내는 유저 ID
                receiver_id TEXT NOT NULL,                  -- 받는 유저 ID
                amount INTEGER NOT NULL,                    -- 송금 금액
                fee INTEGER NOT NULL,                       -- 수수료
                timestamp TEXT NOT NULL                     -- 송금 시각
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS fee_tiers (          -- 수수료 단계 테이블
                fee_threshold INTEGER PRIMARY KEY,          -- 기준 금액 (이 금액 이상일 때 해당 수수료 적용)
                fee INTEGER NOT NULL                        -- 수수료
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS transfer_limits (    -- 송금 제한 테이블
                id INTEGER PRIMARY KEY CHECK (id = 1),      -- 하나만 존재하도록 강제
                daily_send_limit INTEGER,         -- 일일 송금 제한
                daily_receive_limit INTEGER       -- 일일 수취 제한
            )
        """)
        await self._db.commit()
    
    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
            BalanceDataManager._initialized = False

    async def get_balance(self, user_id):
        await self.ensure_initialized()
        async with self._db.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def give(self, user_id, amount):
        await self.ensure_initialized()
        await self._db.execute("""
            INSERT INTO balances (user_id, balance)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
        """, (user_id, amount))
        await self._db.commit()

    async def take(self, user_id, amount):
        await self.ensure_initialized()
        await self._db.execute("""
            UPDATE balances SET balance = balance - ?
            WHERE user_id = ?
        """, (amount, user_id))
        await self._db.commit()

    async def add_auth_item(self, item, reward_amount):
        await self.ensure_initialized()
        await self._db.execute("INSERT OR REPLACE INTO auth (item, reward_amount) VALUES (?, ?)", (item, reward_amount))
        await self._db.commit()

    async def remove_auth_item(self, item):
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM auth WHERE item = ?", (item,))
        await self._db.commit()

    async def is_item_authed(self, item):
        await self.ensure_initialized()
        async with self._db.execute("SELECT 1 FROM auth WHERE item = ?", (item,)) as cursor:
            return await cursor.fetchone() is not None

    async def get_auth_reward_amount(self, item):
        await self.ensure_initialized()
        async with self._db.execute("SELECT reward_amount FROM auth WHERE item = ?", (item,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def list_auth_items(self):
        await self.ensure_initialized()
        async with self._db.execute("SELECT item, reward_amount FROM auth") as cursor:
            rows = await cursor.fetchall()
            return [{"item": row[0], "reward_amount": row[1]} for row in rows]

    # 인증 역할 관련
    async def add_auth_role(self, role_id):
        await self.ensure_initialized()
        await self._db.execute("INSERT OR IGNORE INTO auth_roles (role_id) VALUES (?)", (role_id,))
        await self._db.commit()

    async def remove_auth_role(self, role_id):
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM auth_roles WHERE role_id = ?", (role_id,))
        await self._db.commit()

    async def list_auth_roles(self):
        await self.ensure_initialized()
        async with self._db.execute("SELECT role_id FROM auth_roles") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # 화폐 단위 관련
    async def set_currency_unit(self, emoji):
        await self.ensure_initialized()
        await self._db.execute("INSERT OR REPLACE INTO currency_unit (id, emoji) VALUES (1, ?)", (emoji,))
        await self._db.commit()

    async def get_currency_unit(self):
        await self.ensure_initialized()
        async with self._db.execute("SELECT emoji FROM currency_unit WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return {"emoji": row[0]}
            return None

    # Economy 명령어 허용 채널 관리
    async def add_allowed_channel(self, channel_id):
        await self.ensure_initialized()
        await self._db.execute("INSERT INTO allowed_channels (channel_id) VALUES (?)", (channel_id,))
        await self._db.commit()

    async def remove_allowed_channel(self, channel_id):
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM allowed_channels WHERE channel_id = ?", (channel_id,))
        await self._db.commit()

    async def list_allowed_channels(self):
        await self.ensure_initialized()
        async with self._db.execute("SELECT channel_id FROM allowed_channels") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # 모든 유저 화폐 초기화 (설정 제외)
    async def reset_all_balances(self):
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM balances")
        await self._db.commit()

    # 화폐 송금 기능
    async def transfer(self, sender_id: str, receiver_id: str, amount: int, fee: int) -> bool:
        """화폐 송금 기능 구현"""
        await self.ensure_initialized()
        try:
            # 송금 전 시작점 설정
            await self._db.execute("BEGIN TRANSACTION")
            
            # 보내는 사람의 잔액 차감 (금액 + 수수료)
            await self._db.execute("""
                UPDATE balances 
                SET balance = balance - ? 
                WHERE user_id = ? AND balance >= ?
            """, (amount + fee, sender_id, amount + fee))
            
            if self._db.total_changes == 0:  # 잔액 부족
                await self._db.execute("ROLLBACK")
                return False
            
            # 받는 사람의 잔액 증가
            await self._db.execute("""
                INSERT INTO balances (user_id, balance) 
                VALUES (?, ?) 
                ON CONFLICT(user_id) DO UPDATE 
                SET balance = balance + excluded.balance
            """, (receiver_id, amount))
            
            # 송금 내역 기록
            current_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
            
            await self._db.execute("""
                INSERT INTO transfers 
                (sender_id, receiver_id, amount, fee, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, amount, fee, current_time))
            
            await self._db.commit()
            return True
            
        except Exception as e:
            print(f"송금오류: {e}")
            await self._db.execute("ROLLBACK")
            return False

    async def get_daily_transfer_count(self, user_id: str, is_sender: bool = True) -> int:
        """금일 송금 횟수 반환"""
        await self.ensure_initialized()
        
        today = datetime.now(KST).strftime("%Y-%m-%d")
        
        if is_sender:
            query = """
                SELECT COUNT(*) FROM transfers 
                WHERE sender_id = ? AND date(timestamp) = ?
            """
        else:
            query = """
                SELECT COUNT(*) FROM transfers 
                WHERE receiver_id = ? AND date(timestamp) = ?
            """
        
        async with self._db.execute(query, (user_id, today)) as cursor:
            count = await cursor.fetchone()
            return count[0] if count else 0

    # 화폐 수수료 설정
    async def set_fee_tiers(self, tiers: list):
        await self.ensure_initialized()
        normalized_input = []
        for t in tiers or []:
            try:
                thr = int(t.get("threshold") if t.get("threshold") is not None else t.get("min_amount"))
                fee = int(t.get("fee"))
                normalized_input.append({"threshold": thr, "fee": fee})
            except Exception:
                continue

        # 수수료 오름차순 정렬
        normalized = sorted(normalized_input, key=lambda x: x["threshold"]) if normalized_input else []
        await self._db.execute("DELETE FROM fee_tiers")
        for t in normalized:
            await self._db.execute("INSERT INTO fee_tiers (fee_threshold, fee) VALUES (?, ?)", (t["threshold"], t["fee"]))
        await self._db.commit()

    # 화폐 수수료 조회
    async def get_fee_tiers(self) -> list:
        await self.ensure_initialized()
        async with self._db.execute("SELECT fee_threshold, fee FROM fee_tiers ORDER BY fee_threshold ASC") as cursor:
            rows = await cursor.fetchall()
            return [{"min_amount": int(row[0]), "fee": int(row[1])} for row in rows]

    # 화폐 수수료 개별 설정
    async def set_fee_tier(self, min_amount: int, fee: int):
        await self.ensure_initialized()
        tiers = await self.get_fee_tiers()
        normalized = [{"threshold": t["min_amount"], "fee": t["fee"]} for t in tiers]

        # 업데이트 / 추가
        found = False
        for t in normalized:
            if t["threshold"] == int(min_amount):
                t["fee"] = int(fee)
                found = True
                break
        if not found:
            normalized.append({"threshold": int(min_amount), "fee": int(fee)})

        await self.set_fee_tiers(normalized)

    # 화폐 수수료 개별 삭제
    async def delete_fee_tier(self, min_amount: int) -> bool:
        await self.ensure_initialized()
        tiers = await self.get_fee_tiers()
        filtered = [t for t in tiers if int(t["min_amount"]) != int(min_amount)]
        if len(filtered) == len(tiers):
            return False
        normalized = [{"threshold": t["min_amount"], "fee": t["fee"]} for t in filtered]
        await self.set_fee_tiers(normalized)
        return True

    # 화폐 수수료 계산
    async def get_fee_for_amount(self, amount: int) -> int:
        await self.ensure_initialized()
        tiers = await self.get_fee_tiers()

        selected_fee = None
        for t in tiers:
            if amount >= t.get("min_amount", 0):
                selected_fee = t.get("fee")
            else:
                break
        return selected_fee if selected_fee is not None else (1000 if amount >= 50000 else 500)

    # 일일 송금/수취 한도 설정
    async def set_daily_limits(self, send_limit: int, receive_limit: int):
        await self.ensure_initialized()
        async with self._db.execute("SELECT 1 FROM transfer_limits WHERE id = 1") as cursor:
            exists = await cursor.fetchone()
        if exists:
            await self._db.execute("UPDATE transfer_limits SET daily_send_limit = ?, daily_receive_limit = ? WHERE id = 1", (int(send_limit), int(receive_limit)))
        else:
            await self._db.execute("INSERT INTO transfer_limits (id, daily_send_limit, daily_receive_limit) VALUES (1, ?, ?)", (int(send_limit), int(receive_limit)))
        await self._db.commit()

    # 일일 송금/수취 한도 조회
    async def get_daily_limits(self):
        await self.ensure_initialized()
        async with self._db.execute("SELECT daily_send_limit, daily_receive_limit FROM transfer_limits WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                try:
                    return int(row[0]), int(row[1])
                except Exception:
                    pass
        return 3, 5

    async def swap_user_balance_data(self, old_user_id: str, new_user_id: str) -> bool:
        """
        특정 유저(old_user_id)의 자산 데이터를 다른 유저(new_user_id)로 통합합니다.
        자산은 합산되며, 송금 내역도 모두 이관됩니다.
        """
        await self.ensure_initialized()
        try:
            async with self._db.execute("BEGIN TRANSACTION"):
                # 1. 잔액 합산
                # old_user 잔액 조회
                async with self._db.execute("SELECT balance FROM balances WHERE user_id = ?", (old_user_id,)) as cursor:
                    row = await cursor.fetchone()
                
                if row:
                    old_balance = row[0]
                    # new_user에게 더하기
                    await self._db.execute("""
                        INSERT INTO balances (user_id, balance) VALUES (?, ?)
                        ON CONFLICT(user_id) 
                        DO UPDATE SET balance = balance + excluded.balance
                    """, (new_user_id, old_balance))
                    
                    # old_user 잔액 삭제
                    await self._db.execute("DELETE FROM balances WHERE user_id = ?", (old_user_id,))

                # 2. 송금 내역 변경 (단순 ID 업데이트)
                await self._db.execute("UPDATE transfers SET sender_id = ? WHERE sender_id = ?", (new_user_id, old_user_id))
                await self._db.execute("UPDATE transfers SET receiver_id = ? WHERE receiver_id = ?", (new_user_id, old_user_id))

            await self._db.commit()
            return True
        except Exception as e:
            print(f"지갑 데이터 스왑 중 오류: {e}")
            await self._db.rollback()
            return False

# 싱글턴 인스턴스
balance_manager = BalanceDataManager()