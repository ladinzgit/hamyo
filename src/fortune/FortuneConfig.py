import discord
from discord.ext import commands

from src.core import fortune_db
from src.core.admin_utils import only_in_guild, is_guild_admin



class FortuneGrantView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="🍀 운세 보러 가기",
        style=discord.ButtonStyle.green,
        custom_id="fortune_grant_btn"
    )
    async def grant_fortune(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 메시지 ID 확인
        message_id = interaction.message.id
        guild_id = interaction.guild_id

        # 2. DB에서 버튼 정보 조회
        btn_info = fortune_db.get_button_info(guild_id, message_id)
        if not btn_info:
            await interaction.response.send_message("이 버튼은 만료되었거나 유효하지 않다묘...", ephemeral=True)
            return

        user_id = interaction.user.id
        
        # 3. 이미 눌렀는지 확인
        if fortune_db.is_button_clicked(guild_id, message_id, user_id):
            await interaction.response.send_message("이미 이 버튼에서 보상을 받았다묘!", ephemeral=True)
            return

        # 4. 보상 지급 (운세 대상 추가/연장)
        days = int(btn_info.get("expiration_days", 1))
        
        # 기존 정보 조회
        existing = fortune_db.get_target(guild_id, user_id)
        base_count = int(existing.get("count", 0)) if existing else 0
        new_count = base_count + days
        
        # DB 업데이트 (대상 추가 + 클릭 기록)
        fortune_db.upsert_target(guild_id, user_id, new_count)
        fortune_db.record_button_click(guild_id, message_id, user_id)

        # 역할 부여 필요 시 처리
        # (Cog의 메서드를 직접 부르기 어려우므로 DB 조회해서 처리)
        config = fortune_db.get_guild_config(guild_id)
        role_id = config.get("role_id")
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role and role not in interaction.user.roles:
                try:
                    await interaction.user.add_roles(role, reason="운세 버튼 보상 획득")
                except:
                    pass  # 권한 부족 등은 패스

        await interaction.response.send_message(f"운세 사용권({days}일)을 획득했다묘! (총 {new_count}일)", ephemeral=True)

class FortuneConfig(commands.Cog):
    """운세 기능 관리자 설정용 Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(FortuneGrantView(self.bot))
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
    @is_guild_admin()
    async def fortune_settings(self, ctx):
        """운세 설정 도움말/현황"""
        config = fortune_db.get_guild_config(ctx.guild.id)

        send_times = config.get("send_time", [])
        send_time_text = ", ".join(send_times) if send_times else "미설정"
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
                "`*운세설정 시간추가 [HH:MM]` : 운세를 보내는 시간을 추가 (여러 개 가능)\n"
                "`*운세설정 시간제거 [HH:MM]` : 등록된 전송 시간을 제거\n"
                "`*운세설정 시간목록` : 등록된 전송 시간 목록 확인\n"
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
                f"- 전송 시간(KST): **{send_time_text}**\n"
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

    @fortune_settings.command(name="시간추가")
    @is_guild_admin()
    async def add_send_time_cmd(self, ctx, time_text: str):
        """운세 전송 시간을 추가 (HH:MM 형식)"""
        time_text = time_text.strip()
        try:
            hour, minute = time_text.split(":")
            hour_int, minute_int = int(hour), int(minute)
            if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
                raise ValueError
            formatted = f"{hour_int:02d}:{minute_int:02d}"
        except ValueError:
            await ctx.reply("시간 형식이 이상하다묘... `HH:MM`(예: 09:30) 형식으로 적어달라묘!")
            return

        times = fortune_db.get_send_times(ctx.guild.id)
        if len(times) >= 5:
            await ctx.reply("전송 시간은 최대 5개까지만 등록할 수 있다묘!")
            return

        success = fortune_db.add_send_time(ctx.guild.id, formatted)
        if success:
            await ctx.reply(f"KST 기준 **{formatted}**에 운세를 보내도록 추가했다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 전송 시간에 {formatted} 을(를) 추가함 [길드: {ctx.guild.name}({ctx.guild.id})]")
        else:
            await ctx.reply(f"**{formatted}**은(는) 이미 등록된 시간이다묘!")

    @fortune_settings.command(name="시간제거")
    @is_guild_admin()
    async def remove_send_time_cmd(self, ctx, time_text: str):
        """등록된 운세 전송 시간을 제거"""
        time_text = time_text.strip()
        try:
            hour, minute = time_text.split(":")
            hour_int, minute_int = int(hour), int(minute)
            if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
                raise ValueError
            formatted = f"{hour_int:02d}:{minute_int:02d}"
        except ValueError:
            await ctx.reply("시간 형식이 이상하다묘... `HH:MM`(예: 09:30) 형식으로 적어달라묘!")
            return

        success = fortune_db.remove_send_time(ctx.guild.id, formatted)
        if success:
            fortune_db.set_last_ping_date(ctx.guild.id, formatted, None)
            await ctx.reply(f"KST 기준 **{formatted}** 전송 설정을 제거했다묘!")
            await self.log(f"{ctx.author}({ctx.author.id})가 운세 전송 시간 {formatted} 을(를) 제거함 [길드: {ctx.guild.name}({ctx.guild.id})]")
        else:
            await ctx.reply(f"**{formatted}**은(는) 등록되지 않은 시간이다묘!")

    @fortune_settings.command(name="시간목록")
    @is_guild_admin()
    async def list_send_time_cmd(self, ctx):
        """등록된 운세 전송 시간 목록 확인"""
        times = fortune_db.get_send_times(ctx.guild.id)
        if not times:
            await ctx.reply("현재 등록된 운세 전송 시간이 없다묘!")
            return
            
        time_list_str = "\n".join([f"- **{t}**" for t in times])
        await ctx.reply(f"현재 등록된 운세 전송 시간 목록이다묘:\n{time_list_str}")

    @fortune_settings.command(name="역할")
    @is_guild_admin()
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

    @fortune_settings.command(name="대상추가")
    @is_guild_admin()
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

    @fortune_settings.command(name="대상삭제")
    @is_guild_admin()
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

    @fortune_settings.command(name="채널")
    @is_guild_admin()
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

    @fortune_settings.command(name="사용초기화")
    @is_guild_admin()
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

    @fortune_settings.command(name="버튼생성")
    @is_guild_admin()
    async def create_btn(self, ctx, days: int):
        """
        운세 사용권을 얻을 수 있는 버튼을 생성합니다.
        사용법: *운세설정 버튼생성 [일수]
        """
        if days < 1:
            await ctx.reply("일수는 최소 1일 이상이어야 한다묘!")
            return

        embed = discord.Embed(
            description=f"˖♡ ⁺   ᘏ ⑅ ᘏ\n˖° ⁺ (  っ• · • )╮=͟͟͞🍀 행운 받아라!",
            color=discord.Color.green()
        )
        
        view = FortuneGrantView(self.bot)
        msg = await ctx.send(embed=embed, view=view)
        
        # DB에 버튼 정보 저장
        fortune_db.create_fortune_button(ctx.guild.id, msg.id, days)
        
        # (옵션) 명령어를 친 메시지는 삭제하거나 반응을 남길 수 있음
        # await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(FortuneConfig(bot))
