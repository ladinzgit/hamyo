"""
생일 관리 Cog
유저의 생일을 등록하고 확인할 수 있는 기능을 제공합니다.
"""

import discord
from discord.ext import commands
from discord import app_commands
from src.core import birthday_db
from datetime import datetime
import calendar

from src.core.admin_utils import GUILD_IDS, only_in_guild



class BirthdayModal(discord.ui.Modal, title="🎂 생일 등록하기"):
    """생일 입력을 위한 모달"""
    
    year_input = discord.ui.TextInput(
        label="태어난 연도 (선택사항)",
        placeholder="예: 1995 (입력하지 않으면 연도 없이 등록됩니다)",
        required=False,
        max_length=4,
        style=discord.TextStyle.short
    )
    
    month_input = discord.ui.TextInput(
        label="태어난 월 (필수)",
        placeholder="예: 3 (1~12 사이의 숫자를 입력하세요)",
        required=True,
        max_length=2,
        style=discord.TextStyle.short
    )
    
    day_input = discord.ui.TextInput(
        label="태어난 일 (필수)",
        placeholder="예: 15 (1~31 사이의 숫자를 입력하세요)",
        required=True,
        max_length=2,
        style=discord.TextStyle.short
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        """모달 제출 시 실행"""
        try:
            # 기존 데이터 확인 (수정 횟수 체크)
            existing_data = await birthday_db.get_birthday(str(interaction.user.id))
            if existing_data and existing_data["edit_count"] >= 2:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                        description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}은 이미 2번 수정했다묘...!
(⠀⠀⠀⠀ 더 이상 수정할 수 없다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                        colour=discord.Colour.from_rgb(151, 214, 181)
                    ),
                    ephemeral=True
                )
                return
            
            # 입력값 검증
            year = None
            if self.year_input.value.strip():
                year = int(self.year_input.value.strip())
                current_year = datetime.now().year
                
                # 세는나이 계산: (현재 연도) - (출생연도) + 1
                korean_age = current_year - year + 1
                
                # 1900년 미만 또는 세는나이 13살 미만 체크
                if year < 1900:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 연도는 1900년 이후여야 한다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                            colour=discord.Colour.from_rgb(151, 214, 181)
                        ),
                        ephemeral=True
                    )
                    return
                
                if year > current_year:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 미래에서 왔냐묘...?!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                            colour=discord.Colour.from_rgb(151, 214, 181)
                        ),
                        ephemeral=True
                    )
                    return                
                
                if korean_age < 13:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                            description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 너무 어리다묘...!
