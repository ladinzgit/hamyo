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

class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        self.MAIN_CHAT_CHANNEL_ID = 1396829222978322608
        self.QUEST_COMPLETION_CHANNEL_ID = 1400442713605668875
        
        # 역할 승급 기준
        self.role_thresholds = {
            'hub': 0,
            'dado': 400,
            'daho': 1800,
            'dakyung': 6000,
            'dahyang': 12000
        }
        
        # 역할 순서
        self.role_order = ['hub', 'dado', 'daho', 'dakyung', 'dahyang']
        
        self.ROLE_IDS = {
            'hub': 1396829213172174890,
            'dado': 1396829213172174888,
            'daho': 1398926065111662703,
            'dakyung': 1396829213172174891,
            'dahyang': 1396829213172174892
        }
        
        self.ROLE_DISPLAY = {
            'hub': '허브',
            'dado': '다도',
            'daho': '다호',
            'dakyung': '다경',
            'dahyang': '다향'
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

    @commands.Cog.listener()
    async def on_quest_completion(self, user_id: int, result: Dict[str, Any]):
        """퀘스트 결과 공통 후처리 (메시지 출력, 역할 승급 확인)"""
        # 퀘스트 완료 메시지를 전용 채널에 전송
        await self.send_quest_completion_message(user_id, result)

        # 역할 승급 확인
        if result.get('success') and result.get('exp_gained', 0) > 0:
            role_key = await self._check_role_upgrade(user_id)  # 키 반환
            if role_key:
                display = self._get_role_display_name(role_key)

                # 승급 메시지를 메인채팅에 전송 (키로 호출)
                await self.send_role_upgrade_message(user_id, role_key)

    async def send_quest_completion_message(self, user_id: int, result: Dict[str, Any]):
        """퀘스트 완료 메시지를 전용 채널에 전송"""
        if not result.get('success') or not result.get('messages'):
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
                if result.get('exp_gained', 0) > 0:
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
        - dado/daho/dakyung/dahyang 별 전용 문구 전송
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
                "dahyang": (
                    ".   ◜◝--◜◝\n"
                    "꒰   ˶ ´  ତ ` ˶꒱\n"
                    "✦ ╮ {mention} 님, 다향으로 승급했어요 !\n"
                    "│\n"
                    "│ ⠀몽경의 경지를 넘어, 온 세상에 그 향기가 닿는 자가 되었어요 ˎˊ˗ \n"
                    "│ ⠀맑은 차향이 구름을 타고 만물에 스며들듯\n"
                    "│    모든 경계를 아우르는 고요하고 깊은 울림의 경지입니다 <:BM_k_004:1399387524010606644>\n"
                    "│\n"
                    " ╰ ⊱ ─ · ─ · ─ · ─ ·  ─ · ─ · ─ · ─ · ─ · ─ · ─"
                ),
            }

            template = templates.get(new_role_key)
            if template is None:
                # 템플릿이 없으면 간단한 기본 문구 출력
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
            'dakyung': discord.Color.from_rgb(255, 215, 0),  # 금색
            'dahyang': discord.Color.from_rgb(80, 105, 215)
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

async def setup(bot):
    await bot.add_cog(LevelSystem(bot))
