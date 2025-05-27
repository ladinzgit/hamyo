# herb_db.py
import aiosqlite
from pathlib import Path

# Database file path
DB_PATH = Path("data/herb.db")

async def init_db():
    """
    Initialize SQLite database with required tables.
    Called once on bot startup.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                current_herb_id INTEGER,
                gardener_score INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Herbs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS herbs (
                herb_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                species TEXT,
                rarity TEXT,
                quality TEXT,
                stage TEXT NOT NULL DEFAULT '씨앗',
                vitality INTEGER NOT NULL DEFAULT 0,
                state_sun INTEGER NOT NULL DEFAULT 0,
                state_water INTEGER NOT NULL DEFAULT 0,
                state_nutrient INTEGER NOT NULL DEFAULT 0,
                last_sun TEXT,
                started_at TEXT NOT NULL,
                withered INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)
        # Inventory table for seeds, revive items, grown herbs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                name TEXT NOT NULL,
                species TEXT,
                rarity TEXT,
                PRIMARY KEY(user_id, item_key, name)
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_inventory ON inventory(user_id);")
        await db.commit()

async def get_db():
    """
    Return a new aiosqlite connection with foreign keys enabled.
    """
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    return db

# User helpers
async def create_user_if_not_exists(user_id: int):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES (?);",
        (user_id,)
    )
    await db.commit()
    await db.close()

# Herb helpers
async def create_herb_for_user(user_id: int, species: str, rarity: str, started_at: str) -> int:
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO herbs(user_id, species, rarity, started_at) VALUES (?, ?, ?, ?);",
        (user_id, species, rarity, started_at)
    )
    await db.commit()
    herb_id = cur.lastrowid
    await db.close()
    return herb_id

# Inventory helpers
async def get_user_seed_items(user_id: int):
    """
    Return list of (name, species, rarity) where item_key='seed'.
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT name, species, rarity FROM inventory WHERE user_id = ? AND item_key = 'seed';",
        (user_id,)
    )
    rows = await cursor.fetchall()
    await db.close()
    return rows

async def add_inventory_item(user_id: int, item_key: str, name: str, species: str = None, rarity: str = None):
    """
    Add an item to user's inventory.
    """
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO inventory(user_id, item_key, name, species, rarity) VALUES (?, ?, ?, ?, ?);",
        (user_id, item_key, name, species, rarity)
    )
    await db.commit()
    await db.close()

async def remove_inventory_item(user_id: int, item_key: str, name: str):
    """
    Remove a specific item from user's inventory.
    """
    db = await get_db()
    await db.execute(
        "DELETE FROM inventory WHERE user_id = ? AND item_key = ? AND name = ?;",
        (user_id, item_key, name)
    )
    await db.commit()
    await db.close()

async def get_user_item_count(user_id: int, item_key: str) -> int:
    """
    Return the count of items for a user by item_key.
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_key = ?;",
        (user_id, item_key)
    )
    result = await cursor.fetchone()
    await db.close()
    return result[0] if result else 0