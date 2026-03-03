"""
음성 채널 관련 명령어를 관리하는 모듈입니다.
사용자의 음성 채널 사용 시간을 조회하고, 순위를 확인할 수 있는 기능을 제공합니다.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from src.core.DataManager import DataManager
import pytz
import re
from typing import Callable, List, Optional, Tuple


class TimeSummaryView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        user: discord.Member,
        period: str,
        date_range: str,
        total_seconds: int,
        categories: List[Tuple[Optional[int], dict]],
        formatter: Callable[[int], str],
        rank: Optional[Tuple[int, int]] = None,
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.user = user
        self.period = period
        self.date_range = date_range
        self.total_seconds = total_seconds
        self.categories = categories
        self.format_duration = formatter
        self.rank = rank  # (rank, total_users)
        self.selected_index: Optional[int] = None
        self.message: Optional[discord.Message] = None

        summary_label = f"총합 {self.format_duration(total_seconds)}"
        window_label = f"{period} • {date_range}"
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, label=summary_label, disabled=True))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label=window_label, disabled=True))

        if categories:
            options = []
            for idx, (_, cat) in enumerate(categories):
                label = cat["name"] if len(cat["name"]) < 95 else f"{cat['name'][:95]}…"
                options.append(
                    discord.SelectOption(
                        label=label,
                        description=f"총합 {self.format_duration(cat['total'])}",
                        value=str(idx),
                        default=False,
                    )
                )

            self.category_select = discord.ui.Select(
                placeholder="카테고리를 선택하면 채널별 기록을 보여준다묘 .ᐟ",
                options=options,
                min_values=1,
                max_values=1,
            )
            self.category_select.callback = self.on_select
            self.add_item(self.category_select)

    def render_content(self) -> str:
        # deprecated, 하위 호환성을 위해 유지
        return ""

    def render_embed(self) -> discord.Embed:
        def extract_name(text: str) -> str:
            if not text: return ""
            name = re.sub(r"^[《『][^》』]+[》』]\s*", "", text)
            name = re.sub(r"^[&!]\s*", "", name)
            return name.strip() or text

        display_label = extract_name(self.user.display_name)
        title = f"<:BM_a_000:1477525641623502950>､ {display_label}님의 음성 기록"
        date_range_pretty = self.date_range.replace(" ~ ", " → ")
        desc_lines = [
            f"-# {self.period}､ {date_range_pretty}",
            f"**총합:** {self.format_duration(self.total_seconds)}",
        ]
        if self.rank:
            rank_num, total_users = self.rank
            desc_lines.append(f"**순위:** {rank_num}위 / {total_users}명")
            
        desc_lines.append("𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃")

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_lines),
            colour=discord.Colour.from_rgb(253, 237, 134),
        )

        if self.selected_index is not None and self.categories:
            cat = self.categories[self.selected_index][1]
            embed.add_field(
                name=f"{cat['name']} 채널별 기록",
                value=self.render_category_block(cat),
                inline=False,
            )
        else:
            summary_lines = []
            for _, cat in self.categories:
                summary_lines.append(f"{cat['name']}\n<a:BM_moon_001:1378716907624202421>{self.format_duration(cat['total'])}")
            summary_text = "\n".join(summary_lines) if summary_lines else "표시할 카테고리가 없습니다."
            summary_text += "\n\n세부 기록을 확인할 카테고리를 아래에서 선택하라묘 .ᐟ"
            embed.add_field(
                name="카테고리별 음성 기록",
                value=summary_text,
                inline=False,
            )

        embed.set_thumbnail(url=self.user.display_avatar)
        embed.set_footer(text="반영까지 최대 1분이 소요될 수 있다묘 .ᐟ")
        return embed

    def render_category_block(self, cat: dict) -> str:
        lines = []
        for channel_mention, sec, pos in sorted(cat["channels"], key=lambda x: x[2]):
            lines.append(f"{channel_mention}\n<a:BM_moon_001:1378716907624202421>{self.format_duration(sec)}")

        if cat.get("deleted_total", 0) > 0:
            lines.append(f"삭제된 채널\n<a:BM_moon_001:1378716907624202421>{self.format_duration(cat['deleted_total'])}")

        if lines:
            lines.append("")
        lines.append(f"<:BM_a_000:1399387512945774672> **총 {self.format_duration(cat['total'])}** 채웠다묘 .ᐟ")
        return "\n".join(lines)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 컨트롤은 명령어 실행자만 사용할 수 있어요.", ephemeral=True)
            return

        self.selected_index = int(self.category_select.values[0])
        for opt in self.category_select.options:
            opt.default = opt.value == str(self.selected_index)
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class RankingView(discord.ui.View):
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
        emoji_prefix: str = "<:BM_a_000:1477525641623502950>､ ",
        colour: Optional[discord.Colour] = None,
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.ranked = ranked
        self.format_duration = formatter
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
        self.user_rank_info = next(((idx + 1, secs) for idx, (uid, secs) in enumerate(ranked) if uid == owner_id), None)

        self.prev_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="◀ 이전")
        self.next_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="다음 ▶")
        self.prev_button.callback = self.go_prev
        self.next_button.callback = self.go_next

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_button_states()

    def update_button_states(self):
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    def render_page(self) -> discord.Embed:
        start_index = (self.page - 1) * self.items_per_page
        current = self.ranked[start_index : start_index + self.items_per_page]

        # 커스텀 순위 이모지 매핑
        rank_emojis = {
            1: "<a:BM_n_001:1399388350762319878>",
            2: "<a:BM_n_002:1399388356869226556>",
            3: "<a:BM_n_003:1399388362749640894>",
        }

        rows = []
        for idx, (uid, seconds) in enumerate(current, start=start_index + 1):
            name = self.name_resolver(uid)
            is_me = self.user_rank_info and self.user_rank_info[0] == idx
            marker = " `← 나`" if is_me else ""
            
            if idx in rank_emojis:
                # 1~3위: 커스텀 이모지 + 이름 강조
                rank_display = rank_emojis[idx]
                rows.append(f"{rank_display} **{name}**{marker}\n╰ <a:BM_moon_001:1378716907624202421> {self.format_duration(seconds)}")
            else:
                # 4위 이상: 영어 서수 (4th, 5th...) + 이름
                suffix = "th" if 11 <= idx <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(idx % 10, "th")
                rows.append(f"`{idx}{suffix}` {name}{marker}\n╰ <a:BM_moon_001:1378716907624202421> {self.format_duration(seconds)}")

        if not rows:
            rows.append("표시할 기록이 없습니다.")

        body = "\n".join(rows)

        # TimeSummaryView 스타일의 description 구성
        desc_lines = [
            f"-# {self.window_label}",
        ]
        if self.user_rank_info:
            desc_lines.append(f"**내 순위:** {self.user_rank_info[0]}위")
            desc_lines.append(f"-# ╰ {self.format_duration(self.user_rank_info[1])}")
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

        embed.set_footer(text="반영까지 최대 1분이 소요될 수 있다묘 .ᐟ")

        return embed

    async def go_prev(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 컨트롤은 명령어 실행자만 사용할 수 있어요.", ephemeral=True)
            return

        if self.page > 1:
            self.page -= 1
            self.update_button_states()
        await interaction.response.edit_message(embed=self.render_page(), view=self)

    async def go_next(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 컨트롤은 명령어 실행자만 사용할 수 있어요.", ephemeral=True)
            return

        if self.page < self.total_pages:
            self.page += 1
            self.update_button_states()
        await interaction.response.edit_message(embed=self.render_page(), view=self)

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class VoiceCommands(commands.GroupCog, group_name="보이스"):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.tz = pytz.timezone('Asia/Seoul')
        
    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="🎙️ 음성 시스템 로그", color=discord.Color.blue())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
            
    def calculate_points(self, seconds: int) -> int:
        """음성 채널 사용 시간을 점수로 변환 (1분당 2점, 초 단위 내림)"""
        minutes = seconds // 60
        return minutes * 2

    def format_duration(self, total_seconds: int) -> str:
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}일 {hours}시간 {minutes}분 {seconds}초 ({self.calculate_points(total_seconds)}점)"
    
    async def get_expanded_tracked_channels(self) -> List[int]:
        tracked_ids = await self.data_manager.get_tracked_channels("voice")
        expanded_ids = set()

        # 1. 카테고리ID와 음성채널ID 분리
        category_ids = set()
        voice_channel_ids = set()
        deleted_category_ids = set()  # 삭제된 카테고리 ID 저장
        
        for cid in tracked_ids:
            ch = self.bot.get_channel(cid)
            if ch is None:
                try:
                    ch = await self.bot.fetch_channel(cid)
                except Exception:
                    ch = None
            
            if isinstance(ch, discord.CategoryChannel):
                category_ids.add(cid)
            elif isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                voice_channel_ids.add(cid)
            else:
                # 삭제되었거나 접근 불가 → 삭제된 카테고리로 간주
                deleted_category_ids.add(cid)

        # 2. 카테고리ID로 등록된 경우, 해당 카테고리의 모든 하위 음성채널 포함
        for cat_id in category_ids:
            cat = self.bot.get_channel(cat_id)
            if cat is None:
                try:
                    cat = await self.bot.fetch_channel(cat_id)
                except Exception:
                    continue
            if isinstance(cat, discord.CategoryChannel):
                for vc in cat.voice_channels:
                    expanded_ids.add(vc.id)
                # Stage 채널도 포함
                for sc in getattr(cat, "stage_channels", []):
                    expanded_ids.add(sc.id)

        # 3. 음성채널ID로 등록된 경우, 해당 음성채널만 포함
        expanded_ids.update(voice_channel_ids)

        # 4. 삭제된 채널 중, category_id가 등록된 카테고리ID에 포함된 것만 추가 (삭제된 카테고리 포함)
        all_category_ids = category_ids | deleted_category_ids
        if all_category_ids:
            deleted_channel_ids = await self.data_manager.get_deleted_channels_by_categories(list(all_category_ids))
            expanded_ids.update(deleted_channel_ids)

        return list(expanded_ids)

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        다양한 날짜 형식을 파싱하여 datetime 객체로 반환합니다.
        지원 형식: YYYY-MM-DD, YYYYMMDD, MM-DD, MMDD
        (연도가 생략된 경우 현재 연도 기준)
        """
        now = datetime.now(self.tz)
        current_year = now.year
        
        # 1. YYYY-MM-DD
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # 2. YYYYMMDD
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # 3. MM-DD (현재 연도 적용)
        try:
            # 윤년 처리를 위해 연도를 붙여서 파싱 시도
            test_str = f"{current_year}-{date_str}"
            dt = datetime.strptime(test_str, "%Y-%m-%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        # 4. MMDD (현재 연도 적용)
        try:
            test_str = f"{current_year}{date_str}"
            dt = datetime.strptime(test_str, "%Y%m%d")
            return dt.replace(tzinfo=self.tz)
        except ValueError:
            pass

        return None

    @app_commands.command(name="확인", description="개인 누적 시간을 확인합니다.")
    @app_commands.describe(
        user="확인할 사용자를 선택합니다. (미입력 시 현재 사용자)",
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 미입력 시 오늘)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD, MMDD 등, 미입력 시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])


    async def check_time(self, interaction: discord.Interaction, 
                        user: discord.Member = None, 
                        period: str = "일간",
                        base_date: str = None):
        try:
            user = user or interaction.user

            if base_date:
                base_datetime = self.parse_date(base_date)
                if not base_datetime:
                    await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD, MMDD 등 형식으로 입력해주세요.", ephemeral=True)
                    return
            else:
                base_datetime = datetime.now(self.tz)

            tracked_channels = await self.get_expanded_tracked_channels()
            times, start_date, end_date = await self.data_manager.get_user_times(user.id, period, base_datetime, tracked_channels)

            if not times:
                await interaction.response.send_message(f"해당 기간에 기록된 음성 채팅 기록이 없습니다.", ephemeral=True)
                return

            await interaction.response.defer()

            total_seconds = sum(times.values())
            start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"

            category_details = {}

            # 삭제된 카테고리를 하나로 합치기 위한 특별 키
            DELETED_CATEGORY_KEY = "__DELETED_CATEGORY__"
            
            for channel_id, seconds in times.items():
                channel = self.bot.get_channel(channel_id)

                if channel:
                    category = channel.category
                    category_id = category.id if category else None
                    category_name = category.name if category else "기타"
                    category_position = category.position if category else float('inf')
                    channel_name = channel.name
                    channel_position = channel.position
                    is_deleted_category = False
                else:
                    # 삭제된 채널 처리
                    original_category_id = await self.data_manager.get_deleted_channel_category(channel_id)
                    category = self.bot.get_channel(original_category_id) if original_category_id else None
                    
                    if category:
                        # 카테고리는 존재하지만 채널이 삭제된 경우
                        category_id = original_category_id
                        category_name = category.name
                        category_position = category.position
                        is_deleted_category = False
                    else:
                        # 카테고리도 삭제된 경우 → 모두 "삭제된 카테고리"로 합침
                        category_id = DELETED_CATEGORY_KEY
                        category_name = "삭제된 카테고리"
                        category_position = float('inf')
                        is_deleted_category = True
                    
                    channel_name = "삭제된 채널"
                    channel_position = float('inf')

                if category_id not in category_details:
                    category_details[category_id] = {
                        "name": category_name,
                        "position": category_position,
                        "channels": [],
                        "total": 0,
                        "deleted_total": 0
                    }

                if channel_name == "삭제된 채널":
                    category_details[category_id]["deleted_total"] += seconds
                else:
                    category_details[category_id]["channels"].append((channel.mention, seconds, channel_position))

                category_details[category_id]["total"] += seconds

            sorted_categories = sorted(category_details.items(), key=lambda x: (x[1]["position"], x[1]["name"]))

            # 순위 계산 (동일 기간/채널 기준)
            rank, total_users, user_total, _, _ = await self.data_manager.get_user_rank(
                user.id,
                period,
                base_datetime,
                tracked_channels,
            )

            view = TimeSummaryView(
                owner_id=interaction.user.id,
                user=user,
                period=period,
                date_range=f"{start_str} ~ {end_str}",
                total_seconds=total_seconds,
                categories=sorted_categories,
                formatter=self.format_duration,
                rank=(rank, total_users) if rank else None,
            )

            message = await interaction.followup.send(embed=view.render_embed(), view=view)
            view.message = message
            await self.log(f"{interaction.user}({interaction.user.id})님께서 {user}({user.id})님의 {period} 기록을 조회했습니다. [길드: {interaction.guild.name}({interaction.guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]")

        except Exception as e:
            await self.log(f"음성 채팅 기록 확인 중 오류 발생: {e} [길드: {interaction.guild.name if interaction.guild else 'N/A'}, 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]")
            await interaction.response.send_message("기록 조회 중 오류가 발생했습니다.", ephemeral=True)


    @app_commands.command(name="순위", description="음성 채널 사용 시간 순위를 확인합니다.")
    @app_commands.describe(
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 기본값: 일간)",
        page="확인할 페이지를 선택합니다. (기본값: 1)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD, MMDD 등, 미입력시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])


    async def check_ranking(self, interaction: discord.Interaction, 
                        period: str = "일간", 
                        page: int = 1,
                        base_date: str = None):

        try:
            # 기준일 파싱
            if base_date:
                base_datetime = self.parse_date(base_date)
                if not base_datetime:
                    await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD, MMDD 등 형식으로 입력해주세요.", ephemeral=True)
                    return
            else:
                base_datetime = datetime.now(self.tz)

            # 페이지 유효성 검사
            if page < 1:
                await interaction.response.send_message("페이지 번호는 1 이상이어야 합니다.", ephemeral=True)
                return

            await interaction.response.defer() # 시간이 오래 걸릴 것을 대비해 defer 처리

            # 총 시간 데이터 조회
            tracked_channels = await self.get_expanded_tracked_channels()
            all_data, start_date, end_date = await self.data_manager.get_all_users_times(period, base_datetime, tracked_channels)

            user_totals = [(uid, sum(times.values())) for uid, times in all_data.items()]
            ranked = sorted(user_totals, key=lambda x: x[1], reverse=True)

            if not ranked:
                return await interaction.followup.send("해당 기간에 해당하는 기록이 없습니다.", ephemeral=True)

            items_per_page = 10
            total_pages = (len(ranked) + items_per_page - 1) // items_per_page

            if page > total_pages:
                return await interaction.followup.send(f"요청한 페이지는 존재하지 않습니다. (1-{total_pages})", ephemeral=True)

            start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"

            window_label = f"{period} ({start_str} ~ {end_str})"
            footer_note = "반영까지 최대 1분이 소요될 수 있습니다."

            def resolve_name(uid: int) -> str:
                member = interaction.guild.get_member(uid)
                return member.display_name if member else f"알 수 없음 ({uid})"

            view = RankingView(
                owner_id=interaction.user.id,
                ranked=ranked,
                formatter=self.format_duration,
                name_resolver=resolve_name,
                title="음성 채널 순위",
                window_label=window_label,
                page=page,
                footer_note=footer_note,
                emoji_prefix="<:BM_a_000:1477525641623502950>､ ",
            )

            message = await interaction.followup.send(embed=view.render_page(), view=view)
            view.message = message

        except Exception as e:
            await self.log(f"순위 확인 중 오류 발생: {e} [길드: {interaction.guild.name if interaction.guild else 'N/A'}, 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]")
            await interaction.response.send_message("순위 조회 중 오류가 발생했습니다.", ephemeral=True)


    @app_commands.command(name="역할순위", description="특정 역할 내에서 음성 채널 사용 시간 순위를 확인합니다.")
    @app_commands.describe(
        role="순위를 조회할 디스코드 역할",
        period="확인할 기간을 선택합니다. (일간/주간/월간/누적, 기본값: 일간)",
        page="확인할 페이지를 선택합니다. (기본값: 1)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD, MMDD 등, 미입력시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="누적", value="누적")
    ])


    async def check_role_ranking(self, interaction: discord.Interaction,
                                role: discord.Role,
                                period: str = "일간",
                                page: int = 1,
                                base_date: str = None):
        try:
            # 기준일 파싱
            if base_date:
                base_datetime = self.parse_date(base_date)
                if not base_datetime:
                    await interaction.response.send_message("날짜 형식이 올바르지 않습니다. YYYY-MM-DD, MMDD 등 형식으로 입력해주세요.", ephemeral=True)
                    return
            else:
                base_datetime = datetime.now(self.tz)

            if page < 1:
                await interaction.response.send_message("페이지 번호는 1 이상이어야 합니다.", ephemeral=True)
                return

            await interaction.response.defer()  # 시간이 오래 걸릴 것을 대비해 defer 처리

            # 총 시간 데이터 조회
            tracked_channels = await self.get_expanded_tracked_channels()
            all_data, start_date, end_date = await self.data_manager.get_all_users_times(period, base_datetime, tracked_channels)

            role_member_ids = {member.id for member in role.members}
            filtered = [(uid, sum(times.values())) for uid, times in all_data.items() if uid in role_member_ids]
            ranked = sorted(filtered, key=lambda x: x[1], reverse=True)

            if not ranked:
                return await interaction.followup.send(f"{role.name} 역할의 기록이 없습니다.", ephemeral=True)

            items_per_page = 10
            total_pages = (len(ranked) + items_per_page - 1) // items_per_page

            if page > total_pages:
                return await interaction.followup.send(f"요청한 페이지는 존재하지 않습니다. (1-{total_pages})", ephemeral=True)

            start_str = start_date.strftime("%Y-%m-%d") if start_date else "-"
            end_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d") if end_date else "-"
            window_label = f"{role.name} • {period} ({start_str} ~ {end_str})"
            footer_note = "반영까지 최대 1분이 소요될 수 있습니다."

            def resolve_name(uid: int) -> str:
                member = interaction.guild.get_member(uid)
                return member.display_name if member else f"알 수 없음 ({uid})"

            view = RankingView(
                owner_id=interaction.user.id,
                ranked=ranked,
                formatter=self.format_duration,
                name_resolver=resolve_name,
                title=f"{role.name} 역할 음성 사용 시간 순위",
                window_label=window_label,
                page=page,
                footer_note=footer_note,
                colour=role.colour,
                emoji_prefix="<:BM_a_000:1477525641623502950>､ ",
            )

            message = await interaction.followup.send(embed=view.render_page(), view=view)
            view.message = message

        except Exception as e:
            await self.log(f"역할 순위 확인 중 오류 발생: {e} [길드: {interaction.guild.name if interaction.guild else 'N/A'}, 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]")
            await interaction.response.send_message("역할 순위 조회 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCommands(bot))
