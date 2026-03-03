import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

from src.core import fortune_db
from src.core.admin_utils import GUILD_IDS
from src.birthday.BirthdayInterface import KST


class FortuneTimer(commands.Cog):
    """운세 타이머: 자정 차감, 역할 부여/회수, 지정 시간 멘션"""

    def __init__(self, bot):
        self.bot = bot
        self.mention_task.start()

    def cog_unload(self):
        self.mention_task.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        pass

    async def cog_load(self):
        print(f"🐾{self.__class__.__name__} loaded successfully!")
        # 스케줄러 cog 가져오기
        scheduler = self.bot.get_cog("Scheduler")
        if scheduler:
            scheduler.schedule_daily(self.midnight_task, 0, 0)
        else:
            print("⚠️ Scheduler cog not found! FortuneTimer task validation failed.")

    async def log(self, message: str):
        """Logger cog에 로그 전달"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    async def midnight_task(self):
        """자정마다 count 차감 및 역할 동기화"""
        try:
            result = fortune_db.decrement_all_targets()
            updated, removed = result.get("updated", []), result.get("removed", [])

            if updated or removed:
                summary_parts = []
                if updated:
                    summary_parts.append(f"차감 {len(updated)}명")
                if removed:
                    summary_parts.append(f"삭제 {len(removed)}명")
                summary = ", ".join(summary_parts)
                await self.log(f"운세 대상 count 일괄 차감 완료 ({summary})")

            # 역할 부여/회수 동기화
            for guild_id in GUILD_IDS:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self._sync_roles_for_guild(guild)
        except Exception as e:
            await self.log(f"운세 대상 차감 중 오류 발생: {e}")

    async def _sync_roles_for_guild(self, guild: discord.Guild):
        """count가 남아있는 대상에게 역할 부여, 0 이하/비대상은 회수"""
        config = fortune_db.get_guild_config(guild.id)
        role_id = config.get("role_id")
        if not role_id:
            return

        role = guild.get_role(role_id)
        if not role:
            await self.log(f"운세 역할(ID: {role_id})을 찾지 못함 [길드: {guild.name}({guild.id})]")
            return

        targets = fortune_db.list_targets(guild.id)
        active_user_ids = {
            int(t.get("user_id", 0)) for t in targets
            if int(t.get("count", 0)) > 0
        }

        # 역할 부여
        for user_id in active_user_ids:
            member = guild.get_member(user_id)
            if member and role not in member.roles:
                try:
                    await member.add_roles(role, reason="운세 대상 유지")
                except Exception as e:
                    await self.log(f"{member}({member.id})에게 운세 역할 부여 실패: {e}")

        # 역할 회수
        for member in list(role.members):
            if member.id not in active_user_ids:
                try:
                    await member.remove_roles(role, reason="운세 대상 기간 만료")
                except Exception as e:
                    await self.log(f"{member}({member.id}) 운세 역할 회수 실패: {e}")

    @tasks.loop(minutes=1)
    async def mention_task(self):
        """설정된 시간에 역할 멘션"""
        await self.bot.wait_until_ready()
        await self._send_scheduled_mentions()

    @mention_task.before_loop
    async def before_mention_task(self):
        await self.bot.wait_until_ready()

    async def _send_scheduled_mentions(self):
        now = datetime.now(KST)
        today_str = now.strftime("%Y-%m-%d")

        for guild_id in GUILD_IDS:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            config = fortune_db.get_guild_config(guild_id)
            send_times = config.get("send_time", [])
            channel_id = config.get("channel_id")
            role_id = config.get("role_id")
            last_ping_dates = config.get("last_ping_date", {})

            if not (send_times and channel_id and role_id):
                continue

            for send_time in send_times:
                try:
                    hour, minute = map(int, send_time.split(":"))
                except Exception:
                    continue

                target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now < target_dt:
                    continue

                if last_ping_dates.get(send_time) == today_str:
                    continue

                channel = guild.get_channel(channel_id)
                role = guild.get_role(role_id)
                if not channel or not role:
                    break

                try:
                    await channel.send(f"{role.mention} 오늘의 운세를 아직 확인하지 않았다묘! `*운세`로 확인해달라묘 ~!")
                    fortune_db.set_last_ping_date(guild_id, send_time, today_str)
                    last_ping_dates[send_time] = today_str # 로컬 상태 업데이트
                    await self.log(f"운세 멘션 전송 완료 [길드: {guild.name}({guild.id}), 채널: {channel.name}({channel.id}), 시간: {send_time}]")
                except Exception as e:
                    await self.log(f"운세 멘션 전송 실패: {e} [길드: {guild.name}({guild.id}), 시간: {send_time}]")


async def setup(bot):
    await bot.add_cog(FortuneTimer(bot))
