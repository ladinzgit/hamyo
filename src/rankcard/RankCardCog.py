"""
랭크 카드 디스코드 명령어 모듈입니다.
*rank, *랭크 (접두사), /rank (슬래시) 명령어를 제공합니다.
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import traceback
import io

from src.rankcard.RankCardService import RankCardService
from src.rankcard.RankCardGenerator import RankCardGenerator


class RankCardCog(commands.Cog):
    """랭크 카드 명령어 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = RankCardService(bot)
        self.generator = RankCardGenerator()

    async def cog_load(self):
        await self.log("RankCardCog 로드됨")

    # ── 로깅 ──
    async def log(self, message: str):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        logger_cog = self.bot.get_cog('Logger')
        if logger_cog:
            await logger_cog.log(message, "RankCardCog")
        else:
            print(f"[RankCardCog] {message}")

    # ── 공통 카드 생성 로직 ──
    async def _generate_and_send(
        self,
        ctx_or_interaction,
        user: discord.Member,
        *,
        is_slash: bool = False
    ):
        """
        랭크 카드를 생성하고 전송합니다.

        접두사 명령어와 슬래시 명령어 모두에서 사용되는 공통 로직입니다.
        1. 로딩 메시지 전송
        2. 데이터 수집 + 아바타 다운로드
        3. 이미지 생성
        4. 결과 전송
        """
        loading_msg = None

        try:
            # 로딩 메시지
            if is_slash:
                await ctx_or_interaction.response.defer()
            else:
                loading_embed = discord.Embed(
                    description="<a:loading:1396829217521844316> 랭크 카드를 생성하고 있어요...",
                    color=discord.Color.from_str("#0f0f13")
                )
                loading_msg = await ctx_or_interaction.send(embed=loading_embed)

            # 데이터 수집
            data = await self.service.get_rank_card_data(user)

            # 아바타 이미지 다운로드
            avatar_bytes = await self._download_avatar(data.avatar_url)
            if not avatar_bytes:
                error_msg = "❌ 아바타 이미지를 불러올 수 없습니다."
                if is_slash:
                    await ctx_or_interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await loading_msg.edit(
                        embed=discord.Embed(description=error_msg, color=discord.Color.red())
                    )
                return

            # 이미지 생성
            image_buffer = self.generator.generate(data, avatar_bytes)

            # 파일 생성 및 전송
            file = discord.File(image_buffer, filename="rank_card.png")

            if is_slash:
                await ctx_or_interaction.followup.send(file=file)
            else:
                await loading_msg.delete()
                await ctx_or_interaction.send(file=file)

            # 로그
            requester = ctx_or_interaction.user if is_slash else ctx_or_interaction.author
            guild = ctx_or_interaction.guild
            await self.log(
                f"{requester}({requester.id})님께서 "
                f"{user}({user.id})님의 랭크 카드를 조회했습니다. "
                f"[길드: {guild.name}({guild.id})]"
            )

        except Exception as e:
            tb = traceback.format_exc()
            await self.log(f"랭크 카드 생성 오류: {e}\n{tb}")

            error_embed = discord.Embed(
                description=f"❌ 랭크 카드 생성 중 오류가 발생했습니다.\n```{type(e).__name__}: {e}```",
                color=discord.Color.red()
            )

            if is_slash:
                if not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
                else:
                    await ctx_or_interaction.followup.send(
                        embed=error_embed, ephemeral=True
                    )
            else:
                if loading_msg:
                    await loading_msg.edit(embed=error_embed)
                else:
                    await ctx_or_interaction.send(embed=error_embed)

    async def _download_avatar(self, url: str) -> bytes | None:
        """아바타 이미지를 비동기로 다운로드합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
            return None
        except Exception as e:
            await self.log(f"아바타 다운로드 실패: {e}")
            return None

    # ── 접두사 명령어: *rank / *랭크 ──
    @commands.command(name="rank", aliases=["랭크"])
    @commands.guild_only()
    async def rank_prefix(self, ctx: commands.Context, user: discord.Member = None):
        """랭크 카드를 확인합니다."""
        user = user or ctx.author
        await self._generate_and_send(ctx, user, is_slash=False)

    # ── 슬래시 명령어: /rank ──
    @app_commands.command(name="rank", description="랭크 카드를 확인합니다.")
    @app_commands.describe(user="확인할 사용자를 선택합니다. (미입력 시 현재 사용자)")
    @app_commands.guild_only()
    async def rank_slash(self, interaction: discord.Interaction, user: discord.Member = None):
        """랭크 카드를 확인하는 슬래시 명령어"""
        user = user or interaction.user
        await self._generate_and_send(interaction, user, is_slash=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RankCardCog(bot))
