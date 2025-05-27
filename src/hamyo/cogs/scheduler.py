import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta

class SchedulerCog(commands.Cog):
    """Cog to handle daily herb state updates at midnight KST."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start the daily tick loop
        self.daily_tick.start()

    @tasks.loop(time=time(hour=15, minute=0), reconnect=True)
    async def daily_tick(self):
        """Runs every day at 00:00 KST (15:00 UTC)."""
        storage = self.bot.get_cog('HerbStorageCog')
        if not storage:
            return
        now = datetime.utcnow() + timedelta(hours=9)
        herbs = await storage.get_all_herbs()
        for record in herbs:
            herb_id, user_id, sun, water, nutrient, stage, vitality, started_str = record
            started_at = datetime.fromisoformat(started_str)
            # Skip initial hour
            if now.date() == started_at.date() and (now - started_at).total_seconds() < 3600:
                continue
            # Decay
            new_sun = sun - 10
            new_water = water - 10
            new_nutrient = nutrient - 10
            # Vitality adjustment
            if new_sun >= 70 and new_water >= 70 and new_nutrient >= 15:
                new_nutrient = max(0, new_nutrient - 15)
                delta = int(10 * 1.5)
            elif new_sun < 30 or new_water < 30 or new_nutrient < 30:
                delta = -5
            else:
                delta = 10
            new_vitality = max(0, vitality + delta)
            # Growth progression
            thresholds = {'씨앗': 20, '새싹': 40, '줄기': 80}
            order = ['씨앗', '새싹', '줄기']
            new_stage = stage
            if stage in thresholds and new_vitality >= thresholds[stage]:
                idx = order.index(stage)
                new_stage = order[idx+1] if idx+1 < len(order) else '허브 완성'
                new_vitality = 0
            # Wither check
            new_wither = 1 if (new_sun < 0 or new_water < 0 or new_nutrient < 0) else 0
            # Update
            try:
                await storage.update_herb_states(
                    herb_id,
                    state_sun=new_sun,
                    state_water=new_water,
                    state_nutrient=new_nutrient,
                    vitality=new_vitality,
                    stage=new_stage,
                    withered=new_wither
                )
            except Exception as e:
                # Log to admin channel if set
                config_cog = self.bot.get_cog('HerbConfig')
                if config_cog and config_cog.config.get('log_channel'):
                    channel = self.bot.get_channel(config_cog.config['log_channel'])
                    if channel:
                        await channel.send(f"[Scheduler Error] HerbID {herb_id} update failed: {e}")
                continue

    @daily_tick.before_loop
    async def before_daily_tick(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))