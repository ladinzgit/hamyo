from discord.ext import commands


class FortuneTimer(commands.Cog):
    """운세 타이머 코그 (현재 예약 기능 미사용)"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print(f"🐾{self.__class__.__name__} loaded successfully!")


async def setup(bot):
    await bot.add_cog(FortuneTimer(bot))
