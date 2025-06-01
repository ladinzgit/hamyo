import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta, time as dt_time
import pytz
import asyncio

KST = pytz.timezone("Asia/Seoul")
MAIN_CHANNEL_ID = 1368617001970569297

def make_math_problem():
    op = random.choice(['+', '-', '*'])
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    if op == '+':
        q = f"{a} + {b}"
        a_str = str(a + b)
    elif op == '-':
        # 음수 방지
        a, b = max(a, b), min(a, b)
        q = f"{a} - {b}"
        a_str = str(a - b)
    else:
        q = f"{a} x {b}"
        a_str = str(a * b)
    return q, a_str

def get_today_kst():
    return datetime.now(KST).date()

def random_times_for_today(n=3):
    # 08:00~익일 02:00(=26:00) 사이에서 랜덤하게 n개 시각 반환
    base = datetime.now(KST).replace(hour=8, minute=0, second=0, microsecond=0)
    # 익일 02:00 = 오늘 26:00
    end = base + timedelta(hours=18)  # 08:00 + 18시간 = 26:00(=익일 02:00)
    seconds_range = int((end - base).total_seconds())
    times = set()
    while len(times) < n:
        offset = random.randint(0, seconds_range)
        t = (base + timedelta(seconds=offset)).time()
        times.add(t.replace(second=0, microsecond=0))
    return sorted(times)

class SkyLanternInteraction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skylantern = None
        self.today_times = []
        self.round = 0
        self.active = False
        self.current_answer = None
        self.answered_users = set()
        self.problem_message_id = None
        self.problem_task = None
        self.last_problem_date = None

    async def cog_load(self):
        self.skylantern = self.bot.get_cog("SkyLanternEvent")
        self.schedule_today_problems.start()

    @tasks.loop(time=dt_time(0, 1, tzinfo=KST))
    async def schedule_today_problems(self):
        # 매일 00:01에 오늘의 문제 출제 시각을 정함
        self.today_times = random_times_for_today(3)
        self.last_problem_date = get_today_kst()
        # 문제 출제 예약
        for idx, t in enumerate(self.today_times):
            asyncio.create_task(self.problem_at_time(idx+1, t))

    async def problem_at_time(self, round_num, t):
        # t는 KST 기준 time 객체
        now = datetime.now(KST)
        target_dt = datetime.combine(get_today_kst(), t, tzinfo=KST)
        if now > target_dt:
            # 이미 지난 시각이면 skip
            return
        await asyncio.sleep((target_dt - now).total_seconds())
        await self.spawn_problem(round_num)

    async def spawn_problem(self, round_num):
        self.round = round_num
        self.active = True
        self.answered_users = set()
        q, a = make_math_problem()
        self.current_answer = a
        channel = self.bot.get_channel(MAIN_CHANNEL_ID)
        if channel:
            msg = await channel.send(f"하묘가 나타났다! 수학문제: `{q}` 정답을 이 채널에 입력해 주세요! (선착순 3명 풍등 지급)")
            self.problem_message_id = msg.id
        # 10분 후 자동 종료
        await asyncio.sleep(600)
        self.active = False
        self.current_answer = None
        self.answered_users = set()
        self.problem_message_id = None

    @commands.Cog.listener()
    async def on_message(self, message):
        # 정답은 메인 채널에서만, 문제 활성화 중에만 인정
        if not self.active or message.author.bot:
            return
        if message.channel.id != MAIN_CHANNEL_ID:
            return
        if message.content.strip() == self.current_answer and message.author.id not in self.answered_users:
            self.answered_users.add(message.author.id)
            if self.skylantern:
                ok = await self.skylantern.try_give_interaction(message.author.id, self.round)
                if ok:
                    lantern_channel = message.guild.get_channel(1378353273194545162) if message.guild else None
                    mention = lantern_channel.mention if lantern_channel else "<#1378353273194545162>"
                    await message.reply(
                        f"{message.author.mention}님, 정답! 풍등 2개 지급!\n"
                        f"현재 보유 풍등 개수는 {mention} 채널에서 `/내풍등` 명령어로 확인할 수 있습니다."
                    )
            if len(self.answered_users) >= 3:
                self.active = False

async def setup(bot):
    await bot.add_cog(SkyLanternInteraction(bot))
