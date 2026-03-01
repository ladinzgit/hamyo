import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime, timedelta
import pytz
import asyncio
from src.core.balance_data_manager import balance_manager  # 추가

DB_PATH = 'data/attendance.db'
KST = pytz.timezone("Asia/Seoul")
from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin


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
            
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    @commands.group(name="출석", invoke_without_command=True)
    @only_in_guild()
    async def attendance(self, ctx):
        try:
            """출석 체크"""
            # 출석 허용 채널 체크 (관리자도 예외 없이 적용)
            if not await is_attendance_allowed_channel(ctx.channel.id):
                return  # 무반응

            now = datetime.now(KST)
            today = now.strftime("%Y-%m-%d")
            user_id = ctx.author.id

            attendance_success = False
            count = 0

            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT last_date, count FROM attendance WHERE user_id=?", (user_id,))
                row = await cur.fetchone()

                if row is None:
                    # 첫 출석 - 온도 지급 먼저 시도
                    try:
                        await balance_manager.give(str(user_id), 100)
                        
                        # 온도 지급 성공 시 DB 기록
                        await db.execute(
                            "INSERT INTO attendance (user_id, last_date, count) VALUES (?, ?, ?)",
                            (user_id, today, 1)
                        )
                        await db.commit()
                        
                        count = 1
                        attendance_success = True
                        
                    except Exception as balance_error:
                        print(f"온도 지급 실패: {balance_error}")
                        await ctx.send("❌ 온 지급 중 오류가 발생했습니다. 관리자에게 문의해주세요.")
                        return
                        
                else:
                    last_date, existing_count = row
                    if last_date == today:
                        # 이미 출석함
                        await ctx.send(f"⚠️ {ctx.author.mention} 오늘 이미 출석했다묘! (누적 {existing_count}회)")
                        return
                    else:
                        # 일반 출석 - 온도 지급 먼저 시도
                        try:
                            await balance_manager.give(str(user_id), 100)
                            
                            # 온도 지급 성공 시 DB 업데이트
                            count = existing_count + 1
                            await db.execute(
                                "UPDATE attendance SET last_date=?, count=? WHERE user_id=?",
                                (today, count, user_id)
                            )
                            await db.commit()
                            
                            attendance_success = True
                            
                        except Exception as balance_error:
                            print(f"온도 지급 실패: {balance_error}")
                            await ctx.send("❌ 온도 지급 중 오류가 발생했습니다. 관리자에게 문의해주세요.")
                            return

            # 출석 성공 시 처리
            if attendance_success:
                # 잔액 조회
                balance = await balance_manager.get_balance(str(user_id))
                        
                # 퀘스트 처리 (이벤트 발생으로 분리)
                self.bot.dispatch("quest_attendance", user_id)

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
                
                # 썸네일/푸터 아이콘 URL 안전 처리
                avatar_url = ctx.author.display_avatar.url
                embed.set_thumbnail(url=avatar_url)
                embed.set_footer(text=f"현재 잔액: {balance}온 • 요청자: {ctx.author}", icon_url=avatar_url)
                embed.timestamp = ctx.message.created_at
                
                await ctx.send(embed=embed)

        except Exception as e:
            # 예외 처리
            error_embed = discord.Embed(
                title="❌ 출석 처리 오류",
                description="출석 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            print(f"출석 처리 오류: {e}")


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

                username = user.display_name if hasattr(user, "display_name") else user.name
            except Exception:
                username = f"Unknown({user_id})"
            if user_id == ctx.author.id:
                name_line = f"**{i}위 - {username} (You)**"
            else:
                name_line = f"{i}위 - {username}"
            embed.add_field(
                name=name_line,
                value=f"**누적 출석 {count}회**",
                inline=False
            )

        # 본인 순위가 현재 페이지에 없으면 하단에 추가
        author_rank = None
        for idx, (user_id, count) in enumerate(rows, start=1):
            if user_id == ctx.author.id:
                author_rank = (idx, count)
                break
        if author_rank and not any(user_id == ctx.author.id for user_id, _ in page_rows):
            try:
                user = await self.bot.fetch_user(ctx.author.id)
                username = user.display_name if hasattr(user, "display_name") else user.name
            except Exception:
                username = f"Unknown({ctx.author.id})"
            embed.add_field(
                name="───────── ౨ৎ ─────────",
                value=f"**{author_rank[0]}위 - {username} (You)**\n**누적 출석 {author_rank[1]}회**",
                inline=False
            )

        embed.set_footer(text=f"페이지 {page}/{total_pages} | 총 {len(rows)}명 출석")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)
        await self.log(f"{ctx.author}({ctx.author.id})가 출석 순위 조회 [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    # 출석 허용 채널 관리 명령어 (관리자만)
    @commands.group(name="출석설정", invoke_without_command=True)
    @is_guild_admin()
    async def attendance_channel(self, ctx):
        """출석 명령어 허용 채널 관리"""
        await ctx.send("`출석채널추가`, `출석채널제거`, `출석채널목록`, `유저초기화`, `완전초기화` 하위 명령어를 사용하세요.")

    @attendance_channel.command(name="출석채널추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_attendance_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO attendance_allowed_channels (channel_id) VALUES (?)", (channel.id,))
            await db.commit()
        await ctx.send(f"{channel.mention} 채널이 출석 명령어 허용 채널로 추가되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})가 출석 허용 채널 추가: {channel.name}({channel.id}) [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @attendance_channel.command(name="출석채널제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_attendance_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM attendance_allowed_channels WHERE channel_id = ?", (channel.id,))
            await db.commit()
        await ctx.send(f"{channel.mention} 채널이 출석 명령어 허용 채널에서 제거되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})가 출석 허용 채널 제거: {channel.name}({channel.id}) [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @attendance_channel.command(name="출석채널목록")
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
        await self.log(f"{ctx.author}({ctx.author.id})가 출석 허용 채널 목록 조회 [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @attendance_channel.command(name="유저초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_user_attendance(self, ctx, user: discord.Member):
        """특정 유저의 오늘 출석을 초기화합니다. (관리자 전용)"""
        today = datetime.now(KST).strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(DB_PATH) as db:
            # 먼저 현재 상태 확인
            cur = await db.execute(
                "SELECT last_date, count FROM attendance WHERE user_id=?", 
                (user.id,)
            )
            row = await cur.fetchone()
            
            if not row:
                await ctx.send(f"{user.mention}님은 아직 출석 기록이 없습니다.")
                return
                
            last_date, count = row
            if last_date != today:
                await ctx.send(f"{user.mention}님은 오늘 출석하지 않았습니다.")
                return
            
            # 출석 횟수 차감 및 날짜 초기화
            new_count = max(0, count - 1)  # 음수 방지
            await db.execute("""
                UPDATE attendance 
                SET last_date = ?, count = ? 
                WHERE user_id = ?
            """, (
                (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d"),
                new_count,
                user.id
            ))
            await db.commit()
            
            # 온도 회수 (100온 회수)
            await balance_manager.take(str(user.id), 100)
            
            await ctx.send(
                f"✅ {user.mention}님의 오늘 출석이 초기화되었습니다.\n"
                f"출석 횟수가 {count}회 → {new_count}회로 조정되었고, 지급된 100온도 회수되었습니다."
            )
            await self.log(f"{ctx.author}({ctx.author.id})가 {user}({user.id}) 출석 초기화 [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @attendance_channel.command(name="완전초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_all_attendance(self, ctx):
        """모든 유저의 출석 정보를 완전히 초기화합니다. (관리자 전용)"""
        await ctx.send("⚠️ 경고: 데이터베이스의 **모든 출석 정보**가 삭제됩니다.\n정말로 초기화하시겠습니까? 진행하려면 `확인`이라고 입력해주세요. (15초 이내)")
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "확인"
            
        try:
            await self.bot.wait_for('message', check=check, timeout=15.0)
        except asyncio.TimeoutError:
            await ctx.send("⏳ 시간 초과로 완전초기화가 취소되었습니다.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM attendance")
            await db.commit()
            
        await ctx.send("✅ 모든 출석 정보가 성공적으로 초기화되었습니다.")
        await self.log(f"🚨 {ctx.author}({ctx.author.id})가 모든 출석 정보(완전초기화)를 초기화했습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

async def setup(bot):
    await bot.add_cog(AttendanceCog(bot))
