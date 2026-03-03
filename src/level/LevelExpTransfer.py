import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import datetime
import pytz
import os

from src.core.admin_utils import is_guild_admin
from src.core.LevelDataManager import LevelDataManager

KST = pytz.timezone("Asia/Seoul")
ARCHIVE_DB_PATH = "data/level_archive.db"
SYSTEM_DB_PATH = "data/level_system.db"

class ExpTransferView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="📝 쪽 이전하기", style=discord.ButtonStyle.primary, custom_id="claim_exp_transfer")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        now = datetime.now(KST)
        
        # 1. 기간 검사 (3월 2일 00:00:00 ~ 3월 8일 23:59:59)
        start_date = KST.localize(datetime(2026, 3, 2, 0, 0, 0))
        end_date = KST.localize(datetime(2026, 3, 8, 23, 59, 59))
        
        if now < start_date:
            await interaction.response.send_message("아직 이전 기간이 시작되지 않았다묘! (3월 2일부터 가능)", ephemeral=True)
            return
        if now > end_date:
            await interaction.response.send_message("이전 기간이 종료되었다묘... 다음 기회를 기다려달라묘!", ephemeral=True)
            return

        # 2. 전용 테이블을 생성해 중복 수령 방지 확인
        try:
            async with aiosqlite.connect(SYSTEM_DB_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS exp_transfers (
                        user_id INTEGER PRIMARY KEY,
                        transferred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor = await db.execute("SELECT 1 FROM exp_transfers WHERE user_id = ?", (user_id,))
                already_claimed = await cursor.fetchone()
                if already_claimed:
                    await interaction.response.send_message("이미 비몽다방에서 쪽을 모두 옮겨왔다묘! 두 번은 안된다묘.", ephemeral=True)
                    return
        except Exception as e:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(f"쪽 이전 중 수령 기록 확인 오류: {e}", title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
            await interaction.response.send_message("기록을 확인하는 중 오류가 발생했다묘.", ephemeral=True)
            return

        level_checker = self.bot.get_cog("LevelChecker")
        if not level_checker:
            await interaction.response.send_message("시스템 오류: 레벨 시스템을 찾을 수 없다묘.", ephemeral=True)
            return
            
        data_manager = level_checker.data_manager

        # 3. 아카이브 DB에서 조회
        if not os.path.exists(ARCHIVE_DB_PATH):
            await interaction.response.send_message("시스템 오류: 이전 데이터를 찾을 수 없다묘.", ephemeral=True)
            return
            
        old_exp = 0
        try:
            async with aiosqlite.connect(ARCHIVE_DB_PATH) as db:
                cursor = await db.execute("SELECT total_exp FROM user_exp WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row:
                    old_exp = int(row[0])
        except Exception as e:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(f"쪽 이전 중 아카이브 DB 접근 오류: {e}", title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
            await interaction.response.send_message("데이터베이스를 읽는 중 오류가 발생했다묘.", ephemeral=True)
            return
            
        if old_exp <= 0:
            await interaction.response.send_message("앗, 이전 다방에서 옮겨올 '다공' 기록이 없다묘...", ephemeral=True)
            return
            
        # 4. 50% 계산 후 지급
        new_exp = old_exp // 2
        
        if new_exp <= 0:
            await interaction.response.send_message("가져올 다공이 너무 적어 쪼개지지가 않는다묘... 미안하다묘!", ephemeral=True)
            return

        # 퀘스트 기록(quest_type) 없이 오로지 경험치만 지급
        success = await data_manager.add_exp(user_id, new_exp)
        
        if success:
            # 중복 수령을 막기 위한 전용 기록 추가
            try:
                async with aiosqlite.connect(SYSTEM_DB_PATH) as db:
                    await db.execute("INSERT OR IGNORE INTO exp_transfers (user_id) VALUES (?)", (user_id,))
                    await db.commit()
            except Exception as e:
                pass
                
            # 결과 후처리 (승급, 메인채팅 메시지) - 퀘스트 로그 없이 진행
            result = {
                'success': True,
                'exp_gained': new_exp,
                'messages': [f"비몽다방에서 쪽 가져오기 완료: **+{new_exp:,} 쪽** (기존 {old_exp:,} 다공의 50%)"]
            }
            await level_checker._finalize_quest_result(user_id, result)
            
            # 성공 응답 (유저에게만)
            msg = (
                ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
                f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO 무사히 `+{new_exp:,} 쪽` (기존 {old_exp:,} 다공의 50%) 을 옮겨왔다묘! ᝰꪑ\n"
                "( つ🧾O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯"
            )
            await interaction.response.send_message(msg, ephemeral=True)
            
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(f"쪽 이전 완료: {interaction.user}({user_id})에게 {new_exp} 쪽 지급 (기존 {old_exp})", title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
        else:
            await interaction.response.send_message("쪽 지급 중 알 수 없는 오류가 발생했다묘. 관리자에게 문의하라묘!", ephemeral=True)


class LevelExpTransfer(commands.Cog):
    """경험치 시스템 개편: 기존 다공의 50% 이전 기능"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # 봇 재시작 시 뷰 리스너 등록
        self.bot.add_view(ExpTransferView(self.bot))
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message, title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    @commands.command(name="경험치이전생성")
    @is_guild_admin()
    async def create_transfer_button(self, ctx):
        """기존 다공의 50%를 쪽으로 가져오는 버튼을 생성합니다."""
        embed = discord.Embed(
            title="📦 비몽다방에서의 추억 가져오기",
            description=(
                "비몽책방으로 이전하면서 기존 `다공`이 `쪽`으로 통합되었습니다!\n"
                "아래 버튼을 누르면 이전 다방에서 획득한 다공의 **50%**를 쪽으로 변환하여 지급해 드립니다.\n\n"
                "- 📅 **이전 기간**: 3월 2일 ~ 3월 8일\n"
                "- ⚠️ 유저당 **단 한 번만** 가져올 수 있습니다.\n"
                "- 쪽으로 지급된 후 자동으로 다음 단계로 승급될 수 있어요!"
            ),
            color=0xedccff
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="버튼을 눌러 나만의 이야기 조각을 되찾아오세요!")

        view = ExpTransferView(self.bot)
        await ctx.send(embed=embed, view=view)
        # 명령어 메시지 자체는 삭제. 필요하면 활성화
        try:
            await ctx.message.delete()
        except:
            pass

async def setup(bot):
    await bot.add_cog(LevelExpTransfer(bot))