(⠀⠀⠀⠀ 세는나이 13살 미만은 등록할 수 없다묘...!
(⠀⠀⠀⠀ (현재 세는나이: {korean_age}살)
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                            colour=discord.Colour.from_rgb(151, 214, 181)
                        ),
                        ephemeral=True
                    )
                    return
                
            
            month = int(self.month_input.value.strip())
            day = int(self.day_input.value.strip())
            
            # 월 검증
            if month < 1 or month > 12:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                        description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 월은 1월부터 12월 까지만 있다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                        colour=discord.Colour.from_rgb(151, 214, 181)
                    ),
                    ephemeral=True
                )
                return
            
            # 일 검증 (해당 월의 마지막 날짜 확인)
            max_day = calendar.monthrange(year if year else 2024, month)[1]
            if day < 1 or day > max_day:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                        description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ {month}월은 1일부터 {max_day}일까지다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                        colour=discord.Colour.from_rgb(151, 214, 181)
                    ),
                    ephemeral=True
                )
                return
            
            # DB에 등록
            success = await birthday_db.register_birthday(str(interaction.user.id), year, month, day)
            
            if success:
                # 등록 후 데이터 다시 조회 (수정 횟수 확인)
                updated_data = await birthday_db.get_birthday(str(interaction.user.id))
                edit_count = updated_data["edit_count"] if updated_data else 1
                remaining_edits = 2 - edit_count
                
                # 나이 계산 (연도가 있는 경우만)
                age_text = ""
                if year:
                    current_date = datetime.now()
                    age = current_date.year - year
                    if current_date.month < month or (current_date.month == month and current_date.day < day):
                        age -= 1
                    age_text = f"\n(⠀⠀⠀⠀ 현재 **{age}살**이다묘...✨"
                else:
                    age_text = "\n(⠀⠀⠀⠀ 연도를 입력하지 않아서 나이 관련 서비스는 못 받는다묘..."
                
                birthday_str = f"{year}년 " if year else ""
                birthday_str += f"{month}월 {day}일"
                
                remaining_text = f"\n(⠀⠀⠀⠀ 앞으로 **{remaining_edits}번** 더 수정할 수 있다묘...!" if remaining_edits > 0 else "\n(⠀⠀⠀⠀ 더 이상 수정할 수 없다묘...!"
                
                embed = discord.Embed(
                    title="🎂 생일 등록 완료 ₍ᐢ..ᐢ₎",
                    description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {interaction.user.mention}의 생일을 등록했다묘...✩
(⠀⠀⠀⠀ 생일: **{birthday_str}**{age_text}{remaining_text}
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                    colour=discord.Colour.from_rgb(151, 214, 181)
                )
                embed.set_footer(
                    text=f"등록자: {interaction.user}",
                    icon_url=interaction.user.display_avatar.url
                )
                embed.timestamp = interaction.created_at
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
                # 로그
                logger = self.bot.get_cog('Logger')
                if logger:
                    await logger.log(f"{interaction.user}({interaction.user.id})이 생일을 등록함: {birthday_str} (수정 {edit_count}/2회)", title="🎂 생일 시스템 로그", color=discord.Color.purple())
            else:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                        description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                        colour=discord.Colour.from_rgb(151, 214, 181)
                    ),
                    ephemeral=True
                )
        
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                    description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {interaction.user.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 숫자만 입력하라묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                    colour=discord.Colour.from_rgb(151, 214, 181)
                ),
                ephemeral=True
            )
    
    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="🎂 생일 시스템 로그", color=discord.Color.purple())
        except Exception as e:
            print(f"❌ BirthdayModal 로그 전송 중 오류 발생: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """모달 오류 처리"""
        # 사용자에게는 일반적인 오류 메시지만 표시
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎂 생일 등록 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            ),
            ephemeral=True
        )
        
        # 상세 오류는 로그로만 전송
        await self.log(
            f"생일 등록 모달 오류 발생 - 유저: {interaction.user}({interaction.user.id}), "
            f"오류: {type(error).__name__}: {str(error)} "
            f"[길드: {interaction.guild.name if interaction.guild else 'DM'}({interaction.guild.id if interaction.guild else 'N/A'}), "
            f"채널: {interaction.channel.name if hasattr(interaction.channel, 'name') else 'DM'}({interaction.channel.id if interaction.channel else 'N/A'})]"
        )


class BirthdayButtonView(discord.ui.View):
    """생일 등록/확인/삭제 버튼 뷰"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)  # 영구 지속
        self.bot = bot
    
    @discord.ui.button(label="🎂 생일 등록", style=discord.ButtonStyle.primary, custom_id="birthday_register")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """생일 등록 버튼"""
        modal = BirthdayModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔍 생일 확인", style=discord.ButtonStyle.secondary, custom_id="birthday_check")
    async def check_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """생일 확인 버튼"""
        birthday_data = await birthday_db.get_birthday(str(interaction.user.id))
        
        if birthday_data:
            year = birthday_data["year"]
            month = birthday_data["month"]
            day = birthday_data["day"]
            edit_count = birthday_data["edit_count"]
            remaining_edits = 2 - edit_count
            
            # 나이 계산 (연도가 있는 경우만)
            age_text = ""
            if year:
                current_date = datetime.now()
                age = current_date.year - year
                if current_date.month < month or (current_date.month == month and current_date.day < day):
                    age -= 1
                age_text = f"\n(⠀⠀⠀⠀ 현재 **{age}살**이다묘...✨"
            else:
                age_text = "\n(⠀⠀⠀⠀ 연도를 입력하지 않아서 나이 관련 서비스는 못 받는다묘..."
            
            birthday_str = f"{year}년 " if year else ""
            birthday_str += f"{month}월 {day}일"
            
            remaining_text = f"\n(⠀⠀⠀⠀ 앞으로 **{remaining_edits}번** 더 수정할 수 있다묘...!" if remaining_edits > 0 else "\n(⠀⠀⠀⠀ 더 이상 수정할 수 없다묘...!"
            
            # 등록일 표시
            registered_at = birthday_data["registered_at"]
            updated_at = birthday_data["updated_at"]
            
            embed = discord.Embed(
                title="🎂 생일 확인 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {interaction.user.mention}의 생일 정보다묘...✩
(⠀⠀⠀⠀ 생일: **{birthday_str}**{age_text}{remaining_text}
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.add_field(name="📅 최초 등록일", value=f"<t:{int(datetime.fromisoformat(registered_at).timestamp())}:F>", inline=False)
            if registered_at != updated_at:
                embed.add_field(name="🔄 마지막 수정일", value=f"<t:{int(datetime.fromisoformat(updated_at).timestamp())}:F>", inline=False)
            
            embed.set_footer(
                text=f"요청자: {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = interaction.created_at
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🎂 생일 확인 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {interaction.user.mention}은 생일을 등록하지 않았다묘...
(⠀⠀⠀⠀ 등록 버튼을 눌러서 등록하라묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_footer(
                text=f"요청자: {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = interaction.created_at
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🗑️ 생일 삭제", style=discord.ButtonStyle.danger, custom_id="birthday_delete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """생일 삭제 버튼"""
        birthday_data = await birthday_db.get_birthday(str(interaction.user.id))
        
        if not birthday_data:
            embed = discord.Embed(
                title="🎂 생일 삭제 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {interaction.user.mention}은 생일을 등록하지 않았다묘...
(⠀⠀⠀⠀ 삭제할 생일이 없다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_footer(
                text=f"요청자: {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = interaction.created_at
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        success = await birthday_db.delete_birthday(str(interaction.user.id))
        
        if success:
            # 현재 수정 횟수 조회 (삭제 후에도 유지됨)
            edit_count = await birthday_db.get_user_edit_count(str(interaction.user.id))
            remaining_edits = 2 - edit_count
            
            remaining_text = ""
            if remaining_edits > 0:
                remaining_text = f"\n(⠀⠀⠀⠀ 수정 횟수는 유지되어 앞으로 **{remaining_edits}번** 더 수정 가능하다묘!"
            else:
                remaining_text = "\n(⠀⠀⠀⠀ 수정 횟수가 2번 모두 소진되어 더 이상 등록할 수 없다묘...!"
            
            embed = discord.Embed(
                title="🎂 생일 삭제 완료 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {interaction.user.mention}의 생일 정보를 삭제했다묘...{remaining_text}
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_footer(
                text=f"요청자: {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = interaction.created_at
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # 로그
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(f"{interaction.user}({interaction.user.id})이 생일 정보를 삭제함.", title="🎂 생일 시스템 로그", color=discord.Color.purple())
        else:
            embed = discord.Embed(
                title="🎂 생일 삭제 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_footer(
                text=f"요청자: {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.timestamp = interaction.created_at
            
            await interaction.response.send_message(embed=embed, ephemeral=True)


class Birthday(commands.Cog):
    """생일 관리 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        """Cog 로드 시 실행"""
        await birthday_db.init_db()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
    
    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="🎂 생일 시스템 로그", color=discord.Color.purple())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
    
    @commands.group(name="생일", invoke_without_command=True)
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def birthday(self, ctx):
        """생일 관련 명령어 그룹"""
        embed = discord.Embed(
            title="🎂 생일 명령어 도움말 ₍ᐢ..ᐢ₎",
            description="""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 생일 관련 명령어를 알려주겠다묘...✩
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.add_field(
            name="관리자 전용 명령어",
            value=(
                "`*생일 버튼` : 생일 등록/확인/삭제 버튼이 있는 메시지를 전송합니다.\n"
                "`*생일 확인 @유저` : 특정 유저의 생일을 조회합니다.\n"
                "`*생일 삭제 @유저` : 특정 유저의 생일을 삭제합니다. (수정 횟수는 유지)\n"
                "`*생일 관리자변경 @유저 월 일 [연도]` : 특정 유저의 생일을 변경합니다.\n"
                "`*생일 수정횟수초기화 @유저` : 특정 유저의 수정 횟수를 초기화합니다.\n"
                "`*생일 목록` : 등록된 모든 생일 목록을 월/일 순으로 조회합니다.\n"
            ),
            inline=False
        )
        embed.set_footer(
            text=f"요청자: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        embed.timestamp = ctx.message.created_at
        
        await ctx.reply(embed=embed)
    
    @birthday.command(name="버튼")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def send_button(self, ctx):
        """생일 등록/확인 버튼 메시지 전송 (관리자 전용)"""
        embed = discord.Embed(
            title="🎂 생일 등록 시스템 ₍ᐢ..ᐢ₎",
            description="""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 아래 버튼을 눌러서 생일을 등록하거나
(⠀⠀⠀⠀ 확인하거나 삭제할 수 있다묘...✩
(⠀⠀⠀⠀ 
(⠀ 🎂 **생일 등록**: 생일을 등록한다묘!
(⠀ 🔍 **생일 확인**: 등록된 생일을 확인한다묘!
(⠀ 🗑️ **생일 삭제**: 등록된 생일을 삭제한다묘!
(⠀⠀⠀⠀ 
(⠀ ⚠️ **주의사항**:
(⠀⠀⠀ • 생일 등록/수정은 **총 2회**로 제한된다묘...!
(⠀⠀⠀ • 생일을 삭제해도 수정 횟수는 유지된다묘...!
(⠀⠀⠀ • 연도를 입력하지 않으면 나이 관련 서비스를 못 받는다묘...
(⠀⠀⠀ • 월과 일은 필수로 입력해야 한다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
            colour=discord.Colour.from_rgb(151, 214, 181)
        )
        embed.set_footer(
            text="생일을 등록하고 특별한 혜택을 받으라묘! 🎉"
        )
        
        view = BirthdayButtonView(self.bot)
        await ctx.send(embed=embed, view=view)
        await ctx.message.delete()  # 명령어 메시지 삭제
        
        await self.log(f"{ctx.author}({ctx.author.id})이 생일 버튼 메시지를 전송함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")
    
    @birthday.command(name="확인")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def check_birthday(self, ctx, member: discord.Member):
        """관리자가 특정 유저의 생일 확인 (관리자 전용)"""
        birthday_data = await birthday_db.get_birthday(str(member.id))
        
        if birthday_data:
            year = birthday_data["year"]
            month = birthday_data["month"]
            day = birthday_data["day"]
            
            # 나이 계산 (연도가 있는 경우만)
            age_text = ""
            if year:
                current_date = datetime.now()
                age = current_date.year - year
                if current_date.month < month or (current_date.month == month and current_date.day < day):
                    age -= 1
                age_text = f"\n(⠀⠀⠀⠀ 현재 **{age}살**이다묘...✨"
            else:
                age_text = "\n(⠀⠀⠀⠀ 연도를 입력하지 않아서 나이 관련 서비스는 못 받는다묘..."
            
            birthday_str = f"{year}년 " if year else ""
            birthday_str += f"{month}월 {day}일"
            
            embed = discord.Embed(
                title="🎂 생일 확인 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}의 생일 정보다묘...✩
(⠀⠀⠀⠀ 생일: **{birthday_str}**{age_text}
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯
""",
                colour=discord.Colour.from_rgb(151, 214, 181)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(
                text=f"요청자: {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )
            embed.timestamp = ctx.message.created_at
            
            await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(
                title="🎂 생일 확인 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}은 생일을 등록하지 않았다묘...
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
        
        await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})의 생일을 조회함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")
    
    @birthday.command(name="삭제")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def delete_birthday(self, ctx, member: discord.Member):
        """관리자가 특정 유저의 생일 정보 삭제 (관리자 전용)"""
        birthday_data = await birthday_db.get_birthday(str(member.id))
        
        if not birthday_data:
            embed = discord.Embed(
                title="🎂 생일 삭제 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}은 생일을 등록하지 않았다묘...
(⠀⠀⠀⠀ 삭제할 생일이 없다묘...!
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
        
        success = await birthday_db.delete_birthday(str(member.id))
        
        if success:
            # 현재 수정 횟수 조회 (삭제 후에도 유지됨)
            edit_count = await birthday_db.get_user_edit_count(str(member.id))
            remaining_edits = 2 - edit_count
            
            remaining_text = ""
            if remaining_edits > 0:
                remaining_text = f"\n(⠀⠀⠀⠀ 수정 횟수는 유지되어 앞으로 **{remaining_edits}번** 더 수정 가능하다묘!"
            else:
                remaining_text = "\n(⠀⠀⠀⠀ 수정 횟수가 2번 모두 소진되어 더 이상 등록할 수 없다묘...!"
            
            embed = discord.Embed(
                title="🎂 생일 삭제 완료 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}의 생일 정보를 삭제했다묘...{remaining_text}
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
            await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})의 생일 정보를 관리자 권한으로 삭제함.")
        else:
            embed = discord.Embed(
                title="🎂 생일 삭제 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
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
    
    @birthday.command(name="관리자변경")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def admin_change_birthday(self, ctx, member: discord.Member, month: int, day: int, year: int = None):
        """관리자가 특정 유저의 생일을 변경 (관리자 전용)
        
        사용법:
        *생일 관리자변경 @유저 월 일 [연도]
        예시: *생일 관리자변경 @유저 3 15 (연도 없이)
        예시: *생일 관리자변경 @유저 3 15 1995 (연도 포함)
        """
        # 월 검증
        if month < 1 or month > 12:
            embed = discord.Embed(
                title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 월은 1월부터 12월 까지만 있다묘...!
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
        
        # 일 검증 (해당 월의 마지막 날짜 확인)
        max_day = calendar.monthrange(year if year else 2024, month)[1]
        if day < 1 or day > max_day:
            embed = discord.Embed(
                title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ {month}월은 1일부터 {max_day}일까지다묘...!
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
        
        # 연도 검증
        if year is not None:
            current_year = datetime.now().year
            if year < 1900:
                embed = discord.Embed(
                    title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                    description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 연도는 1900년 이후여야 한다묘...!
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
            
            # 세는나이 계산
            korean_age = current_year - year + 1
            if korean_age < 13:
                embed = discord.Embed(
                    title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                    description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {member.mention}은 너무 어리다묘...!
(⠀⠀⠀⠀ 세는나이 13살 미만은 등록할 수 없다묘...!
(⠀⠀⠀⠀ (현재 세는나이: {korean_age}살)
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
            
            if year > current_year:
                embed = discord.Embed(
                    title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                    description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀ {ctx.author.mention}는 바보냐묘..!!!
(⠀⠀⠀⠀ 미래에서 왔냐묘...?!
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
        
        # DB에 강제 업데이트
        success = await birthday_db.admin_update_birthday(str(member.id), year, month, day)
        
        if success:
            # 나이 계산 (연도가 있는 경우만)
            age_text = ""
            if year:
                current_date = datetime.now()
                age = current_date.year - year
                if current_date.month < month or (current_date.month == month and current_date.day < day):
                    age -= 1
                age_text = f"\n(⠀⠀⠀⠀ 현재 **{age}살**이다묘...✨"
            else:
                age_text = "\n(⠀⠀⠀⠀ 연도를 입력하지 않아서 나이 관련 서비스는 못 받는다묘..."
            
            birthday_str = f"{year}년 " if year else ""
            birthday_str += f"{month}월 {day}일"
            
            embed = discord.Embed(
                title="🎂 생일 변경 완료 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}의 생일을 변경했다묘...✩
(⠀⠀⠀⠀ 생일: **{birthday_str}**{age_text}
(⠀⠀⠀⠀ 관리자가 변경해서 수정 횟수는 그대로다묘...!
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
            await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})의 생일을 {birthday_str}로 관리자 변경함. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")
        else:
            embed = discord.Embed(
                title="🎂 생일 변경 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
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
    
    @birthday.command(name="수정횟수초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_edit_count(self, ctx, member: discord.Member):
        """관리자가 특정 유저의 수정 횟수 초기화 (관리자 전용)"""
        # 현재 수정 횟수 확인
        current_count = await birthday_db.get_user_edit_count(str(member.id))
        
        if current_count == 0:
            embed = discord.Embed(
                title="🎂 수정 횟수 초기화 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}의 수정 횟수는 이미 0이다묘...
(⠀⠀⠀⠀ 초기화할 필요가 없다묘...!
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
        
        success = await birthday_db.reset_edit_count(str(member.id))
        
        if success:
            embed = discord.Embed(
                title="🎂 수정 횟수 초기화 완료 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ {member.mention}의 수정 횟수를 초기화했다묘...
(⠀⠀⠀⠀ 이전 수정 횟수: **{current_count}회**
(⠀⠀⠀⠀ 이제 다시 **2번** 수정할 수 있다묘...!
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
            await self.log(f"{ctx.author}({ctx.author.id})이 {member}({member.id})의 수정 횟수를 초기화함. (이전: {current_count}회)")
        else:
            embed = discord.Embed(
                title="🎂 수정 횟수 초기화 실패 ₍ᐢ..ᐢ₎",
                description=f"""
⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀`ㅅ´ )
(⠀⠀ 엥... 뭔가 이상하다묘..??
(⠀⠀⠀⠀ 어디선가 오류가 났다묘.....
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
    
    @birthday.command(name="목록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def list_birthdays(self, ctx):
        """등록된 모든 생일 목록 조회 (관리자 전용)"""
        all_birthdays = await birthday_db.get_all_birthdays()
        
        if not all_birthdays:
            message = """⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎
╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮
(⠀⠀⠀´ㅅ` )
(⠀ 아직 등록된 생일이 없다묘...
(⠀⠀⠀⠀ 유저들이 생일을 등록하면 여기에 나타난다묘...!
╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯"""
            await ctx.reply(message)
            return
        
        # 월/일 순으로 정렬
        sorted_birthdays = sorted(all_birthdays, key=lambda x: (x["month"], x["day"]))
        
        # 메시지 헤더
        message_lines = [
            "⠀.⠀♡ 묘묘묘... ‧₊˚ ⯎",
            "╭◜ᘏ ⑅ ᘏ◝  ͡  ◜◝  ͡  ◜◝╮",
            "(⠀⠀⠀´ㅅ` )",
            f"(⠀ 현재 등록된 생일 목록이다묘...✩",
            f"(⠀⠀⠀⠀ 총 **{len(sorted_birthdays)}명**이 등록했다묘!",
            "╰◟◞  ͜   ◟◞  ͜  ◟◞  ͜  ◟◞╯",
            ""
        ]
        
        # 생일 정보 추가
        for birthday_data in sorted_birthdays:
            user_id = birthday_data["user_id"]
            year = birthday_data["year"]
            month = birthday_data["month"]
            day = birthday_data["day"]
            
            # 유저 정보 가져오기
            try:
                member = await ctx.guild.fetch_member(int(user_id))
                user_name = f"{member.display_name} ({member.name})"
            except:
                user_name = f"Unknown User (ID: {user_id})"
            
            # 나이 계산 (연도가 있는 경우만)
            age_text = ""
            if year:
                current_date = datetime.now()
                age = current_date.year - year
                if current_date.month < month or (current_date.month == month and current_date.day < day):
                    age -= 1
                age_text = f" ({age}살)"
            
            birthday_str = f"{year}년 " if year else ""
            birthday_str += f"{month}월 {day}일"
            
            message_lines.append(f"🎂 **{birthday_str}** - {user_name}{age_text}")
        
        # 메시지 전송 (Discord 메시지 길이 제한: 2000자)
        message = "\n".join(message_lines)
        
        # 메시지가 너무 길면 분할 전송
        if len(message) > 2000:
            chunks = []
            current_chunk = message_lines[0:7]  # 헤더 포함
            
            for line in message_lines[7:]:
                test_chunk = "\n".join(current_chunk + [line])
                if len(test_chunk) > 1900:  # 여유 공간 확보
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                else:
                    current_chunk.append(line)
            
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            
            # 첫 번째 청크는 reply, 나머지는 일반 메시지
            await ctx.reply(chunks[0])
            for chunk in chunks[1:]:
                await ctx.send(chunk)
        else:
            await ctx.reply(message)
        
        await self.log(f"{ctx.author}({ctx.author.id})이 생일 목록을 조회함. (총 {len(sorted_birthdays)}명) [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")


async def setup(bot):
    """Cog 설정"""
    await bot.add_cog(Birthday(bot))
    bot.add_view(BirthdayButtonView(bot))
