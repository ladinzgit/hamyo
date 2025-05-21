import aiosqlite
import asyncio

DB_FILE = "data/balance.db"

class BalanceDataManager:
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()

    def __new__(cls, db_path: str = DB_FILE):
        if cls._instance is None:
            cls._instance = super(BalanceDataManager, cls).__new__(cls)
            cls._instance.db_path = db_path
        return cls._instance

    def __init__(self, db_path: str = DB_FILE):
        if not hasattr(self, 'db_path'):
            self.db_path = db_path

    async def ensure_initialized(self):
        if not BalanceDataManager._initialized:
            async with self._init_lock:
                if not BalanceDataManager._initialized:
                    await self.init_db()
                    BalanceDataManager._initialized = True

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auth (
                    item TEXT PRIMARY KEY,
                    reward_amount INTEGER DEFAULT 100
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auth_roles (
                    role_id INTEGER PRIMARY KEY
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS currency_unit (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT,
                    emoji TEXT
                )
            """)
            await db.commit()

    async def get_balance(self, user_id):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def give(self, user_id, amount):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO balances (user_id, balance)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
            """, (user_id, amount))
            await db.commit()

    async def take(self, user_id, amount):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE balances SET balance = balance - ?
                WHERE user_id = ?
            """, (amount, user_id))
            await db.commit()

    async def add_auth_item(self, item, reward_amount):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO auth (item, reward_amount) VALUES (?, ?)", (item, reward_amount))
            await db.commit()

    async def remove_auth_item(self, item):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM auth WHERE item = ?", (item,))
            await db.commit()

    async def is_item_authed(self, item):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM auth WHERE item = ?", (item,)) as cursor:
                return await cursor.fetchone() is not None

    async def get_auth_reward_amount(self, item):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT reward_amount FROM auth WHERE item = ?", (item,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def list_auth_items(self):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT item, reward_amount FROM auth") as cursor:
                rows = await cursor.fetchall()
                return [{"item": row[0], "reward_amount": row[1]} for row in rows]

    # 인증 역할 관련
    async def add_auth_role(self, role_id):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO auth_roles (role_id) VALUES (?)", (role_id,))
            await db.commit()

    async def remove_auth_role(self, role_id):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM auth_roles WHERE role_id = ?", (role_id,))
            await db.commit()

    async def list_auth_roles(self):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id FROM auth_roles") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    # 화폐 단위 관련
    async def set_currency_unit(self, name, emoji):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO currency_unit (id, name, emoji) VALUES (1, ?, ?)", (name, emoji))
            await db.commit()

    async def get_currency_unit(self):
        await self.ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT name, emoji FROM currency_unit WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"name": row[0], "emoji": row[1]}
                return None

# 싱글턴 인스턴스
balance_manager = BalanceDataManager()