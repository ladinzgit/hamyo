import discord
from discord import app_commands
from discord.ext import commands
from .EmbedUtils import embed_manager
from src.core.admin_utils import is_guild_admin_app as is_guild_admin
import asyncio

class RoleEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    role_group = app_commands.Group(name="역할", description="역할 임베드 관리 명령어")

    async def log(self, message: str):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return

        # 모든 임베드 설정을 확인하여 해당 메시지가 추적 대상인지 확인
        config = embed_manager.config.get("embeds", {})
        target_embed_name = None
        target_role_data = None

        for name, data in config.items():
            if data.get("type") != "role":
                continue
            
            # 메시지 ID가 목록에 있는지 확인
            for _, msg_id in data.get("message_ids", []):
                if msg_id == payload.message_id:
                    target_embed_name = name
                    break
            
            if target_embed_name:
                roles = data["data"].get("roles", [])
                for r in roles:
                    if str(payload.emoji) == r["emoji"]:
                        target_role_data = r
                        break
                break
        
        if target_role_data:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                role_obj = discord.utils.get(guild.roles, name=target_role_data["role"])
                if role_obj:
                    try:
                        await payload.member.add_roles(role_obj)
                    except discord.Forbidden:
                        await self.log(f"권한 부족으로 {payload.member}({payload.member.id})에게 역할 {role_obj.name} 부여 실패 [길드: {guild.name}({guild.id})]")
                    except Exception as e:
                        await self.log(f"역할 {role_obj.name} 부여 중 오류 발생: {e} [사용자: {payload.member}({payload.member.id})]")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        # 봇인지는 payload.member가 없을 수 있어서(캐시 문제) 확인 어려울 수 있으나, 
        # 로직상 봇이 반응을 제거하는 경우는 드물거나 무시해도 됨.
        
        config = embed_manager.config.get("embeds", {})
        target_embed_name = None
        target_role_data = None

        for name, data in config.items():
            if data.get("type") != "role":
                continue
            
            for _, msg_id in data.get("message_ids", []):
                if msg_id == payload.message_id:
                    target_embed_name = name
                    break
            
            if target_embed_name:
                roles = data["data"].get("roles", [])
                for r in roles:
                     if str(payload.emoji) == r["emoji"]:
                        target_role_data = r
                        break
                break

        if target_role_data:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                member = guild.get_member(payload.user_id)
                if not member:
                     try:
                        member = await guild.fetch_member(payload.user_id)
                     except:
                        pass
                
                if member and not member.bot:
                    role_obj = discord.utils.get(guild.roles, name=target_role_data["role"])
                    if role_obj:
                        try:
                            await member.remove_roles(role_obj)
                        except discord.Forbidden:
                            await self.log(f"권한 부족으로 {member}({member.id})에게서 역할 {role_obj.name} 회수 실패 [길드: {guild.name}({guild.id})]")
                        except Exception as e:
                            await self.log(f"역할 {role_obj.name} 회수 중 오류 발생: {e} [사용자: {member}({member.id})]")


    def build_role_embed(self, name: str, data: dict) -> discord.Embed:
        # 특정 포맷의 설명 구성
        roles_data = data["data"].get("roles", [])
        
        description_lines = [
            "✩ ᘏ ⑅ ᘏ",
            f"（⠀´ㅅ` ) ... {name} 받으라묘....✩",
            "𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃",
            "",
            ""  # 요청대로 중앙 간격을 위한 공백 2줄
        ]

        for role in roles_data:
            description_lines.append(f"{role['emoji']} {role['role']}")
            description_lines.append(f"-# ⠀◟. {role['description']}")
            description_lines.append("-# ⠀")
        
        description_lines.append("𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃")

        color_list = data.get("color", [255, 255, 255])
        color = discord.Color.from_rgb(*color_list)

        embed = discord.Embed(
            title="", # 공란으로 설정
            description="\n".join(description_lines),
            color=color
        )
        return embed

    async def update_reactions(self, name: str, data: dict):
        # 모든 추적된 메시지의 반응 업데이트
        # 추가 명령 시 기존 이모지는 유지하고 새 이모지만 추가
        
        message_ids = data.get("message_ids", [])
        roles = data["data"].get("roles", [])
        
        # 목표 이모지 목록
        target_emojis = [r['emoji'] for r in roles]

        for channel_id, message_id in message_ids:
            try:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                     channel = await self.bot.fetch_channel(channel_id)
                
                message = await channel.fetch_message(message_id)
                
                # 불필요한 API 호출 방지를 위해 기존 반응 확인
                existing_reactions = {str(r.emoji): r for r in message.reactions}
                
                for emoji in target_emojis:
                     reacted = False
                     if emoji in existing_reactions:
                        if existing_reactions[emoji].me:
                            reacted = True
                     
                     if not reacted:
                         try:
                             await message.add_reaction(emoji)
                         except discord.HTTPException as e:
                             print(f"반응 추가 실패 {emoji}: {e}")

            except Exception as e:
                print(f"메시지 {message_id} 반응 업데이트 중 오류 발생: {e}")

    async def reset_reactions(self, name: str, data: dict):
        message_ids = data.get("message_ids", [])
        roles = data["data"].get("roles", [])
        target_emojis = [r['emoji'] for r in roles]

        for channel_id, message_id in message_ids:
            try:
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                
                # 봇의 모든 반응 제거 (초기화)
                await message.clear_reactions()

                # 다시 추가
                for emoji in target_emojis:
                    await message.add_reaction(emoji)
            except Exception as e:
                 print(f"메시지 {message_id} 반응 초기화 중 오류 발생: {e}")


    @is_guild_admin()
    @role_group.command(name="추가", description="역할 임베드에 새로운 역할을 추가합니다.")
    @app_commands.describe(
        name="임베드 이름", 
        role="역할명", 
        description="역할 설명", 
        emoji="이모지"
    )
    async def add_role(self, interaction: discord.Interaction, name: str, role: str, description: str, emoji: str):
        data = embed_manager.get_embed_data(name)
        if not data:
            await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.")
            return
        
        if data["type"] != "role":
            await interaction.response.send_message(f"'{name}'은 역할 임베드가 아닙니다.")
            return

        new_role = {
            "name": name, 
            "role": role,
            "description": description,
            "emoji": emoji
        }
        
        if "roles" not in data["data"]:
            data["data"]["roles"] = []
        
        data["data"]["roles"].append(new_role)
        embed_manager.set_embed_data(name, data)

        # 메시지 업데이트
        embed = self.build_role_embed(name, data)
        await embed_manager.update_embed_messages(self.bot, name, embed)
        
        # 반응 추가
        await self.update_reactions(name, data)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드에 '{role}' 역할을 추가함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드에 '{role}' 역할이 추가되었습니다.")

    @is_guild_admin()
    @role_group.command(name="제거", description="역할 임베드에서 역할을 제거합니다.")
    @app_commands.describe(name="임베드 이름", role="제거할 역할명")
    async def remove_role(self, interaction: discord.Interaction, name: str, role: str):
        data = embed_manager.get_embed_data(name)
        if not data or data["type"] != "role":
            await interaction.response.send_message(f"'{name}' 역할 임베드를 찾을 수 없습니다.")
            return

        roles = data["data"].get("roles", [])
        # 찾아서 제거
        new_roles = [r for r in roles if r["role"] != role]
        
        if len(roles) == len(new_roles):
             await interaction.response.send_message(f"'{name}' 임베드에서 '{role}' 역할을 찾을 수 없습니다.")
             return

        data["data"]["roles"] = new_roles
        embed_manager.set_embed_data(name, data)

        # 메시지 업데이트
        embed = self.build_role_embed(name, data)
        await embed_manager.update_embed_messages(self.bot, name, embed)

        # 반응 초기화
        await self.reset_reactions(name, data)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드에서 '{role}' 역할을 제거함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드에서 '{role}' 역할이 제거되었습니다.")

    @is_guild_admin()
    @role_group.command(name="수정", description="역할 임베드의 역할을 수정합니다.")
    @app_commands.describe(
        name="임베드 이름", 
        role="수정할 역할명", 
        description="새로운 설명 (선택)", 
        emoji="새로운 이모지 (선택)"
    )
    async def edit_role(self, interaction: discord.Interaction, name: str, role: str, description: str = None, emoji: str = None):
        data = embed_manager.get_embed_data(name)
        if not data or data["type"] != "role":
             await interaction.response.send_message(f"'{name}' 역할 임베드를 찾을 수 없습니다.")
             return

        roles = data["data"].get("roles", [])
        found_idx = -1
        for i, r in enumerate(roles):
            if r["role"] == role:
                found_idx = i
                break
        
        if found_idx == -1:
             await interaction.response.send_message(f"'{name}' 임베드에서 '{role}' 역할을 찾을 수 없습니다.")
             return

        if description:
            roles[found_idx]["description"] = description
        if emoji:
            roles[found_idx]["emoji"] = emoji
        
        data["data"]["roles"] = roles
        embed_manager.set_embed_data(name, data)
        
        embed = self.build_role_embed(name, data)
        await embed_manager.update_embed_messages(self.bot, name, embed)
        
        if emoji:
             await self.update_reactions(name, data)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드의 '{role}' 역할을 수정함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드의 '{role}' 역할이 수정되었습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleEmbed(bot))
