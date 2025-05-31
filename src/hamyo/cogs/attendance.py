import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime
import pytz
from balance_data_manager import balance_manager  # 추가

DB_PATH = 'data/attendance.db'
KST = pytz.timezone("Asia/Seoul")
GUILD_ID = 1368459027851509891

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id == GUILD_ID:
            return True
        return False  # 메시지 없이 무반응
    return commands.check(predicate)

async def is_attendance_allowed_channel(channel_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM attendance_allowed_channels WHERE channel_id = ?", (channel_id,)) as cur:
            row = await cur.fetchone()
            return row is not None

class AttendanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    user_id INTEGER PRIMARY KEY,
                    last_date TEXT,
                    count INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS attendance_allowed_channels (
                    channel_id INTEGER PRIMARY KEY
                )
            """)
            await db.commit()

    @commands.group(name="출석", invoke_without_command=True)
    @only_in_guild()
    async def attendance(self, ctx):
        """출석 체크"""
        # 출석 허용 채널 체크
        if not ctx.author.guild_permissions.administrator:
            if not await is_attendance_allowed_channel(ctx.channel.id):
                return  # 무반응

        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        user_id = ctx.author.id

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT last_date, count FROM attendance WHERE user_id=?", (user_id,))
            row = await cur.fetchone()

            if row is None:
                await db.execute(
                    "INSERT INTO attendance (user_id, last_date, count) VALUES (?, ?, ?)",
                    (user_id, today, 1)
                )
                await db.commit()
                # 온 지급
                await balance_manager.give(str(user_id), 100)
                balance = await balance_manager.get_balance(str(user_id))
                embed = discord.Embed(
                    title=f"출석 ₍ᐢ..ᐢ₎",
                    description=f"""
                    ⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
                    ╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
                    (⠀⠀⠀´ㅅ` )
                    (⠀ {ctx.author.mention}님, 첫 출석 완료했다묘...✩
                        누적 1회 출석했다묘...✩
                        자동으로 100온도 지급했다묘...✩
                    ╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
                    """,
                    colour=discord.Colour.from_rgb(252, 252, 126)
                )
                embed.set_footer(text=f"현재 잔액: {balance}온")
                await ctx.send(embed=embed)
            else:
                last_date, count = row
                if last_date == today:
                    await ctx.send(f"⚠️ {ctx.author.mention} 오늘 이미 출석했다묘! (누적 {count}회)")
                else:
                    count += 1
                    await db.execute(
                        "UPDATE attendance SET last_date=?, count=? WHERE user_id=?",
                        (today, count, user_id)
                    )
                    await db.commit()
                    # 온 지급
                    await balance_manager.give(str(user_id), 100)
                    balance = await balance_manager.get_balance(str(user_id))
                    embed = discord.Embed(
                        title=f"출석 ₍ᐢ..ᐢ₎",
                        description=f"""
                        ⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
                        ╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
                        (⠀⠀⠀´ㅅ` )
                        (⠀ {ctx.author.mention}님, 출석 완료했다묘...✩
                            누적 {count}회 출석했다묘...✩
                            자동으로 100온도 지급했다묘...✩
                        ╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
                        """,
                        colour=discord.Colour.from_rgb(252, 252, 126)
                    )
                    embed.set_footer(text=f"현재 잔액: {balance}온")
                    await ctx.send(embed=embed)

    @attendance.command(name="순위")
    async def ranking(self, ctx, page: int = 1):
        """출석 순위 (페이지네이션, 임베드)"""
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id, count FROM attendance ORDER BY count DESC, user_id ASC"
            )
            rows = await cur.fetchall()

        if not rows:
            await ctx.send("아직 출석한 사람이 없습니다.")
            return

        items_per_page = 10
        total_pages = (len(rows) + items_per_page - 1) // items_per_page
        if page < 1 or page > total_pages:
            await ctx.send(f"페이지 번호는 1~{total_pages} 사이여야 합니다.")
            return

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_rows = rows[start_index:end_index]

        embed = discord.Embed(
            title="비몽다방 출석 순위",
            description=f"출석 TOP {len(rows)} (페이지 {page}/{total_pages})",
            colour=discord.Colour.from_rgb(252, 252, 126)
        )

        for i, (user_id, count) in enumerate(page_rows, start=start_index + 1):
            try:
                user = await self.bot.fetch_user(user_id)
                username = user.mention
            except Exception:
                username = f"Unknown({user_id})"
            if user_id == ctx.author.id:
                name_line = f"**{i}위 - {username} (You)**"
            else:
                name_line = f"{i}위 - {username}"
            embed.add_field(
                name=name_line,
                value=f"출석 {count}회",
                inline=False
            )

        # 본인 순위가 현재 페이지에 없으면 하단에 추가
        author_rank = None
        for idx, (user_id, count) in enumerate(rows, start=1):
            if user_id == ctx.author.id:
                author_rank = (idx, count)
                break
        if author_rank and not any(user_id == ctx.author.id for user_id, _ in page_rows):
            embed.add_field(
                name="───────── ౨ৎ ─────────",
                value=f"**{author_rank[0]}위 - {ctx.author.mention} (You)**\n출석 {author_rank[1]}회",
                inline=False
            )

        embed.set_footer(text=f"페이지 {page}/{total_pages} | 총 {len(rows)}명 출석")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    # 출석 허용 채널 관리 명령어 (관리자만)
    @commands.group(name="출석채널", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def attendance_channel(self, ctx):
        """출석 명령어 허용 채널 관리"""
        await ctx.send("`추가`, `제거`, `목록` 하위 명령어를 사용하세요.")

    @attendance_channel.command(name="추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_attendance_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO attendance_allowed_channels (channel_id) VALUES (?)", (channel.id,))
            await db.commit()
        await ctx.send(f"{channel.mention} 채널이 출석 명령어 허용 채널로 추가되었습니다.")

    @attendance_channel.command(name="제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_attendance_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM attendance_allowed_channels WHERE channel_id = ?", (channel.id,))
            await db.commit()
        await ctx.send(f"{channel.mention} 채널이 출석 명령어 허용 채널에서 제거되었습니다.")

    @attendance_channel.command(name="목록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def list_attendance_channels(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT channel_id FROM attendance_allowed_channels") as cur:
                rows = await cur.fetchall()
        if not rows:
            await ctx.send("등록된 출석 명령어 허용 채널이 없습니다.")
        else:
            mentions = [f"<#{row[0]}>" for row in rows]
            await ctx.send("출석 명령어 허용 채널 목록:\n" + ", ".join(mentions))

async def setup(bot):
    await bot.add_cog(AttendanceCog(bot))
