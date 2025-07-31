import discord
from discord.ext import commands
from LevelDataManager import LevelDataManager
from typing import Optional, Dict, Any, List
import logging
import asyncio
import datetime

class LevelChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        self.MAIN_CHAT_CHANNEL_ID = 1396829222978322608
        self.QUEST_COMPLETION_CHANNEL_ID = 1400442713605668875
        self.DIARY_CHANNEL_ID = 1396829222978322609
        
        # 퀘스트 경험치 설정
        self.quest_exp = {
            'daily': {
                'attendance': 10,
                'diary': 5,
                'voice_30min': 15,
                'bbibbi': 5
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
            result['messages'].append(f"📅 출석 수행 완료! **+{daily_exp} 수행력**")
            
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
                    result['messages'].append(f"🏆 주간 출석 4회 달성! **+{bonus_exp_4} 수행력**")
            
            # 7회 달성 확인
            elif current_count == 7:
                # 7회 보상 지급
                milestone_7_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'attendance_7', 'week')
                if milestone_7_count == 0:
                    bonus_exp_7 = self.quest_exp['weekly']['attendance_7']
                    await self.data_manager.add_exp(user_id, bonus_exp_7, 'weekly', 'attendance_7')
                    result['exp_gained'] += bonus_exp_7
                    result['quest_completed'].append('weekly_attendance_7')
                    result['messages'].append(f"🏆 주간 출석 7회 달성! **+{bonus_exp_7} 수행력**")
            
        except Exception as e:
            await self.log(f"출석 퀘스트 처리 중 오류 발생: {e}")
            result['messages'].append("출석 수행 처리 중 오류가 발생했습니다.")
        
        # 공통 후처리
        return await self._finalize_quest_result(user_id, result)
    
    # ===========================================
    # 다방일지 퀘스트 처리
    # ===========================================
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """메시지 이벤트 리스너 - 다방일지/삐삐 퀘스트 감지"""
        # 봇 메시지 무시
        if message.author.bot:
            return

        # --- 삐삐 퀘스트 감지 ---
        BBIBBI_CHANNEL_ID = 1396829223267598346
        BBIBBI_ROLE_ID = 1396829213163520021
        if message.channel.id == BBIBBI_CHANNEL_ID:
            # 역할 멘션이 포함되어 있는지 확인
            if any(role.id == BBIBBI_ROLE_ID for role in message.role_mentions):
                user_id = message.author.id
                result = await self.process_bbibbi(user_id)
                if result['success']:
                    await message.add_reaction('📢')
                return  # 삐삐 퀘스트 감지 시 다방일지 체크는 하지 않음

        # --- 다방일지 퀘스트 감지 ---
        if not self.DIARY_CHANNEL_ID or message.channel.id != self.DIARY_CHANNEL_ID:
            return
        
        # 메시지 길이 체크 (5자 이상)
        if len(message.content.strip()) < 5:
            return
        
        user_id = message.author.id
        
        try:
            # 오늘 작성한 다방일지가 있는지 확인
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs 
                    WHERE user_id = ? AND quest_type = 'daily' AND quest_subtype = 'diary' 
                    AND DATE(completed_at) = DATE('now')
                """, (user_id,))
                today_count = (await cursor.fetchone())[0]
            
            if today_count > 0:
                return  # 오늘 이미 작성함
            
            # 다방일지 퀘스트 처리
            result = await self.process_diary(user_id)
            
            # 성공 시 반응 추가
            if result['success']:
                await message.add_reaction('<:BM_j_010:1399387534101843978>')
            
        except Exception as e:
            self.logger.error(f"다방일지 처리 중 오류 발생: {e}")

    async def process_bbibbi(self, user_id: int) -> Dict[str, Any]:
        """삐삐(특정 역할 멘션) 일일 퀘스트 처리"""
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # 오늘 이미 지급했는지 확인
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs
                    WHERE user_id = ? AND quest_type = 'daily' AND quest_subtype = 'bbibbi'
                      AND DATE(completed_at) = DATE('now')
                """, (user_id,))
                today_count = (await cursor.fetchone())[0]
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['bbibbi']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'bbibbi')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_bbibbi')
            result['messages'].append(f"📢 삐삐 퀘스트 완료! **+{exp} 수행력**")
        except Exception as e:
            await self.log(f"삐삐 퀘스트 처리 중 오류: {e}")
            result['messages'].append("삐삐 퀘스트 처리 중 오류가 발생했습니다.")
        return await self._finalize_quest_result(user_id, result)

    async def process_diary(self, user_id: int) -> Dict[str, Any]:
        """다방일지 퀘스트 처리 (일간 + 주간 마일스톤)"""
        await self.data_manager.ensure_initialized()
        
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        
        try:
            # 일간 다방일지 퀘스트 처리
            daily_exp = self.quest_exp['daily']['diary']
            await self.data_manager.add_exp(user_id, daily_exp, 'daily', 'diary')
            
            result['success'] = True
            result['exp_gained'] = daily_exp
            result['quest_completed'].append('daily_diary')
            result['messages'].append(f"📝 일지 수행 완료! **+{daily_exp} 수행력**")
            
            # 주간 다방일지 마일스톤 직접 확인
            current_count = await self.data_manager.get_quest_count(user_id, 'daily', 'diary', 'week')
            
            # 4회 달성 확인
            if current_count == 4:
                milestone_4_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'diary_4', 'week')
                if milestone_4_count == 0:
                    bonus_exp_4 = self.quest_exp['weekly']['diary_4']
                    await self.data_manager.add_exp(user_id, bonus_exp_4, 'weekly', 'diary_4')
                    result['exp_gained'] += bonus_exp_4
                    result['quest_completed'].append('weekly_diary_4')
                    result['messages'].append(f"🏆 주간 일지 4회 달성! **+{bonus_exp_4} 수행력**")
            
            # 7회 달성 확인
            elif current_count == 7:
                # 4회 보상이 없다면 먼저 지급
                milestone_4_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'diary_4', 'week')
                if milestone_4_count == 0:
                    bonus_exp_4 = self.quest_exp['weekly']['diary_4']
                    await self.data_manager.add_exp(user_id, bonus_exp_4, 'weekly', 'diary_4')
                    result['exp_gained'] += bonus_exp_4
                    result['quest_completed'].append('weekly_diary_4')
                    result['messages'].append(f"🏆 주간 일지 4회 달성! **+{bonus_exp_4} 수행력**")
                
                # 7회 보상 지급
                milestone_7_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'diary_7', 'week')
                if milestone_7_count == 0:
                    bonus_exp_7 = self.quest_exp['weekly']['diary_7']
                    await self.data_manager.add_exp(user_id, bonus_exp_7, 'weekly', 'diary_7')
                    result['exp_gained'] += bonus_exp_7
                    result['quest_completed'].append('weekly_diary_7')
                    result['messages'].append(f"🏆 주간 일지 7회 달성! **+{bonus_exp_7} 수행력**")
            
        except Exception as e:
            self.logger.error(f"Error processing diary for user {user_id}: {e}")
            result['messages'].append("일지 수행 처리 중 오류가 발생했습니다.")
        
        return await self._finalize_quest_result(user_id, result)
    
    # ===========================================
    # 음성방 퀘스트 처리
    # ===========================================

    async def process_voice_30min(self, user_id: int) -> dict:
        """
        음성방 30분 일일 퀘스트 처리 (중복 지급 방지)
        """
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # 오늘 이미 지급했는지 확인
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs
                    WHERE user_id = ? AND quest_type = 'daily' AND quest_subtype = 'voice_30min'
                      AND DATE(completed_at) = DATE('now')
                """, (user_id,))
                today_count = (await cursor.fetchone())[0]
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['voice_30min']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'voice_30min')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_voice_30min')
            result['messages'].append(f"🔊 음성방 30분 수행 완료! **+{exp} 수행력**")
        except Exception as e:
            await self.log(f"음성 30분 퀘스트 처리 중 오류: {e}")
            result['messages'].append("음성 30분 퀘스트 처리 중 오류가 발생했습니다.")
        return await self._finalize_quest_result(user_id, result)

    async def process_voice_weekly(self, user_id: int, hour: int) -> dict:
        """
        음성방 주간 5/10/20시간 퀘스트 처리 (중복 지급 방지)
        hour: 5, 10, 20 중 하나
        """
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        quest_map = {5: 'voice_5h', 10: 'voice_10h', 20: 'voice_20h'}
        if hour not in quest_map:
            return result
        quest_subtype = quest_map[hour]
        try:
            # 이번 주 이미 지급했는지 확인
            week_start = self.data_manager._get_week_start()
            async with self.data_manager.db_connect() as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs
                    WHERE user_id = ? AND quest_type = 'weekly' AND quest_subtype = ? AND week_start = ?
                """, (user_id, quest_subtype, week_start))
                week_count = (await cursor.fetchone())[0]
            if week_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['weekly'][quest_subtype]
            await self.data_manager.add_exp(user_id, exp, 'weekly', quest_subtype)
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append(f'weekly_{quest_subtype}')
            result['messages'].append(f"🏆 음성방 {hour}시간(주간) 수행 완료! **+{exp} 수행력**")
        except Exception as e:
            await self.log(f"음성 {hour}시간 퀘스트 처리 중 오류: {e}")
            result['messages'].append(f"음성 {hour}시간 퀘스트 처리 중 오류가 발생했습니다.")
        return await self._finalize_quest_result(user_id, result)
    
    async def process_recommend_quest(self, user_id: int, count: int = 1) -> Dict[str, Any]:
        """
        추천 인증 시 호출: 주간 추천 3회 달성 시 경험치 지급
        Economy.py에서 '추천' 인증마다 호출됨.
        """
        await self.data_manager.ensure_initialized()
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # 추천 인증 기록 (quest_logs에 'weekly', 'recommend'로 count만큼 기록)
            async with self.data_manager.db_connect() as db:
                week_start = self.data_manager._get_week_start()
                for _ in range(count):
                    await db.execute("""
                        INSERT INTO quest_logs (user_id, quest_type, quest_subtype, exp_gained, week_start)
                        VALUES (?, 'weekly', 'recommend', 0, ?)
                    """, (user_id, week_start))
                await db.commit()

            # 이번 주 추천 인증 횟수 확인
            recommend_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'recommend', 'week')

            # 이미 보상 지급 여부 확인
            already_rewarded = await self.data_manager.get_quest_count(user_id, 'weekly', 'recommend_3', 'week') > 0

            if recommend_count >= 3 and not already_rewarded:
                exp = self.quest_exp['weekly']['recommend_3']
                await self.data_manager.add_exp(user_id, exp, 'weekly', 'recommend_3')
                result['success'] = True
                result['exp_gained'] = exp
                result['quest_completed'].append('weekly_recommend_3')
                result['messages'].append(f"🌱 주간 추천 3회 달성! **+{exp} 수행력**")
                # 공통 후처리(메시지, 승급 등)
                return await self._finalize_quest_result(user_id, result)
        except Exception as e:
            await self.log(f"추천 퀘스트 처리 중 오류: {e}")
            result['messages'].append("추천 퀘스트 처리 중 오류가 발생했습니다.")
        return result

async def setup(bot):
    await bot.add_cog(LevelChecker(bot))
