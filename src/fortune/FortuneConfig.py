import discord
from discord.ext import commands

from src.core import fortune_db
from src.core.admin_utils import is_guild_admin


class FortuneConfig(commands.Cog):
    """운세 기능 관리자 설정용 Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print(f"🐾{self.__class__.__name__} loaded successfully!")

    async def log(self, message: str):
        """Logger cog를 통해 로그 메시지를 전송"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message, title="🍀 운세 시스템 로그", color=discord.Color.green())
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    @commands.group(name="운세설정", invoke_without_command=True)
    @is_guild_admin()
    async def fortune_settings(self, ctx):
        """운세 설정 도움말/현황"""
        config = fortune_db.get_guild_config(ctx.guild.id)
        channel_id = config.get("channel_id")
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        channel_text = channel.mention if channel else "미설정"

        embed = discord.Embed(
            title="하묘의 운세 설정 안내다묘!ฅ^•ﻌ•^ฅ",
            description=(
                "운세는 모든 유저가 하루에 한 번 사용할 수 있다묘!\n"
                "여기서는 채널 지정과 사용 초기화만 관리하면 된다묘."
            ),
            colour=discord.Colour.from_rgb(151, 214, 181),
        )
        embed.add_field(
            name="관리자 명령어",
            value=(
                "`*운세설정 채널지정 [#채널]` : 운세 명령 허용 채널 지정/해제\n"
                "`*운세설정 사용초기화 [@유저]` : 하루 1회 사용 제한 초기화 (미지정 시 전체 초기화)"
            ),
            inline=False,
        )
        embed.add_field(
            name="현재 설정",
            value=f"- 운세 사용 채널: {channel_text}",
            inline=False,
        )
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = ctx.message.created_at
        await ctx.reply(embed=embed)

    @fortune_settings.command(name="채널지정")
    @is_guild_admin()
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """운세 명령 사용 채널 설정/해제"""
        if channel:
            fortune_db.set_channel_id(ctx.guild.id, channel.id)
            await ctx.reply(f"운세 사용 채널을 {channel.mention} 으로 설정했다묘!")
            await self.log(
                f"{ctx.author}({ctx.author.id})가 운세 사용 채널을 "
                f"{channel.name}({channel.id}) 으로 설정함 [길드: {ctx.guild.name}({ctx.guild.id})]"
            )
            return

        fortune_db.set_channel_id(ctx.guild.id, None)
        await ctx.reply("운세 사용 채널 지정을 해제했다묘! 이제 모든 채널에서 사용 가능하다묘.")
        await self.log(f"{ctx.author}({ctx.author.id})가 운세 사용 채널 지정을 해제함 [길드: {ctx.guild.name}({ctx.guild.id})]")

    @fortune_settings.command(name="사용초기화")
    @is_guild_admin()
    async def reset_daily_limit(self, ctx, member: discord.Member = None):
        """
        운세 명령어 하루 1회 제한을 초기화합니다.
        - 멤버를 지정하지 않으면 길드 전체 사용자 기록을 초기화합니다.
        """
        if member:
            updated = fortune_db.reset_last_used(ctx.guild.id, member.id)
            if updated:
                await ctx.reply(f"{member.mention}의 운세 일일 사용 제한을 초기화했다묘! 오늘 다시 사용할 수 있다묘.")
                await self.log(
                    f"{ctx.author}({ctx.author.id})가 {member}({member.id})의 운세 일일 사용 제한을 초기화함 "
                    f"[길드: {ctx.guild.name}({ctx.guild.id})]"
                )
            else:
                await ctx.reply("해당 멤버의 초기화할 기록이 없다묘.")
            return

        updated = fortune_db.reset_last_used(ctx.guild.id, None)
        if updated:
            await ctx.reply(f"길드 내 {updated}명의 운세 일일 사용 제한을 초기화했다묘! 오늘 다시 사용할 수 있다묘.")
        else:
            await ctx.reply("초기화할 기록이 없다묘.")
        await self.log(
            f"{ctx.author}({ctx.author.id})가 길드 전체 운세 일일 사용 제한을 초기화함(갱신 {updated}명) "
            f"[길드: {ctx.guild.name}({ctx.guild.id})]"
        )


async def setup(bot):
    await bot.add_cog(FortuneConfig(bot))
