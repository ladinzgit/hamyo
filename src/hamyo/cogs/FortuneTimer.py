import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

import fortune_db
from .BirthdayInterface import GUILD_ID, KST


class FortuneTimer(commands.Cog):
    """운세 타이머: 자정 차감, 역할 부여/회수, 지정 시간 멘션"""

    def __init__(self, bot):
        self.bot = bot
        self.midnight_task.start()
        self.mention_task.start()

    def cog_unload(self):
        self.midnight_task.cancel()
        self.mention_task.cancel()

    async def cog_load(self):
        print(f"🐾{self.__class__.__name__} loaded successfully!")

    async def log(self, message: str):
        """Logger cog에 로그 전달"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    @tasks.loop(hours=24)
    async def midnight_task(self):
        """자정마다 count 차감 및 역할 동기화"""
        await self.bot.wait_until_ready()

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
            for guild_id in GUILD_ID:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self._sync_roles_for_guild(guild)
        except Exception as e:
            await self.log(f"운세 대상 차감 중 오류 발생: {e}")

    @midnight_task.before_loop
    async def before_midnight_task(self):
        """다음 자정(KST)까지 대기"""
        await self.bot.wait_until_ready()
        now = datetime.now(KST)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await self.log(f"운세 자정 타이머 대기 시작 (다음 실행: {next_midnight.strftime('%Y-%m-%d %H:%M:%S')})")
        await discord.utils.sleep_until(next_midnight)

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

        for guild_id in GUILD_ID:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            config = fortune_db.get_guild_config(guild_id)
            send_time = config.get("send_time")
            channel_id = config.get("channel_id")
            role_id = config.get("role_id")
            last_ping_date = config.get("last_ping_date")

            if not (send_time and channel_id and role_id):
                continue

            try:
                hour, minute = map(int, send_time.split(":"))
            except Exception:
                continue

            target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now < target_dt:
                continue

            if last_ping_date == today_str:
                continue

            channel = guild.get_channel(channel_id)
            role = guild.get_role(role_id)
            if not channel or not role:
                continue

            try:
                await channel.send(f"{role.mention} 오늘의 운세를 아직 확인하지 않았다묘! `*운세`로 확인해달라묘 ~!")
                fortune_db.set_last_ping_date(guild_id, today_str)
                await self.log(f"운세 멘션 전송 완료 [길드: {guild.name}({guild.id}), 채널: {channel.name}({channel.id})]")
            except Exception as e:
                await self.log(f"운세 멘션 전송 실패: {e} [길드: {guild.name}({guild.id})]")


async def setup(bot):
    await bot.add_cog(FortuneTimer(bot))
