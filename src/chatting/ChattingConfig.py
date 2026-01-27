"""
채팅 실적 설정을 관리하는 모듈입니다.
추적할 채널을 등록/제거/초기화하는 관리자 명령어를 제공합니다.
"""
import discord
from discord.ext import commands
import json
import os

from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin


# 설정 파일 경로
CONFIG_PATH = "config/chatting_config.json"


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tracked_channels": []}


def save_config(config: dict):
    """설정 파일을 저장합니다."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class ChattingConfig(commands.Cog):
    """채팅 실적 설정 관리 Cog"""
    
    def __init__(self, bot):
        self.bot = bot

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

    @commands.group(name="실적", invoke_without_command=True)
    @is_guild_admin()
    async def chatting(self, ctx):
        """실적 관리자 명령어 도움말을 표시합니다."""
        command_name = ctx.invoked_with
        
        embed = discord.Embed(
            title="실적 관리자 명령어",
            description="채팅 실적 관리자 명령어 사용 방법입니다.\n[*실적]으로 접근 가능합니다.",
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        
        embed.add_field(
            name=f"*{command_name} 채널등록 (채널)",
            value="실적을 기록할 채널을 등록합니다. (채널 여러 개 지정 가능)",
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

        embed.add_field(name="||.||", value="**현재 설정**", inline=False)
        embed.add_field(name="실적 기록중인 채널", value=", ".join(channel_mentions), inline=False)

        await ctx.reply(embed=embed)
        await self.log(f"관리자 {ctx.author}({ctx.author.id})님께서 실적 명령어 사용 방법을 조회하였습니다.")

    @chatting.command(name="채널등록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def register_channel(self, ctx, *channels: discord.TextChannel):
        """실적 추적 채널을 등록합니다."""
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
                    f"{ctx.author}({ctx.author.id})님에 의해 실적 추적 채널에 "
                    f"{ch.mention}({ch.id})를 등록 완료하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
                )

        config["tracked_channels"] = tracked
        save_config(config)

        if added:
            await ctx.reply(f"다음 채널을 실적 추적에 등록했습니다:\n{', '.join(added)}")
        else:
            await ctx.reply("모든 채널이 이미 등록되어 있습니다.")

    @chatting.command(name="채널제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def unregister_channel(self, ctx, *channels: discord.TextChannel):
        """실적 추적 채널을 제거합니다."""
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
                    f"{ch.mention}({ch.id}) 채널 실적 추적을 중지하였습니다. "
                    f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
                )

        config["tracked_channels"] = tracked
        save_config(config)

        if removed:
            await ctx.reply(f"다음 채널을 실적 추적에서 제거했습니다:\n{', '.join(removed)}")
        else:
            await ctx.reply("제거할 채널을 찾지 못했습니다.")

    @chatting.command(name="채널초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_channels(self, ctx):
        """모든 실적 추적 채널을 초기화합니다."""
        config = load_config()
        config["tracked_channels"] = []
        save_config(config)
        
        await ctx.reply("모든 실적 추적 채널이 초기화되었습니다.")
        await self.log(
            f"{ctx.author}({ctx.author.id})님에 의해 모든 실적 추적 채널이 초기화되었습니다. "
            f"[길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChattingConfig(bot))
