import discord
from discord.ext import commands
import aiosqlite
import asyncio

from src.core.admin_utils import is_guild_admin
from src.core.DataManager import DataManager
from src.core.LevelDataManager import LevelDataManager
from src.core.balance_data_manager import balance_manager as BalanceDataManager
from src.core.ChattingDataManager import ChattingDataManager

class DatabaseResetter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_db = DataManager()
        self.level_db = LevelDataManager()
        self.chat_db = ChattingDataManager()

    @commands.command(name="전체DB초기화")
    @is_guild_admin()
    async def reset_all_db(self, ctx):
        """
        설정 파일과 생일 데이터를 제외한 모든 DB 데이터를 초기화합니다.
        (음성 기록, 레벨/경험치, 자산 데이터, 출석, 채팅 기록 등)
        사용법: *전체DB초기화 (또는 접두사에 맞게 사용)
        """
        
        # 확인 메시지 전송
        confirm_msg = await ctx.reply(
            f"🚨 **[경고] 데이터베이스 초기화 안내** 🚨\n\n"
            f"**다음 데이터들이 모두 삭제/초기화됩니다:**\n"
            f"- 음성 기록 데이터\n"
            f"- 레벨/경험치(다공) 및 퀘스트 데이터\n"
            f"- 자산 및 송금 내역 데이터\n"
            f"- 출석 기록 데이터\n"
            f"- 채팅 기록 데이터\n\n"
            f"**유지되는 데이터:** 서버 설정, 생일 데이터, 화폐 수수료 설정 등\n\n"
            f"이 작업은 **돌이킬 수 없습니다**. 정말로 초기화를 진행하려면 30초 내에 `확인`을 입력하세요."
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "확인"

        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.reply("시간이 초과되어 취소되었습니다.")
            return

        # 2차 보완 메시지 (안전 확보)
        confirm_msg2 = await ctx.reply(
            f"⚠️ **마지막 경고입니다.**\n"
            f"정말로 지정된 모든 DB의 데이터를 영구적으로 삭제하시겠습니까?\n"
            f"진행하려면 30초 내에 `정말초기화`를 입력하세요."
        )
        
        def check2(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "정말초기화"
            
        try:
            await self.bot.wait_for('message', check=check2, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.reply("시간이 초과되어 취소되었습니다.")
            return

        # 진행 메시지
        progress_msg = await ctx.reply("🔄 지정된 데이터베이스 초기화 작업을 시작합니다...")
        
        results = []

        # 1. 음성 기록 (Voice)
        try:
            await self.voice_db.reset_data()
            results.append("✅ 음성 기록 DB 초기화 완료")
        except Exception as e:
            results.append(f"⚠️ 음성 기록 DB 초기화 실패: {e}")

        # 2. 레벨/경험치 (Level)
        try:
            await self.level_db.reset_all_users()
            # rank_certifications 테이블을 포함한 추가 테이블 초기화 보완
            await self.level_db.ensure_initialized()
            if self.level_db._db:
                await self.level_db._db.execute("DELETE FROM rank_certifications")
                await self.level_db._db.commit()
            results.append("✅ 레벨/경험치 데이터 DB 초기화 완료")
        except Exception as e:
            results.append(f"⚠️ 레벨/경험치 데이터 DB 초기화 실패: {e}")

        # 3. 자산/경제 (Economy)
        try:
            await BalanceDataManager.reset_all_balances()
            # 송금 내역 테이블도 추가 보조 삭제
            await BalanceDataManager.ensure_initialized()
            if BalanceDataManager._db:
                await BalanceDataManager._db.execute("DELETE FROM transfers")
                await BalanceDataManager._db.commit()
            results.append("✅ 자산 데이터 DB 초기화 완료")
        except Exception as e:
            results.append(f"⚠️ 자산 데이터 DB 초기화 실패: {e}")

        # 4. 출석 DB (Attendance) - SQLite 직접 접근 (attendance.db)
        try:
            db_path = 'data/attendance.db'
            async with aiosqlite.connect(db_path) as db:
                await db.execute("DELETE FROM attendance")
                await db.commit()
            results.append("✅ 출석 DB 초기화 완료")
        except Exception as e:
            results.append(f"⚠️ 출석 DB 초기화 실패: {e}")

        # 5. 채팅 DB (Chat)
        try:
            await self.chat_db.clear_all()
            results.append("✅ 채팅 데이터 DB 초기화 완료")
        except Exception as e:
            results.append(f"⚠️ 채팅 데이터 DB 초기화 실패: {e}")

        # 결과 종합
        result_text = "\n".join(results)
        await progress_msg.edit(content=f"🎉 **데이터베이스 초기화 작업이 완료되었습니다.**\n\n{result_text}")

async def setup(bot):
    await bot.add_cog(DatabaseResetter(bot))
