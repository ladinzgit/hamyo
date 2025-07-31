import discord
from discord.ext import commands
from LevelDataManager import LevelDataManager
from typing import Optional, Dict, Any, List
import logging
import asyncio

class LevelChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        self.MAIN_CHAT_CHANNEL_ID = 1396829222978322608
        self.QUEST_COMPLETION_CHANNEL_ID = 1400442713605668875
        
        # 퀘스트 경험치 설정
        self.quest_exp = {
            'daily': {
                'attendance': 10,
                'diary': 8,
                'voice_30min': 15
            },
            'weekly': {
                'recommend_3': 50,
                'attendance_4': 20,
                'attendance_7': 50,
                'diary_4': 10,
                'diary_7': 30,
                'voice_5h': 50,
                'voice_10h': 70,
                'voice_20h': 100,
                'shop_purchase': 30,
                'board_participate': 25,
                'ping_use': 25
            },
            'one_time': {
                'self_intro': 50,
                'review': 80,
                'monthly_role': 100
            }
        }
        
        # 역할 승급 기준
        self.role_thresholds = {
            'hub': 0,
            'dado': 400,
            'daho': 1800,
            'dakyung': 6000
        }
        
        # 역할 순서
        self.role_order = ['hub', 'dado', 'daho', 'dakyung']
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.ensure_initialized()
        
    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")
        
    # ===========================================
    # 공통 부분 처리
    # ===========================================
    
    async def _finalize_quest_result(self, user_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
        """퀘스트 결과 공통 후처리 (메시지 출력, 역할 승급 확인)"""
        # 퀘스트 완료 메시지를 전용 채널에 전송
        await self.send_quest_completion_message(user_id, result)
        
        # 역할 승급 확인
        if result['success'] and result['exp_gained'] > 0:
            role_update = await self._check_role_upgrade(user_id)
            if role_update:
                result['role_updated'] = True
                result['new_role'] = role_update
                result['messages'].append(f"🎉 축하합니다! **{role_update}** 역할로 승급했습니다!")
                
                # 승급 메시지를 메인채팅에 전송
                await self.send_role_upgrade_message(user_id, role_update)
            else:
                result['role_updated'] = False
                result['new_role'] = None
        
        return result
    
    async def send_quest_completion_message(self, user_id: int, result: Dict[str, Any]):
        """퀘스트 완료 메시지를 전용 채널에 전송"""
        if not result['success'] or not result['messages']:
            return
        
        quest_channel = self.bot.get_channel(self.QUEST_COMPLETION_CHANNEL_ID)
        if not quest_channel:
            return
        
        try:
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            # 사용자의 현재 역할 정보 가져오기
            user_data = await self.data_manager.get_user_exp(user_id)
            current_role = user_data['current_role'] if user_data else 'hub'
            
            # 역할별 색상 가져오기
            embed_color = await self._get_role_color(current_role, quest_channel.guild)
            
            # 몽경수행 컨셉에 맞는 임베드
            embed = discord.Embed(
                title="✨ 몽경수행 - 수행 완료",
                color=embed_color
            )
            
            # 사용자 정보
            embed.set_author(
                name=f"{user.display_name}의 수행 기록",
                icon_url=user.display_avatar.url
            )
            
            # 완료한 수행들 (승급 메시지 제외)
            quest_text = ""
            for message in result['messages']:
                # 승급 관련 메시지는 제외
                if "승급" in message or "역할" in message:
                    continue
                
                quest_text += f"• {message}\n"
            
            if quest_text:  # 승급 메시지 제외 후에도 내용이 있는 경우만
                embed.add_field(
                    name="🌙 완료한 수행",
                    value=quest_text,
                    inline=False
                )
                
                # 총 획득 수행력
                if result['exp_gained'] > 0:
                    embed.add_field(
                        name="💫 획득한 수행력",
                        value=f"**+{result['exp_gained']:,}** 수행력",
                        inline=True
                    )
                
                # 완료 시간
                embed.timestamp = discord.utils.utcnow()
                
                await quest_channel.send(embed=embed)
            
        except Exception as e:
            await self.log(f"퀘스트 완료 메시지 전송 중 오류 발생: {e}")
    
            
    async def _get_role_color(self, role_name: str, guild) -> discord.Color:
        """역할 색상 가져오기"""
        # 역할 ID 매핑
        role_ids = {
            'hub': 1396829213172174890,
            'dado': 1396829213172174888,
            'daho': 1398926065111662703,
            'dakyung': 1396829213172174891
        }
        
        # 기본 색상 (역할별)
        fallback_colors = {
            'hub': discord.Color.green(),
            'dado': discord.Color.from_rgb(144, 238, 144),  # 연한 초록
            'daho': discord.Color.from_rgb(255, 182, 193),  # 연한 분홍
            'dakyung': discord.Color.from_rgb(255, 215, 0)  # 금색
        }
        
        try:
            if role_name in role_ids and guild:
                discord_role = guild.get_role(role_ids[role_name])
                if discord_role and discord_role.color.value != 0:
                    return discord_role.color
            
            return fallback_colors.get(role_name, discord.Color.purple())
        
        except Exception as e:
            await self.log(f"역할 색상 가져오기 중 오류 발생: {e}")
            return fallback_colors.get(role_name, discord.Color.purple())
        
    async def _check_role_upgrade(self, user_id: int) -> Optional[str]:
        """역할 승급 확인"""
        user_data = await self.data_manager.get_user_exp(user_id)
        if not user_data:
            return None
        
        current_exp = user_data['total_exp']
        current_role = user_data['current_role']
        
        # 현재 역할의 인덱스 찾기
        try:
            current_index = self.role_order.index(current_role)
        except ValueError:
            current_index = 0
        
        # 다음 역할들 확인
        for i in range(current_index + 1, len(self.role_order)):
            next_role = self.role_order[i]
            if current_exp >= self.role_thresholds[next_role]:
                # 역할 업데이트
                await self.data_manager.update_user_role(user_id, next_role)
                return self._get_role_display_name(next_role)
        
        return None
        
    # ===========================================
    # 출석 퀘스트 처리
    # ===========================================
    
    async def process_attendance(self, user_id: int) -> Dict[str, Any]:
        """출석 퀘스트 처리 (일간 + 주간 마일스톤)"""
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        
        try:
            # 일간 출석 퀘스트 처리
            daily_exp = self.quest_exp['daily']['attendance']
            await self.data_manager.add_exp(user_id, daily_exp, 'daily', 'attendance')
            
            result['success'] = True
            result['exp_gained'] = daily_exp
            result['quest_completed'].append('daily_attendance')
            result['messages'].append(f"📅 일일 미션: 출석 완료")
            
            # 주간 출석 마일스톤 직접 확인
            current_count = await self.data_manager.get_quest_count(user_id, 'daily', 'attendance', 'week')
            
            # 4회 달성 확인
            if current_count == 4:
                milestone_4_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'attendance_4', 'week')
                if milestone_4_count == 0:
                    bonus_exp_4 = self.quest_exp['weekly']['attendance_4']
                    await self.data_manager.add_exp(user_id, bonus_exp_4, 'weekly', 'attendance_4')
                    result['exp_gained'] += bonus_exp_4
                    result['quest_completed'].append('weekly_attendance_4')
                    result['messages'].append(f"🏆 주간 미션: 주간 출석 4회 달성")
            
            # 7회 달성 확인
            elif current_count == 7:
                # 7회 보상 지급
                milestone_7_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'attendance_7', 'week')
                if milestone_7_count == 0:
                    bonus_exp_7 = self.quest_exp['weekly']['attendance_7']
                    await self.data_manager.add_exp(user_id, bonus_exp_7, 'weekly', 'attendance_7')
                    result['exp_gained'] += bonus_exp_7
                    result['quest_completed'].append('weekly_attendance_7')
                    result['messages'].append(f"🏆 주간 미션: 주간 출석 7회 달성")
            
        except Exception as e:
            await self.log(f"출석 퀘스트 처리 중 오류 발생: {e}")
            result['messages'].append("출석 수행 처리 중 오류가 발생했습니다.")
        
        # 공통 후처리
        return await self._finalize_quest_result(user_id, result)
    
async def setup(bot):
    await bot.add_cog(LevelChecker(bot))
