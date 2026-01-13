import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import pytz
import logging
from typing import List, Callable, Dict, Any

KST = pytz.timezone("Asia/Seoul")

class Scheduler(commands.Cog):
    """중앙 작업 스케줄러: 등록된 작업을 지정된 시간에 실행합니다."""

    def __init__(self, bot):
        self.bot = bot
        self.scheduled_tasks: List[Dict[str, Any]] = []
        self.scheduler_loop.start()

    def cog_unload(self):
        self.scheduler_loop.cancel()

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    def schedule_daily(self, callback: Callable, hour: int, minute: int):
        """매일 지정된 시간에 실행될 작업을 등록합니다."""
        task_info = {
            "callback": callback,
            "hour": hour,
            "minute": minute,
            "name": callback.__name__
        }
        self.scheduled_tasks.append(task_info)
        print(f"📅 작업 등록됨: {callback.__name__} (매일 {hour:02d}:{minute:02d} KST)")

    @tasks.loop(minutes=1)
    async def scheduler_loop(self):
        """1분마다 실행되어 예약된 작업을 확인합니다."""
        await self.bot.wait_until_ready()
        
        now = datetime.now(KST)
        current_hour = now.hour
        current_minute = now.minute

        for task in self.scheduled_tasks:
            if task["hour"] == current_hour and task["minute"] == current_minute:
                # 비동기 실행을 위해 create_task 사용 (하나가 막혀도 다른 것은 실행되게)
                asyncio.create_task(self._run_task(task))

    async def _run_task(self, task):
        try:
            func = task["callback"]
            name = task["name"]

            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

        except Exception as e:
            await self.log(f"❌ 스케줄러: {task.get('name')} 실행 중 오류 발생: {e}")
            print(f"Scheduler error in {task.get('name')}: {e}")

    @scheduler_loop.before_loop
    async def before_scheduler_loop(self):
        await self.bot.wait_until_ready()
        # 정각(00초)에 가깝게 맞추기 위해 초기 딜레이
        now = datetime.now(KST)
        # 다음 분의 0초까지 대기
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        delay = (next_minute - now).total_seconds()
        await asyncio.sleep(delay)

async def setup(bot):
    await bot.add_cog(Scheduler(bot))
