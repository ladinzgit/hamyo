# cogs/garden.py
import discord
from discord.ext import commands
from datetime import datetime
from DataManager import DataManager

class GardenCog(commands.Cog):
    """Handles garden overview and mastery commands."""
    def __init__(self, bot):
        self.bot = bot
        self.storage = bot.get_cog('HerbStorage')
        self.dm = DataManager()

    @commands.command(name='내정원')
    async def my_garden(self, ctx):
        """Display current herb and completed herbs."""
        user_id = ctx.author.id
        herb = await self.storage.get_user_herb(user_id)
        embed = discord.Embed(color=0xB2FF66, title="내 정원", timestamp=datetime.utcnow())
        if herb:
            embed.add_field(
                name="현재 허브",
                value=(
                    f"종: {herb['species']} ({herb['rarity']})\n"
                    f"단계: {herb['stage']}\n"
                    f"햇빛: {herb['state_sun']}, 물: {herb['state_water']}, 양분: {herb['state_nutrient']}, 기운: {herb['vitality']}"
                ),
                inline=False
            )
        else:
            embed.add_field(name="현재 허브", value="키우고 있는 허브가 없습니다.", inline=False)
        completed = await self.storage.get_user_item_count(user_id, 'herb')
        embed.add_field(name="완료된 허브 수", value=f"{completed}개", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='숙련도')
    async def mastery(self, ctx):
        """Show user's gardener experience and rank."""
        user_id = ctx.author.id
        # Fetch score from DB
        db = await self.storage.get_db()
        cursor = await db.execute(
            "SELECT gardener_score FROM users WHERE user_id = ?;",
            (user_id,)
        )
        row = await cursor.fetchone()
        await db.close()
        score = row['gardener_score'] if row and 'gardener_score' in row else (row[0] if row else 0)
        # Determine title
        thresholds = [
            (700, '향기의 주인'),
            (400, '고요한 정원사'),
            (200, '잎새의 손길'),
            (0,   '초보 정원사'),
        ]
        title = next(name for thresh, name in thresholds if score >= thresh)
        await ctx.send(f"🎖 숙련도: {score}pt ({title})")

async def setup(bot: commands.Bot):
    await bot.add_cog(GardenCog(bot))