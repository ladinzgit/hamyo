import discord
from discord.ext import commands
from LevelDataManager import LevelDataManager
from typing import Optional, Dict, Any, List
import json, os
import logging
import pytz

KST = pytz.timezone("Asia/Seoul")    
CONFIG_PATH = "config/level_config.json"

def _ensure_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"guilds": {}}, f, ensure_ascii=False, indent=2)

def _load_levelcfg():
    _ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_levelcfg(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class LevelConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        self.logger = logging.getLogger(__name__)
        
        # 역할 정보
        self.role_info = {
            'hub': {'name': '허브', 'threshold': 0, 'emoji': '🌱'},
            'dado': {'name': '다도', 'threshold': 400, 'emoji': '🍃'},
            'daho': {'name': '다호', 'threshold': 1800, 'emoji': '🌸'},
            'dakyung': {'name': '다경', 'threshold': 6000, 'emoji': '🌟'}
        }
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.ensure_initialized()
    
    # ===========================================
    # 경험치 관리 명령어들
    # ===========================================
    
    @commands.group(name='exp', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def exp_group(self, ctx):
        """경험치 관리 명령어 그룹"""
        embed = discord.Embed(
            title="🎯 경험치 관리 명령어",
            description="경험치 시스템을 관리하는 명령어들입니다.",
            color=0x7289da
        )
        embed.add_field(
            name="⚙️ 관리",
            value="`*exp give <유저> <경험치> [사유]` - 경험치 지급\n`*exp remove <유저> <경험치> [사유]` - 경험치 회수",
            inline=False
        )
        embed.add_field(
            name="🔄 초기화",
            value="`*exp reset <유저>` - 유저 초기화\n`*exp reset_all` - 전체 초기화",
            inline=False
        )
        await ctx.send(embed=embed)
    
    @exp_group.command(name='give')
    @commands.has_permissions(administrator=True)
    async def give_exp(self, ctx, member: discord.Member, amount: int, *, reason: str = "관리자 지급"):
        """경험치 지급"""
        if amount <= 0:
            await ctx.send("❌ 다공은 1 이상이어야 합니다.")
            return
        
        if amount > 10000:
            await ctx.send("❌ 한 번에 지급할 수 있는 다공은 10,000 이하입니다.")
            return
        
        # 경험치 지급 전 현재 상태 확인
        before_data = await self.data_manager.get_user_exp(member.id)
        before_role = before_data['current_role'] if before_data else 'hub'
        
        success = await self.data_manager.add_exp(member.id, amount, 'manual', reason)
        
        if success:
            # 역할 승급 확인
            level_checker = self.bot.get_cog('LevelChecker')
            role_update = None
            if level_checker:
                role_update = await level_checker._check_role_upgrade(member.id)
            
            embed = discord.Embed(
                title="✅ 다공 지급 완료",
                color=0x00ff00
            )
            embed.add_field(name="대상", value=member.mention, inline=True)
            embed.add_field(name="지급량", value=f"+{amount:,} 다공", inline=True)
            embed.add_field(name="사유", value=reason, inline=True)
            
            # 현재 총 다공 표시
            after_data = await self.data_manager.get_user_exp(member.id)
            if after_data:
                embed.add_field(
                    name="총 다공", 
                    value=f"{after_data['total_exp']:,} 다공", 
                    inline=True
                )
            
            if role_update:
                embed.add_field(
                    name="🎉 역할 승급!",
                    value=f"**{role_update}** 역할로 승급했습니다!",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ 다공 지급 중 오류가 발생했습니다.")
    
    @exp_group.command(name='remove')
    @commands.has_permissions(administrator=True)
    async def remove_exp(self, ctx, member: discord.Member, amount: int, *, reason: str = "관리자 회수"):
        """경험치 회수"""
        if amount <= 0:
            await ctx.send("❌ 다공은 1 이상이어야 합니다.")
            return
        
        # 현재 경험치 확인
        user_data = await self.data_manager.get_user_exp(member.id)
        if not user_data or user_data['total_exp'] == 0:
            await ctx.send("❌ 해당 유저는 경험치가 없습니다.")
            return
        
        current_exp = user_data['total_exp']
        will_remove = min(amount, current_exp)  # 실제 회수될 양
        
        success = await self.data_manager.remove_exp(member.id, amount)
        
        if success:
            embed = discord.Embed(
                title="✅ 다공 회수 완료",
                color=0xff9900
            )
            embed.add_field(name="대상", value=member.mention, inline=True)
            embed.add_field(name="회수량", value=f"-{will_remove:,} 다공", inline=True)
            embed.add_field(name="사유", value=reason, inline=True)
            
            # 회수 후 총 다공 표시
            after_data = await self.data_manager.get_user_exp(member.id)
            if after_data:
                embed.add_field(
                    name="남은 다공", 
                    value=f"{after_data['total_exp']:,} 다공", 
                    inline=True
                )
            
            if will_remove < amount:
                embed.add_field(
                    name="⚠️ 알림",
                    value=f"보유 다공이 부족하여 {will_remove:,} 다공만 회수되었습니다.",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ 다공 회수 중 오류가 발생했습니다.")
    
    @exp_group.command(name='reset')
    @commands.has_permissions(administrator=True)
    async def reset_user(self, ctx, member: discord.Member):
        """특정 유저 초기화"""
        # 현재 데이터 확인
        user_data = await self.data_manager.get_user_exp(member.id)
        if not user_data or user_data['total_exp'] == 0:
            await ctx.send("❌ 해당 유저는 초기화할 데이터가 없습니다.")
            return
        
        # 확인 메시지
        embed = discord.Embed(
            title="⚠️ 유저 초기화 확인",
            description=f"{member.mention}의 모든 경험치와 퀘스트 데이터를 초기화하시겠습니까?",
            color=0xff0000
        )
        embed.add_field(
            name="현재 데이터",
            value=f"다공: {user_data['total_exp']:,} 다공\n역할: {user_data['current_role']}",
            inline=False
        )
        embed.add_field(name="⚠️ 주의", value="이 작업은 되돌릴 수 없습니다!", inline=False)
        
        view = ConfirmView(ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        
        await view.wait()
        if view.confirmed:
            success = await self.data_manager.reset_user(member.id)
            if success:
                embed = discord.Embed(
                    title="✅ 유저 초기화 완료",
                    description=f"{member.mention}의 데이터가 초기화되었습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ 초기화 실패",
                    description="데이터 초기화 중 오류가 발생했습니다.",
                    color=0xff0000
                )
        else:
            embed = discord.Embed(
                title="❌ 초기화 취소",
                description="유저 초기화가 취소되었습니다.",
                color=0x999999
            )
        
        await message.edit(embed=embed, view=None)
    
    @exp_group.command(name='reset_all')
    @commands.has_permissions(administrator=True)
    async def reset_all_users(self, ctx):
        """전체 유저 초기화"""
        # 전체 유저 수 확인
        try:
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("SELECT COUNT(*) FROM user_exp WHERE total_exp > 0")
                user_count = (await cursor.fetchone())[0]
        except:
            user_count = 0
        
        if user_count == 0:
            await ctx.send("❌ 초기화할 유저 데이터가 없습니다.")
            return
        
        # 확인 메시지
        embed = discord.Embed(
            title="🚨 전체 초기화 확인",
            description=f"**{user_count}명의 유저** 데이터를 모두 초기화하시겠습니까?",
            color=0xff0000
        )
        embed.add_field(
            name="⚠️ 경고", 
            value="이 작업은 되돌릴 수 없으며, 모든 데이터가 영구적으로 삭제됩니다!", 
            inline=False
        )
        embed.add_field(
            name="삭제될 데이터",
            value="• 모든 유저의 다공\n• 모든 퀘스트 기록\n• 모든 일회성 퀘스트 완료 기록",
            inline=False
        )
        
        view = ConfirmView(ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        
        await view.wait()
        if view.confirmed:
            success = await self.data_manager.reset_all_users()
            if success:
                embed = discord.Embed(
                    title="✅ 전체 초기화 완료",
                    description=f"{user_count}명의 유저 데이터가 초기화되었습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ 초기화 실패",
                    description="데이터 초기화 중 오류가 발생했습니다.",
                    color=0xff0000
                )
        else:
            embed = discord.Embed(
                title="❌ 초기화 취소",
                description="전체 초기화가 취소되었습니다.",
                color=0x999999
            )
        
        await message.edit(embed=embed, view=None)
    
    # ===========================================
    # 퀘스트 관리 명령어들
    # ===========================================
    
    @commands.group(name='quest', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def quest_group(self, ctx):
        """퀘스트 관리 명령어 그룹"""
        embed = discord.Embed(
            title="📋 퀘스트 관리 명령어",
            description="퀘스트 시스템을 관리하는 명령어들입니다.",
            color=0x7289da
        )
        embed.add_field(
            name="🔧 관리",
            value="`*quest complete <유저> <퀘스트> [사유]` - 퀘스트 강제 완료\n`*quest reset <유저>` - 퀘스트 초기화",
            inline=False
        )
        embed.add_field(
            name="🏆 랭크 인증",
            value="`*quest voice <유저> <레벨>` - 보이스 랭크 인증\n`*quest chat <유저> <레벨>` - 채팅 랭크 인증",
            inline=False
        )
        await ctx.send(embed=embed)
    
    @quest_group.command(name='complete')
    @commands.has_permissions(administrator=True)
    async def force_complete_quest(self, ctx, member: discord.Member, quest_type: str, *, reason: str = "관리자 강제 완료"):
        """퀘스트 강제 완료"""
        level_checker = self.bot.get_cog('LevelChecker')
        if not level_checker:
            await ctx.send("❌ LevelChecker를 찾을 수 없습니다.")
            return

        # 퀘스트 유효성 확인 (one_time 포함)
        try:
            is_valid = await level_checker.is_valid_quest(quest_type)
        except Exception as e:
            await ctx.send(f"❌ 퀘스트 유효성 검사 중 오류: {e}")
            return

        if not is_valid:
            quest_exp = getattr(level_checker, "quest_exp", None)
            available_quests = []
            if quest_exp:
                for category in ['daily', 'weekly', 'one_time']:
                    available_quests.extend(list(quest_exp.get(category, {}).keys()))
            embed = discord.Embed(
                title="❌ 유효하지 않은 퀘스트",
                description=f"'{quest_type}'는 존재하지 않는 퀘스트입니다.",
                color=0xff0000
            )
            embed.add_field(
                name="사용 가능한 퀘스트",
                value=f"```{', '.join(available_quests[:20])}{'...' if len(available_quests) > 20 else ''}```",
                inline=False
            )
            embed.add_field(
                name="전체 목록 보기",
                value="`!quest list` 명령어를 사용하세요.",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        # 경험치값을 LevelChecker의 quest_exp에서 직접 가져옴
        quest_exp = level_checker.quest_exp
        exp_amount = None
        quest_category = None
        for category in ['daily', 'weekly', 'one_time']:
            if quest_type in quest_exp[category]:
                exp_amount = quest_exp[category][quest_type]
                quest_category = category
                break

        if exp_amount is None:
            await ctx.send(f"❌ '{quest_type}'의 경험치 정보를 찾을 수 없습니다.")
            return

        # 퀘스트 강제 완료: DB에 quest_type/quest_subtype/exp_amount 반영
        try:
            # 경험치 지급 및 로그 기록
            success = await self.data_manager.add_exp(
                member.id,
                exp_amount,
                quest_category,
                quest_type
            )
            # LevelChecker의 추가 처리(역할 승급 등)
            result = await level_checker.process_quest(member.id, quest_type)
        except Exception as e:
            await ctx.send(f"❌ 퀘스트 처리 중 오류: {e}")
            return

        embed = discord.Embed(
            title="🔧 퀘스트 강제 완료",
            color=0x00ff00 if result.get('success') else 0xff0000
        )
        embed.add_field(name="대상", value=member.mention, inline=True)
        embed.add_field(name="퀘스트", value=quest_type, inline=True)
        embed.add_field(name="다공", value=f"{exp_amount} 다공", inline=True)
        embed.add_field(name="사유", value=reason, inline=True)

        if result.get('success'):
            embed.add_field(name="결과", value=f"+{result.get('exp_gained', 0):,} 다공", inline=False)
            if result.get('role_updated'):
                embed.add_field(name="🎉 역할 승급", value=f"**{result.get('new_role')}** 역할로 승급!", inline=False)
            if result.get('quest_completed'):
                embed.add_field(
                    name="완료된 퀘스트",
                    value="\n".join([f"• {quest}" for quest in result['quest_completed']]),
                    inline=False
                )
        else:
            error_messages = "\n".join(result.get('messages', [])) if result.get('messages') else "알 수 없는 오류"
            embed.add_field(name="오류", value=error_messages, inline=False)

        await ctx.send(embed=embed)
        
    @quest_group.command(name='voice')
    @commands.has_permissions(administrator=True)
    async def certify_voice_rank(self, ctx, member: discord.Member, level: int):
        """보이스 랭크 인증 및 보상 지급"""
        await self._certify_rank(ctx, member, level, 'voice', '🎤 보이스')

    @quest_group.command(name='chat')
    @commands.has_permissions(administrator=True)
    async def certify_chat_rank(self, ctx, member: discord.Member, level: int):
        """채팅 랭크 인증 및 보상 지급"""
        await self._certify_rank(ctx, member, level, 'chat', '💬 채팅')

    async def _certify_rank(self, ctx, member: discord.Member, new_level: int, rank_type: str, rank_display: str):
        """랭크 인증 공통 로직"""
        if new_level < 1:
            await ctx.send("❌ 레벨은 1 이상이어야 합니다.")
            return
        
        if new_level > 200:  # 최대 레벨 제한을 높게 설정
            await ctx.send("❌ 레벨은 200 이하여야 합니다.")
            return
        
        # 현재 인증된 레벨 조회
        current_certified_level = await self.data_manager.get_certified_rank_level(member.id, rank_type)
        
        if new_level <= current_certified_level:
            await ctx.send(f"❌ {member.display_name}님은 이미 {rank_display} {current_certified_level}레벨까지 인증받았습니다.")
            return
        
        # 5단위 보상 레벨 계산 (5, 10, 15, 20, 25, 30, ...)
        def get_reward_levels(start_level, end_level):
            """start_level 초과부터 end_level 이하까지의 5단위 레벨들 반환"""
            reward_levels = []
            # 다음 5의 배수부터 시작
            next_reward = ((start_level // 5) + 1) * 5
            while next_reward <= end_level:
                reward_levels.append(next_reward)
                next_reward += 5
            return reward_levels
        
        reward_levels = get_reward_levels(current_certified_level, new_level)
        exp_per_reward = 20  # 각 단계별 다공
        
        total_exp = 0
        completed_quests = []
        
        for reward_level in reward_levels:
            # 해당 레벨 보상 지급
            quest_name = f'rank_{reward_level}'
            
            # 일회성 퀘스트로 이미 완료했는지 확인
            already_completed = await self.data_manager.is_one_time_quest_completed(member.id, quest_name)
            if not already_completed:
                await self.data_manager.mark_one_time_quest_completed(member.id, quest_name)
                await self.data_manager.add_exp(member.id, exp_per_reward, 'one_time', quest_name)
                total_exp += exp_per_reward
                completed_quests.append(f"{rank_display} {reward_level}레벨 달성")
        
        if total_exp == 0:
            await ctx.send(f"❌ {member.display_name}님은 {current_certified_level}레벨에서 {new_level}레벨 사이에 받을 수 있는 보상이 없습니다.\n(5단위 레벨에서만 보상을 받을 수 있습니다)")
            return
        
        # 인증된 레벨 업데이트
        success = await self.data_manager.update_certified_rank_level(member.id, rank_type, new_level)
        
        if not success:
            await ctx.send("❌ 랭크 인증 중 오류가 발생했습니다.")
            return
        
        # 역할 승급 확인
        level_checker = self.bot.get_cog('LevelChecker')
        role_update = None
        if level_checker:
            role_update = await level_checker._check_role_upgrade(member.id)
        
        # 결과 임베드
        embed = discord.Embed(
            title=f"✅ {rank_display} 랭크 인증 완료",
            color=0x00ff00
        )
        embed.add_field(name="대상", value=member.mention, inline=True)
        embed.add_field(name="인증 레벨", value=f"{new_level}레벨", inline=True)
        embed.add_field(name="이전 인증", value=f"{current_certified_level}레벨", inline=True)
        
        embed.add_field(name="획득 다공", value=f"+{total_exp:,} 다공", inline=True)
        embed.add_field(name="완료된 퀘스트", value=f"{len(completed_quests)}개", inline=True)
        embed.add_field(name="", value="", inline=True)  # 빈 필드로 줄바꿈
        
        if completed_quests:
            # 너무 많은 퀘스트가 완료된 경우 일부만 표시
            display_quests = completed_quests[:10]  # 최대 10개만 표시
            quest_text = "\n".join([f"• {quest}" for quest in display_quests])
            if len(completed_quests) > 10:
                quest_text += f"\n... 외 {len(completed_quests) - 10}개"
            
            embed.add_field(
                name="🎉 달성한 마일스톤",
                value=quest_text,
                inline=False
            )
        
        if role_update:
            embed.add_field(
                name="🎊 역할 승급!",
                value=f"**{role_update}** 역할로 승급했습니다!",
                inline=False
            )
        
        # 현재 총 경험치 표시
        user_data = await self.data_manager.get_user_exp(member.id)
        if user_data:
            embed.add_field(
                name="총 다공",
                value=f"{user_data['total_exp']:,} 다공",
                inline=True
            )
        
        await ctx.send(embed=embed)

    @quest_group.command(name='rank_status')
    @commands.has_permissions(administrator=True)
    async def rank_status(self, ctx, member: discord.Member = None):
        """유저의 랭크 인증 현황 조회"""
        if member is None:
            await ctx.send("❌ 조회할 유저를 지정해주세요. 예: `!quest rank_status @유저`")
            return
        
        certified_ranks = await self.data_manager.get_all_certified_ranks(member.id)
        
        embed = discord.Embed(
            title=f"🏆 {member.display_name}의 랭크 인증 현황",
            color=0x7289da
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        voice_level = certified_ranks.get('voice', 0)
        chat_level = certified_ranks.get('chat', 0)
        
        embed.add_field(name="🎤 보이스 랭크", value=f"{voice_level}레벨", inline=True)
        embed.add_field(name="💬 채팅 랭크", value=f"{chat_level}레벨", inline=True)
        embed.add_field(name="", value="", inline=True)  # 빈 필드
        
        # 다음 보상까지의 진행도
        reward_levels = [5, 10, 15, 20]
        
        def get_next_reward(current_level):
            for reward_level in reward_levels:
                if current_level < reward_level:
                    return reward_level
            return None
        
        voice_next = get_next_reward(voice_level)
        chat_next = get_next_reward(chat_level)
        
        progress_text = ""
        if voice_next:
            progress_text += f"🎤 다음 보상: {voice_next}레벨 ({voice_next - voice_level}레벨 남음)\n"
        else:
            progress_text += f"🎤 모든 보상 완료!\n"
        
        if chat_next:
            progress_text += f"💬 다음 보상: {chat_next}레벨 ({chat_next - chat_level}레벨 남음)"
        else:
            progress_text += f"💬 모든 보상 완료!"
        
        embed.add_field(name="📈 진행도", value=progress_text, inline=False)
        
        # 완료한 랭크 퀘스트 확인
        completed_rank_quests = []
        for reward_level in reward_levels:
            quest_name = f'rank_{reward_level}'
            if await self.data_manager.is_one_time_quest_completed(member.id, quest_name):
                completed_rank_quests.append(f"✅ {reward_level}레벨 달성")
            else:
                completed_rank_quests.append(f"❌ {reward_level}레벨 달성")
        
        embed.add_field(
            name="🎯 랭크 퀘스트 완료 현황",
            value="\n".join(completed_rank_quests),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @quest_group.command(name='reset')
    @commands.has_permissions(administrator=True)
    async def reset_quest(self, ctx, member: discord.Member):
        """특정 유저의 퀘스트 초기화"""
        # 퀘스트 기록 확인
        try:
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs WHERE user_id = ?
                """, (member.id,))
                quest_log_count = (await cursor.fetchone())[0]
                
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM one_time_quests WHERE user_id = ?
                """, (member.id,))
                one_time_count = (await cursor.fetchone())[0]
        except:
            quest_log_count = 0
            one_time_count = 0
        
        if quest_log_count == 0 and one_time_count == 0:
            await ctx.send("❌ 해당 유저는 초기화할 퀘스트 기록이 없습니다.")
            return
        
        # 확인 메시지
        embed = discord.Embed(
            title="⚠️ 퀘스트 초기화 확인",
            description=f"{member.mention}의 모든 퀘스트 기록을 초기화하시겠습니까?",
            color=0xff0000
        )
        embed.add_field(
            name="삭제될 데이터",
            value=f"• 퀘스트 완료 기록: {quest_log_count}개\n• 일회성 퀘스트 기록: {one_time_count}개",
            inline=False
        )
        embed.add_field(name="⚠️ 주의", value="경험치는 유지되지만 퀘스트 기록은 모두 삭제됩니다!", inline=False)
        
        view = ConfirmView(ctx.author.id)
        message = await ctx.send(embed=embed, view=view)
        
        await view.wait()
        if view.confirmed:
            try:
                async with self.data_manager.db_connect() as db:
                    await db.execute("DELETE FROM quest_logs WHERE user_id = ?", (member.id,))
                    await db.execute("DELETE FROM one_time_quests WHERE user_id = ?", (member.id,))
                    await db.commit()
                
                embed = discord.Embed(
                    title="✅ 퀘스트 초기화 완료",
                    description=f"{member.mention}의 퀘스트 기록이 초기화되었습니다.",
                    color=0x00ff00
                )
                embed.add_field(
                    name="초기화된 데이터",
                    value=f"• 퀘스트 완료 기록: {quest_log_count}개\n• 일회성 퀘스트 기록: {one_time_count}개",
                    inline=False
                )
            except Exception as e:
                self.logger.error(f"Error resetting quest: {e}")
                embed = discord.Embed(
                    title="❌ 초기화 실패",
                    description="퀘스트 초기화 중 오류가 발생했습니다.",
                    color=0xff0000
                )
        else:
            embed = discord.Embed(
                title="❌ 초기화 취소",
                description="퀘스트 초기화가 취소되었습니다.",
                color=0x999999
            )
        
        await message.edit(embed=embed, view=None)
    
    @quest_group.command(name='list')
    @commands.has_permissions(administrator=True)
    async def quest_list(self, ctx):
        """모든 퀘스트 목록 조회"""
        level_checker = self.bot.get_cog('LevelChecker')
        if not level_checker:
            await ctx.send("❌ LevelChecker를 찾을 수 없습니다.")
            return

        # LevelChecker의 quest_exp 구조 직접 사용
        quest_exp = level_checker.quest_exp

        embed = discord.Embed(
            title="📝 전체 퀘스트 목록",
            description="시스템에서 사용 가능한 모든 퀘스트입니다.",
            color=0x7289da
        )

        # 일일 퀘스트
        daily_quests = []
        for quest, exp in quest_exp['daily'].items():
            if quest == "bbibbi":
                daily_quests.append(f"`{quest}` ({exp} 다공) - 다방삐삐(지정 채널에서 역할 멘션)")
            else:
                daily_quests.append(f"`{quest}` ({exp} 다공)")
        embed.add_field(
            name="📅 일일 퀘스트",
            value="\n".join(daily_quests) if daily_quests else "없음",
            inline=False
        )

        # 주간 퀘스트
        weekly_quests = []
        for quest, exp in quest_exp['weekly'].items():
            weekly_quests.append(f"`{quest}` ({exp} 다공)")
        embed.add_field(
            name="📊 주간 퀘스트",
            value="\n".join(weekly_quests) if weekly_quests else "없음",
            inline=False
        )

        # 일회성 퀘스트
        one_time_quests = []
        for quest, exp in quest_exp['one_time'].items():
            one_time_quests.append(f"`{quest}` ({exp} 다공)")
        embed.add_field(
            name="✨ 일회성 퀘스트",
            value="\n".join(one_time_quests) if one_time_quests else "없음",
            inline=False
        )

        embed.set_footer(text="!quest info <퀘스트명> 으로 상세 정보를 확인할 수 있습니다.")
        await ctx.send(embed=embed)

    @quest_group.command(name='info')
    @commands.has_permissions(administrator=True)
    async def quest_info(self, ctx, quest_type: str):
        """퀘스트 상세 정보 조회"""
        level_checker = self.bot.get_cog('LevelChecker')
        if not level_checker:
            await ctx.send("❌ LevelChecker를 찾을 수 없습니다.")
            return

        quest_exp = level_checker.quest_exp

        # 카테고리 및 경험치 찾기
        quest_category = None
        exp_amount = None
        for category in ['daily', 'weekly', 'one_time']:
            if quest_type in quest_exp[category]:
                quest_category = category
                exp_amount = quest_exp[category][quest_type]
                break

        if not quest_category:
            await ctx.send(f"❌ '{quest_type}'는 존재하지 않는 퀘스트입니다. `!quest list`로 전체 목록을 확인하세요.")
            return

        # 퀘스트 설명
        quest_descriptions = {
            'attendance': '매일 서버에 출석하는 퀘스트',
            'diary': '다방일지 채널에 일기를 작성하는 퀘스트',
            'voice_30min': '음성방에서 30분 이상 활동하는 퀘스트',
            'bbibbi': '특정 채널에서 역할을 멘션하는 삐삐 퀘스트',
            'recommend_3': '서버를 외부 사이트에 3회 추천하는 퀘스트',
            'shop_purchase': '비몽상점에서 상품을 구매하는 퀘스트',
            'board_participate': '비몽게시판에 참여하는 퀘스트',
            'ping_use': '다방삐삐를 사용하는 퀘스트',
            'voice_5h': '주간 음성방 5시간 달성 퀘스트',
            'voice_10h': '주간 음성방 10시간 달성 퀘스트',
            'voice_20h': '주간 음성방 20시간 달성 퀘스트',
            'attendance_4': '주간 출석 4회 달성 시 자동 완료',
            'attendance_7': '주간 출석 7회 달성 시 자동 완료',
            'diary_4': '주간 다방일지 4회 달성 시 자동 완료',
            'diary_7': '주간 다방일지 7회 달성 시 자동 완료',
            'self_intro': '허브 카테고리에 자기소개 채널을 만드는 퀘스트',
            'review': '디코올에 서버 후기를 작성하는 퀘스트',
            'monthly_role': '이달의 역할을 구매하는 퀘스트'
        }

        category_names = {
            'daily': '📅 일일 퀘스트',
            'weekly': '📊 주간 퀘스트',
            'one_time': '✨ 일회성 퀘스트'
        }

        embed = discord.Embed(
            title=f"📝 {quest_type} 퀘스트 정보",
            color=0x7289da
        )

        embed.add_field(name="카테고리", value=category_names.get(quest_category, quest_category), inline=True)
        embed.add_field(name="다공", value=f"{exp_amount} 다공", inline=True)
        embed.add_field(name="설명", value=quest_descriptions.get(quest_type, "설명이 없습니다."), inline=False)

        # 특별 조건
        special_conditions = []
        if quest_type.startswith('voice_'):
            if 'h' in quest_type:
                hours = quest_type.split('_')[1].replace('h', '')
                special_conditions.append(f"주간 음성방 {hours}시간 달성 필요")
            elif quest_type == 'voice_30min':
                special_conditions.append("하루 1회, 30분 이상 음성방 활동 필요")
        elif quest_type == 'bbibbi':
            special_conditions.append("지정된 채널에서 지정된 역할 멘션 필요")
        elif quest_category == 'weekly' and quest_type not in ['attendance_4', 'attendance_7', 'diary_4', 'diary_7']:
            special_conditions.append("주 1회 완료 가능")
        elif quest_category == 'one_time':
            special_conditions.append("계정당 1회만 완료 가능")

        if special_conditions:
            embed.add_field(name="특별 조건", value="\n".join(special_conditions), inline=False)

        # 사용 예시
        embed.add_field(
            name="강제 완료 명령어",
            value=f"`!quest complete @유저 {quest_type} [사유]`",
            inline=False
        )

        await ctx.send(embed=embed)
        
    # ===========================================
    # 내정보 채널 관리 명령어들
    # ===========================================
        
    @commands.group(name="내정보채널", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def level_settings(self, ctx: commands.Context):
        await ctx.send("사용법: `내정보채널 추가|제거|조회`")

    @level_settings.command(name="추가")
    @commands.has_permissions(administrator=True)
    async def add_myinfo_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = _load_levelcfg()
        g = cfg["guilds"].setdefault(str(ctx.guild.id), {})
        lst = g.setdefault("my_info_channels", [])
        if channel.id not in lst:
            lst.append(channel.id)
            _save_levelcfg(cfg)
            await ctx.send(f"✅ `내정보` 허용 채널에 {channel.mention} 추가됨.")
        else:
            await ctx.send(f"ℹ️ 이미 허용 목록에 있는 채널입니다: {channel.mention}")

    @level_settings.command(name="제거")
    @commands.has_permissions(administrator=True)
    async def remove_myinfo_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = _load_levelcfg()
        g = cfg["guilds"].setdefault(str(ctx.guild.id), {})
        lst = g.setdefault("my_info_channels", [])
        if channel.id in lst:
            lst.remove(channel.id)
            _save_levelcfg(cfg)
            await ctx.send(f"✅ `내정보` 허용 채널에서 {channel.mention} 제거됨.")
        else:
            await ctx.send(f"ℹ️ 허용 목록에 없는 채널입니다: {channel.mention}")

    @level_settings.command(name="조회")
    @commands.has_permissions(administrator=True)
    async def list_myinfo_channels(self, ctx: commands.Context):
        cfg = _load_levelcfg()
        ids = cfg.get("guilds", {}).get(str(ctx.guild.id), {}).get("my_info_channels", [])
        if not ids:
            await ctx.send("🔓 현재 `내정보`는 **모든 채널 허용** 상태입니다.")
            return
        mentions = []
        for cid in ids:
            ch = ctx.guild.get_channel(cid)
            mentions.append(ch.mention if ch else f"`{cid}`(삭제됨)")
        await ctx.send("✅ 허용 채널 목록: " + ", ".join(mentions) if mentions else "비어 있음")



class ConfirmView(discord.ui.View):
    """확인 버튼 뷰"""
    def __init__(self, author_id: int):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.confirmed = False
    
    @discord.ui.button(label='확인', style=discord.ButtonStyle.danger, emoji='✅')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 명령어를 실행한 사용자만 버튼을 누를 수 있습니다.", ephemeral=True)
            return
        
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
    
    @discord.ui.button(label='취소', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 명령어를 실행한 사용자만 버튼을 누를 수 있습니다.", ephemeral=True)
            return
        
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


async def setup(bot):
    await bot.add_cog(LevelConfig(bot))