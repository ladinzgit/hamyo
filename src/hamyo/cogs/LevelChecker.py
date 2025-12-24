import discord
from discord.ext import commands
from LevelDataManager import LevelDataManager
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
        
        self.ROLE_IDS = {
            'hub': 1396829213172174890,
            'dado': 1396829213172174888,
            'daho': 1398926065111662703,
            'dakyung': 1396829213172174891
        }
        
        self.ROLE_DISPLAY = {
            'hub': '허브',
            'dado': '다도',
            'daho': '다호',
            'dakyung': '다경'
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
        """퀘스트 결과 공통 후처리 (메시지 출력, 역할 승급 확인)"""
        # 퀘스트 완료 메시지를 전용 채널에 전송
        await self.send_quest_completion_message(user_id, result)

        # 역할 승급 확인
        if result['success'] and result['exp_gained'] > 0:
            role_key = await self._check_role_upgrade(user_id)  # 키 반환
            if role_key:
                display = self._get_role_display_name(role_key)
                result['role_updated'] = True
                result['new_role'] = display
                result['messages'].append(f"🎉 축하합니다! **{display}** 역할로 승급했습니다!")
                # 승급 메시지를 메인채팅에 전송 (키로 호출)
                await self.send_role_upgrade_message(user_id, role_key)
            else:
                result['role_updated'] = False
                result['new_role'] = None

        # 다른 Cog로 이벤트 전파 (TreeCommand 등에서 수신)
        if result.get('quest_completed'):
             quest_channel = self.bot.get_channel(self.QUEST_COMPLETION_CHANNEL_ID)
             for quest_name in result['quest_completed']:
                 self.bot.dispatch('mission_completion', user_id, quest_name, quest_channel)

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
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
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
                        name="💫 획득한 다공",
                        value=f"**+{result['exp_gained']:,} 다공**",
                        inline=True
                    )
                
                # 완료 시간
                embed.timestamp = discord.utils.utcnow()
                
                # 멘션과 embed를 동시에 전송
                await quest_channel.send(content=user.mention, embed=embed)
            
        except Exception as e:
            await self.log(f"퀘스트 완료 메시지 전송 중 오류 발생: {e}")
            
    async def send_role_upgrade_message(self, user_id: int, new_role_key: str):
        """
        승급 축하 브로드캐스트 (텍스트 아트 버전)
        - {mention} 플레이스홀더를 실제 멘션으로 치환
        - dado/daho/dakyung 별 전용 문구 전송
        """
        try:
            channel = self.bot.get_channel(self.MAIN_CHAT_CHANNEL_ID)
            if channel is None:
                await self.log("메인 채널을 찾을 수 없어 승급 메시지 전송 실패")
                return

            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if user is None:
                await self.log(f"승급 메시지: 유저 캐시/페치 실패 (user_id={user_id})")
                return

            # 역할별 메시지 템플릿
            templates = {
                "dado": (
                    ".  ◜◝--◜◝\n"
                    "꒰   ˶ ´  ତ ` ˶꒱\n"
                    "✦ ╮ {mention} 님, 다도로 승급했어요 !\n"
                    "│\n"
                    "│ ⠀차향이 스며든 꿈의 첫 단계에 발을 들였어요 ˎˊ˗ \n"
                    "│ ⠀따뜻한 차 한 잔처럼 마음이 편안해지는\n"
                    "│    수행의 길이 시작되었습니다 <:BM_k_005:1399387515626197092>\n"
                    "│\n"
                    " ╰ ⊱ ─ · ─ · ─ · ─ ·  ─ · ─ · ─ · ─ · ─ · ─ · ─ "
                ),
                "daho": (
                    ".  ◜◝--◜◝\n"
                    "꒰   ˶ ´  ତ ` ˶꒱\n"
                    "✦ ╮  {mention} 님, 다호로 승급했어요 !\n"
                    "│\n"
                    "│ ⠀꿈과 현실 사이의 경계를 넘나드는 자가 되었어요 ˎˊ˗ \n"
                    "│ ⠀벚꽃잎처럼 흩날리는 몽환 속에서\n"
                    "│    더 깊은 수행의 세계가 펼쳐집니다 <:BM_k_002:1399387517668819065>\n"
                    "│\n"
                    " ╰ ⊱ ─ · ─ · ─ · ─ ·  ─ · ─ · ─ · ─ · ─ · ─ · ─"
                ),
                "dakyung": (
                    ".  ◜◝--◜◝\n"
                    "꒰   ˶ ´  ତ ` ˶꒱\n"
                    "✦ ╮ {mention} 님, 다경으로 승급했어요 !\n"
                    "│\n"
                    "│ ⠀몽경의 깊은 경지에 이른 진정한 수행자가 되었어요 ˎˊ˗ \n"
                    "│ ⠀별빛처럼 빛나는 지혜로 다른 이들을\n"
                    "│    꿈길로 인도하는 대가의 경지입니다 <:BM_k_003:1399387520135069770>\n"
                    "│\n"
                    " ╰ ⊱ ─ · ─ · ─ · ─ ·  ─ · ─ · ─ · ─ · ─ · ─ · ─"
                ),
            }

            template = templates.get(new_role_key)
            if template is None:
                # 알 수 없는 키면 간단한 기본 문구
                display = self._get_role_display_name(new_role_key)
                content = f"{user.mention} 님, {display}로 승급했어요! 🎉"
            else:
                content = template.replace("{mention}", user.mention)

            # 멘션 허용 범위: 해당 유저만
            allowed = discord.AllowedMentions(everyone=False, roles=False, users=[user])

            await channel.send(content, allowed_mentions=allowed)

        except Exception as e:
            await self.log(f"승급 메시지 전송 중 오류: {e}")
            
    async def _get_role_color(self, role_name: str, guild) -> discord.Color:
        """역할 색상 가져오기""" 
        # 기본 색상 (역할별)
        fallback_colors = {
            'hub': discord.Color.green(),
            'dado': discord.Color.from_rgb(144, 238, 144),  # 연한 초록
            'daho': discord.Color.from_rgb(255, 182, 193),  # 연한 분홍
            'dakyung': discord.Color.from_rgb(255, 215, 0)  # 금색
        }
        
        try:
            if role_name in self.ROLE_IDS and guild:
                discord_role = guild.get_role(self.ROLE_IDS[role_name])
                if discord_role and discord_role.color.value != 0:
                    return discord_role.color
            
            return fallback_colors.get(role_name, discord.Color.purple())
        
        except Exception as e:
            await self.log(f"역할 색상 가져오기 중 오류 발생: {e}")
            return fallback_colors.get(role_name, discord.Color.purple())
        
    async def _check_role_upgrade(self, user_id: int) -> Optional[str]:
        """역할 승급 확인(최고 도달 등급으로 즉시 반영 + 길드 역할 부여)"""
        user_data = await self.data_manager.get_user_exp(user_id)
        if not user_data:
            return None

        current_exp = user_data['total_exp']
        current_role = user_data['current_role']

        # 현재 인덱스
        try:
            current_idx = self.role_order.index(current_role)
        except ValueError:
            current_idx = 0

        # 도달한 '최고' 역할 찾기
        target_role_key = None
        for role_key in reversed(self.role_order):
            if current_exp >= self.role_thresholds.get(role_key, 0):
                target_role_key = role_key
                break

        # 현재보다 높은 역할이면 업데이트
        if target_role_key and self.role_order.index(target_role_key) > current_idx:
            await self.data_manager.update_user_role(user_id, target_role_key)
            # 실제 길드 역할 적용
            await self._apply_role_update(user_id, target_role_key, previous_role_key=current_role)
            return target_role_key

        return None
    
    def _get_role_display_name(self, role_key: str) -> str:
        """역할 키 -> 한글 표시명"""
        return self.ROLE_DISPLAY.get(role_key, role_key)

    async def _get_home_guild(self):
        """메시지를 보낼 메인 길드 탐색(메인채널→퀘채널→첫 길드)"""
        guild = None
        ch = self.bot.get_channel(self.MAIN_CHAT_CHANNEL_ID)
        if ch and ch.guild:
            guild = ch.guild
        if guild is None:
            ch = self.bot.get_channel(self.QUEST_COMPLETION_CHANNEL_ID)
            if ch and ch.guild:
                guild = ch.guild
        if guild is None and self.bot.guilds:
            guild = self.bot.guilds[0]
        return guild

    async def _safe_fetch_member(self, guild, user_id: int):
        """guild에서 멤버 안전 조회 (캐시→fetch)"""
        if guild is None:
            return None
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except Exception:
            return None

    async def _apply_role_update(self, user_id: int, new_role_key: str, previous_role_key: str) -> bool:
        """
        길드 역할 실제 부여/제거.
        규칙:
          - hub→dado 진입: hub 제거, dado 지급
          - daho/dakyung 진입: 중복 지급(기존 역할 유지)
        """
        try:
            guild = await self._get_home_guild()
            member = await self._safe_fetch_member(guild, user_id)
            if not guild or not member:
                await self.log(f"역할 갱신 실패: 길드/멤버를 찾을 수 없음 (user_id={user_id})")
                return False

            # 대상 역할 객체
            target_role_id = self.ROLE_IDS.get(new_role_key)
            if not target_role_id:
                await self.log(f"역할 갱신 실패: 매핑에 없는 역할 {new_role_key}")
                return False

            target_role = guild.get_role(target_role_id)
            if not target_role:
                await self.log(f"역할 갱신 실패: 서버에 존재하지 않는 역할 ID {target_role_id} ({new_role_key})")
                return False

            # hub → dado 특수 규칙
            if previous_role_key == 'hub' and new_role_key == 'dado':
                hub_role_id = self.ROLE_IDS.get('hub')
                if hub_role_id:
                    hub_role = guild.get_role(hub_role_id)
                    if hub_role and hub_role in member.roles:
                        try:
                            await member.remove_roles(hub_role, reason="승급: hub→dado")
                        except Exception as e:
                            await self.log(f"hub 제거 실패: {e}")

            # 새 역할 부여(중복 허용)
            if target_role not in member.roles:
                try:
                    await member.add_roles(target_role, reason=f"승급: {new_role_key}")
                except Exception as e:
                    await self.log(f"역할 부여 실패({new_role_key}): {e}")
                    return False

            return True

        except Exception as e:
            await self.log(f"_apply_role_update 오류: {e}")
            return False
        
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
        BBIBBI_CHANNEL_ID = 1396829223267598346
        BBIBBI_ROLE_ID = 1396829213163520021
        
        if message.channel.id == BBIBBI_CHANNEL_ID and any(role.id == BBIBBI_ROLE_ID for role in message.role_mentions):
            user_id = message.author.id
            result = await self.process_bbibbi(user_id)
            if result.get('success'):
                await message.add_reaction('📢')
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

    async def process_bbibbi(self, user_id: int) -> Dict[str, Any]:
        """삐삐(특정 역할 멘션) 일일 퀘스트 처리"""
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
                quest_subtype='bbibbi',
                timeframe='day'
            )
            if today_count > 0:
                return result  # 이미 지급됨

            exp = self.quest_exp['daily']['bbibbi']
            await self.data_manager.add_exp(user_id, exp, 'daily', 'bbibbi')
            result['success'] = True
            result['exp_gained'] = exp
            result['quest_completed'].append('daily_bbibbi')
            result['messages'].append(f"📢 삐삐 퀘스트 완료! **+{exp} 다공**")
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
        
        # Always trigger event for Snowflake (regardless of weekly reward)
        result['quest_completed'].append('recommend')
        return await self._finalize_quest_result(user_id, result)

    async def process_up_quest(self, user_id: int, count: int = 1) -> Dict[str, Any]:
        """
        '업' 인증 시 호출: 눈송이 지급용 이벤트 발생
        Economy.py에서 '업' 인증마다 호출됨. (무제한)
        """
        result = {
            'success': True, # EXP 로직이 없어도 성공으로 처리하여 이벤트 발송
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        # Trigger event for Snowflake
        # loop count times to support multiple completions at once? 
        # Actually Event system usually handles one by one or TreeCommand needs to handle amount.
        # TreeCommand handles one event -> one validation. 
        # To support bulk, we might need to emit multiple events or change TreeCommand.
        # Given current TreeCommand structure, firing multiple events is safer/easier.
        for _ in range(count):
             result['quest_completed'].append('up')
             
        return await self._finalize_quest_result(user_id, result)

    async def process_invite_quest(self, user_id: int, count: int = 1) -> Dict[str, Any]:
        """
        '지인초대' 인증 시 호출: 눈송이 지급용 이벤트 발생
        Economy.py에서 '지인초대' 인증마다 호출됨. (무제한)
        """
        result = {
            'success': True,
            'exp_gained': 0,
            'messages': [],
            'quest_completed': []
        }
        # Trigger event for Snowflake
        for _ in range(count):
             result['quest_completed'].append('invite')
             
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
