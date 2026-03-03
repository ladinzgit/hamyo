import discord
from discord.ext import commands
from src.core.LevelDataManager import LevelDataManager
from src.level.LevelConstants import (
    ROLE_THRESHOLDS, ROLE_ORDER, ROLE_IDS, ROLE_DISPLAY,
    MAIN_CHAT_CHANNEL_ID, QUEST_COMPLETION_CHANNEL_ID,
    ROLE_FALLBACK_COLORS, ROLE_UPGRADE_TEMPLATES,
    EMBED_QUEST_TITLE_EMOJI, EMBED_QUEST_TITLE_TRAIL,
    EMBED_PAGE_EMOJI, EMBED_NEW_PAGE_EMOJI
)
from typing import Optional, Dict, Any, List
import logging
import asyncio
import datetime
from datetime import datetime
import pytz
import random
import re

KST = pytz.timezone("Asia/Seoul")

def extract_name(text: str) -> str:
    if not text: return ""
    name = re.sub(r"^[《『][^》』]+[》』]\s*", "", text)
    name = re.sub(r"^[&!]\s*", "", name)
    return name.strip() or text

class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = LevelDataManager()
        
        # LevelConstants에서 불러온 설정
        self.role_thresholds = ROLE_THRESHOLDS
        self.role_order = ROLE_ORDER
        self.ROLE_IDS = ROLE_IDS
        self.ROLE_DISPLAY = ROLE_DISPLAY
    
    async def cog_load(self):
        """Cog 로드 시 데이터베이스 초기화"""
        await self.data_manager.ensure_initialized()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        
    async def log(self, message):
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
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
        
        quest_channel = self.bot.get_channel(QUEST_COMPLETION_CHANNEL_ID)
        if not quest_channel:
            return
        
        try:
            # 닉네임 표시를 위해 먼저 Guild Member로 조회
            user = await self._safe_fetch_member(quest_channel.guild, user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    return
            
            # 사용자의 현재 역할 정보 가져오기
            user_data = await self.data_manager.get_user_exp(user_id)
            current_role = user_data['current_role'] if user_data else 'yeobaek'
            
            # 역할별 색상 가져오기
            embed_color = await self._get_role_color(current_role, quest_channel.guild)
            
            # 백지동화 컨셉에 맞는 임베드
            titles = [
                f"{EMBED_QUEST_TITLE_EMOJI} 백지동화､ 당신의 이야기가 한 장 적혔어요 {EMBED_QUEST_TITLE_TRAIL}",
                f"{EMBED_QUEST_TITLE_EMOJI} 백지동화､ 조용한 잉크방울이 스며들었어요 {EMBED_QUEST_TITLE_TRAIL}",
                f"{EMBED_QUEST_TITLE_EMOJI} 백지동화､ 새로운 페이지가 차박차박 넘어가요 {EMBED_QUEST_TITLE_TRAIL}",
                f"{EMBED_QUEST_TITLE_EMOJI} 백지동화､ 당신만의 문장이 반짝이며 새겨졌어요 {EMBED_QUEST_TITLE_TRAIL}",
                f"{EMBED_QUEST_TITLE_EMOJI} 백지동화､ 포근한 이야기가 또 하나 쌓였어요 {EMBED_QUEST_TITLE_TRAIL}"
            ]
            embed = discord.Embed(
                title=random.choice(titles),
                color=embed_color
            )
            
            # 사용자 정보
            embed.set_author(
                name=f"{extract_name(user.display_name)}의 집필 기록",
                icon_url=user.display_avatar.url
            )
            
            # 완료한 집필들 (승급 메시지 제외)
            quest_text = ""
            for message in result['messages']:
                # 승급 관련 메시지는 제외
                if "승급" in message or "역할" in message:
                    continue
                
                quest_text += f"• {message}\n"
            
            if quest_text:  # 승급 메시지 제외 후에도 내용이 있는 경우만
                embed.add_field(
                    name=f"{EMBED_PAGE_EMOJI} 방금 적어내린 문장들",
                    value=quest_text,
                    inline=False
                )
                
                # 총 획득 쪽수
                if result.get('exp_gained', 0) > 0:
                    embed.add_field(
                        name=f"{EMBED_NEW_PAGE_EMOJI} 새롭게 기록한 페이지",
                        value=f"**+{result['exp_gained']:,} 쪽**",
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
            channel = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
            if channel is None:
                await self.log("메인 채널을 찾을 수 없어 승급 메시지 전송 실패")
                return

            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if user is None:
                await self.log(f"승급 메시지: 유저 캐시/페치 실패 (user_id={user_id})")
                return

            # LevelConstants에서 승급 메시지 템플릿 사용
            templates = ROLE_UPGRADE_TEMPLATES

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
        fallback_colors = ROLE_FALLBACK_COLORS
        
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
        ch = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
        if ch and ch.guild:
            guild = ch.guild
        if guild is None:
            ch = self.bot.get_channel(QUEST_COMPLETION_CHANNEL_ID)
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
          1. yeobaek -> goyo: yeobaek 역할 제거 (기존 goyo 역할 추가)
          2. goyo -> seoyu: goyo 역할 유지, seoyu 역할 추가
          3. seoyu -> seorim: seoyu 역할 유지, seorim 역할 추가
          4. seorim -> seohyang: seorim 역할 유지, seohyang 역할 추가
          - 이후 추가될 시, 2, 3, 4번과 동일하게 작동(이전 역할 유지)
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

            # 1. 새 역할 부여 (항상)
            if target_role not in member.roles:
                try:
                    await member.add_roles(target_role, reason=f"승급: {new_role_key}")
                except Exception as e:
                    await self.log(f"역할 부여 실패({new_role_key}): {e}")
                    return False

            # 2. 이전 역할 제거 판별
            # 기본 원칙: 앞으로는 모든 역할을 유지 (단, 여백(yeobaek)만 제거)
            should_remove_previous = False
            
            if previous_role_key == 'yeobaek':
                should_remove_previous = True
            
            if should_remove_previous and previous_role_key and previous_role_key in self.ROLE_IDS:
                prev_role_id = self.ROLE_IDS.get(previous_role_key)
                prev_role = guild.get_role(prev_role_id)
                
                if prev_role and prev_role in member.roles:
                    try:
                        await member.remove_roles(prev_role, reason=f"승급: {new_role_key} (이전 역할 {previous_role_key} 제거)")
                    except Exception as e:
                        await self.log(f"이전 역할({previous_role_key}) 제거 실패: {e}")

            return True

        except Exception as e:
            await self.log(f"_apply_role_update 오류: {e}")
            return False
async def setup(bot):
    await bot.add_cog(LevelSystem(bot))
