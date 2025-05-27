# cogs/growth.py
import discord
import asyncio
import random
from discord.ext import commands
from datetime import datetime
from DataManager import DataManager

# Seed pools
C_SEEDS = ['바질','민트','타임','세이지','오레가노','파슬리','차이브','고수','로즈마리','레몬밤']
B_SEEDS = ['라벤더','로즈마리(심화)','레몬밤(심화)','카렌듈라','페퍼민트','코리앤더','카다멈','라임바질','히솝','메리골드']
A_SEEDS = ['카모마일','제라늄','멜리사','호로파','월계수']

NUMBER_EMOJIS = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']

class GrowthCog(commands.Cog):
    """Handles growth-related commands for herb progression."""
    def __init__(self, bot):
        self.bot = bot
        self.dm = DataManager()
    
    def choose_random_species(self, rarity: str) -> str:
        """정체불명의 씨앗일 때, rarity에 따라 랜덤 종을 부여"""
        if rarity.lower() == 'common':
            return random.choice(C_SEEDS)
        elif rarity.upper() == 'B':
            return random.choice(B_SEEDS)
        elif rarity.upper() == 'A':
            return random.choice(A_SEEDS)
        else:
            return random.choice(C_SEEDS)

    @commands.command(name='씨앗받기')
    async def seed(self, ctx):
        storage = self.bot.get_cog('HerbStorage')
        if not storage:
            return await ctx.send("❗ HerbStorage cog가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.")
        user_id = ctx.author.id
        if await storage.get_user_herb(user_id):
            return await ctx.send("🌱 이미 허브가 존재합니다.")
        owned = await storage.get_user_seed_items(user_id)
        options = [(name, species, rarity) for name, species, rarity in owned]
        options.append(('정체불명의 씨앗','unknown','common'))
        embed = discord.Embed(color=0xB2FF66, title="씨앗 선택", description="번호 반응으로 5분 내에 선택하세요")
        for idx, (name, _, _) in enumerate(options):
            embed.add_field(name=f"{NUMBER_EMOJIS[idx]} {name}", value=' ', inline=False)
        msg = await ctx.send(embed=embed)
        for idx in range(len(options)):
            await msg.add_reaction(NUMBER_EMOJIS[idx])
        def check(reaction, user):
            return user.id == user_id and reaction.message.id == msg.id and str(reaction.emoji) in NUMBER_EMOJIS[:len(options)]
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=300.0, check=check)
        except asyncio.TimeoutError:
            return await msg.edit(content="⏰ 씨앗 선택이 취소되었습니다.", embed=None)
        choice = NUMBER_EMOJIS.index(str(reaction.emoji))
        name, species, rarity = options[choice]
        # unknown 처리
        if species == 'unknown':
            species = self.choose_random_species(rarity)
            name = species
        started = datetime.utcnow().isoformat()
        herb_id = await storage.create_seed(user_id, species, rarity, started)
        if name != '정체불명의 씨앗':
            await storage.remove_inventory_item(user_id, 'seed', name)
        await msg.edit(content=f"🌰 `{name}` 씨앗({rarity})이 분양되었습니다! (ID: {herb_id})", embed=None)

    @commands.command(name='햇빛')
    async def sunlight(self, ctx):
        storage = self.bot.get_cog('HerbStorage')
        if not storage:
            return await ctx.send("❗ HerbStorage cog가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.")
        user_id = ctx.author.id
        herb = await storage.get_user_herb(user_id)
        if not herb:
            return await ctx.send("❗ 허브가 없습니다. /씨앗받기 먼저 실행해주세요.")
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if herb['last_sun'] == today:
            return await ctx.send("🌞 오늘 이미 햇빛을 받았습니다.")
        new_sun = herb['state_sun'] + 20
        new_vit = herb['vitality'] + 10
        await storage.update_herb_states(
            herb['herb_id'],
            state_sun=new_sun,
            vitality=new_vit,
            last_sun=today
        )
        await ctx.send(f"🌞 햇빛: {herb['state_sun']}→{new_sun}, 기운: {herb['vitality']}→{new_vit}")

    @commands.command(name='물')
    async def water(self, ctx):
        storage = self.bot.get_cog('HerbStorage')
        if not storage:
            return await ctx.send("❗ HerbStorage cog가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.")
        user_id = ctx.author.id
        herb = await storage.get_user_herb(user_id)
        if not herb:
            return await ctx.send("❗ 허브가 없습니다. /씨앗받기 먼저 실행해주세요.")
        await self.dm.ensure_initialized()
        times, _, _ = await self.dm.get_user_times(user_id, period='일간')
        if sum(times.values()) < 1800:
            return await ctx.send("💧 30분 이상 보이스 채널에서 활동해야 합니다.")
        new_w = herb['state_water'] + 15
        await storage.update_herb_states(herb['herb_id'], water=new_w)
        await ctx.send(f"💧 수분: {herb['state_water']}→{new_w}")

    @commands.command(name='비료등록')
    @commands.has_permissions(manage_messages=True)
    async def fertilize(self, ctx, member: discord.Member):
        storage = self.bot.get_cog('HerbStorage')
        if not storage:
            return await ctx.send("❗ HerbStorage cog가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.")
        user_id = member.id
        herb = await storage.get_user_herb(user_id)
        if not herb:
            return await ctx.send(f"❗ {member.mention}님은 키우고 있는 허브가 없습니다.")
        new_n = herb['state_nutrient'] + 20
        await storage.update_herb_states(herb['herb_id'], nutrient=new_n)
        await ctx.send(f"🌱 양분: {herb['state_nutrient']}→{new_n}")

    @commands.command(name='되살리기')
    async def revive(self, ctx):
        storage = self.bot.get_cog('HerbStorage')
        if not storage:
            return await ctx.send("❗ HerbStorage cog가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.")
        user_id = ctx.author.id
        herb = await storage.get_user_herb(user_id)
        if not herb or herb['withered'] == 0:
            return await ctx.send("❗ 회복 가능한 시든 허브가 없습니다.")
        count = await storage.get_user_item_count(user_id, 'revive')
        if count < 1:
            return await ctx.send("❗ 되살리기 아이템이 없습니다.")
        await storage.remove_inventory_item(user_id, 'revive', '되살리기')
        await storage.update_herb_states(
            herb['herb_id'],
            stage='새싹',
            vitality=0,
            sun=30,
            water=30,
            withered=0
        )
        await ctx.send("🌱 허브가 새싹 단계로 회복되었습니다! 다시 성장 여정을 시작하세요.")

async def setup(bot: commands.Bot):
    await bot.add_cog(GrowthCog(bot))