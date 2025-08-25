import asyncio
import random
from datetime import datetime, timedelta, time, timezone
from typing import Optional, List

import discord
from discord.ext import commands, tasks

# 하묘 기존 경제 시스템 연동
from balance_data_manager import balance_manager

# ----- 타임존(KST) 유틸 -----
# ZoneInfo가 없는 환경 대비 고정 오프셋(+09:00)
KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    return datetime.now(tz=KST)

# 제출 가능한 시간: 00:00 ~ 22:00 (KST)
SUBMIT_START = time(0, 0, tzinfo=KST)
SUBMIT_END = time(22, 0, tzinfo=KST)

# 게시 가능한 시간: 다음날 10:00 ~ 24:00 (KST)
POST_START = time(10, 0, tzinfo=KST)
POST_END = time(23, 59, tzinfo=KST)  # 24:00 대신 23:59 처리

# 가격
DEFAULT_PRICE = 1000

# ----- DB -----
import aiosqlite
DB_FILE = "data/dream_posts.db"

INIT_SQL = [
    # 설정 테이블
    """
    CREATE TABLE IF NOT EXISTS dream_settings (
        guild_id INTEGER PRIMARY KEY,
        review_channel_id INTEGER,
        letter_channel_id INTEGER, -- 꿈편지 게시 채널
        price INTEGER DEFAULT 1000
    )
    """,
    # 게시물 테이블
    """
    CREATE TABLE IF NOT EXISTS dream_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        post_type TEXT NOT NULL CHECK (post_type IN ('LETTER')),
        content TEXT NOT NULL,
        is_anonymous INTEGER NOT NULL DEFAULT 1,
        recipient_id TEXT, -- 받는 사람 ID (옵션)
        scheduled_at TEXT, -- ISO8601, KST 기준 저장
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','POSTED','CANCELED')),
        review_message_id INTEGER, -- 검토용 임베드 메시지 id(옵션)
        created_at TEXT NOT NULL,
        approved_by TEXT,
        rejected_by TEXT,
        reject_reason TEXT
    )
    """,
    # (길드, 시각) 단위로 중복 방지 인덱스
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_dream_unique ON dream_posts (guild_id, scheduled_at)
    """,
]

# ----- UI 구성요소 -----
class DreamModal(discord.ui.Modal, title="꿈편지 작성"):
    def __init__(self, *, price: int, on_submit_cb):
        super().__init__()
        self.price = price
        self.on_submit_cb = on_submit_cb

        self.recipient = discord.ui.TextInput(
            label="받는 사람 (선택사항)",
            placeholder="@사용자 또는 사용자ID (비워두면 익명으로 전송)",
            style=discord.TextStyle.short,
            max_length=100,
            required=False,
        )
        self.add_item(self.recipient)

        self.content = discord.ui.TextInput(
            label="메시지 내용 (1000자 제한)",
            placeholder="보낼 메시지를 입력하세요",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_submit_cb(interaction, self)


def kst_date(dt: datetime) -> datetime:
    return dt.astimezone(KST)


def next_day(dt: datetime) -> datetime:
    return (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def clamp_to_10m(dt: datetime) -> datetime:
    # 분을 10분 단위로 스냅(내림)
    minute = (dt.minute // 10) * 10
    return dt.replace(minute=minute, second=0, microsecond=0)


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        for sql in INIT_SQL:
            await db.execute(sql)
        await db.commit()


class TimeSelect(discord.ui.Select):
    """다음날 10:00~24:00 사이의 10분 단위 슬롯 중 사용 가능한 시각을 선택."""
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(placeholder="게시 시각을 선택하세요 (다음날)", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: DreamTimeView = self.view  # type: ignore
        await view.on_time_selected(interaction, self.values[0])


class DreamTimeView(discord.ui.View):
    def __init__(self, *, author_id: int, on_pick):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.on_pick = on_pick

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user and interaction.user.id == self.author_id

    async def on_time_selected(self, interaction: discord.Interaction, iso_str: str):
        await self.on_pick(interaction, iso_str)


# ----- 메인 Cog -----
class DreamPosts(commands.Cog):
    """꿈편지(LETTER)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dispatcher.start()

    async def cog_load(self):
        await init_db()

    async def get_price(self, guild_id: int) -> int:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT COALESCE(price, ?) FROM dream_settings WHERE guild_id = ?", (DEFAULT_PRICE, guild_id)) as cur:
                row = await cur.fetchone()
                return row[0] if row else DEFAULT_PRICE

    # ----- 설정 커맨드 (관리자) -----
    @commands.group(name="꿈설정", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def dream_settings(self, ctx: commands.Context):
        await ctx.reply("하위 명령: 리뷰채널, 편지채널, 가격")

    @dream_settings.command(name="리뷰채널")
    @commands.has_permissions(administrator=True)
    async def set_review_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._upsert_settings(ctx.guild.id, review_channel_id=channel.id)
        await ctx.reply(f"검토 채널을 {channel.mention} 로 설정했어요.")

    @dream_settings.command(name="편지채널")
    @commands.has_permissions(administrator=True)
    async def set_letter_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._upsert_settings(ctx.guild.id, letter_channel_id=channel.id)
        await ctx.reply(f"꿈편지 게시 채널을 {channel.mention} 로 설정했어요.")

    @dream_settings.command(name="가격")
    @commands.has_permissions(administrator=True)
    async def set_price(self, ctx: commands.Context, price: int):
        await self._upsert_settings(ctx.guild.id, price=max(0, price))
        await ctx.reply(f"가격을 {price} 으로 설정했어요.")

    async def _upsert_settings(self, guild_id: int, **kwargs):
        keys = [*kwargs.keys()]
        values = [*kwargs.values()]
        async with aiosqlite.connect(DB_FILE) as db:
            # INSERT 또는 UPDATE
            await db.execute(
                "INSERT INTO dream_settings (guild_id) VALUES (?) ON CONFLICT(guild_id) DO NOTHING",
                (guild_id,)
            )
            if keys:
                set_clause = ", ".join(f"{k} = ?" for k in keys)
                await db.execute(f"UPDATE dream_settings SET {set_clause} WHERE guild_id = ?", (*values, guild_id))
            await db.commit()

    async def _load_settings(self, guild_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT review_channel_id, letter_channel_id, COALESCE(price, ?) FROM dream_settings WHERE guild_id = ?", (DEFAULT_PRICE, guild_id)) as cur:
                row = await cur.fetchone()
                if row:
                    return {
                        "review": row[0],
                        "letter": row[1],
                        "price": row[2],
                    }
                return None

    # ----- 버튼 진입점 -----
    @commands.command(name="꿈버튼")
    @commands.has_permissions(administrator=True)
    async def send_buttons(self, ctx: commands.Context):
        """유저용 버튼 전송 (꿈편지)"""
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="꿈편지 작성", style=discord.ButtonStyle.primary, custom_id="dream_letter"))
        await ctx.reply("꿈편지를 작성해보세요:", view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
        cid = interaction.data.get("custom_id") if interaction.data else None
        if cid != "dream_letter":
            return

        assert interaction.guild is not None
        settings = await self._load_settings(interaction.guild.id)
        if not settings or not settings.get("review"):
            return await interaction.response.send_message("아직 관리자가 검토 채널을 설정하지 않았어요.", ephemeral=True)

        # 제출 가능 시간 체크
        now = now_kst()
        if not (SUBMIT_START <= now.timetz() <= SUBMIT_END):
            return await interaction.response.send_message("작성 가능 시간은 00:00 ~ 22:00 (KST) 입니다.", ephemeral=True)

        # 잔액 확인
        price = settings["price"] if settings else DEFAULT_PRICE
        balance = await balance_manager.get_balance(str(interaction.user.id))
        if balance < price:
            unit_info = await balance_manager.get_currency_unit()
            unit = unit_info["emoji"] if unit_info else "코인"
            return await interaction.response.send_message(f"잔액이 부족해요. 최소 {price}{unit} 이 필요합니다.", ephemeral=True)

        # 모달 열기
        modal = DreamModal(price=price, on_submit_cb=self.handle_modal_submit)
        await interaction.response.send_modal(modal)

    # ----- 모달 처리 -----
    async def handle_modal_submit(self, interaction: discord.Interaction, modal: DreamModal):
        assert interaction.guild is not None
        settings = await self._load_settings(interaction.guild.id)
        price = settings["price"] if settings else DEFAULT_PRICE

        is_anon = 1
        
        # 받는 사람 파싱
        recipient_id = self.parse_recipient(modal.recipient.value, interaction.guild)

        # 기본 데이터 생성 (시간은 후속 단계에서)
        created = now_kst()
        post_id = None
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute(
                """
                INSERT INTO dream_posts (guild_id, user_id, post_type, content, is_anonymous, recipient_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (
                    interaction.guild.id,
                    str(interaction.user.id),
                    'LETTER',
                    modal.content.value.strip(),
                    is_anon,
                    recipient_id,
                    created.isoformat(),
                ),
            )
            await db.commit()
            post_id = cursor.lastrowid

        if not post_id:
            return await interaction.response.send_message("오류가 발생하여 제출하지 못했어요. 다시 시도해주세요.", ephemeral=True)

        # 시간 선택
        options = await self._build_time_options(interaction.guild.id)
        if not options:
            return await interaction.response.send_message("다음날 가능한 시간이 모두 예약되었어요. 내일 다시 시도해주세요.", ephemeral=True)
        view = DreamTimeView(author_id=interaction.user.id, on_pick=self.on_pick_time)
        view.add_item(TimeSelect(options))
        await interaction.response.send_message("다음날 게시 시각을 선택하세요 (10분 단위).", view=view, ephemeral=True)

    def parse_recipient(self, recipient_input: str, guild: discord.Guild) -> Optional[str]:
        """받는 사람 입력을 파싱하여 유효한 사용자 ID를 반환"""
        if not recipient_input or not recipient_input.strip():
            return None
        
        recipient_input = recipient_input.strip()
        
        # 멘션 형태 (<@123456789> 또는 <@!123456789>)
        if recipient_input.startswith('<@') and recipient_input.endswith('>'):
            user_id = recipient_input[2:-1]
            if user_id.startswith('!'):
                user_id = user_id[1:]
            try:
                user_id = int(user_id)
                member = guild.get_member(user_id)
                if member:
                    return str(user_id)
            except ValueError:
                pass
        
        # 숫자 ID
        try:
            user_id = int(recipient_input)
            member = guild.get_member(user_id)
            if member:
                return str(user_id)
        except ValueError:
            pass
        
        return None

    async def _build_time_options(self, guild_id: int) -> List[discord.SelectOption]:
        """다음날 10:00~24:00의 1시간 간격 중 미점유 슬롯을 옵션으로 생성"""
        tomorrow = next_day(now_kst())
        start = datetime.combine(tomorrow.date(), POST_START, tzinfo=KST)
        end = datetime.combine(tomorrow.date(), POST_END, tzinfo=KST)

        # 이미 예약된 시간 조회
        reserved = set()
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT scheduled_at FROM dream_posts WHERE guild_id = ? AND scheduled_at IS NOT NULL AND status IN ('PENDING','APPROVED')",
                (guild_id,),
            ) as cur:
                rows = await cur.fetchall()
                for (iso_str,) in rows:
                    reserved.add(iso_str)

        options: List[discord.SelectOption] = []
        t = start
        while t <= end:
            iso = t.isoformat()
            if iso not in reserved:
                label = t.strftime("%m/%d %H:%M")
                options.append(discord.SelectOption(label=label, value=iso))
            t += timedelta(hours=1)  # 10분 단위 → 1시간 단위

        return options

    async def on_pick_time(self, interaction: discord.Interaction, iso_str: str):
        assert interaction.guild is not None
        # 가장 최근 본인이 만든 PENDING & LETTER 중 아직 시간 미지정 건을 찾아 갱신
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT id FROM dream_posts WHERE guild_id = ? AND user_id = ? AND post_type = 'LETTER' AND status = 'PENDING' AND scheduled_at IS NULL ORDER BY id DESC LIMIT 1",
                (interaction.guild.id, str(interaction.user.id)),
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return await interaction.response.send_message("대상 항목을 찾지 못했어요. 다시 시도해주세요.", ephemeral=True)
                post_id = row[0]

            try:
                await db.execute(
                    "UPDATE dream_posts SET scheduled_at = ? WHERE id = ?",
                    (iso_str, post_id),
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                return await interaction.response.send_message("방금 사이에 해당 시간이 선점되었어요. 다른 시간을 선택해주세요.", ephemeral=True)

        await interaction.response.send_message("제출 완료! 관리자가 내일 10시까지 검토해요.", ephemeral=True)

        # 검토 채널로 카드 전송/갱신
        await self.push_to_review(interaction.guild.id, post_id)

    # ----- 검토 채널 전송 -----
    async def push_to_review(self, guild_id: int, post_id: int):
        settings = await self._load_settings(guild_id)
        if not settings or not settings["review"]:
            return
        
        channel = self.bot.get_channel(settings["review"]) or await self.bot.fetch_channel(settings["review"])
        if not isinstance(channel, discord.TextChannel):
            return

        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT id, user_id, post_type, content, is_anonymous, recipient_id, scheduled_at, status, created_at FROM dream_posts WHERE id = ?", (post_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return
                _id, user_id, post_type, content, is_anonymous, recipient_id, scheduled_at, status, created_at_str = row
                created_at = datetime.fromisoformat(created_at_str)

        author_disp = "익명"
        when = datetime.fromisoformat(scheduled_at).astimezone(KST).strftime("%m/%d %H:%M") if scheduled_at else "미지정"
        
        # 받는 사람 표시
        recipient_disp = "익명의 대상"
        if recipient_id:
            try:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(int(recipient_id))
                    if member:
                        recipient_disp = f"{member.display_name}({member.mention})"
            except (ValueError, AttributeError):
                pass

        embed = discord.Embed(title="[검토] 꿈편지", description=content, color=discord.Color.blurple())
        embed.add_field(name="작성자", value=author_disp, inline=True)
        embed.add_field(name="받는 사람", value=recipient_disp, inline=True)
        embed.add_field(name="게시시각", value=when, inline=True)
        embed.add_field(name="상태", value=status, inline=False)
        embed.set_footer(text=f"ID: {post_id} | 생성: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        view = ReviewView(cog=self, post_id=post_id)
        msg = await channel.send(embed=embed, view=view)
        # 메시지 id 저장
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE dream_posts SET review_message_id = ? WHERE id = ?", (msg.id, post_id))
            await db.commit()

    # ----- 검토용 View -----
class ReviewView(discord.ui.View):
    def __init__(self, *, cog: "DreamPosts", post_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.post_id = post_id

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_review(interaction, self.post_id, approve=True)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_review(interaction, self.post_id, approve=False)


class DreamPosts(DreamPosts):
    async def handle_review(self, interaction: discord.Interaction, post_id: int, approve: bool):
        assert interaction.guild is not None
        settings = await self._load_settings(interaction.guild.id)
        price = settings["price"] if settings else DEFAULT_PRICE

        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT user_id, post_type, scheduled_at, status FROM dream_posts WHERE id = ?", (post_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return await interaction.response.send_message("항목을 찾을 수 없어요.", ephemeral=True)
                user_id, post_type, scheduled_at, status = row

            if status != "PENDING":
                return await interaction.response.send_message("이미 검토된 항목이에요.", ephemeral=True)

            if not approve:
                await db.execute(
                    "UPDATE dream_posts SET status = 'REJECTED', rejected_by = ? WHERE id = ?",
                    (str(interaction.user.id), post_id),
                )
                await db.commit()
                await interaction.response.send_message("거절 처리했습니다.", ephemeral=True)
                return await self.refresh_review_message(interaction, post_id)

            # 승인 로직: 결제(회수) -> 상태 갱신
            # 잔액 확인 및 회수
            balance = await balance_manager.get_balance(user_id)
            if balance < price:
                await db.execute(
                    "UPDATE dream_posts SET status = 'REJECTED', reject_reason = '잔액부족(검토시)', rejected_by = ? WHERE id = ?",
                    (str(interaction.user.id), post_id),
                )
                await db.commit()
                await interaction.response.send_message("사용자 잔액 부족으로 거절했습니다.", ephemeral=True)
                return await self.refresh_review_message(interaction, post_id)

            # 비용 회수
            await balance_manager.take(user_id, price)

            await db.execute(
                "UPDATE dream_posts SET status = 'APPROVED', approved_by = ? WHERE id = ?",
                (str(interaction.user.id), post_id),
            )
            await db.commit()

        await interaction.response.send_message("승인 및 결제 완료!", ephemeral=True)
        await self.refresh_review_message(interaction, post_id)

    async def refresh_review_message(self, interaction: discord.Interaction, post_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT review_message_id, user_id, post_type, content, is_anonymous, recipient_id, scheduled_at, status FROM dream_posts WHERE id = ?", (post_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return
                msg_id, user_id, post_type, content, is_anonymous, recipient_id, scheduled_at, status = row
        
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not msg_id:
            return
        
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            return

        author_disp = "익명"
        when = datetime.fromisoformat(scheduled_at).astimezone(KST).strftime("%m/%d %H:%M") if scheduled_at else "미지정"
        
        # 받는 사람 표시
        recipient_disp = "익명의 대상"
        if recipient_id:
            try:
                guild = interaction.guild
                if guild:
                    member = guild.get_member(int(recipient_id))
                    if member:
                        recipient_disp = f"{member.display_name}({member.mention})"
            except (ValueError, AttributeError):
                pass
        
        embed = discord.Embed(title="[검토] 꿈편지", description=content, color=discord.Color.blurple())
        embed.add_field(name="작성자", value=author_disp, inline=True)
        embed.add_field(name="받는 사람", value=recipient_disp, inline=True)
        embed.add_field(name="게시시각", value=when, inline=True)
        embed.add_field(name="상태", value=status, inline=False)
        
        new_view = None if status != 'PENDING' else ReviewView(cog=self, post_id=post_id)
        await msg.edit(embed=embed, view=new_view)


    # ----- 디스패처(스케줄러) -----
    @tasks.loop(seconds=30)
    async def dispatcher(self):
        now = now_kst()
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                """
                SELECT id, guild_id, user_id, post_type, content, is_anonymous
                FROM dream_posts
                WHERE status = 'APPROVED' AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                LIMIT 10
                """,
                (now.isoformat(),),
            ) as cur:
                rows = await cur.fetchall()

        for id_, guild_id, user_id, post_type, content, is_anonymous in rows:
            try:
                await self._post_item(id_, guild_id, user_id, post_type, content, is_anonymous)
            except Exception as e:
                print(f"Error posting item {id_}: {e}") # 로깅 추가
                continue

    @dispatcher.before_loop
    async def before_dispatcher(self):
        await self.bot.wait_until_ready()
        await init_db()

    async def _post_item(self, post_id: int, guild_id: int, user_id: str, post_type: str, content: str, is_anonymous: int):
        settings = await self._load_settings(guild_id)
        if not settings:
            return
        
        channel_id = settings["letter"]
        if not channel_id:
            return
        
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel): return
        except discord.NotFound:
            # 채널을 찾을 수 없는 경우 처리
            return

        # 받는 사람 정보 조회
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT recipient_id FROM dream_posts WHERE id = ?", (post_id,)) as cur:
                row = await cur.fetchone()
                recipient_id = row[0] if row else None

        author_disp = "익명"
        
        # 받는 사람 멘션 처리
        recipient_mention = ""
        if recipient_id:
            try:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(int(recipient_id))
                    if member:
                        recipient_mention = f"{member.mention} "
            except (ValueError, AttributeError):
                pass

        embed = discord.Embed(title="꿈편지", description=content, color=discord.Color.green())
        embed.set_footer(text=author_disp)
        
        # 받는 사람이 있으면 멘션과 함께 전송
        message_content = recipient_mention if recipient_mention else None
        await channel.send(content=message_content, embed=embed)

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE dream_posts SET status = 'POSTED' WHERE id = ?", (post_id,))
            await db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(DreamPosts(bot))