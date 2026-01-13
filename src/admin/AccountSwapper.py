
import discord
from discord.ext import commands
from src.core.admin_utils import is_guild_admin
from src.core.DataManager import DataManager
from src.core.LevelDataManager import LevelDataManager
from src.core.balance_data_manager import balance_manager as BalanceDataManager
from src.core.fortune_db import swap_user_fortune_data
from src.core.birthday_db import swap_user_birthday_data

class AccountSwapper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_db = DataManager()
        self.level_db = LevelDataManager()

    @commands.command(name="본부계변경")
    @is_guild_admin()
    async def swap_account(self, ctx, main_account: discord.User, sub_account: discord.User):
        """
        부계정의 데이터를 본계정으로 덮어씁니다.
        사용법: *본부계변경 (본계정) (부계정)
        """
        
        # 확인 메시지 전송
        confirm_msg = await ctx.reply(
            f"⚠️ **데이터 통합 안내**\n\n"
            f"**본계정**: {main_account.mention} (ID: {main_account.id})\n"
            f"**부계정**: {sub_account.mention} (ID: {sub_account.id})\n\n"
            f"**부계정**의 데이터를 **본계정**으로 통합하시겠습니까?\n"
            f"- **자산/경험치/음성시간**: 본계정 데이터에 **합산**됩니다.\n"
            f"- **기본 정보(생일 등)**: 본계정 데이터가 있는 경우 **유지**됩니다.\n"
            f"- **부계정의 데이터**는 통합 후 **삭제/초기화**됩니다.\n\n"
            f"진행하려면 `확인`을 입력하세요."
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "확인"

        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except:
            await ctx.reply("시간이 초과되어 취소되었습니다.")
            return

        # 진행 메시지
        progress_msg = await ctx.reply("🔄 계정 데이터 교체 작업을 시작합니다...")
        
        main_id = main_account.id
        sub_id = sub_account.id
        main_id_str = str(main_id)
        sub_id_str = str(sub_id)

        results = []

        # 1. 음성 기록 (Voice)
        if await self.voice_db.swap_user_voice_data(sub_id, main_id):
            results.append("✅ 음성 기록 교체 완료")
        else:
            results.append("⚠️ 음성 기록 교체 실패 또는 데이터 없음")

        # 2. 레벨/경험치 (Level)
        if await self.level_db.swap_user_level_data(sub_id, main_id):
            results.append("✅ 레벨/경험치 데이터 교체 완료")
        else:
            results.append("⚠️ 레벨/경험치 데이터 교체 실패 또는 데이터 없음")

        # 3. 자산/경제 (Economy)
        if await BalanceDataManager.swap_user_balance_data(sub_id_str, main_id_str):
            results.append("✅ 자산 데이터 교체 완료")
        else:
            results.append("⚠️ 자산 데이터 교체 실패 또는 데이터 없음")

        # 4. 운세 (Fortune) - 동기 함수이므로 await 없음 (파일 I/O)
        if swap_user_fortune_data(sub_id, main_id):
            results.append("✅ 운세 데이터 교체 완료")
        else:
            results.append("⚠️ 운세 데이터 교체 실패 또는 데이터 없음")
            
        # 5. 생일 (Birthday)
        if await swap_user_birthday_data(sub_id_str, main_id_str):
            results.append("✅ 생일 데이터 교체 완료")
        else:
            results.append("⚠️ 생일 데이터 교체 실패 또는 데이터 없음")

        # 6. 이벤트 디스패치 (다른 cog들을 위해)
        self.bot.dispatch('user_id_swap', sub_id, main_id)
        results.append("✅ 추가 모듈 동기화 이벤트 발생 완료")

        # 결과 종합
        result_text = "\n".join(results)
        await progress_msg.edit(content=f"🎉 **계정 데이터 교체 작업이 완료되었습니다.**\n\n{result_text}")

async def setup(bot):
    await bot.add_cog(AccountSwapper(bot))
