import aiosqlite
import asyncio

DB_FILE = "data/balance.db"

class BalanceDataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BalanceDataManager, cls).__new__(cls)
        return cls._instance

    async def init_db(self):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auth (
                    item TEXT PRIMARY KEY
                )
            """)
            await db.commit()

    async def get_balance(self, user_id):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def give(self, user_id, amount):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                INSERT INTO balances (user_id, balance)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
            """, (user_id, amount))
            await db.commit()

    async def take(self, user_id, amount):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                UPDATE balances SET balance = balance - ?
                WHERE user_id = ?
            """, (amount, user_id))
            await db.commit()

    async def add_auth_item(self, item):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT OR IGNORE INTO auth (item) VALUES (?)", (item,))
            await db.commit()

    async def remove_auth_item(self, item):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("DELETE FROM auth WHERE item = ?", (item,))
            await db.commit()

    async def is_item_authed(self, item):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT 1 FROM auth WHERE item = ?", (item,)) as cursor:
                return await cursor.fetchone() is not None

    async def give_if_authed(self, user_id, amount, item):
        if await self.is_item_authed(item):
            await self.give(user_id, amount)
            return True
        return False

# 싱글턴 인스턴스
balance_manager = BalanceDataManager()