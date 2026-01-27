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

    class RoleButton(discord.ui.Button):
        def __init__(self, role_id: int, role_name: str, emoji: str):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"role_btn:{role_id}"
            )
            self.role_id = role_id
            self.role_name = role_name

        async def callback(self, interaction: discord.Interaction):
            guild = interaction.guild
            member = interaction.user
            
            role = guild.get_role(self.role_id)
            if not role:
                 # ID 조회 실패 시 이름으로 검색 (호환성)
                 role = discord.utils.get(guild.roles, name=self.role_name)
            
            if not role:
                await interaction.response.send_message("해당 역할을 찾을 수 없다묘... 관리자에게 문의하라묘!", ephemeral=True)
                return

            try:
                if role in member.roles:
                    await member.remove_roles(role)
                    await interaction.response.send_message(f"'{self.role_name}' 역할을 회수했다묘. 필요하면 다시 누르라묘.", ephemeral=True)
                else:
                    await member.add_roles(role)
                    await interaction.response.send_message(f"'{self.role_name}' 역할을 줬다묘! 잘 쓰라묘!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("권한이 없어서 역할을 줄 수 없다묘... 내 권한을 확인해달라묘!", ephemeral=True)
            except Exception as e:
                print(f"역할 버튼 처리 오류: {e}")
                await interaction.response.send_message("오류가 발생했다묘... 다시 시도해달라묘.", ephemeral=True)

    class RoleView(discord.ui.View):
        def __init__(self, roles_data: list):
            super().__init__(timeout=None)
            added_ids = set()
            for role_info in roles_data:
                role_id = role_info.get("role_id")
                role_name = role_info.get("role")
                emoji = role_info.get("emoji")
                
                # ID가 유효한 경우에만 버튼 생성
                if role_id:
                    if role_id in added_ids:
                        continue
                    self.add_item(RoleEmbed.RoleButton(role_id, role_name, emoji))
                    added_ids.add(role_id)
                else:
                    pass

    def build_role_view(self, data: dict) -> discord.ui.View:
        roles_data = data["data"].get("roles", [])
        return self.RoleView(roles_data)

    def build_role_embed(self, name: str, data: dict) -> discord.Embed:
        # 임베드 설명문 구성
        roles_data = data["data"].get("roles", [])
        
        description_lines = [
            "✩ ᘏ ⑅ ᘏ",
            f"（⠀´ㅅ` ) ... {name} 받으라묘....✩",
            "𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃",
            "",
            ""  # 중앙 간격 추가
        ]

        for role in roles_data:
            description_lines.append(f"{role['emoji']} <@&{role['role_id']}>")
            description_lines.append(f"-# ⠀◟. {role['description']}")
            description_lines.append("-# ⠀")
        
        description_lines.append("𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃𓂃")

        color_list = data.get("color", [255, 255, 255])
        color = discord.Color.from_rgb(*color_list)

        embed = discord.Embed(
            title="", # 공란
            description="\n".join(description_lines),
            color=color
        )
        return embed

    @is_guild_admin()
    @role_group.command(name="추가", description="역할 임베드에 새로운 역할을 추가합니다.")
    @app_commands.describe(
        name="임베드 이름", 
        role="역할명", 
        description="역할 설명", 
        emoji="이모지"
    )
    async def add_role(self, interaction: discord.Interaction, name: str, role: discord.Role, description: str, emoji: str):
        data = embed_manager.get_embed_data(name, reload=True)
        if not data:
            available = list(embed_manager.config.get("embeds", {}).keys())
            print(f"DEBUG: '{name}' 찾기 실패. 현재 등록된 임베드: {available}")
            await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.")
            return
        
        if data["type"] != "role":
            await interaction.response.send_message(f"'{name}'은 역할 임베드가 아닙니다.")
            return

        roles = data["data"].get("roles", [])
        for r in roles:
            if r.get("role_id") == role.id:
                await interaction.response.send_message(f"이미 '{role.name}' 역할이 등록되어 있습니다.")
                return
            # 이름 중복 체크 (선택사항이나 안전을 위해)
            if r.get("role") == role.name:
                await interaction.response.send_message(f"이미 '{role.name}' 이름의 역할이 등록되어 있습니다.")
                return

        new_role = {
            "name": name, 
            "role": role.name,
            "role_id": role.id,
            "description": description,
            "emoji": emoji
        }
        
        if "roles" not in data["data"]:
            data["data"]["roles"] = []
        
        data["data"]["roles"].append(new_role)
        embed_manager.set_embed_data(name, data)

        # 임베드 및 버튼 업데이트
        embed = self.build_role_embed(name, data)
        view = self.build_role_view(data)
        await embed_manager.update_embed_messages(self.bot, name, embed, view=view)
        
        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드에 '{role.name}' 역할을 추가함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드에 '{role.name}' 역할이 추가되었습니다.")

    @is_guild_admin()
    @role_group.command(name="제거", description="역할 임베드에서 역할을 제거합니다.")
    @app_commands.describe(name="임베드 이름", role="제거할 역할명")
    async def remove_role(self, interaction: discord.Interaction, name: str, role: str):
        data = embed_manager.get_embed_data(name)
        if not data or data["type"] != "role":
            await interaction.response.send_message(f"'{name}' 역할 임베드를 찾을 수 없습니다.")
            return

        roles = data["data"].get("roles", [])
        new_roles = [r for r in roles if r["role"] != role]
        
        if len(roles) == len(new_roles):
             await interaction.response.send_message(f"'{name}' 임베드에서 '{role}' 역할을 찾을 수 없습니다.")
             return

        data["data"]["roles"] = new_roles
        embed_manager.set_embed_data(name, data)

        # 임베드 및 버튼 업데이트
        embed = self.build_role_embed(name, data)
        view = self.build_role_view(data)
        await embed_manager.update_embed_messages(self.bot, name, embed, view=view)

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
        view = self.build_role_view(data)
        await embed_manager.update_embed_messages(self.bot, name, embed, view=view)
        
        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드의 '{role}' 역할을 수정함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드의 '{role}' 역할이 수정되었습니다.")

    @commands.Cog.listener()
    async def on_ready(self):
        """봇 시작 시 모든 역할 임베드의 View를 등록하여 버튼 상호작용 복원"""
        try:
            # embed_config에서 모든 role 타입 임베드를 가져와 View 등록
            config = embed_manager.load_config()
            embeds = config.get("embeds", {})
            
            registered_count = 0
            for name, data in embeds.items():
                if data.get("type") == "role":
                    roles_data = data.get("data", {}).get("roles", [])
                    if roles_data:
                        view = self.RoleView(roles_data)
                        self.bot.add_view(view)
                        registered_count += 1
            
            if registered_count > 0:
                await self.log(f"역할 버튼 View {registered_count}개 등록 완료")
        except Exception as e:
            print(f"역할 버튼 View 등록 중 오류: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleEmbed(bot))
