import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime, timedelta
import pytz

DB_PATH = "data/skylantern_event.db"
KST = pytz.timezone("Asia/Seoul")

# 채널 ID 상수
CHANNEL_RANKING = 1378352416571002880
CHANNEL_CELEBRATION = 1378353093200183316
CHANNEL_MY_LANTERN = 1378353273194545162

# 이벤트 기간 (기본값, 관리자 명령어로 변경 가능)
EVENT_START = datetime(2025, 6, 2, 0, 0, 0, tzinfo=KST)
EVENT_END = datetime(2025, 6, 15, 23, 59, 59, tzinfo=KST)

# 지급량 상수 (관리자 명령어로 변경 가능)
LANTERN_REWARD = {
    "celebration": 5,
    "attendance": 1,
    "up": 2,
    "recommend": 3,
    "interaction": 2
}
INTERACTION_LIMIT = 3  # 하묘 선착순 지급 인원

def now_kst():
    return datetime.now(KST)

async def is_event_period():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT start, end FROM config LIMIT 1") as cur:
            row = await cur.fetchone()
            if row:
                start = datetime.fromisoformat(row[0])
                end = datetime.fromisoformat(row[1])
            else:
                start, end = EVENT_START, EVENT_END
    return start <= now_kst() <= end

class SkyLanternEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lanterns (
                    user_id TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS celebration_log (
                    user_id TEXT PRIMARY KEY
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    start TEXT,
                    end TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reward_config (
                    key TEXT PRIMARY KEY,
                    amount INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS interaction_log (
                    date TEXT,
                    round INTEGER,
                    user_id TEXT,
                    PRIMARY KEY(date, round, user_id)
                )
            """)
            await db.commit()
            # 기본 config 없으면 삽입
            async with db.execute("SELECT 1 FROM config WHERE id=1") as cur:
                if not await cur.fetchone():
                    await db.execute("INSERT INTO config (id, start, end) VALUES (1, ?, ?)", (EVENT_START.isoformat(), EVENT_END.isoformat()))
            # 지급량 기본값
            for k, v in LANTERN_REWARD.items():
                await db.execute("INSERT OR IGNORE INTO reward_config (key, amount) VALUES (?, ?)", (k, v))
            await db.commit()

    # 풍등 지급
    async def give_lantern(self, user_id: int, key: str):
        if not await is_event_period():
            return False
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT amount FROM reward_config WHERE key=?", (key,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return False
                amount = row[0]
            await db.execute("""
                INSERT INTO lanterns (user_id, count)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET count = count + excluded.count
            """, (str(user_id), amount))
            await db.commit()
        return True

    # 풍등 개수 조회
    async def get_lantern_count(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT count FROM lanterns WHERE user_id=?", (str(user_id),)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    # 풍등 랭킹 top N
    async def get_top_lanterns(self, top_n=5):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, count FROM lanterns ORDER BY count DESC, user_id ASC LIMIT ?", (top_n,)) as cur:
                return await cur.fetchall()

    # celebration(오픈응원글) 자동 지급
    async def try_give_celebration(self, user_id: int):
        if not await is_event_period():
            return False
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM celebration_log WHERE user_id=?", (str(user_id),)) as cur:
                if await cur.fetchone():
                    return False
            await db.execute("INSERT INTO celebration_log (user_id) VALUES (?)", (str(user_id),))
            await db.commit()
        await self.give_lantern(user_id, "celebration")
        return True

    # 하묘 상호작용 지급 (선착순 3명)
    async def try_give_interaction(self, user_id: int, round_num: int):
        if not await is_event_period():
            return False
        today = now_kst().strftime("%Y-%m-%d")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM interaction_log WHERE date=? AND round=?", (today, round_num)) as cur:
                cnt = (await cur.fetchone())[0]
                if cnt >= INTERACTION_LIMIT:
                    return False
            async with db.execute("SELECT 1 FROM interaction_log WHERE date=? AND round=? AND user_id=?", (today, round_num, str(user_id))) as cur:
                if await cur.fetchone():
                    return False
            await db.execute("INSERT INTO interaction_log (date, round, user_id) VALUES (?, ?, ?)", (today, round_num, str(user_id)))
            await db.commit()
        await self.give_lantern(user_id, "interaction")
        return True

    # 내풍등 확인 명령어
    @commands.command(name="내풍등")
    async def my_lantern(self, ctx):
        count = await self.get_lantern_count(ctx.author.id)
        await ctx.reply(f"{ctx.author.mention}님의 풍등 개수: {count}개")

    # 오픈응원글 자동 지급 (on_message 이벤트에서 호출)
    async def handle_celebration_message(self, message):
        if message.channel.id != CHANNEL_CELEBRATION:
            return
        if len(message.content.strip()) < 10:
            return
        ok = await self.try_give_celebration(message.author.id)
        if ok:
            await message.reply(f"{message.author.mention}님, 오픈 응원글로 풍등 5개가 지급되었습니다!")

    # 관리자: 지급량/기간 설정 등은 SkyLanternConfig.py에서 구현

async def setup(bot):
    cog = SkyLanternEvent(bot)
    await bot.add_cog(cog)
    # celebration 자동 지급을 위해 on_message hook 등록
    @bot.listen("on_message")
    async def _celebration_hook(message):
        if message.author.bot:
            return
        cog = bot.get_cog("SkyLanternEvent")
        if cog:
            await cog.handle_celebration_message(message)
