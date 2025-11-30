import discord
from discord.ext import commands

import fortune_db
from .BirthdayInterface import only_in_guild


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
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    def _format_targets(self, guild: discord.Guild) -> str:
        targets = fortune_db.list_targets(guild.id)
        if not targets:
            return "등록된 운세 사용 대상이 없다묘..."

        max_lines = 15
        lines = []
        for idx, target in enumerate(targets):
            if idx >= max_lines:
                lines.append(f"...외 {len(targets) - max_lines}명")
                break
            member = guild.get_member(int(target["user_id"]))
            mention = member.mention if member else f"탈퇴자? (ID: {target['user_id']})"
            lines.append(f"- {mention} · 남은 일수: **{target['count']}일**")
        return "\n".join(lines)

    async def _grant_role(self, guild: discord.Guild, member: discord.Member):
        """운세 역할을 대상에게 부여"""
        config = fortune_db.get_guild_config(guild.id)
        role_id = config.get("role_id")
        if not role_id:
            return
        role = guild.get_role(role_id)
        if not role:
            await self.log(f"운세 역할(ID: {role_id})을 찾지 못함 [길드: {guild.name}({guild.id})]")
            return
        if role not in member.roles:
            try:
                await member.add_roles(role, reason="운세 대상 등록")
            except Exception as e:
                await self.log(f"{member}({member.id})에게 운세 역할 부여 실패: {e}")

    async def _remove_role_from_all(self, guild: discord.Guild, role: discord.Role):
        """길드 내 모든 멤버에서 특정 역할 제거"""
        for member in role.members:
            try:
                await member.remove_roles(role, reason="운세 역할 해제")
            except Exception as e:
                await self.log(f"{member}({member.id}) 운세 역할 회수 실패: {e}")

    @commands.group(name="운세설정", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def fortune_setup(self, ctx):
        """운세 설정 도움말/현황"""
        config = fortune_db.get_guild_config(ctx.guild.id)

        send_time = config.get("send_time") or "미설정"
        role_id = config.get("role_id")
        role = ctx.guild.get_role(role_id) if role_id else None
        role_text = role.mention if role else "미설정"
        channel_id = config.get("channel_id")
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        channel_text = channel.mention if channel else "미설정"

        embed = discord.Embed(
            title="하묘의 운세 설정 안내다묘!ฅ^•ﻌ•^ฅ",
            description="""
ฅ՞•ﻌ•՞ฅ 꾸준히 운세를 챙기고 싶다면 여기서 설정해 달라묘!
(*운세설정 명령어는 관리자 전용이라묘.)
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.add_field(
            name="관리자 명령어",
            value=(
                "`*운세설정 시간 [HH:MM]` : 운세를 보내는 시간을 KST 기준으로 저장\n"
                "`*운세설정 역할 [@역할]` : 운세 안내에 사용할 역할을 설정/해제\n"
                "`*운세설정 채널 [#채널]` : 운세 안내를 멘션할 채널을 지정/해제\n"
                "`*운세설정 대상추가 [@유저] [일수]` : 특정 유저를 운세 대상에 추가 (count 일 뒤 자동 만료)\n"
                "`*운세설정 대상삭제 [@유저]` : 운세 대상을 목록에서 제거\n"
                "`*운세설정 사용초기화 [@유저]` : 하루 1회 사용 제한을 초기화 (미지정 시 전체 초기화)"
            ),
            inline=False
        )
        embed.add_field(
            name="현재 설정",
            value=(
                f"- 전송 시간(KST): **{send_time}**\n"
                f"- 운세 역할: {role_text}\n"
                f"- 운세 안내 채널: {channel_text}\n"
                f"- 대상 목록:\n{self._format_targets(ctx.guild)}"
            ),
            inline=False
        )
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        await ctx.reply(embed=embed)

    @fortune_setup.command(name="시간")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_send_time(self, ctx, time_text: str):
        """운세 전송 시간을 HH:MM 형식으로 설정"""
        time_text = time_text.strip()
        if time_text.lower() in {"none", "해제", "초기화"}:
            fortune_db.set_send_time(ctx.guild.id, None)
            await ctx.reply("운세 전송 시간이 해제되었다묘. 자유롭게 *운세 명령을 쓸 수 있다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 전송 시간을 해제함 [길드: {ctx.guild.name}({ctx.guild.id})]")
            return

        try:
            hour, minute = time_text.split(":")
            hour_int, minute_int = int(hour), int(minute)
            if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
                raise ValueError
            formatted = f"{hour_int:02d}:{minute_int:02d}"
        except ValueError:
            await ctx.reply("시간 형식이 이상하다묘... `HH:MM`(예: 09:30) 형식으로 적어달라묘!")
            return

        fortune_db.set_send_time(ctx.guild.id, formatted)
        await ctx.reply(f"KST 기준 **{formatted}**에 운세를 보내도록 기억했다묘!")
        await self.log(f"{ctx.author}({ctx.author.id})가 운세 전송 시간을 {formatted} 으로 설정함 [길드: {ctx.guild.name}({ctx.guild.id})]")

    @fortune_setup.command(name="역할")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx, role: discord.Role = None):
        """운세 안내에 사용할 역할을 설정/해제"""
        if role:
            prev_role_id = fortune_db.get_guild_config(ctx.guild.id).get("role_id")
            fortune_db.set_role_id(ctx.guild.id, role.id)
            await ctx.reply(f"운세 역할을 {role.mention} 로 설정했다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 역할을 {role.name}({role.id}) 로 설정함 [길드: {ctx.guild.name}({ctx.guild.id})]")

            # 이전 역할 회수
            if prev_role_id and prev_role_id != role.id:
                prev_role = ctx.guild.get_role(prev_role_id)
                if prev_role:
                    await self._remove_role_from_all(ctx.guild, prev_role)

            # 이미 등록된 대상들에게 역할 부여
            for target in fortune_db.list_targets(ctx.guild.id):
                member = ctx.guild.get_member(int(target["user_id"]))
                if member and int(target.get("count", 0)) > 0:
                    await self._grant_role(ctx.guild, member)
        else:
            # 기존 역할 회수 후 해제
            prev_role_id = fortune_db.get_guild_config(ctx.guild.id).get("role_id")
            fortune_db.set_role_id(ctx.guild.id, None)
            await ctx.reply("운세 역할을 비워두었다묘. 더 이상 역할 멘션은 하지 않는다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 역할을 해제함 [길드: {ctx.guild.name}({ctx.guild.id})]")

            if prev_role_id:
                prev_role = ctx.guild.get_role(prev_role_id)
                if prev_role:
                    await self._remove_role_from_all(ctx.guild, prev_role)

    @fortune_setup.command(name="대상추가")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def add_target(self, ctx, member: discord.Member, count: int):
        """운세 사용 대상을 추가/수정"""
        if count < 1:
            await ctx.reply("count는 1 이상이어야 한다묘! 최소 하루 이상 넣어달라묘.")
            return

        existing = fortune_db.get_target(ctx.guild.id, member.id)
        base_count = int(existing.get("count", 0)) if existing else 0
        new_count = base_count + count

        fortune_db.upsert_target(ctx.guild.id, member.id, new_count)
        await ctx.reply(f"{member.mention} 님을 운세 대상에 추가했다묘! 기존 {base_count}일에 {count}일을 더해 **총 {new_count}일**로 설정했다묘.")
        await self.log(f"{ctx.author}({ctx.author.id})가 {member}({member.id})를 운세 대상(count {base_count}→{new_count})으로 등록/갱신 [길드: {ctx.guild.name}({ctx.guild.id})]")

        # 바로 역할 부여
        if int(new_count) > 0:
            await self._grant_role(ctx.guild, member)

    @fortune_setup.command(name="대상삭제")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def remove_target(self, ctx, member: discord.Member):
        """운세 사용 대상을 제거"""
        removed = fortune_db.remove_target(ctx.guild.id, member.id)
        if removed:
            await ctx.reply(f"{member.mention} 님을 운세 대상에서 뺐다묘. 이제 *운세 명령을 못 쓴다묘.")
            await self.log(f"{ctx.author}({ctx.author.id})가 {member}({member.id})를 운세 대상에서 제거 [길드: {ctx.guild.name}({ctx.guild.id})]")

            # 역할이 설정되어 있다면 회수
            role_id = fortune_db.get_guild_config(ctx.guild.id).get("role_id")
            if role_id:
                role = ctx.guild.get_role(role_id)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="운세 대상 해제")
                    except Exception as e:
                        await self.log(f"{member}({member.id}) 운세 역할 회수 실패: {e}")
        else:
            await ctx.reply("이미 목록에 없거나 못 찾겠다묘...")

    @fortune_setup.command(name="채널")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """운세 안내를 멘션할 채널 설정/해제"""
        if channel:
            fortune_db.set_channel_id(ctx.guild.id, channel.id)
            await ctx.reply(f"운세 안내 채널을 {channel.mention} 으로 설정했다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 안내 채널을 {channel.name}({channel.id}) 으로 설정함 [길드: {ctx.guild.name}({ctx.guild.id})]")
        else:
            fortune_db.set_channel_id(ctx.guild.id, None)
            await ctx.reply("운세 안내 채널을 비워두었다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 안내 채널을 해제함 [길드: {ctx.guild.name}({ctx.guild.id})]")

    @fortune_setup.command(name="사용초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_daily_limit(self, ctx, member: discord.Member = None):
        """
        운세 명령어 하루 1회 제한을 초기화합니다.
        - 멤버를 지정하지 않으면 길드 내 모든 운세 대상의 당일 사용 기록을 초기화합니다.
        """
        if member:
            updated = fortune_db.reset_last_used(ctx.guild.id, member.id)
            if updated:
                await ctx.reply(f"{member.mention}의 운세 일일 사용 제한을 초기화했다묘! 오늘 다시 사용할 수 있다묘.")
                await self.log(f"{ctx.author}({ctx.author.id})가 {member}({member.id})의 운세 일일 사용 제한을 초기화함 [길드: {ctx.guild.name}({ctx.guild.id})]")
            else:
                await ctx.reply("해당 멤버는 운세 대상이 아니거나 초기화할 기록이 없다묘.")
        else:
            updated = fortune_db.reset_last_used(ctx.guild.id, None)
            if updated:
                await ctx.reply(f"길드 내 {updated}명의 운세 일일 사용 제한을 초기화했다묘! 오늘 다시 사용할 수 있다묘.")
            else:
                await ctx.reply("초기화할 운세 대상이 없거나 이미 모두 초기화된 상태다묘.")
            await self.log(f"{ctx.author}({ctx.author.id})가 길드 전체 운세 일일 사용 제한을 초기화함(갱신 {updated}명) [길드: {ctx.guild.name}({ctx.guild.id})]")


async def setup(bot):
    await bot.add_cog(FortuneConfig(bot))
