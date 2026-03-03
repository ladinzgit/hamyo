"""
생일 표시 인터페이스 Cog
특정 채널에 생일 정보를 임베드로 표시하고 매일 자정마다 자동 업데이트합니다.
"""

import discord
from discord.ext import commands, tasks
from src.core import birthday_db
from src.core import fortune_db
from datetime import datetime, timedelta
import json
from pathlib import Path
import pytz
from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin

CONFIG_PATH = Path("config/birthday_config.json")
KST = pytz.timezone("Asia/Seoul")


def load_config() -> dict:
    """설정 파일 로드"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """설정 파일 저장"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class BirthdayInterface(commands.Cog):
    """생일 표시 인터페이스 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        pass

    def cog_unload(self):
        """Cog 언로드 시 태스크 종료"""
        pass
    
    async def cog_load(self):
        """Cog 로드 시 실행"""
        # JSON 파일이 없으면 생성
        if not CONFIG_PATH.exists():
            save_config({})
            print(f"✅ Birthday Interface config initialized at {CONFIG_PATH}")
        print(f"✅ {self.__class__.__name__} loaded successfully!")

        # 스케줄러 cog 가져오기
        scheduler = self.bot.get_cog("Scheduler")
        if scheduler:
            scheduler.schedule_daily(self.midnight_update, 0, 0)
        else:
            print("⚠️ Scheduler cog not found! BirthdayInterface task validation failed.")
    
    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="🎂 생일 시스템 로그", color=discord.Color.purple())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
    
    def get_channel_config(self, guild_id: int):
        """특정 길드의 생일 채널 설정 조회"""
        config = load_config()
        guild_key = str(guild_id)
        
        if guild_key in config:
            return config[guild_key]
        return None
    
    def set_channel_config(self, guild_id: int, channel_id: int, message_id: int = None):
        """생일 채널 설정 저장"""
        config = load_config()
        guild_key = str(guild_id)
        
        if guild_key not in config:
            config[guild_key] = {}
        
        config[guild_key]["guild_id"] = guild_id
        config[guild_key]["channel_id"] = channel_id
        config[guild_key]["message_id"] = message_id
        config[guild_key]["last_updated"] = datetime.now(KST).isoformat()
        
        save_config(config)
    
    async def clean_invalid_users(self, guild: discord.Guild):
        """서버에 없는 유저의 생일 정보 삭제"""
        all_birthdays = await birthday_db.get_all_birthdays()
        member_ids = {str(member.id) for member in guild.members}
        
        deleted_users = []
        for birthday in all_birthdays:
            if birthday["user_id"] not in member_ids:
                await birthday_db.delete_birthday(birthday["user_id"])
                deleted_users.append({
                    "user_id": birthday["user_id"],
                    "month": birthday["month"],
                    "day": birthday["day"]
                })
        
        return deleted_users
    
    def calculate_days_until(self, month: int, day: int) -> int:
        """다음 생일까지 남은 일수 계산"""
        now = datetime.now(KST)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        current_year = today.year
        
        # 올해 생일
        birthday_this_year = KST.localize(datetime(current_year, month, day))
        
        # 생일이 이미 지났으면 내년 생일로 계산
        if birthday_this_year < today:
            birthday_next = KST.localize(datetime(current_year + 1, month, day))
        else:
            birthday_next = birthday_this_year
        
        delta = birthday_next - today
        return delta.days
    
    async def create_birthday_message(self, guild: discord.Guild) -> str:
        """생일 정보 메시지 생성 (Markdown 형식)"""
        now = datetime.now(KST)
        today_month = now.month
        today_day = now.day
        
        # 모든 생일 정보 조회
        all_birthdays = await birthday_db.get_all_birthdays()
        
        # 서버 멤버만 필터링
        member_ids = {str(member.id) for member in guild.members}
        valid_birthdays = [b for b in all_birthdays if b["user_id"] in member_ids]
        
        # 오늘 생일인 사람들
        today_birthdays = [b for b in valid_birthdays if b["month"] == today_month and b["day"] == today_day]
        
        # 가장 가까운 생일과 D-Day 계산 (같은 D-Day면 모두 포함)
        min_days = float('inf')
        for birthday in valid_birthdays:
            days = self.calculate_days_until(birthday["month"], birthday["day"])
            if 0 < days < min_days:  # 오늘은 제외
                min_days = days

        closest_birthdays = []
        if min_days != float('inf'):
            for birthday in valid_birthdays:
                days = self.calculate_days_until(birthday["month"], birthday["day"])
                if days == min_days and days > 0:
                    closest_birthdays.append(birthday)
        
        # 마지막으로 지나간 생일 (가장 최근에 생일이 지난 사람) - 같은 날짜면 모두 포함
        min_days_passed = float('inf')
        for birthday in valid_birthdays:
            days_until = self.calculate_days_until(birthday["month"], birthday["day"])
            # days_until이 0이면 오늘 생일이므로 제외
            if days_until == 0:
                continue

            # 지나간 생일까지의 일수 계산 (365 - days_until)
            # 예: 내일이 생일이면 days_until=1, 지나간 지 364일
            # 어제가 생일이었으면 days_until=364, 지나간 지 1일
            days_passed = 365 - days_until

            if days_passed < min_days_passed:
                min_days_passed = days_passed

        last_birthdays = []
        if min_days_passed != float('inf'):
            for birthday in valid_birthdays:
                days_until = self.calculate_days_until(birthday["month"], birthday["day"])
                if days_until == 0:
                    continue
                days_passed = 365 - days_until
                if days_passed == min_days_passed:
                    last_birthdays.append(birthday)
        
        # 이번 달 생일 리스트
        this_month_birthdays = sorted(
            [b for b in valid_birthdays if b["month"] == today_month],
            key=lambda x: x["day"]
        )
        
        # 메시지 생성 (Markdown 형식)
        message_parts = []
        
        # 1. 제목 (큰 글씨)
        message_parts.append("（ <:BM_a_000:1477525641623502950> ）₊ **생일 달력**")

        # 오늘의 날짜
        message_parts.append(f"-# <:BM_inv:1384475516152582144> ୨ {now.year} . {now.month} . {now.day} ୧")
        message_parts.append("⠀\n")
        
        # 2. 오늘 생일 (있을 경우에만 표시)
        if today_birthdays:
            message_parts.append("## <a:slg03:1378567322985304184> 오늘 생일이다묘 .ᐟ")
            message_parts.append(f"> -# <:BM_inv:1384475516152582144> **{today_month}월 {today_day}일**")
            for b in today_birthdays:
                member = guild.get_member(int(b["user_id"]))
                if member:
                    message_parts.append(f"> <a:BM_gliter_005:1377697008344891572> {member.mention} <a:BM_gliter_005:1377697008344891572>")
            message_parts.append("\n")
            
            # 3. 구분선 (오늘 생일이 있을 경우에만)
            message_parts.append("𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃\n")
        
        # 4. 다가오는 생일
        message_parts.append("## <a:slg13:1378567371324653618> 다가오는 생일이다묘 .ᐟ")
        if closest_birthdays:
            # 같은 D-Day인 모든 생일 날짜(같은 날짜일 것) 표시 후 멘션들 나열
            cb = closest_birthdays[0]
            message_parts.append(f"> -# <:BM_inv:1384475516152582144> **{cb['month']}월 {cb['day']}일** (D-{min_days})")
            for b in closest_birthdays:
                member = guild.get_member(int(b["user_id"]))
                if member:
                    message_parts.append(f"> <a:BM_gliter_005:1377697008344891572> {member.mention} <a:BM_gliter_005:1377697008344891572>")
            message_parts.append("\n")
        else:
            message_parts.append("> 아직 예정된 생일이 없다묘...\n")
        
        # 5. 이번 달 생일 리스트
        message_parts.append(f"## <a:slg13:1378567371324653618> {today_month}월의 생일이다묘 .ᐟ")
        if this_month_birthdays:
            month_list = []
            last_day = 0
            for birthday in this_month_birthdays:
                member = guild.get_member(int(birthday["user_id"]))

                if member:
                    if birthday['day'] != last_day: # 중복일 경우 날짜는 한 번만 표시
                        is_today = "🍰" if birthday["day"] == today_day else "<:BM_inv:1384475516152582144>"
                        message_parts.append(f"> -# {is_today} **{birthday['month']}월 {birthday['day']}일** {is_today}")
                        last_day = birthday['day']
                    
                    month_list.append(f"> <a:BM_gliter_005:1377697008344891572> {member.mention} <a:BM_gliter_005:1377697008344891572>")
            
                if month_list:
                    message_parts.append("\n".join(month_list))
                    month_list = []
                else:
                    message_parts.append("> 이번 달 생일이 없다묘...\n")
        else:
            message_parts.append("> 이번 달 생일이 없다묘...\n")
        
        # 푸터
        message_parts.append("\n-# <a:BM_m_001:1477540758755086488> 매일 자정에 자동으로 업데이트 된다묘 .ᐟ.ᐟ <a:BM_m_002:1477540760386539612>")
        
        return "\n".join(message_parts)
    
    async def update_birthday_message(self, guild: discord.Guild):
        """생일 메시지 업데이트"""
        config = self.get_channel_config(guild.id)
        if not config:
            return
        
        channel = guild.get_channel(config["channel_id"])
        if not channel:
            await self.log(f"생일 채널을 찾을 수 없음 [길드: {guild.name}({guild.id}), 채널 ID: {config['channel_id']}]")
            return
        
        # 서버에 없는 유저 정리
        deleted_users = await self.clean_invalid_users(guild)
        
        # 메시지 생성
        message_content = await self.create_birthday_message(guild)
        
        try:
            message = None      # 메시지 객체
            resend = False      # 새롭게 전송 여부
            
            # 기존 메시지가 있는 경우 수정
            if config.get("message_id"):
                try:
                    message = await channel.fetch_message(config["message_id"])
                    await message.edit(content=message_content)
                except discord.NotFound:
                    # 메시지가 삭제된 경우, 새로 전송
                    resend = True
                except Exception as e:
                    # 그 외 오류 (권한 문제 등), 로그 남기고 새로 전송
                    await self.log(f"메시지 수정 실패 ({e}), 새로 전송 [길드: {guild.name}({guild.id})]")
                    resend = True
            else:
                resend = True
            
            # 메시지를 새로 보내야 하는 경우 (신규, 수정실패, 삭제)
            if resend:
                # 기존 메시지 ID가 있다면 삭제 시도
                if config.get("message_id"):
                    try:
                        old_msg = await channel.fetch_message(config["message_id"])
                        await old_msg.delete()
                    except:
                        pass

                message = await channel.send(message_content)
                self.set_channel_config(guild.id, channel.id, message.id)
            
            # 로그 메시지 생성
            log_msg = f"생일 메시지 갱신 완료 [길드: {guild.name}({guild.id}), 채널: {channel.name}({channel.id})]"
            
            # 삭제된 유저 정보 추가
            if deleted_users:
                deleted_info = ", ".join([f"{u['user_id']}({u['month']}/{u['day']})" for u in deleted_users])
                log_msg += f" | 서버를 떠난 {len(deleted_users)}명의 생일 정보 삭제: {deleted_info}"
            
            await self.log(log_msg)
        
        except Exception as e:
            await self.log(f"생일 메시지 갱신 실패: {e} [길드: {guild.name}({guild.id})]")
    
    async def midnight_update(self):
        """매일 자정에 모든 길드의 생일 메시지 업데이트"""
        # 스케줄러에 의해 호출됨
        for guild_id in GUILD_IDS:
            guild = self.bot.get_guild(guild_id)
            if guild:
                await self.update_birthday_message(guild)
    
    @commands.group(name="생일설정", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def birthday_setup(self, ctx):
        """생일 표시 설정 명령어 그룹"""
        embed = discord.Embed(
            title="🎂 생일 표시 설정 도움말 ₍ᐢ..ᐢ₎",
            description="""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 생일 표시 관련 명령어를 알려주겠다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.add_field(
            name="관리자 전용 명령어",
            value=(
                "`*생일설정 채널등록 [채널]` : 생일 표시 채널을 설정합니다. (채널 미입력 시 현재 채널)\n"
                "`*생일설정 강제갱신` : 서버 멤버 검증 및 생일 메시지를 강제로 갱신합니다.\n"
            ),
            inline=False
        )
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
    
    @birthday_setup.command(name="채널등록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def register_channel(self, ctx, channel: discord.TextChannel = None):
        """생일 표시 채널 등록"""
        target_channel = channel or ctx.channel
        
        # 기존 메시지 확인 및 삭제
        config = self.get_channel_config(ctx.guild.id)
        if config and config.get("message_id"):
            try:
                old_channel = ctx.guild.get_channel(config["channel_id"])
                if old_channel:
                    old_message = await old_channel.fetch_message(config["message_id"])
                    await old_message.delete()
            except:
                pass
        
        # 새 채널 설정
        self.set_channel_config(ctx.guild.id, target_channel.id)
        
        # 서버에 없는 유저 정리
        deleted_users = await self.clean_invalid_users(ctx.guild)
        
        # 생일 메시지 생성
        message_content = await self.create_birthday_message(ctx.guild)
        message = await target_channel.send(message_content)
        self.set_channel_config(ctx.guild.id, target_channel.id, message.id)
        
        embed = discord.Embed(
            title="🎂 생일 채널 등록 완료 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {target_channel.mention}에 생일 메시지를 띄웠다묘...✩
(⠀⠀⠀⠀ 매일 자정마다 자동으로 업데이트된다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        
        # 로그 메시지 생성
        log_msg = f"{ctx.author}({ctx.author.id})이 생일 채널을 {target_channel.name}({target_channel.id})로 등록함. [길드: {ctx.guild.name}({ctx.guild.id})]]"
        if deleted_users:
            deleted_info = ", ".join([f"{u['user_id']}({u['month']}/{u['day']})" for u in deleted_users])
            log_msg += f" | 서버를 떠난 {len(deleted_users)}명의 생일 정보 삭제: {deleted_info}"
        
        await self.log(log_msg)
    
    @birthday_setup.command(name="강제갱신")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def force_refresh(self, ctx):
        """서버 멤버 검증 및 생일 메시지 강제 갱신"""
        config = self.get_channel_config(ctx.guild.id)
        if not config:
            embed = discord.Embed(
                title="🎂 강제갱신 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ 생일 채널이 등록되지 않았다묘...!
(⠀⠀⠀⠀ `*생일설정 채널등록`으로 먼저 등록하라묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_footer(
                text=f"요청자: {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
            return
        
        # 서버에 없는 유저 정리
        deleted_users = await self.clean_invalid_users(ctx.guild)
        
        # 생일 메시지 업데이트
        await self.update_birthday_message(ctx.guild)
        
        deleted_text = ""
        if deleted_users:
            deleted_text = f"\n(⠀⠀⠀⠀ 서버를 떠난 {len(deleted_users)}명의 생일 정보를 삭제했다묘...!"
        
        embed = discord.Embed(
            title="🎂 강제갱신 완료 ₍ᐢ..ᐢ₎",
            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 서버 멤버 검증을 완료했다묘...✩
(⠀⠀⠀⠀ 생일 메시지도 갱신했다묘...!{deleted_text}
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
        
        # 로그 메시지 생성
        log_msg = f"{ctx.author}({ctx.author.id})이 생일 메시지를 강제갱신함. [길드: {ctx.guild.name}({ctx.guild.id})]]"
        if deleted_users:
            deleted_info = ", ".join([f"{u['user_id']}({u['month']}/{u['day']})" for u in deleted_users])
            log_msg += f" | 삭제된 유저 {len(deleted_users)}명: {deleted_info}"
        
        await self.log(log_msg)


async def setup(bot):
    """Cog 설정"""
    await bot.add_cog(BirthdayInterface(bot))
