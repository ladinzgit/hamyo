"""
채팅 설정을 관리하는 모듈입니다.
추적할 채널을 등록/제거/초기화하고, DB 동기화 및 무시 역할 관리 명령어를 제공합니다.
"""
import discord
from discord.ext import commands
import json
import os
import re
from datetime import datetime
import pytz

from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin
from src.core.ChattingDataManager import ChattingDataManager

KST = pytz.timezone("Asia/Seoul")

# 설정 파일 경로
CONFIG_PATH = "config/chatting_config.json"

# 한글 정규식
KOREAN_PATTERN = re.compile(r'[가-힣]')

# 점수 설정 (ChattingTracker와 동일)
BASE_POINTS = 2
LONG_MESSAGE_POINTS = 3
LONG_MESSAGE_THRESHOLD = 30
MIN_KOREAN_CHARS = 10


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 기존 설정에 ignored_role_ids가 없으면 추가
            if "ignored_role_ids" not in config:
                config["ignored_role_ids"] = []
            return config
    return {"tracked_channels": [], "ignored_role_ids": []}


def save_config(config: dict):
    """설정 파일을 저장합니다."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class ChattingConfig(commands.Cog):
    """채팅 설정 관리 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
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

    @commands.group(name="채팅설정", invoke_without_command=True)
    @is_guild_admin()
    async def chatting_config(self, ctx):
        """채팅 설정 관리자 명령어 도움말을 표시합니다."""
        command_name = ctx.invoked_with
        
        embed = discord.Embed(
            title="채팅 설정 관리자 명령어",
            description="채팅 설정 관리자 명령어 사용 방법입니다.\n[*채팅설정]으로 접근 가능합니다.",
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        
        embed.add_field(
            name=f"*{command_name} 채널등록 (채널)",
            value="채팅을 기록할 채널을 등록합니다. (채널 여러 개 지정 가능)",
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} 채널제거 (채널)",
            value="기존에 등록되어 있던 채널을 제거합니다. (채널 여러 개 지정 가능)",
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} 채널초기화",
            value="현재 등록되어 있는 모든 채널을 제거합니다.",
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} 무시역할추가 (@역할)",
            value="해당 역할이 멘션된 메시지는 채팅 점수에 반영되지 않습니다.",
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} 무시역할제거 (@역할)",
            value="무시 역할 목록에서 해당 역할을 제거합니다.",
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} DB동기화",
            value="기존 DB를 삭제하고 현재 채널 히스토리 기반으로 DB를 재구축합니다.",
            inline=False
        )

        # 현재 설정된 채널 표시
        config = load_config()
        channel_mentions = []
        
        for channel_id in config.get("tracked_channels", []):
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            
            if channel:
                channel_mentions.append(channel.mention)
            else:
                channel_mentions.append(f"삭제된 채널(ID: {channel_id})")

        if not channel_mentions:
            channel_mentions.append("None")

        # 무시 역할 표시
        ignored_roles = []
        for role_id in config.get("ignored_role_ids", []):
            if ctx.guild:
                role = ctx.guild.get_role(role_id)
                if role:
                    ignored_roles.append(role.mention)
                else:
                    ignored_roles.append(f"삭제된 역할(ID: {role_id})")

        if not ignored_roles:
            ignored_roles.append("None")

        embed.add_field(name="||.||\n", value="**현재 설정**", inline=False)
        embed.add_field(name="채팅 기록중인 채널", value=", ".join(channel_mentions), inline=False)
        embed.add_field(name="무시 역할", value=", ".join(ignored_roles), inline=False)

        await ctx.reply(embed=embed)
        await self.log(f"관리자 {ctx.author}({ctx.author.id})님께서 채팅설정 명령어 사용 방법을 조회하였습니다.")

    @chatting_config.command(name="채널등록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def register_channel(self, ctx, *channels: discord.TextChannel):
        """채팅 추적 채널을 등록합니다."""
        if not channels:
            await ctx.reply("등록할 텍스트 채널을 지정해주세요.")
            return
            
        config = load_config()
        tracked = config.get("tracked_channels", [])
        added = []
        
        for ch in channels:
            if ch.id not in tracked:
                tracked.append(ch.id)
                added.append(ch.mention)
                await self.log(
                    f"{ctx.author}({ctx.author.id})님에 의해 채팅 추적 채널에 "
                    f"{ch.mention}({ch.id})를 등록 완료하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
                )

        config["tracked_channels"] = tracked
        save_config(config)

        if added:
            await ctx.reply(f"다음 채널을 채팅 추적에 등록했습니다:\n{', '.join(added)}")
        else:
            await ctx.reply("모든 채널이 이미 등록되어 있습니다.")

    @chatting_config.command(name="채널제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def unregister_channel(self, ctx, *channels: discord.TextChannel):
        """채팅 추적 채널을 제거합니다."""
        if not channels:
            await ctx.reply("제거할 텍스트 채널을 지정해주세요.")
            return
            
        config = load_config()
        tracked = config.get("tracked_channels", [])
        removed = []
        
        for ch in channels:
            if ch.id in tracked:
                tracked.remove(ch.id)
                removed.append(ch.mention)
                await self.log(
                    f"{ctx.author}({ctx.author.id})님에 의해 "
                    f"{ch.mention}({ch.id}) 채널 채팅 추적을 중지하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
                )

        config["tracked_channels"] = tracked
        save_config(config)

        if removed:
            await ctx.reply(f"다음 채널을 채팅 추적에서 제거했습니다:\n{', '.join(removed)}")
        else:
            await ctx.reply("제거할 채널을 찾지 못했습니다.")

    @chatting_config.command(name="채널초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_channels(self, ctx):
        """모든 채팅 추적 채널을 초기화합니다."""
        config = load_config()
        config["tracked_channels"] = []
        save_config(config)
        
        await ctx.reply("모든 채팅 추적 채널이 초기화되었습니다.")
        await self.log(
            f"{ctx.author}({ctx.author.id})님에 의해 모든 채팅 추적 채널이 초기화되었습니다. "
            f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
        )

    @chatting_config.command(name="무시역할추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_ignored_role(self, ctx, *roles: discord.Role):
        """무시할 역할을 추가합니다."""
        if not roles:
            await ctx.reply("추가할 역할을 지정해주세요.")
            return

        config = load_config()
        ignored = config.get("ignored_role_ids", [])
        added = []

        for role in roles:
            if role.id not in ignored:
                ignored.append(role.id)
                added.append(role.mention)
                await self.log(
                    f"{ctx.author}({ctx.author.id})님에 의해 채팅 무시 역할에 "
                    f"{role.name}({role.id})를 추가하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id})]"
                )

        config["ignored_role_ids"] = ignored
        save_config(config)

        if added:
            await ctx.reply(f"다음 역할을 무시 목록에 추가했습니다:\n{', '.join(added)}")
        else:
            await ctx.reply("모든 역할이 이미 등록되어 있습니다.")

    @chatting_config.command(name="무시역할제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_ignored_role(self, ctx, *roles: discord.Role):
        """무시할 역할을 제거합니다."""
        if not roles:
            await ctx.reply("제거할 역할을 지정해주세요.")
            return

        config = load_config()
        ignored = config.get("ignored_role_ids", [])
        removed = []

        for role in roles:
            if role.id in ignored:
                ignored.remove(role.id)
                removed.append(role.mention)
                await self.log(
                    f"{ctx.author}({ctx.author.id})님에 의해 채팅 무시 역할에서 "
                    f"{role.name}({role.id})를 제거하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id})]"
                )

        config["ignored_role_ids"] = ignored
        save_config(config)

        if removed:
            await ctx.reply(f"다음 역할을 무시 목록에서 제거했습니다:\n{', '.join(removed)}")
        else:
            await ctx.reply("제거할 역할을 찾지 못했습니다.")

    @chatting_config.command(name="DB동기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def sync_db(self, ctx):
        """DB를 초기화하고 채널 히스토리를 기반으로 재구축합니다."""
        config = load_config()
        tracked_channels = config.get("tracked_channels", [])
        ignored_role_ids = config.get("ignored_role_ids", [])

        if not tracked_channels:
            await ctx.reply("설정된 채팅 추적 채널이 없습니다.")
            return

        # 확인 메시지
        embed = discord.Embed(
            title="DB 동기화 시작",
            description="기존 DB를 삭제하고 채널 히스토리를 기반으로 재구축합니다.\n잠시 기다려 주세요...",
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        embed.add_field(name="대상 채널 수", value=f"{len(tracked_channels)}개", inline=True)
        progress_msg = await ctx.reply(embed=embed)

        # DB 초기화
        await self.data_manager.clear_all()

        total_records = 0
        processed_channels = 0

        for channel_id in tracked_channels:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    continue

            if not isinstance(channel, discord.TextChannel):
                continue

            # 채널별 메시지 수집
            batch = []
            channel_count = 0

            try:
                async for message in channel.history(limit=None, oldest_first=True):
                    # 봇 메시지 무시
                    if message.author.bot:
                        continue

                    # 시스템 메시지 무시
                    if message.type != discord.MessageType.default:
                        continue

                    content = message.content or ""

                    # 무시할 역할 멘션 확인
                    if ignored_role_ids and message.role_mentions:
                        has_ignored = any(
                            role.id in ignored_role_ids for role in message.role_mentions
                        )
                        if has_ignored:
                            continue

                    # 한글 10글자 이상 확인
                    korean_count = len(KOREAN_PATTERN.findall(content))
                    if korean_count < MIN_KOREAN_CHARS:
                        continue

                    # 점수 계산
                    if len(content) >= LONG_MESSAGE_THRESHOLD:
                        points = LONG_MESSAGE_POINTS
                    else:
                        points = BASE_POINTS

                    created_at = message.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")

                    batch.append((
                        message.author.id,
                        channel.id,
                        message.id,
                        len(content),
                        points,
                        created_at
                    ))

                    # 1000개씩 배치 삽입
                    if len(batch) >= 1000:
                        inserted = await self.data_manager.bulk_insert(batch)
                        channel_count += inserted
                        batch = []

                # 남은 배치 처리
                if batch:
                    inserted = await self.data_manager.bulk_insert(batch)
                    channel_count += inserted

            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"채널 {channel.name} 동기화 중 오류: {e}")

            total_records += channel_count
            processed_channels += 1

            # 진행률 업데이트
            embed.description = (
                f"동기화 진행 중... ({processed_channels}/{len(tracked_channels)} 채널)\n"
                f"현재까지 {total_records}개 기록 처리됨"
            )
            try:
                await progress_msg.edit(embed=embed)
            except discord.HTTPException:
                pass

        # 완료 메시지
        embed.title = "DB 동기화 완료"
        embed.description = f"총 {processed_channels}개 채널에서 {total_records}개 기록을 동기화했습니다."
        embed.colour = discord.Colour.green()
        try:
            await progress_msg.edit(embed=embed)
        except discord.HTTPException:
            pass

        await self.log(
            f"{ctx.author}({ctx.author.id})님에 의해 채팅 DB 동기화가 완료되었습니다. "
            f"({processed_channels}개 채널, {total_records}개 기록) "
            f"[길드: {ctx.guild.name}({ctx.guild.id})]"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChattingConfig(bot))
