import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta, time as dt_time
import pytz
import asyncio
import aiosqlite

KST = pytz.timezone("Asia/Seoul")

async def get_main_channel_id():
    async with aiosqlite.connect("data/skylantern_event.db") as db:
        async with db.execute("SELECT main_channel_id FROM config WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else 1368617001970569297

def make_math_problem():
    op = random.choice(['+', '-', '*'])
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    if op == '+':
        q = f"{a} + {b}"
        a_str = str(a + b)
    elif op == '-':
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
    # 08:00 오늘 ~ 24:00(=16시간) 사이에서 랜덤 n개, 최소 10분 텀 보장
    base = datetime.now(KST).replace(hour=8, minute=0, second=0, microsecond=0)
    end = base + timedelta(hours=16)  # 08:00~24:00
    min_gap = 600  # 10분(초)
    total_seconds = int((end - base).total_seconds())
    attempts = 0
    while True:
        # n개 랜덤 초 추출, 정렬
        offsets = sorted(random.sample(range(0, total_seconds), n))
        # 텀 체크: 모든 차이가 10분 이상이면 통과
        if all((offsets[i+1] - offsets[i]) >= min_gap for i in range(n-1)):
            break
        attempts += 1
        if attempts > 1000:
            # fallback: 강제 등간격
            offsets = [int(i * total_seconds / (n + 1)) for i in range(1, n+1)]
            break
    times = [(base + timedelta(seconds=offset)).time().replace(second=0, microsecond=0)
             for offset in offsets]
    return times

async def get_my_lantern_channel_id():
    async with aiosqlite.connect("data/skylantern_event.db") as db:
        async with db.execute("SELECT my_lantern_channel_id FROM config WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else 1378353273194545162

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
        self.today_times = random_times_for_today(3)
        self.last_problem_date = get_today_kst()
        for idx, t in enumerate(self.today_times):
            asyncio.create_task(self.problem_at_time(idx+1, t))

    async def problem_at_time(self, round_num, t):
        now = datetime.now(KST)
        target_dt = datetime.combine(get_today_kst(), t, tzinfo=KST)
        if now > target_dt:
            return
        await asyncio.sleep((target_dt - now).total_seconds())
        await self.spawn_problem(round_num)

    async def spawn_problem(self, round_num):
        self.round = round_num
        self.active = True
        self.answered_users = set()
        q, a = make_math_problem()
        self.current_answer = a
        main_channel_id = await get_main_channel_id()
        channel = self.bot.get_channel(main_channel_id)
        if channel:
            msg = await channel.send(f"하묘가 나타났다묘! 수학문제: `{q}` 정답을 이 채널에 입력해 달라묘!!! (선착순 3명 풍등 지급)")
            self.problem_message_id = msg.id
        await asyncio.sleep(600)
        self.active = False
        self.current_answer = None
        self.answered_users = set()
        self.problem_message_id = None

    @commands.command(name="하묘테스트")
    @commands.has_permissions(administrator=True)
    async def test_hamyo(self, ctx):
        """테스트용: 메인채팅에 즉시 하묘 문제 출제"""
        await self.spawn_problem(round_num=99)  # 테스트용 라운드 번호

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.active or message.author.bot:
            return
        main_channel_id = await get_main_channel_id()
        if message.channel.id != main_channel_id:
            return
        if message.content.strip() == self.current_answer and message.author.id not in self.answered_users:
            self.answered_users.add(message.author.id)
            if self.skylantern:
                ok = await self.skylantern.try_give_interaction(message.author.id, self.round)
                if ok:
                    channel_id = await get_my_lantern_channel_id()
                    lantern_channel = message.guild.get_channel(channel_id) if message.guild else None
                    mention = lantern_channel.mention if lantern_channel else f"<#{channel_id}>"
                    await message.reply(
                        f"{message.author.mention}님, 정답이다묘! 풍등 2개 지급해주게따묘...☆\n"
                        f"현재 보유 풍등 개수는 {mention} 채널에서 `/내풍등` 명령어로 확인할 수 있습니다묘!"
                    )
            if len(self.answered_users) >= 3:
                self.active = False

async def setup(bot):
    await bot.add_cog(SkyLanternInteraction(bot))
