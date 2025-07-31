import discord
from discord.ext import commands
from LevelDataManager import LevelDataManager
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta

class LevelCommands(commands.Cog):
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
        
        self.role_order = ['hub', 'dado', 'daho', 'dakyung']
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.initialize_database()
    
    @commands.command(name='내정보', aliases=['myinfo', '정보'])
    async def my_info(self, ctx):
        """내 경험치 및 퀘스트 정보 조회"""
        user_id = ctx.author.id
        
        # 유저 경험치 정보 가져오기
        user_data = await self.data_manager.get_user_exp(user_id)
        if not user_data:
            await ctx.send("❌ 사용자 데이터를 찾을 수 없습니다.")
            return
        
        current_exp = user_data['total_exp']
        current_role = user_data['current_role']
        
        # 인증된 랭크 정보 가져오기
        certified_ranks = await self.data_manager.get_all_certified_ranks(user_id)
        voice_level = certified_ranks.get('voice', 0)
        chat_level = certified_ranks.get('chat', 0)
        
        # 다음 역할까지 필요한 경험치 계산
        next_role_info = self._get_next_role_info(current_role, current_exp)
        
        # 메인 임베드 생성
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}의 정보",
            color=0x7289da
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # 기본 정보
        role_emoji = self.role_info[current_role]['emoji']
        role_name = self.role_info[current_role]['name']
        embed.add_field(
            name="💎 현재 상태",
            value=f"**수행력:** {current_exp:,} EXP\n**역할:** {role_emoji} {role_name}",
            inline=True
        )
        
        # 다음 역할 정보
        if next_role_info:
            progress = (current_exp - self.role_info[current_role]['threshold']) / (next_role_info['threshold'] - self.role_info[current_role]['threshold'])
            progress_bar = self._create_progress_bar(progress)
            embed.add_field(
                name="🎯 다음 역할까지",
                value=f"**목표:** {next_role_info['next_role']}\n**필요:** {next_role_info['needed']:,} EXP\n{progress_bar}",
                inline=True
            )
        else:
            embed.add_field(
                name="🏆 최고 역할 달성!",
                value="축하합니다! 🎉",
                inline=True
            )
            
        # 랭크 정보 추가
        rank_info = f"🎤 **보이스:** {voice_level}레벨\n💬 **채팅:** {chat_level}레벨"
        
        # 다음 보상 레벨 계산
        def get_next_reward_level(current_level):
            return ((current_level // 5) + 1) * 5
        
        voice_next = get_next_reward_level(voice_level)
        chat_next = get_next_reward_level(chat_level)
        
        if voice_level > 0 or chat_level > 0:
            rank_info += f"\n\n📈 **다음 보상**\n🎤 {voice_next}레벨 ({voice_next - voice_level}↑)\n💬 {chat_next}레벨 ({chat_next - chat_level}↑)"
        else:
            rank_info += f"\n\n📈 **다음 보상**\n🎤 5레벨 (5↑)\n💬 5레벨 (5↑)"
        
        embed.add_field(
            name="🏆 인증된 랭크",
            value=rank_info,
            inline=True
        )
        
        # 퀘스트 진행 현황
        quest_status = await self._get_quest_status(user_id)
        embed.add_field(
            name="📋 이번 주 퀘스트 현황",
            value=quest_status,
            inline=False
        )
        
        # 이번 주 완료 기록
        weekly_history = await self._get_weekly_quest_history(user_id)
        if weekly_history:
            embed.add_field(
                name="✅ 이번 주 완료한 퀘스트",
                value=weekly_history,
                inline=False
            )
        
        # 랭크 보상 통계 (선택적으로 추가)
        voice_rewards = (voice_level // 5) * 20
        chat_rewards = (chat_level // 5) * 20
        total_rank_exp = voice_rewards + chat_rewards
        
        if total_rank_exp > 0:
            embed.add_field(
                name="📊 랭크 보상 통계",
                value=f"랭크로 획득한 경험치: **{total_rank_exp:,} EXP**\n(보이스: {voice_rewards} + 채팅: {chat_rewards})",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='순위', aliases=['ranking', 'rank', 'leaderboard'])
    async def ranking(self, ctx, period: str = '누적'):
        """경험치 순위 조회"""
        valid_periods = ['일간', 'daily', '주간', 'weekly', '월간', 'monthly', '누적', 'total', 'all']
        
        if period not in valid_periods:
            embed = discord.Embed(
                title="❌ 잘못된 기간",
                description="사용 가능한 기간: `일간`, `주간`, `월간`, `누적`",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # 기간 정규화
        if period in ['일간', 'daily']:
            period_type = 'daily'
            period_name = '일간'
            emoji = '📅'
        elif period in ['주간', 'weekly']:
            period_type = 'weekly'
            period_name = '주간'
            emoji = '📊'
        elif period in ['월간', 'monthly']:
            period_type = 'monthly'
            period_name = '월간'
            emoji = '📈'
        else:
            period_type = 'total'
            period_name = '누적'
            emoji = '🏆'
        
        # 순위 데이터 가져오기
        rankings = await self.data_manager.get_period_rankings(period_type)
        
        if not rankings:
            embed = discord.Embed(
                title=f"{emoji} {period_name} 순위",
                description="아직 순위 데이터가 없습니다.",
                color=0x999999
            )
            await ctx.send(embed=embed)
            return
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"{emoji} {period_name} 경험치 순위",
            color=0xffd700
        )
        
        rank_emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 17
        
        # 사용자의 순위 찾기
        user_rank = None
        user_exp = None
        for i, (user_id, exp, role) in enumerate(rankings, 1):
            if user_id == ctx.author.id:
                user_rank = i
                user_exp = exp
                break
        
        # 상위 10명 표시
        leaderboard_text = ""
        for i, (user_id, exp, role) in enumerate(rankings[:10], 1):
            try:
                user = self.bot.get_user(user_id)
                username = user.display_name if user else f"Unknown User"
                role_emoji = self.role_info.get(role, {'emoji': '❓'})['emoji']
                role_name = self.role_info.get(role, {'name': role})['name']
                
                # 현재 사용자 강조
                if user_id == ctx.author.id:
                    leaderboard_text += f"{rank_emojis[i-1]} **{i}.** **{username}** ⭐\n"
                else:
                    leaderboard_text += f"{rank_emojis[i-1]} **{i}.** {username}\n"
                
                leaderboard_text += f"   └ {exp:,} EXP ({role_emoji} {role_name})\n\n"
            except:
                continue
        
        embed.description = leaderboard_text
        
        # 사용자가 10위 밖이면 자신의 순위 표시
        if user_rank and user_rank > 10:
            embed.add_field(
                name="📍 내 순위",
                value=f"**{user_rank}위** - {ctx.author.display_name} ({user_exp:,} EXP)",
                inline=False
            )
        
        # 기간별 설명 추가
        if period_type != 'total':
            period_descriptions = {
                'daily': '오늘 획득한 경험치 기준',
                'weekly': '이번 주 획득한 경험치 기준',
                'monthly': '이번 달 획득한 경험치 기준'
            }
            embed.set_footer(text=period_descriptions[period_type])
        
        await ctx.send(embed=embed)
    
    # ===========================================
    # 유틸리티 메소드들
    # ===========================================
    
    async def _get_quest_status(self, user_id: int) -> str:
        """퀘스트 진행 현황 문자열 생성"""
        try:
            # 일일 퀘스트 진행도
            attendance_count = await self.data_manager.get_quest_count(user_id, 'daily', 'attendance', 'week')
            diary_count = await self.data_manager.get_quest_count(user_id, 'daily', 'diary', 'week')
            bbibbi_count = await self.data_manager.get_quest_count(user_id, 'daily', 'bbibbi', 'week')

            # 주간 퀘스트 완료 현황
            weekly_quests = {
                'recommend_3': '추천 3회',
                'shop_purchase': '상점 구매',
                'board_participate': '게시판 참여',
                'ping_use': '다방삐삐'
            }

            status_lines = []

            # 일일 퀘스트
            status_lines.append(f"📅 **일일 퀘스트**")
            status_lines.append(f"   출석: {attendance_count}/7 {'✅' if attendance_count >= 7 else '🔄'}")
            status_lines.append(f"   다방일지: {diary_count}/7 {'✅' if diary_count >= 7 else '🔄'}")
            # 다방삐삐(일일) 명시적으로 추가
            status_lines.append(f"   다방삐삐: {bbibbi_count}/7 {'✅' if bbibbi_count >= 7 else '🔄'} (멘션)")

            # 주간 퀘스트
            status_lines.append(f"\n📊 **주간 퀘스트**")
            for quest_key, quest_name in weekly_quests.items():
                count = await self.data_manager.get_quest_count(user_id, 'weekly', quest_key, 'week')
                status = "✅" if count > 0 else "❌"
                status_lines.append(f"   {status} {quest_name}")

            return "\n".join(status_lines)

        except Exception as e:
            self.logger.error(f"Error getting quest status: {e}")
            return "퀘스트 정보를 불러올 수 없습니다."
    
    async def _get_weekly_quest_history(self, user_id: int) -> str:
        """이번 주 완료한 퀘스트 기록"""
        try:
            week_start = self.data_manager._get_week_start()
            
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT quest_type, quest_subtype, exp_gained, completed_at
                    FROM quest_logs 
                    WHERE user_id = ? AND week_start = ?
                    ORDER BY completed_at DESC
                    LIMIT 15
                """, (user_id, week_start))
                results = await cursor.fetchall()
            
            if not results:
                return None
            
            quest_names = {
                'attendance': '출석',
                'diary': '다방일지',
                'voice_30min': '음성방 30분',
                'recommend_3': '추천 3회',
                'shop_purchase': '상점 구매',
                'board_participate': '게시판 참여',
                'ping_use': '다방삐삐',
                'attendance_4': '출석 4회 달성',
                'attendance_7': '출석 7회 달성',
                'diary_4': '다방일지 4회 달성',
                'diary_7': '다방일지 7회 달성',
                'voice_5h': '음성방 5시간',
                'voice_10h': '음성방 10시간',
                'voice_20h': '음성방 20시간'
            }
            
            history_lines = []
            total_exp = 0
            
            for quest_type, quest_subtype, exp_gained, completed_at in results:
                quest_name = quest_names.get(quest_subtype or quest_type, quest_subtype or quest_type)
                date_str = completed_at[5:10]  # MM-DD 형식
                history_lines.append(f"• {quest_name} (+{exp_gained}) - {date_str}")
                total_exp += exp_gained
            
            result = "\n".join(history_lines)
            if len(result) > 900:  # 임베드 필드 길이 제한
                result = result[:900] + "..."
            
            result += f"\n\n**이번 주 총 획득: {total_exp} EXP**"
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting weekly history: {e}")
            return None
    
    def _get_next_role_info(self, current_role: str, current_exp: int) -> Optional[Dict]:
        """다음 역할 정보 반환"""
        try:
            current_index = self.role_order.index(current_role)
            if current_index < len(self.role_order) - 1:
                next_role = self.role_order[current_index + 1]
                next_threshold = self.role_info[next_role]['threshold']
                return {
                    'next_role': f"{self.role_info[next_role]['emoji']} {self.role_info[next_role]['name']}",
                    'threshold': next_threshold,
                    'needed': next_threshold - current_exp
                }
        except ValueError:
            pass
        
        return None
    
    def _create_progress_bar(self, progress: float, length: int = 10) -> str:
        """진행률 바 생성"""
        progress = max(0, min(1, progress))  # 0-1 사이로 제한
        filled = int(progress * length)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int(progress * 100)
        return f"{bar} {percentage}%"


async def setup(bot):
    await bot.add_cog(LevelCommands(bot))
