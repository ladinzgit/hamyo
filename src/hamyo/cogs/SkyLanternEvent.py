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
EVENT_START = datetime(2025, 6, 1, 0, 0, 0, tzinfo=KST)
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

class SkyLanternEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_event_period(self):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT start, end FROM config LIMIT 1") as cur:
                row = await cur.fetchone()
                if row:
                    start = datetime.fromisoformat(row[0])
                    end = datetime.fromisoformat(row[1])
                else:
                    start, end = EVENT_START, EVENT_END
        return start <= now_kst() <= end

    async def get_channel_ids(self):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT ranking_channel_id, celebration_channel_id, my_lantern_channel_id FROM config WHERE id=1") as cur:
                row = await cur.fetchone()
                if row:
                    return {
                        "ranking": row[0],
                        "celebration": row[1],
                        "my_lantern": row[2]
                    }
                # fallback to hardcoded if not set
                return {
                    "ranking": 1378352416571002880,
                    "celebration": 1378353093200183316,
                    "my_lantern": 1378353273194545162
                }

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
    async def give_lantern(self, user_id: int, key: str, count: int = 1):
        """풍등 지급"""
        try:
            if not await self.is_event_period():
                return False
            if count <= 0:  # count 유효성 검사
                return False
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT amount FROM reward_config WHERE key=?", (key,)) as cur:
                    row = await cur.fetchone()
                    if not row:
                        return False
                    amount = row[0] * count  # 기본 지급량 × count
                await db.execute("""
                    INSERT INTO lanterns (user_id, count)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET count = count + excluded.count
                """, (str(user_id), amount))
                await db.commit()
            return True
        except Exception as e:
            print(f"풍등 지급 중 오류 발생: {e}")
            return False

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
        if not await self.is_event_period():
            return False
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM celebration_log WHERE user_id=?", (str(user_id),)) as cur:
                if await cur.fetchone():
                    return False
            await db.execute("INSERT INTO celebration_log (user_id) VALUES (?)", (str(user_id),))
            await db.commit()
        ok = await self.give_lantern(user_id, "celebration")
        return ok

    # 하묘 상호작용 지급 (선착순 3명)
    async def try_give_interaction(self, user_id: int, round_num: int):
        if not await self.is_event_period():
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
        channel_ids = await self.get_channel_ids()
        if ctx.channel.id != channel_ids["my_lantern"]:
            return
        count = await self.get_lantern_count(ctx.author.id)
        embed = discord.Embed(
            title=f"🏮 내 풍등 확인 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {ctx.author.mention}님의 풍등 개수는 **{count}개** 이다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(252, 252, 126)
        )
        embed.set_thumbnail(url=ctx.author.display_avatar)
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.display_avatar)
        embed.timestamp = ctx.message.created_at if hasattr(ctx.message, "created_at") else None
        await ctx.reply(embed=embed)

    # 오픈응원글 자동 지급 (on_message 이벤트에서 직접 처리)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        channel_ids = await self.get_channel_ids()
        if not channel_ids["celebration"]:
            return  # celebration 채널이 설정되지 않은 경우
        if message.channel.id != channel_ids["celebration"]:
            return
        if len(message.content.strip()) < 10:
            return
        try:
            ok = await self.try_give_celebration(message.author.id)
        except Exception as e:
            await message.reply(f"오픈 응원글 지급 중 오류 발생: {e}")
            return
        if ok:
            await message.reply(f"{message.author.mention}님, 오픈 응원글로 풍등 5개를 지급했다묘...✩")

    # 풍등 수동 지급 명령어 (관리자 전용)
    @commands.command(name="풍등지급")
    @commands.has_permissions(administrator=True)
    async def give_lantern_manual(self, ctx, member: discord.Member, amount: int):
        """관리자가 특정 유저에게 풍등을 수동 지급합니다."""
        if amount <= 0:
            await ctx.send("지급할 풍등 개수는 1개 이상이어야 합니다.")
            return
        ok = await self.manual_give_lantern(member.id, amount)
        if ok:
            await ctx.send(f"{member.mention}님에게 풍등 {amount}개를 수동 지급했습니다.")
        else:
            await ctx.send("풍등 지급에 실패했습니다.")

    async def manual_give_lantern(self, user_id: int, amount: int):
        """관리자 수동 풍등 지급 (이벤트 기간 무관, reward_config 무관, 직접 개수 입력)"""
        try:
            if amount <= 0:
                return False
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO lanterns (user_id, count)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET count = count + excluded.count
                """, (str(user_id), amount))
                await db.commit()
            return True
        except Exception as e:
            print(f"수동 풍등 지급 중 오류 발생: {e}")
            return False

    # 풍등 수동 회수 명령어 (관리자 전용)
    @commands.command(name="풍등회수")
    @commands.has_permissions(administrator=True)
    async def take_lantern_manual(self, ctx, member: discord.Member, amount: int):
        """관리자가 특정 유저의 풍등을 수동 회수합니다."""
        if amount <= 0:
            await ctx.send("회수할 풍등 개수는 1개 이상이어야 합니다.")
            return
        ok = await self.manual_take_lantern(member.id, amount)
        if ok:
            await ctx.send(f"{member.mention}님에게서 풍등 {amount}개를 수동 회수했습니다.")
        else:
            await ctx.send("풍등 회수에 실패했습니다. (잔여 풍등이 부족할 수 있습니다.)")

    async def manual_take_lantern(self, user_id: int, amount: int):
        """관리자 수동 풍등 회수 (이벤트 기간 무관, reward_config 무관, 직접 개수 입력)"""
        try:
            if amount <= 0:
                return False
            async with aiosqlite.connect(DB_PATH) as db:
                # 현재 풍등 개수 확인
                async with db.execute("SELECT count FROM lanterns WHERE user_id=?", (str(user_id),)) as cur:
                    row = await cur.fetchone()
                    current = row[0] if row else 0
                if current < amount:
                    return False
                await db.execute("""
                    UPDATE lanterns SET count = count - ? WHERE user_id = ?
                """, (amount, str(user_id)))
                await db.commit()
            return True
        except Exception as e:
            print(f"수동 풍등 회수 중 오류 발생: {e}")
            return False

async def setup(bot):
    cog = SkyLanternEvent(bot)
    await bot.add_cog(cog)
