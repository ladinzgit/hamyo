import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta, time as dt_time
import pytz
import asyncio
import aiosqlite

KST = pytz.timezone("Asia/Seoul")

INTERACTION_DB_PATH = "data/skylantern_event.db"

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
        offsets = sorted(random.sample(range(0, total_seconds), n))
        if all((offsets[i+1] - offsets[i]) >= min_gap for i in range(n-1)):
            break
        attempts += 1
        if attempts > 1000:
            offsets = [int(i * total_seconds / (n + 1)) for i in range(1, n+1)]
            break
    # 기존 코드: .time().replace(second=0, microsecond=0)
    # 문제: tzinfo가 없는 naive time 객체로 반환됨
    # 수정: datetime 객체로 반환하여 tzinfo를 유지하고, 예약 시에도 tzinfo를 유지
    times = [(base + timedelta(seconds=offset)).astimezone(KST).time().replace(second=0, microsecond=0)
             for offset in offsets]
    return times

async def get_my_lantern_channel_id():
    async with aiosqlite.connect("data/skylantern_event.db") as db:
        async with db.execute("SELECT my_lantern_channel_id FROM config WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else 1378353273194545162

async def save_today_times(times):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    async with aiosqlite.connect(INTERACTION_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interaction_times (
                date TEXT PRIMARY KEY,
                time1 TEXT,
                time2 TEXT,
                time3 TEXT
            )
        """)
        await db.execute("""
            INSERT OR REPLACE INTO interaction_times (date, time1, time2, time3)
            VALUES (?, ?, ?, ?)
        """, (today, *(t.strftime("%H:%M") for t in times)))
        await db.commit()

async def load_today_times():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    async with aiosqlite.connect(INTERACTION_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interaction_times (
                date TEXT PRIMARY KEY,
                time1 TEXT,
                time2 TEXT,
                time3 TEXT
            )
        """)
        async with db.execute("SELECT time1, time2, time3 FROM interaction_times WHERE date=?", (today,)) as cur:
            row = await cur.fetchone()
            if row and all(row):
                return [datetime.strptime(t, "%H:%M").time() for t in row]
    return None

class SkyLanternInteraction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skylantern = None
        self.today_times = []
        self.active = False
        self.current_answer = None
        self.answered_users = set()
        self.problem_task = None
        self.last_problem_date = None
        self.scheduled_task = None  # 단일 예약 task

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        await self.init_today_times()
        await self.schedule_next_task()
        self.schedule_today_problems.start()

    async def schedule_next_task(self):
        # 예약된 task가 있으면 취소
        if self.scheduled_task and not self.scheduled_task.done():
            self.scheduled_task.cancel()
        now = datetime.now(KST)
        # 오늘 남은 시간 중 가장 가까운 시간 찾기
        next_idx = None
        for idx, t in enumerate(self.today_times):
            target_dt = datetime.combine(get_today_kst(), t, tzinfo=KST)
            if target_dt > now:
                next_idx = idx
                break
        if next_idx is not None:
            t = self.today_times[next_idx]
            target_dt = datetime.combine(get_today_kst(), t, tzinfo=KST)
            delay = (target_dt - now).total_seconds()
            await self.log(f"다음 문제 예약: {t.strftime('%H:%M')} (남은 시간 {int(delay)}초)")
            self.scheduled_task = asyncio.create_task(self._sleep_and_spawn(delay))
        else:
            await self.log("오늘 남은 예약 시간이 없습니다. 다음 타임을 예약하지 않습니다.")

    async def _sleep_and_spawn(self, delay):
        try:
            await asyncio.sleep(delay)
            await self.spawn_problem()
        except asyncio.CancelledError:
            pass

    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def init_today_times(self):
        loaded = await load_today_times()
        if loaded:
            self.today_times = loaded
            await self.log(f"오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 상호작용 시간(복구): {', '.join(t.strftime('%H:%M') for t in self.today_times)}")
        else:
            self.today_times = random_times_for_today(3)
            await save_today_times(self.today_times)
            await self.log(f"오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 상호작용 시간(신규): {', '.join(t.strftime('%H:%M') for t in self.today_times)}")

    @tasks.loop(time=dt_time(0, 1, tzinfo=KST))
    async def schedule_today_problems(self):
        # 자정마다 새로운 시간 생성 및 저장
        self.today_times = random_times_for_today(3)
        await save_today_times(self.today_times)
        await self.log(f"오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 상호작용 시간(갱신): {', '.join(t.strftime('%H:%M') for t in self.today_times)}")
        await self.log(
            f"자정 갱신: 오늘({datetime.now(KST).strftime('%Y-%m-%d')}) 상호작용 시간: "
            f"{', '.join(t.strftime('%H:%M') for t in self.today_times)}"
        )
        self.last_problem_date = get_today_kst()
        await self.schedule_next_task()

    @schedule_today_problems.before_loop
    async def before_schedule_today_problems(self):
        await self.bot.wait_until_ready()
        await self.init_today_times()
        await self.schedule_next_task()
        await self.log(
            f"스케줄러 루프: 오늘({datetime.now(KST).strftime('%Y-%m-%d')}) 상호작용 시간: "
            f"{', '.join(t.strftime('%H:%M') for t in self.today_times)}"
        )

    async def spawn_problem(self):
        self.active = True
        self.answered_users = set()
        q, a = make_math_problem()
        self.current_answer = a
        main_channel_id = await get_main_channel_id()
        channel = self.bot.get_channel(main_channel_id)
        if channel:
            await channel.send(f"하묘가 나타났다묘! 수학문제: `{q}` `정답 그대로` 이 채널에 입력해 달라묘!!!"  
                                "\n(선착순 3명 풍등 지급, 10분 제한)")
        # 10분 후 자동 종료 및 다음 예약
        asyncio.create_task(self._problem_timeout())

    async def _problem_timeout(self):
        await asyncio.sleep(600)
        if not self.active:
            return  # 이미 종료됨(3명 정답 등)
        self.active = False
        self.current_answer = None
        self.answered_users = set()
        await self.schedule_next_task()

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.active or message.author.bot:
            return
        main_channel_id = await get_main_channel_id()
        if message.channel.id != main_channel_id:
            return
        if self.current_answer is None:
            return
        if message.content.strip() == self.current_answer and message.author.id not in self.answered_users:
            self.answered_users.add(message.author.id)
            skylantern = self.bot.get_cog("SkyLanternEvent")
            if skylantern:
                ok = await skylantern.try_give_interaction(message.author.id, None)  # round_num 제거
                if ok:
                    channel_id = await get_my_lantern_channel_id()
                    lantern_channel = message.guild.get_channel(channel_id) if message.guild else None
                    mention = lantern_channel.mention if lantern_channel else f"<#{channel_id}>"
                    await message.reply(
                        f"{message.author.mention}님, 정답이다묘! 풍등 2개 지급해주게따묘...☆\n"
                        f"현재 보유 풍등 개수는 {mention} 채널에서 `*내풍등` 명령어로 확인할 수 있다묘!"
                    )
            if len(self.answered_users) >= 3:
                if self.active:
                    self.active = False
                    self.current_answer = None
                    self.answered_users = set()
                    await self.schedule_next_task()

    @commands.command(name="시간확인")
    async def check_times(self, ctx):
        """오늘의 하묘 출제 예정 시간을 확인합니다."""
        if not self.today_times:
            await ctx.send("오늘의 하묘 출제 시간이 아직 설정되지 않았습니다.")
            return
        times_str = ", ".join(t.strftime("%H:%M") for t in self.today_times)
        await ctx.send(f"오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 하묘 출제 예정 시간은:\n{times_str}")

    @commands.command(name="시간다시뽑기")
    @commands.has_permissions(administrator=True)
    async def reroll_times(self, ctx):
        """오늘의 하묘 출제 시간을 즉시 새로 뽑고 저장합니다. (관리자 전용)"""
        self.today_times = random_times_for_today(3)
        await save_today_times(self.today_times)
        await self.log(f"{ctx.author}({ctx.author.id})님이 수동으로 오늘의 상호작용 시간을 다시 뽑았습니다: {', '.join(t.strftime('%H:%M') for t in self.today_times)}")
        await self.log(
            f"{ctx.author}({ctx.author.id})님이 수동으로 오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 상호작용 시간을 다시 뽑음: "
            f"{', '.join(t.strftime('%H:%M') for t in self.today_times)}"
        )
        await self.schedule_next_task()
        times_str = ", ".join(t.strftime("%H:%M") for t in self.today_times)
        await ctx.send(f"오늘({datetime.now(KST).strftime('%Y-%m-%d')})의 하묘 출제 시간이 새로 설정되었습니다:\n{times_str}")

async def setup(bot):
    await bot.add_cog(SkyLanternInteraction(bot))
