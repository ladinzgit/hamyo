import discord
from discord.ext import commands, tasks
from datetime import datetime
from DataManager import DataManager
import asyncio

class VoiceTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.join_times = {}  # {user_id: {channel_id: join_time}}
        bot.loop.create_task(self.data_manager.initialize())
        self.track_voice_time.start()

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    def get_all_voice_channels(self):
        return [channel for guild in self.bot.guilds for channel in guild.voice_channels]

    @tasks.loop(minutes=1)
    async def track_voice_time(self):
        now = datetime.now()
        channels = self.get_all_voice_channels()

        for channel in channels:
            for member in channel.members:
                if member.bot:
                    continue

                user_id = member.id
                channel_id = channel.id

                if user_id not in self.join_times:
                    self.join_times[user_id] = {}

                if channel_id not in self.join_times[user_id]:
                    self.join_times[user_id][channel_id] = now
                    continue

                join_time = self.join_times[user_id][channel_id]

                if join_time.date() != now.date():
                    midnight = join_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    duration1 = int((midnight - join_time).total_seconds())
                    duration2 = int((now - next_day).total_seconds())

                    if duration1 > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration1)
                    if duration2 > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration2)

                    self.join_times[user_id][channel_id] = next_day
                else:
                    duration = int((now - join_time).total_seconds())
                    if duration > 0:
                        await self.data_manager.add_voice_time(user_id, channel_id, duration)
                        self.join_times[user_id][channel_id] = now

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.VoiceChannel) and channel.category:
            await self.data_manager.register_deleted_channel(channel.id, channel.category.id)
            await self.log(f"추적된 카테고리 {channel.category.name}의 음성 채널 {channel.name}({channel.id})이 삭제되었습니다.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            if member.bot or before.channel == after.channel:
                return

            now = datetime.now()

            # 나간 채널 처리
            if before.channel:
                if member.id in self.join_times and before.channel.id in self.join_times[member.id]:
                    join_time = self.join_times[member.id][before.channel.id]

                    if join_time.date() != now.date():
                        midnight = join_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                        duration1 = int((midnight - join_time).total_seconds())
                        duration2 = int((now - next_day).total_seconds())

                        if duration1 > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration1)
                        if duration2 > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration2)
                    else:
                        duration = int((now - join_time).total_seconds())
                        if duration > 0:
                            await self.data_manager.add_voice_time(member.id, before.channel.id, duration)

                    del self.join_times[member.id][before.channel.id]

            # 입장한 채널 등록
            if after.channel:
                if member.id not in self.join_times:
                    self.join_times[member.id] = {}
                self.join_times[member.id][after.channel.id] = now
        except Exception as e:
            print(e)
            
    @commands.command()
    async def check_all_time(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        data = await self.data_manager.get_user_times(user.id, "누적")
        times, start, end = data
        if not times:
            return await ctx.send(f"{user.display_name}님의 누적 기록이 없습니다.")

        total_seconds = sum(times.values())
        d, r = divmod(total_seconds, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        await ctx.send(f"{user.display_name}님의 전체 기록: {d}일 {h}시간 {m}분 {s}초")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceTracker(bot))