import discord
from discord.ext import commands
from src.core.LevelDataManager import LevelDataManager
from typing import Optional, Dict, Any, List
import logging
import asyncio
import datetime
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

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
                'bbibbi': 5,
                'call': 3,
                'friend': 3
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
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.ensure_initialized()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        
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
        """퀘스트 결과 공통 후처리 (이벤트 발생)"""
        # 이벤트를 발생시켜 LevelSystem에서 처리하도록 함
        self.bot.dispatch('quest_completion', user_id, result)
        return result

        
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
            result['messages'].append(f"📅 출석 수행 완료! **+{daily_exp} 다공**")
            
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
                    result['messages'].append(f"🏆 주간 출석 4회 달성! **+{bonus_exp_4} 다공**")
            
            # 7회 달성 확인
            elif current_count == 7:
                # 7회 보상 지급
                milestone_7_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'attendance_7', 'week')
                if milestone_7_count == 0:
                    bonus_exp_7 = self.quest_exp['weekly']['attendance_7']
                    await self.data_manager.add_exp(user_id, bonus_exp_7, 'weekly', 'attendance_7')
                    result['exp_gained'] += bonus_exp_7
                    result['quest_completed'].append('weekly_attendance_7')
                    result['messages'].append(f"🏆 주간 출석 7회 달성! **+{bonus_exp_7} 다공**")
            
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
        """메시지 이벤트 리스너 - 다방일지/삐삐/게시판 퀘스트 감지"""
        # 봇 메시지 무시
        if message.author.bot:
            return

        # 스레드 채널 무시
        if isinstance(message.channel, discord.Thread):
            return

        # 시스템 메시지 무시 (스레드 생성, 핀 추가 등)
        if message.type != discord.MessageType.default:
            return

        # --- 삐삐 퀘스트 감지 ---
        CALL_CHANNEL_ID = 1453179899568324700
        CALL_ROLE_ID = 1452283108979118196
        FRIEND_CHANNEL_ID = 1453179765237223676
        FRIEND_ROLE_ID = 1396829213163520021

        if message.channel.id == CALL_CHANNEL_ID and any(role.id == CALL_ROLE_ID for role in message.role_mentions):
            user_id = message.author.id
            result = await self.process_call(user_id)
            if result.get('success'):
                await message.add_reaction('<:BM_r_008:1445392406332575804>')
                return

        if message.channel.id == FRIEND_CHANNEL_ID and any(role.id == FRIEND_ROLE_ID for role in message.role_mentions):
            user_id = message.author.id
            result = await self.process_friend(user_id)
            if result.get('success'):
                await message.add_reaction('<:BM_r_008:1445392406332575804>')
                return
        
        # --- 다방일지 퀘스트 감지 ---
        if message.channel.id == self.DIARY_CHANNEL_ID:
            # 최소 길이 체크 (5자 이상)
            if len(message.content.strip()) >= 5:
                user_id = message.author.id

                try:
                    # get_quest_count로 오늘 작성했는지 확인 (0 또는 1 반환)
                    today_count = await self.data_manager.get_quest_count(
                        user_id, 
                        quest_type='daily', 
                        quest_subtype='diary',
                        timeframe='day'
                    )

                    if today_count > 0:
                        return  # 오늘 이미 작성함
                    
                    # 다방일지 퀘스트 처리
                    result = await self.process_diary(user_id)
                    
                    # 성공 시 반응 추가
                    if result['success']:
                        await message.add_reaction('<:BM_j_010:1399387534101843978>')
                except Exception as e:
                    await self.log(f"다방일지 처리 중 오류 발생: {e}")

        # --- 게시판 퀘스트 감지 ---
        BOARD_CATEGORY_ID = 1396829223267598348
        
        if hasattr(message.channel, 'category_id') and message.channel.category_id == BOARD_CATEGORY_ID:
            try:
                user_id = message.author.id
                result = await self.process_board(user_id)
                await message.add_reaction('<:BM_k_008:1399387531534930063>')
                
                if not result.get('success'):
                    await self.log(f"게시판 퀘스트 처리 결과: {result}")
            except Exception as e:
                await self.log(f"게시판 퀘스트 처리 중 오류 발생: {e}")

    async def process_call(self, user_id: int) -> Dict[str, Any]:
        """전화하자 일일 퀘스트 처리"""
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # get_quest_count로 오늘 이미 지급했는지 확인
            today_count = await self.data_manager.get_quest_count(
                user_id,
                quest_type='daily',
                quest_subtype='call',
                timeframe='day'
            )
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['call']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'call')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_call')
            result['messages'].append(f"📢 전화하자 퀘스트 완료! **+{exp} 다공**")
        except Exception as e:
            await self.log(f"전화하자 퀘스트 처리 중 오류: {e}")
            result['messages'].append("전화하자 퀘스트 처리 중 오류가 발생했습니다.")
        return await self._finalize_quest_result(user_id, result)

    async def process_friend(self, user_id: int) -> Dict[str, Any]:
        """친구하자 일일 퀘스트 처리"""
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # get_quest_count로 오늘 이미 지급했는지 확인
            today_count = await self.data_manager.get_quest_count(
                user_id,
                quest_type='daily',
                quest_subtype='friend',
                timeframe='day'
            )
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['friend']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'friend')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_friend')
            result['messages'].append(f"📢 친구하자 퀘스트 완료! **+{exp} 다공**")
        except Exception as e:
            await self.log(f"친구하자 퀘스트 처리 중 오류: {e}")
            result['messages'].append("친구하자 퀘스트 처리 중 오류가 발생했습니다.")
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
            result['messages'].append(f"📝 일지 수행 완료! **+{daily_exp} 다공**")
            
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
                    result['messages'].append(f"🏆 주간 일지 4회 달성! **+{bonus_exp_4} 다공**")
            
            # 7회 달성 확인
            elif current_count == 7:
                # 4회 보상이 없다면 먼저 지급
                milestone_4_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'diary_4', 'week')
                if milestone_4_count == 0:
                    bonus_exp_4 = self.quest_exp['weekly']['diary_4']
                    await self.data_manager.add_exp(user_id, bonus_exp_4, 'weekly', 'diary_4')
                    result['exp_gained'] += bonus_exp_4
                    result['quest_completed'].append('weekly_diary_4')
                    result['messages'].append(f"🏆 주간 일지 4회 달성! **+{bonus_exp_4} 다공**")
                
                # 7회 보상 지급
                milestone_7_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'diary_7', 'week')
                if milestone_7_count == 0:
                    bonus_exp_7 = self.quest_exp['weekly']['diary_7']
                    await self.data_manager.add_exp(user_id, bonus_exp_7, 'weekly', 'diary_7')
                    result['exp_gained'] += bonus_exp_7
                    result['quest_completed'].append('weekly_diary_7')
                    result['messages'].append(f"🏆 주간 일지 7회 달성! **+{bonus_exp_7} 다공**")
            
        except Exception as e:
            await self.log(f"다방일지 처리 중 오류 발생: {e}")
        
        return await self._finalize_quest_result(user_id, result)
    
    async def process_board(self, user_id: int) -> Dict[str, Any]:
        """
        게시판 참여 시 호출: 주간 게시판 3회 달성 시 경험치 지급
        on_message에서 특정 카테고리에 글 작성 시 호출됨.
        """
        await self.data_manager.ensure_initialized()
        result = {
            'success': False,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        try:
            # 게시판 참여 기록 (quest_logs에 'weekly', 'board_participate'로 기록)
            async with self.data_manager.db_connect() as db:
                week_start = self.data_manager._get_week_start()
                await db.execute("""
                    INSERT INTO quest_logs (user_id, quest_type, quest_subtype, exp_gained, week_start)
                    VALUES (?, 'weekly', 'board_participate', 0, ?)
                """, (user_id, week_start))
                await db.commit()

            # 이번 주 게시판 참여 횟수 확인
            board_count = await self.data_manager.get_quest_count(user_id, 'weekly', 'board_participate', 'week')

            # 이미 보상 지급 여부 확인
            already_rewarded = await self.data_manager.get_quest_count(user_id, 'weekly', 'board_participate_3', 'week') > 0

            if board_count >= 3 and not already_rewarded:
                exp = self.quest_exp['weekly']['board_participate']
                await self.data_manager.add_exp(user_id, exp, 'weekly', 'board_participate_3')
                result['success'] = True
                result['exp_gained'] = exp
                result['quest_completed'].append('weekly_board_participate_3')
                result['messages'].append(f"📝 주간 게시판 3회 작성 달성! **+{exp} 다공**")
                # 공통 후처리(메시지, 승급 등)
                return await self._finalize_quest_result(user_id, result)
        except Exception as e:
            await self.log(f"게시판 퀘스트 처리 중 오류: {e}")
            result['messages'].append("게시판 퀘스트 처리 중 오류가 발생했습니다.")
        return result

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
                today_kst = datetime.now(KST).strftime("%Y-%m-%d")
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM quest_logs
                    WHERE user_id = ? AND quest_type = 'daily' AND quest_subtype = 'voice_30min'
                      AND DATE(completed_at, '+9 hours') = ?
                """, (user_id, today_kst))
                today_count = (await cursor.fetchone())[0]
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['voice_30min']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'voice_30min')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_voice_30min')
            result['messages'].append(f"🔊 음성방 30분 수행 완료! **+{exp} 다공**")
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
            result['messages'].append(f"🏆 음성방 {hour}시간(주간) 수행 완료! **+{exp} 다공**")
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
                result['messages'].append(f"🌱 주간 추천 3회 달성! **+{exp} 다공**")
                # 공통 후처리(메시지, 승급 등)
                return await self._finalize_quest_result(user_id, result)
        except Exception as e:
            await self.log(f"추천 퀘스트 처리 중 오류: {e}")
            result['messages'].append("추천 퀘스트 처리 중 오류가 발생했습니다.")
        
        return await self._finalize_quest_result(user_id, result)



    async def is_valid_quest(self, quest_type: str) -> bool:
        # quest_exp의 모든 카테고리에서 퀘스트명 확인
        for category in self.quest_exp:
            if quest_type in self.quest_exp[category]:
                return True
        return False

    async def get_all_quest_types(self) -> dict:
        # quest_exp 딕셔너리 반환
        return self.quest_exp

    async def process_quest(self, user_id: int, quest_type: str) -> dict:
        # quest_type에 따라 해당 퀘스트 처리 메소드 호출
        # 예시: self_intro, review 등 one_time 퀘스트
        if quest_type in self.quest_exp.get('daily', {}):
            # ...일일 퀘스트 처리...
            pass
        elif quest_type in self.quest_exp.get('weekly', {}):
            # board_participate, shop_purchase만 처리
            if quest_type in ['board_participate', 'shop_purchase']:
                # 이미 이번 주에 완료했는지 확인
                week_count = await self.data_manager.get_quest_count(
                    user_id, 'weekly', quest_type, 'week'
                )
                result = {
                    'success': False,
                    'exp_gained': 0,
                    'messages': [],
                    'quest_completed': []
                }
                if week_count > 0:
                    result['messages'].append("이미 이번 주에 완료한 퀘스트입니다.")
                    return result
                exp = self.quest_exp['weekly'][quest_type]
                await self.data_manager.add_exp(user_id, exp, 'weekly', quest_type)
                result['success'] = True
                result['exp_gained'] = exp
                result['quest_completed'].append(quest_type)
                result['messages'].append(f"✨ {quest_type} 주간 퀘스트 완료! **+{exp} 다공**")
                return await self._finalize_quest_result(user_id, result)
            else:
                # 그 외 weekly는 강제 완료 불가
                return {
                    'success': False,
                    'exp_gained': 0,
                    'messages': ["이 주간 퀘스트는 강제 완료가 지원되지 않습니다."],
                    'quest_completed': []
                }
        elif quest_type in self.quest_exp.get('one_time', {}):
            # 일회성 퀘스트 처리
            already = await self.data_manager.is_one_time_quest_completed(user_id, quest_type)
            result = {
                'success': False,
                'exp_gained': 0,
                'messages': [],
                'quest_completed': []
            }
            if already:
                result['messages'].append("이미 완료한 일회성 퀘스트입니다.")
                return result
            exp = self.quest_exp['one_time'][quest_type]
            await self.data_manager.mark_one_time_quest_completed(user_id, quest_type)
            await self.data_manager.add_exp(user_id, exp, 'one_time', quest_type)
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append(quest_type)
            result['messages'].append(f"✨ {quest_type} 일회성 퀘스트 완료! **+{exp} 다공**")
            return await self._finalize_quest_result(user_id, result)
        elif quest_type.startswith("rank_voice_") or quest_type.startswith("rank_chat_"):
            # 보이스/채팅 랭크 인증 보상 (ex: rank_voice_8_15)
            try:
                parts = quest_type.split("_")
                rank_type = parts[1]  # 'voice' or 'chat'
                old = int(parts[2])
                new = int(parts[3])
            except Exception:
                return {
                    'success': False,
                    'exp_gained': 0,
                    'messages': ["잘못된 랭크 퀘스트명입니다."],
                    'quest_completed': []
                }
            result = {
                'success': False,
                'exp_gained': 0,
                'messages': [],
                'quest_completed': []
            }
            # 5레벨 단위로 지급
            reward_levels = []
            next_reward = ((old // 5) + 1) * 5
            while next_reward <= new:
                reward_levels.append(next_reward)
                next_reward += 5
            exp_per_reward = 20
            for level in reward_levels:
                quest_key = f"rank_{rank_type}_{level}"
                already_completed = await self.data_manager.is_one_time_quest_completed(user_id, quest_key)
                if not already_completed:
                    await self.data_manager.mark_one_time_quest_completed(user_id, quest_key)
                    await self.data_manager.add_exp(user_id, exp_per_reward, 'one_time', quest_key)
                    result['exp_gained'] += exp_per_reward
                    result['quest_completed'].append(quest_key)
                    result['messages'].append(
                        f"{'보이스' if rank_type == 'voice' else '채팅'} {level}레벨 달성 보상! **+{exp_per_reward} 다공**"
                    )
            if result['exp_gained'] > 0:
                result['success'] = True
            else:
                result['messages'].append("받을 수 있는 보상이 없습니다. (이미 지급되었거나 달성하지 못함)")
            return await self._finalize_quest_result(user_id, result)
        elif quest_type.startswith("rank_"):
            # ...기존 rank_ 처리...
            try:
                level = int(quest_type.split("_")[1])
            except Exception:
                return {
                    'success': False,
                    'exp_gained': 0,
                    'messages': ["잘못된 랭크 퀘스트명입니다."],
                    'quest_completed': []
                }
            # 일회성 퀘스트로 처리
            already_completed = await self.data_manager.is_one_time_quest_completed(user_id, quest_type)
            result = {
                'success': False,
                'exp_gained': 0,
                'messages': [],
                'quest_completed': []
            }
            if already_completed:
                result['messages'].append("이미 완료한 랭크 퀘스트입니다.")
                return result
            exp_per_reward = 20
            await self.data_manager.mark_one_time_quest_completed(user_id, quest_type)
            await self.data_manager.add_exp(user_id, exp_per_reward, 'one_time', quest_type)
            result['success'] = True
            result['exp_gained'] = exp_per_reward
            result['quest_completed'].append(quest_type)
            result['messages'].append(f"랭크 {level}레벨 달성 보상! **+{exp_per_reward} 다공**")
            return await self._finalize_quest_result(user_id, result)
        else:
            return {
                'success': False,
                'exp_gained': 0,
                'messages': ["존재하지 않는 퀘스트입니다."],
                'quest_completed': []
            }
        
async def setup(bot):
    await bot.add_cog(LevelChecker(bot))
