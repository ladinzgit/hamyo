"""
채팅 순위 관련 명령어를 관리하는 모듈입니다.
사용자들의 채팅 활동 순위를 조회할 수 있는 기능을 제공합니다.
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import pytz
import re
import json
import os
from typing import Callable, Dict, List, Optional, Tuple


# 채팅 1개당 점수 (수정 가능)
POINTS_PER_MESSAGE = 1

# 채널당 최대 조회 메시지 수 (성능 최적화)
MAX_MESSAGES_PER_CHANNEL = 1000000

# 설정 파일 경로
CONFIG_PATH = "config/chatting_config.json"


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tracked_channels": []}


class ChattingRankingView(discord.ui.View):
    """채팅 순위를 표시하는 View 클래스"""
    
    def __init__(
        self,
        *,
        owner_id: int,
        ranked: List[Tuple[int, int]],
        formatter: Callable[[int], str],
        name_resolver: Callable[[int], str],
        title: str,
        window_label: str,
        page: int,
        footer_note: str,
        emoji_prefix: str = "<:BM_k_003:1399387520135069770>، ",
        colour: Optional[discord.Colour] = None,
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.ranked = ranked
        self.format_count = formatter
        self.name_resolver = name_resolver
        self.title = title
        self.window_label = window_label
        self.items_per_page = 10
        self.page = page
        self.total_pages = max(1, (len(ranked) + self.items_per_page - 1) // self.items_per_page)
        self.footer_note = footer_note
        self.emoji_prefix = emoji_prefix
        self.colour = colour or discord.Colour.from_rgb(253, 237, 134)
        self.message: Optional[discord.Message] = None
        self.user_rank_info = next(((idx + 1, count) for idx, (uid, count) in enumerate(ranked) if uid == owner_id), None)

        # 페이지 이동 버튼
        self.prev_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="◀ 이전")
        self.next_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="다음 ▶")
        self.prev_button.callback = self.go_prev
        self.next_button.callback = self.go_next

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_button_states()

    def update_button_states(self):
        """버튼 활성화/비활성화 상태를 업데이트합니다."""
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    def render_page(self) -> discord.Embed:
        """현재 페이지의 순위를 embed로 렌더링합니다."""
        start_index = (self.page - 1) * self.items_per_page
        current = self.ranked[start_index : start_index + self.items_per_page]

        # 커스텀 순위 이모지 매핑
        rank_emojis = {
            1: "<a:BM_n_001:1399388350762319878>",
            2: "<a:BM_n_002:1399388356869226556>",
            3: "<a:BM_n_003:1399388362749640894>",
        }

        rows = []
        for idx, (uid, count) in enumerate(current, start=start_index + 1):
            name = self.name_resolver(uid)
            is_me = self.user_rank_info and self.user_rank_info[0] == idx
            marker = " `← 나`" if is_me else ""
            
            if idx in rank_emojis:
                # 1~3위: 커스텀 이모지 + 이름 강조
                rank_display = rank_emojis[idx]
                rows.append(f"{rank_display} **{name}**{marker}\n╰ <a:BM_moon_001:1378716907624202421> {self.format_count(count)}")
            else:
                # 4위 이상: 영어 서수 (4th, 5th...) + 이름
                suffix = "th" if 11 <= idx <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(idx % 10, "th")
                rows.append(f"`{idx}{suffix}` {name}{marker}\n╰ <a:BM_moon_001:1378716907624202421> {self.format_count(count)}")

        if not rows:
            rows.append("표시할 기록이 없습니다.")

        body = "\n".join(rows)

        # TimeSummaryView 스타일의 description 구성
        desc_lines = [
            f"-# {self.window_label}",
        ]
        if self.user_rank_info:
            desc_lines.append(f"**내 순위:** {self.user_rank_info[0]}위")
            desc_lines.append(f"-# ╰ {self.format_count(self.user_rank_info[1])}")
        desc_lines.append("𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃")

        embed = discord.Embed(
            title=f"{self.emoji_prefix}{self.title}",
            description="\n".join(desc_lines),
            colour=self.colour,
        )
        
        embed.add_field(
            name=f"순위 ({self.page}/{self.total_pages} 페이지)",
            value=f"\n{body}\n",
            inline=False,
        )

        embed.set_footer(text=self.footer_note)

        return embed

    async def go_prev(self, interaction: discord.Interaction):
        """이전 페이지로 이동합니다."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 컨트롤은 명령어 실행자만 사용할 수 있어요.", ephemeral=True)
            return

        if self.page > 1:
            self.page -= 1
            self.update_button_states()
        await interaction.response.edit_message(embed=self.render_page(), view=self)

    async def go_next(self, interaction: discord.Interaction):
        """다음 페이지로 이동합니다."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 컨트롤은 명령어 실행자만 사용할 수 있어요.", ephemeral=True)
            return

        if self.page < self.total_pages:
            self.page += 1
            self.update_button_states()
        await interaction.response.edit_message(embed=self.render_page(), view=self)

    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ChattingRanking(commands.Cog):
    """채팅 순위 조회 명령어 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone('Asia/Seoul')
        
    async def cog_load(self):
        # ChattingCommands가 소유한 '채팅' 그룹을 찾아서 '순위' 명령어를 추가
        chatting_cog = self.bot.get_cog('ChattingCommands')
        if chatting_cog:
            # GroupCog의 app_command가 곧 그룹 자체
            group = chatting_cog.__cog_app_commands_group__
            if group and not group.get_command('순위'):
                group.add_command(self._build_ranking_command())
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def cog_unload(self):
        # 언로드 시 '순위' 명령어 제거
        chatting_cog = self.bot.get_cog('ChattingCommands')
        if chatting_cog:
            group = chatting_cog.__cog_app_commands_group__
            if group:
                group.remove_command('순위')

    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    def get_tracked_channels(self) -> List[int]:
        """설정된 추적 채널 목록을 반환합니다."""
        config = load_config()
        return config.get("tracked_channels", [])

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        다양한 날짜 형식을 파싱하여 datetime 객체로 반환합니다.
        지원 형식: YYYY-MM-DD, YYYYMMDD, MM-DD, MMDD
        """
        now = datetime.now(self.tz)
        current_year = now.year
        
        # YYYY-MM-DD
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # YYYYMMDD
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # MM-DD (현재 연도 적용)
        try:
            test_str = f"{current_year}-{date_str}"
            dt = datetime.strptime(test_str, "%Y-%m-%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # MMDD (현재 연도 적용)
        try:
            test_str = f"{current_year}{date_str}"
            dt = datetime.strptime(test_str, "%Y%m%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        return None

    def get_period_range(self, period: str, base_datetime: datetime) -> Tuple[datetime, datetime]:
        """기간에 따른 시작/종료 datetime을 반환합니다."""
        base_datetime = base_datetime.astimezone(self.tz)
        
        if period == '일간':
            start = base_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == '주간':
            start = base_datetime - timedelta(days=base_datetime.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == '월간':
            start = base_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:  # 총합
            # 총합의 경우 서버 오픈 일부터 현재까지
            start = datetime(2025, 8, 1, tzinfo=self.tz)
            end = datetime.now(self.tz) + timedelta(days=1)
            
        return start, end

    def format_message_count(self, count: int) -> str:
        """메시지 수를 포맷팅합니다."""
        points = count * POINTS_PER_MESSAGE
        return f"{count}개 ({points}점)"

    async def count_all_users_messages(
        self,
        channel: discord.TextChannel,
        start: datetime,
        end: datetime,
        target_user_ids: Optional[set] = None
    ) -> Dict[int, int]:
        """
        지정된 채널에서 모든 사용자의 메시지 수를 계산합니다.
        target_user_ids가 지정되면 해당 유저들만 집계합니다.
        """
        user_counts: Dict[int, int] = {}
        try:
            async for message in channel.history(
                after=start,
                before=end,
                limit=MAX_MESSAGES_PER_CHANNEL,
                oldest_first=True
            ):
                # 봇 메시지 제외
                if message.author.bot:
                    continue
                    
                uid = message.author.id
                
                # 특정 유저만 필터링
                if target_user_ids is not None and uid not in target_user_ids:
                    continue
                    
                user_counts[uid] = user_counts.get(uid, 0) + 1
        except discord.Forbidden:
            # 채널 접근 권한 없음
            pass
        except Exception as e:
            print(f"채널 {channel.name} 순위 조회 중 오류: {e}")
        return user_counts

    def _build_ranking_command(self) -> app_commands.Command:
        """'순위' 명령어를 동적으로 생성합니다."""
        cog_self = self

        @app_commands.command(name="순위", description="채팅 순위를 확인합니다.")
        @app_commands.describe(
            role="순위를 조회할 역할입니다. (미입력 시 전체 유저)",
            period="확인할 기간을 선택합니다. (일간/주간/월간/총합, 미입력 시 일간)",
            page="확인할 페이지를 선택합니다. (기본값: 1)",
            base_date="기준일을 지정합니다. (YYYY-MM-DD, MMDD 등, 미입력 시 현재 날짜)"
        )
        @app_commands.choices(period=[
            app_commands.Choice(name="일간", value="일간"),
            app_commands.Choice(name="주간", value="주간"),
            app_commands.Choice(name="월간", value="월간"),
            app_commands.Choice(name="총합", value="총합")
        ])
        async def check_ranking(
            interaction: discord.Interaction,
            role: discord.Role = None,
            period: str = "일간",
            page: int = 1,
            base_date: str = None
        ):
            await cog_self._check_ranking(interaction, role, period, page, base_date)

        return check_ranking

    async def _check_ranking(
        self,
        interaction: discord.Interaction,
        role: discord.Role = None,
        period: str = "일간",
        page: int = 1,
        base_date: str = None
    ):
        """채팅 순위를 확인하는 슬래시 명령어"""
        try:
            # 기준일 파싱
            if base_date:
                base_datetime = self.parse_date(base_date)
                if not base_datetime:
                    await interaction.response.send_message(
                        "날짜 형식이 올바르지 않습니다. YYYY-MM-DD, MMDD 등 형식으로 입력해주세요.",
                        ephemeral=True
                    )
                    return
            else:
                base_datetime = datetime.now(self.tz)

            # 페이지 유효성 검사
            if page < 1:
                await interaction.response.send_message("페이지 번호는 1 이상이어야 합니다.", ephemeral=True)
                return

            # 추적 채널 목록 가져오기
            tracked_channel_ids = self.get_tracked_channels()
            if not tracked_channel_ids:
                await interaction.response.send_message(
                    "설정된 채팅 추적 채널이 없습니다. 관리자에게 문의해주세요.",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # 기간 범위 계산
            start, end = self.get_period_range(period, base_datetime)

            # 역할 필터링 대상 유저 ID 집합
            target_user_ids = None
            if role is not None:
                target_user_ids = {member.id for member in role.members}
                if not target_user_ids:
                    await interaction.followup.send(
                        f"{role.name} 역할을 가진 멤버가 없습니다.",
                        ephemeral=True
                    )
                    return

            # 모든 채널에서 메시지 수 집계
            all_user_counts: Dict[int, int] = {}

            for channel_id in tracked_channel_ids:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception:
                        continue
                
                if not isinstance(channel, discord.TextChannel):
                    continue

                channel_counts = await self.count_all_users_messages(channel, start, end, target_user_ids)
                for uid, count in channel_counts.items():
                    all_user_counts[uid] = all_user_counts.get(uid, 0) + count

            # 순위 정렬
            user_totals = [(uid, count) for uid, count in all_user_counts.items()]
            ranked = sorted(user_totals, key=lambda x: x[1], reverse=True)

            if not ranked:
                role_text = f"{role.name} 역할의 " if role else ""
                await interaction.followup.send(
                    f"해당 기간에 {role_text}채팅 기록이 없습니다.",
                    ephemeral=True
                )
                return

            # 페이지 유효성 검사
            items_per_page = 10
            total_pages = (len(ranked) + items_per_page - 1) // items_per_page

            if page > total_pages:
                await interaction.followup.send(
                    f"요청한 페이지는 존재하지 않습니다. (1-{total_pages})",
                    ephemeral=True
                )
                return

            # 날짜 범위 문자열 생성
            start_str = start.strftime("%Y-%m-%d")
            end_str = (end - timedelta(days=1)).strftime("%Y-%m-%d")

            # 타이틀 및 라벨 설정
            if role:
                title = f"{role.name} 역할 채팅 순위"
                window_label = f"{role.name} • {period} ({start_str} ~ {end_str})"
                colour = role.colour
            else:
                title = "채팅 순위"
                window_label = f"{period} ({start_str} ~ {end_str})"
                colour = discord.Colour.from_rgb(253, 237, 134)

            footer_note = "메시지 조회에 시간이 걸릴 수 있다묘 .ᐟ"

            def resolve_name(uid: int) -> str:
                member = interaction.guild.get_member(uid)
                return member.display_name if member else f"알 수 없음 ({uid})"

            view = ChattingRankingView(
                owner_id=interaction.user.id,
                ranked=ranked,
                formatter=self.format_message_count,
                name_resolver=resolve_name,
                title=title,
                window_label=window_label,
                page=page,
                footer_note=footer_note,
                emoji_prefix="<:BM_k_003:1399387520135069770>، ",
                colour=colour,
            )

            message = await interaction.followup.send(embed=view.render_page(), view=view)
            view.message = message

            role_text = f"{role.name} 역할 " if role else ""
            await self.log(
                f"{interaction.user}({interaction.user.id})님께서 "
                f"{role_text}{period} 채팅 순위를 조회했습니다. "
                f"[길드: {interaction.guild.name}({interaction.guild.id}), "
                f"채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]"
            )

        except Exception as e:
            await self.log(
                f"채팅 순위 확인 중 오류 발생: {e} "
                f"[길드: {interaction.guild.name if interaction.guild else 'N/A'}, "
                f"채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]"
            )
            if not interaction.response.is_done():
                await interaction.response.send_message("채팅 순위 조회 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.followup.send("채팅 순위 조회 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChattingRanking(bot))
