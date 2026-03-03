import json
import os
from typing import Dict, Optional, Tuple, List

import discord
from discord import app_commands
from discord.ext import commands, tasks

# =============================
# 복수 길드 전용 CountChannel Cog
# - 아래 TARGET_GUILD_IDS 에 지정한 길드에서만 동작
# - 데이터 저장도 한 파일(count_channels.json)만 사용
# =============================

from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin

# TARGET_GUILD_IDS is used in other places like store.all_items/register_app_commands so we can map it to GUILD_IDS
TARGET_GUILD_IDS = GUILD_IDS


STORAGE_FILE = "data/count_channels.json"

class SingleFileStore:
    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Dict] = {"channels": {}}
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"channels": {}}
        self._loaded = True

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def all_items(self) -> List[Tuple[int, Dict]]:
        self.load()
        return [(int(cid), meta) for cid, meta in self._data.get("channels", {}).items()]

    def get(self, channel_id: int) -> Optional[Dict]:
        self.load()
        return self._data.get("channels", {}).get(str(channel_id))

    def set(self, channel_id: int, role_id: Optional[int], prefix: str, include_bots: bool, additional_role_ids: Optional[List[int]] = None):
        self.load()
        self._data.setdefault("channels", {})[str(channel_id)] = {
            "role_id": role_id,
            "prefix": prefix,
            "include_bots": include_bots,
            "additional_role_ids": additional_role_ids or [],
        }
        self.save()

    def delete(self, channel_id: int) -> bool:
        self.load()
        existed = str(channel_id) in self._data.get("channels", {})
        if existed:
            del self._data["channels"][str(channel_id)]
            self.save()
        return existed


class CountChannelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = SingleFileStore(STORAGE_FILE)
        self._reconcile.start()

    def cog_unload(self):
        self._reconcile.cancel()
        
    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message, title="🛠️ 유틸리티 로그", color=discord.Color.dark_grey())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    @staticmethod
    def extract_prefix(current_name: str) -> str:
        stripped = current_name.rstrip()
        i = len(stripped) - 1
        while i >= 0 and stripped[i].isdigit():
            i -= 1
        prefix = stripped[:i+1]
        return prefix if prefix else stripped

    @staticmethod
    def build_name(prefix: str, count: int) -> str:
        return f"{prefix}{count}"

    @staticmethod
    def count_members(guild: discord.Guild, role: Optional[discord.Role], include_bots: bool, additional_roles: Optional[List[discord.Role]] = None) -> int:
        all_members = set()
        
        # 기본 역할의 멤버들 추가
        if role is None:
            all_members.update(guild.members)
        else:
            all_members.update(role.members)
        
        # 추가 역할들의 멤버들 추가 (중복 제거됨)
        if additional_roles:
            for additional_role in additional_roles:
                all_members.update(additional_role.members)
        
        # 봇 포함 여부에 따라 필터링
        if include_bots:
            return len(all_members)
        return sum(1 for m in all_members if not m.bot)

    def _is_target_guild(self, guild: discord.Guild) -> bool:
        return guild.id in TARGET_GUILD_IDS

    async def update_one_channel(self, guild: discord.Guild, channel_id: int):
        if not self._is_target_guild(guild):
            return
        meta = self.store.get(channel_id)
        if not meta:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return

        role_id = meta.get("role_id")
        include_bots = meta.get("include_bots", False)
        additional_role_ids = meta.get("additional_role_ids", [])
        
        role = guild.get_role(role_id) if role_id else None
        additional_roles = [guild.get_role(rid) for rid in additional_role_ids if guild.get_role(rid)]

        current_prefix = self.extract_prefix(channel.name)
        if current_prefix and current_prefix != meta.get("prefix"):
            meta["prefix"] = current_prefix
            self.store.save()

        prefix = meta.get("prefix") or (role.name if role else "전체 인원: ")
        count = self.count_members(guild, role, include_bots, additional_roles)
        desired = self.build_name(prefix, count)

        if channel.name != desired:
            try:
                await channel.edit(name=desired, reason="역할 카운트 자동 업데이트")
            except discord.Forbidden:
                await self.log(f"❌ 카운트 채널 {channel.name} 수정 권한 부족 [길드: {guild.name}({guild.id}), 채널: {channel.name}({channel.id})] [시스템]")
            except discord.HTTPException as e:
                await self.log(f"❌ 카운트 채널 {channel.name} 수정 실패: {e} [길드: {guild.name}({guild.id}), 채널: {channel.name}({channel.id})] [시스템]")

    async def update_all_channels(self, guild: Optional[discord.Guild] = None):
        g = guild or None
        if not g or not self._is_target_guild(g):
            return
        
        for cid, _ in self.store.all_items():
            await self.update_one_channel(g, cid)

    async def set_voice_permissions(self, channel: discord.VoiceChannel):
        overwrites = {
            channel.guild.default_role: discord.PermissionOverwrite(view_channel=True, manage_channels=False, manage_permissions=False, manage_webhooks=False, send_messages=False, connect=False, speak=False, create_instant_invite=False),
            channel.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True),
        }
        try:
            await channel.edit(overwrites=overwrites, reason="카운트 채널 권한 설정")
            await self.log(f"🔒 카운트 채널 권한 설정 완료: {channel.name} [길드: {channel.guild.name}({channel.guild.id}), 채널: {channel.name}({channel.id})] [시스템]")
        except discord.HTTPException as e:
            await self.log(f"❌ 카운트 채널 권한 설정 실패: {channel.name} - {e} [길드: {channel.guild.name}({channel.guild.id}), 채널: {channel.name}({channel.id})] [시스템]")

    @tasks.loop(minutes=10)
    async def _reconcile(self):
        for guild in self.bot.guilds:
            if not self._is_target_guild(guild):
                continue
            try:
                await self.update_all_channels(guild)
            except Exception as e:
                await self.log(f"❌ 길드 {guild.name} 카운트 채널 정기 업데이트 중 오류: {e} [길드: {guild.name}({guild.id})] [시스템]")

    @_reconcile.before_loop
    async def _before_reconcile(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not self._is_target_guild(before.guild):
            return
        if set(before.roles) != set(after.roles):
            await self.update_all_channels(after.guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self._is_target_guild(member.guild):
            return
        await self.update_all_channels(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not self._is_target_guild(member.guild):
            return
        await self.update_all_channels(member.guild)

    count_group = app_commands.Group(name="카운트", description="역할 카운트 채널 관리")

    @count_group.command(name="채널생성", description="역할 카운트 음성 채널을 생성합니다.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        역할="카운트할 역할 (@everyone 선택 시 서버 전체)",
        접두어="채널 이름의 접두어(기본: 역할 이름 또는 '전체 인원: ')",
        봇포함="봇 계정도 카운트에 포함할지 여부(기본: 포함 안 함)",
        카테고리="생성할 카테고리(미지정 시 최상위)",
        추가역할="함께 카운트할 추가 역할 (중복 제거됨)"
    )
    async def create_channel(
        self,
        interaction: discord.Interaction,
        역할: Optional[discord.Role] = None,
        접두어: Optional[str] = None,
        봇포함: Optional[bool] = False,
        카테고리: Optional[discord.CategoryChannel] = None,
        추가역할: Optional[discord.Role] = None,
    ):
        if interaction.guild is None or not self._is_target_guild(interaction.guild):
            return await interaction.response.send_message("이 명령은 지정된 길드에서만 사용할 수 있어요.", ephemeral=True)

        guild = interaction.guild
        role = 역할
        default_prefix = (role.name + ": ") if role else "전체 인원: "
        prefix = (접두어 if 접두어 is not None else default_prefix)

        # 추가 역할 처리
        additional_roles = []
        additional_role_ids = []
        if 추가역할:
            additional_roles.append(추가역할)
            additional_role_ids.append(추가역할.id)

        for cid, meta in self.store.all_items():
            if meta.get("role_id") == (role.id if role else None):
                await self.log(f"⚠️ 중복 채널 생성 시도: 역할 {role.name if role else '@everyone'} [길드: {guild.name}({guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
                return await interaction.response.send_message("해당 역할에 대한 카운트 채널이 이미 존재합니다.", ephemeral=True)

        count = self.count_members(guild, role, 봇포함 or False, additional_roles)
        name = self.build_name(prefix, count)

        try:
            channel = await guild.create_voice_channel(
                name=name,
                category=카테고리,
                reason="역할 카운트 채널 생성",
                user_limit=0,
            )
            
            role_info = role.name if role else '@everyone'
            if additional_roles:
                additional_names = [r.name for r in additional_roles]
                role_info += f" + {', '.join(additional_names)}"
            
            await self.log(f"✅ 카운트 채널 생성: {channel.name} (역할: {role_info}) [길드: {guild.name}({guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
        except discord.Forbidden:
            await self.log(f"❌ 카운트 채널 생성 권한 부족 [길드: {guild.name}({guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
            return await interaction.response.send_message("채널 생성 권한이 부족합니다.", ephemeral=True)
        except discord.HTTPException as e:
            await self.log(f"❌ 카운트 채널 생성 실패: {e} [길드: {guild.name}({guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
            return await interaction.response.send_message(f"채널 생성에 실패했습니다: {e}", ephemeral=True)

        await self.set_voice_permissions(channel)
        self.store.set(channel.id, role.id if role else None, prefix, bool(봇포함), additional_role_ids)

        additional_info = ""
        if additional_roles:
            additional_info = f" + 추가역할: {', '.join([r.name for r in additional_roles])}"

        await interaction.response.send_message(
            f"{channel.mention} 채널을 생성했어요! (접두어: `{prefix}` / 봇 포함: `{bool(봇포함)}`{additional_info})",
            ephemeral=True,
        )

    @count_group.command(name="채널삭제", description="카운트 채널 트래킹을 중단하고 채널을 삭제합니다.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(채널="삭제할 음성 채널")
    async def delete_channel(self, interaction: discord.Interaction, 채널: discord.VoiceChannel):
        if interaction.guild is None or not self._is_target_guild(interaction.guild):
            return await interaction.response.send_message("이 명령은 지정된 길드에서만 사용할 수 있어요.", ephemeral=True)

        tracked = self.store.get(채널.id)
        if not tracked:
            await self.log(f"⚠️ 비관리 채널 삭제 시도: {채널.name} [길드: {interaction.guild.name}({interaction.guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
            return await interaction.response.send_message("해당 채널은 카운트 채널로 관리되고 있지 않아요.", ephemeral=True)

        self.store.delete(채널.id)
        try:
            await 채널.delete(reason="카운트 채널 삭제")
            await self.log(f"🗑️ 카운트 채널 삭제: {채널.name} [길드: {interaction.guild.name}({interaction.guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
        except discord.HTTPException as e:
            await self.log(f"❌ 카운트 채널 삭제 실패: {채널.name} - {e} [길드: {interaction.guild.name}({interaction.guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
        await interaction.response.send_message("채널을 삭제했어요.", ephemeral=True)

    @count_group.command(name="채널목록", description="현재 관리 중인 카운트 채널 목록을 보여줍니다.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def list_channels(self, interaction: discord.Interaction):
        if interaction.guild is None or not self._is_target_guild(interaction.guild):
            return await interaction.response.send_message("이 명령은 지정된 길드에서만 사용할 수 있어요.", ephemeral=True)
        items = self.store.all_items()
        if not items:
            return await interaction.response.send_message("관리 중인 카운트 채널이 없습니다.", ephemeral=True)

        guild = interaction.guild
        lines = []
        cleaned_count = 0
        for cid, meta in items:
            ch = guild.get_channel(cid)
            if isinstance(ch, discord.VoiceChannel):
                role_id = meta.get("role_id")
                additional_role_ids = meta.get("additional_role_ids", [])
                
                role_txt = "@everyone" if not role_id else (guild.get_role(role_id).mention if guild.get_role(role_id) else f"<@&{role_id}>")
                
                if additional_role_ids:
                    additional_mentions = []
                    for rid in additional_role_ids:
                        additional_role = guild.get_role(rid)
                        if additional_role:
                            additional_mentions.append(additional_role.mention)
                        else:
                            additional_mentions.append(f"<@&{rid}>")
                    role_txt += f" + {', '.join(additional_mentions)}"
                
                prefix = meta.get("prefix", "")
                inc_bots = "포함" if meta.get("include_bots", False) else "미포함"
                lines.append(f"• {ch.mention} — 역할: {role_txt} / 접두어: `{prefix}` / 봇: {inc_bots}")
            else:
                self.store.delete(cid)
                cleaned_count += 1
        
        if cleaned_count > 0:
            await self.log(f"🧹 유효하지 않은 카운트 채널 {cleaned_count}개 정리 [길드: {guild.name}({guild.id}), 채널: {interaction.channel.name if interaction.channel else 'DM'}({interaction.channel_id})] [유저: {interaction.user.id}]")
        
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    async def register_app_commands(self, tree: app_commands.CommandTree):
        for gid in TARGET_GUILD_IDS:
            tree.add_command(self.count_group, guild=discord.Object(id=gid))

async def setup(bot: commands.Bot):
    await bot.add_cog(CountChannelCog(bot))
