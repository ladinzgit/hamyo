import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime
import pytz
from src.level.LevelConstants import MAIN_CHAT_CHANNEL_ID, QUEST_EXP
from src.core.admin_utils import is_guild_admin

KST = pytz.timezone("Asia/Seoul")

class ClaimPieceView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # no timeout
        self.bot = bot
        self.claimed_users = set()
        self.max_claims = 3

    @discord.ui.button(label="📝 조각 줍기", style=discord.ButtonStyle.primary, custom_id="claim_story_piece")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id in self.claimed_users:
            await interaction.response.send_message("이미 이야기 조각을 주웠다묘!", ephemeral=True)
            return
            
        if len(self.claimed_users) >= self.max_claims:
            await interaction.response.send_message("앗, 다른 고요가 이미 모두 주워갔다묘!", ephemeral=True)
            return

        self.claimed_users.add(user_id)
        
        # 보상 지급
        level_checker = self.bot.get_cog("LevelChecker")
        if level_checker:
            # 직접 add_exp 호출 (선착순 제한이므로 process_quest의 기본 daily 로직 우회)
            exp = QUEST_EXP['daily'].get('story_piece', 20)
            await level_checker.data_manager.add_exp(user_id, exp, 'daily', 'story_piece')
            
            # 후처리 이벤트 발생용
            result = {
                'success': True,
                'exp_gained': exp,
                'messages': [f"이야기 조각 줍기 보상: **+{exp} 쪽**"],
                'quest_completed': ['daily_story_piece']
            }
            await level_checker._finalize_quest_result(user_id, result)
        else:
            await interaction.response.send_message("시스템 오류가 발생했다묘!", ephemeral=True)
            return

        # 성공 메시지 (ephemeral)
        success_msg = (
            ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
            f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {interaction.user.mention}, 조각을 주워줘서 고맙다묘! `20 쪽`을 책에 끼워두겠다묘! ᝰꪑ\n"
            "( つ📖O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯"
        )
        await interaction.response.send_message(success_msg, ephemeral=True)

        if len(self.claimed_users) >= self.max_claims:
            button.disabled = True
            
            # 마감 메시지로 수정
            closed_msg = (
                ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
                "꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO 다행히 잃어버린 이야기 조각을 모두 찾았다묘! ᝰꪑ\n"
                "( つ📦O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯"
            )
            await interaction.message.edit(content=closed_msg, view=self)
            self.stop()


class ScatteredStoryPiece(commands.Cog):
    """미션 1: 흩날리는 이야기 조각 줍기"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        self.bot.loop.create_task(self.setup_schedules())

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def setup_schedules(self):
        await self.bot.wait_until_ready()
        scheduler = self.bot.get_cog("Scheduler")
        if scheduler:
            # 매일 자정에 시간을 세팅하는 작업을 등록
            scheduler.schedule_daily(self.generate_daily_times, 0, 0)
            
            # 봇 로드 시, 이미 저장된 시간이 미래라면 한번 등록해둔다
            level_config = self.bot.get_cog("LevelConfig")
            if level_config:
                times_str = level_config.get_story_piece_times()
                now = datetime.now(KST)
                
                for t_str in times_str:
                    try:
                        # 형식: YYYY-MM-DD HH:MM:SS
                        # LevelConfig에 문자열 없이 KST를 적용하려면 strptime 사용
                        dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
                        dt = KST.localize(dt)
                        
                        # 오늘 날짜이고 미래 시간일 때만 (봇 재시작시 날아가는 것 방지)
                        if dt.date() == now.date() and dt > now:
                            scheduler.schedule_once(self.spawn_story_piece, dt)
                    except Exception as e:
                        print(f"스토리 조각 스케줄 복구 중 오류: {e}")
                        pass

    async def generate_daily_times(self):
        now = datetime.now(KST)
        # 09:00 ~ 23:59 사이 랜덤 시간 2개 생성
        times = []
        for _ in range(2):
            random_hour = random.randint(9, 23)
            random_minute = random.randint(0, 59)
            random_second = random.randint(0, 59)
            run_time = now.replace(hour=random_hour, minute=random_minute, second=random_second, microsecond=0)
            times.append(run_time)
            
        scheduler = self.bot.get_cog("Scheduler")
        level_config = self.bot.get_cog("LevelConfig")
        
        times_str = []
        if scheduler and level_config:
            for t in times:
                scheduler.schedule_once(self.spawn_story_piece, t)
                # KST 객체에서 포맷팅
                times_str.append(t.strftime("%Y-%m-%d %H:%M:%S"))
                
            level_config.set_story_piece_times(times_str)
            await self.log("흩날리는 이야기 조각 등장 일정이 설정되었습니다.")

    async def spawn_story_piece(self):
        channel = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
        if channel:
            msg_content = (
                ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
                "꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO 앗! 바람이 불어서 이야기 조각이 날아간다묘! ᝰꪑ\n"
                "( つ💨O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯ \n\n"
                "-# ◟. 빠르게 이야기 조각을 주워주는 선착순 3명에게 `20 쪽` 을 준다묘!"
            )
            view = ClaimPieceView(self.bot)
            await channel.send(content=msg_content, view=view)

    @commands.command(name="조각생성테스트")
    @is_guild_admin()
    async def test_spawn(self, ctx):
        await self.spawn_story_piece()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(ScatteredStoryPiece(bot))
