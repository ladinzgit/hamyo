"""
채팅 관련 명령어를 관리하는 모듈입니다.
사용자의 채팅 활동을 DB 기반으로 조회할 수 있는 기능을 제공합니다.
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import pytz
import re
import json
import os
from typing import List, Optional, Tuple

from src.core.ChattingDataManager import ChattingDataManager

# 설정 파일 경로
CONFIG_PATH = "config/chatting_config.json"


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tracked_channels": [], "ignored_role_ids": []}


class ChattingSummaryView(discord.ui.View):
    """채팅 기록 요약을 표시하는 View 클래스"""
    
    def __init__(
        self,
        *,
        owner_id: int,
        user: discord.Member,
        period: str,
        date_range: str,
        total_messages: int,
        total_points: int,
        channel_details: List[Tuple[discord.TextChannel, int, int]],
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.user = user
        self.period = period
        self.date_range = date_range
        self.total_messages = total_messages
        self.total_points = total_points
        self.channel_details = channel_details
        self.message: Optional[discord.Message] = None

        # 총합 점수 및 기간 표시 버튼
        summary_label = f"총합 {total_messages}개 ({total_points}점)"
        window_label = f"{period} • {date_range}"
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, label=summary_label, disabled=True))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label=window_label, disabled=True))

    def render_embed(self) -> discord.Embed:
        """채팅 기록 정보를 embed로 렌더링합니다."""
        def extract_name(text: str) -> str:
            match = re.search(r"([가-힣A-Za-z0-9_]+)$", text or "")
            return match.group(1) if match else text

        display_label = extract_name(self.user.display_name)
        title = f"<:BM_k_003:1399387520135069770>، {display_label}님의 채팅 기록"
        date_range_pretty = self.date_range.replace(" ~ ", " → ")
        
        desc_lines = [
            f"-# {self.period}، {date_range_pretty}",
            f"**총합:** {self.total_messages}개 ({self.total_points}점)",
            "𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃",
        ]

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_lines),
            colour=discord.Colour.from_rgb(253, 237, 134),
        )

        # 채널별 상세 정보
        if self.channel_details:
            channel_lines = []
            for channel, count, points in sorted(self.channel_details, key=lambda x: x[2], reverse=True):
                channel_lines.append(f"{channel.mention}\n<a:BM_moon_001:1378716907624202421>{count}개 ({points}점)")
            
            channel_text = "\n".join(channel_lines)
            embed.add_field(
                name="채널별 채팅 기록",
                value=channel_text if channel_text else "표시할 기록이 없습니다.",
                inline=False,
            )

        embed.set_thumbnail(url=self.user.display_avatar)
        embed.set_footer(text="채팅 기록 조회 결과다묘 .ᐟ")
        return embed

    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ChattingCommands(commands.GroupCog, group_name="채팅"):
    """채팅 조회 명령어 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone('Asia/Seoul')
        self.data_manager = ChattingDataManager()
        bot.loop.create_task(self.data_manager.initialize())
        
    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

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
            start = datetime(2025, 8, 1, tzinfo=self.tz)
            end = datetime.now(self.tz) + timedelta(days=1)
            
        return start, end

    @app_commands.command(name="확인", description="개인 채팅 기록을 확인합니다.")
    @app_commands.describe(
        user="확인할 사용자를 선택합니다. (미입력 시 현재 사용자)",
        period="확인할 기간을 선택합니다. (일간/주간/월간/총합, 미입력 시 일간)",
        base_date="기준일을 지정합니다. (YYYY-MM-DD, MMDD 등, 미입력 시 현재 날짜)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="일간", value="일간"),
        app_commands.Choice(name="주간", value="주간"),
        app_commands.Choice(name="월간", value="월간"),
        app_commands.Choice(name="총합", value="총합")
    ])
    async def check_chatting(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        period: str = "일간",
        base_date: str = None
    ):
        """채팅 기록을 확인하는 슬래시 명령어"""
        try:
            user = user or interaction.user

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
            start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end.strftime("%Y-%m-%d %H:%M:%S")

            # DB에서 유저의 채팅 통계 조회
            total_messages, total_points = await self.data_manager.get_user_chat_stats(
                user.id, start_str, end_str
            )

            if total_messages == 0:
                await interaction.followup.send(
                    f"해당 기간에 기록된 채팅 기록이 없습니다.",
                    ephemeral=True
                )
                return

            # 채널별 상세 통계 조회
            channel_stats = await self.data_manager.get_user_channel_stats(
                user.id, start_str, end_str
            )

            channel_details: List[Tuple[discord.TextChannel, int, int]] = []
            for channel_id, count, points in channel_stats:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception:
                        continue
                if isinstance(channel, discord.TextChannel) and count > 0:
                    channel_details.append((channel, count, points))

            # 날짜 범위 문자열 생성
            date_start_str = start.strftime("%Y-%m-%d")
            date_end_str = (end - timedelta(days=1)).strftime("%Y-%m-%d")

            # View 생성 및 응답
            view = ChattingSummaryView(
                owner_id=interaction.user.id,
                user=user,
                period=period,
                date_range=f"{date_start_str} ~ {date_end_str}",
                total_messages=total_messages,
                total_points=total_points,
                channel_details=channel_details,
            )

            message = await interaction.followup.send(embed=view.render_embed(), view=view)
            view.message = message
            
            await self.log(
                f"{interaction.user}({interaction.user.id})님께서 {user}({user.id})님의 "
                f"{period} 채팅 기록을 조회했습니다. "
                f"[길드: {interaction.guild.name}({interaction.guild.id}), "
                f"채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]"
            )

        except Exception as e:
            await self.log(
                f"채팅 기록 확인 중 오류 발생: {e} "
                f"[길드: {interaction.guild.name if interaction.guild else 'N/A'}, "
                f"채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})]"
            )
            if not interaction.response.is_done():
                await interaction.response.send_message("채팅 기록 조회 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.followup.send("채팅 기록 조회 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChattingCommands(bot))
