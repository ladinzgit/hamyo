import aiosqlite
from discord.ext import commands
from herb_db import (
    get_db,
    init_db,
    create_user_if_not_exists,
    create_herb_for_user,
    get_user_seed_items as db_get_user_seed_items,
    add_inventory_item as db_add_inventory_item,
    remove_inventory_item as db_remove_inventory_item,
    get_user_item_count as db_get_user_item_count
)

class HerbStorage(commands.Cog):
    """
    Database CRUD operations for users and herbs.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Initialize database schema
        await init_db()

    # Inventory helper wrappers
    async def get_user_seed_items(self, user_id: int):
        """Return list of seed items for the user."""
        await create_user_if_not_exists(user_id)
        return await db_get_user_seed_items(user_id)

    async def add_inventory_item(self, user_id: int, item_key: str, name: str, species: str = None, rarity: str = None):
        """Add an item to the user's inventory."""
        await create_user_if_not_exists(user_id)
        await db_add_inventory_item(user_id, item_key, name, species, rarity)

    async def remove_inventory_item(self, user_id: int, item_key: str, name: str):
        """Remove an item from the user's inventory."""
        await create_user_if_not_exists(user_id)
        return await db_remove_inventory_item(user_id, item_key, name)

    async def get_user_item_count(self, user_id: int, item_key: str) -> int:
        """Return count of a specific item for the user."""
        await create_user_if_not_exists(user_id)
        return await db_get_user_item_count(user_id, item_key)

    async def add_revive_item(self, user_id: int, name: str):
        """Add a revive item to the user's inventory."""
        await create_user_if_not_exists(user_id)
        await db_add_inventory_item(user_id, 'revive', name)

    async def remove_revive_item(self, user_id: int, name: str):
        """Remove a revive item from the user's inventory."""
        await create_user_if_not_exists(user_id)
        return await db_remove_inventory_item(user_id, 'revive', name)

    # Existing herb operations (unchanged)
    async def update_herb_states(self, herb_id: int, sun=None, water=None, nutrient=None, vitality=None, stage=None, withered=None):
        """
        Update various state fields of a herb.
        """
        fields = []
        values = []
        if sun is not None:
            fields.append("state_sun = ?")
            values.append(sun)
        if water is not None:
            fields.append("state_water = ?")
            values.append(water)
        if nutrient is not None:
            fields.append("state_nutrient = ?")
            values.append(nutrient)
        if vitality is not None:
            fields.append("vitality = ?")
            values.append(vitality)
        if stage is not None:
            fields.append("stage = ?")
            values.append(stage)
        if withered is not None:
            fields.append("withered = ?")
            values.append(withered)
        if not fields:
            return
        query = f"UPDATE herbs SET {', '.join(fields)} WHERE herb_id = ?;"
        values.append(herb_id)
        db = await get_db()
        await db.execute(query, tuple(values))
        await db.commit()
        await db.close()

async def setup(bot):
    await bot.add_cog(HerbStorage(bot))