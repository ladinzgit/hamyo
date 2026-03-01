import discord
from discord import app_commands
from discord.ext import commands
from .EmbedUtils import embed_manager
from .RoleEmbed import RoleEmbed
from src.core.admin_utils import is_guild_admin_app as is_guild_admin

class EmbedCommon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    embed_group = app_commands.Group(name="임베드", description="임베드 관리 명령어")

    async def log(self, message: str):
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")


    @is_guild_admin()
    @embed_group.command(name="생성", description="새로운 임베드를 생성합니다.")
    @app_commands.describe(kind="임베드 종류 ('역할', '입장' 지원)", name="임베드 이름")
    @app_commands.choices(kind=[
        app_commands.Choice(name="역할", value="role"),
        app_commands.Choice(name="입장", value="entrance")
    ])
    async def create_embed(self, interaction: discord.Interaction, kind: str, name: str):
        if embed_manager.get_embed_data(name):
            await interaction.response.send_message(f"이미 '{name}'이라는 이름의 임베드가 존재합니다.")
            return

        if kind == "entrance":
            # 입장 임베드는 1개만 존재해야 함
            embeds = embed_manager.config.get("embeds", {})
            for e_name, e_data in embeds.items():
                if e_data.get("type") == "entrance":
                    await interaction.response.send_message("입장 임베드는 이미 존재합니다. (단 1개만 생성 가능합니다.)", ephemeral=True)
                    return

        data = {
            "type": kind,
            "color": [255, 255, 255], 
            "message_ids": [],
            "data": {}
        }

        if kind == "role":
            data["data"]["roles"] = []
        elif kind == "entrance":
            data["data"] = {
                "channel_id": None,
                "title": "환영합니다!",
                "description": "{user.mention}님, {server.name}에 오신 것을 환영합니다!\n현재 인원: {member_count}명",
                "author": {"name": "", "icon_url": ""},
                "footer": {"text": "", "icon_url": ""},
                "images": {"thumbnail": "", "image": ""},
                "roles": [] # 지급할 역할 ID 목록
            }
        
        embed_manager.set_embed_data(name, data)
        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드({kind})를 생성함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드({kind})가 생성되었습니다.")

    @is_guild_admin()
    @embed_group.command(name="출력", description="임베드를 현재 채널에 출력합니다.")
    @app_commands.describe(name="출력할 임베드 이름")
    async def print_embed(self, interaction: discord.Interaction, name: str):
        data = embed_manager.get_embed_data(name)
        if not data:
            await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.", ephemeral=True)
            return
        
        role_embed_cog = None
        view = None
        if data["type"] == "role":
            role_embed_cog = self.bot.get_cog("RoleEmbed")
            if role_embed_cog:
                embed = role_embed_cog.build_role_embed(name, data)
                view = role_embed_cog.build_role_view(data)
            else:
                 await interaction.response.send_message("RoleEmbed 모듈이 로드되지 않았습니다.", ephemeral=True)
                 return
        else:
             await interaction.response.send_message(f"알 수 없는 임베드 타입입니다: {data['type']}", ephemeral=True)
             return

        msg = await interaction.channel.send(embed=embed, view=view)
        
        await embed_manager.add_message_id(name, interaction.channel_id, msg.id)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드를 채널 {interaction.channel.name}({interaction.channel.id})에 출력함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message("출력이 완료되었습니다.", ephemeral=True)

    @is_guild_admin()
    @embed_group.command(name="목록", description="현재 등록된 모든 임베드와 정보를 확인합니다.")
    async def list_embeds(self, interaction: discord.Interaction):
        # 최신 상태 로드
        embed_manager.config = embed_manager.load_config()
        embeds = embed_manager.config.get("embeds", {})

        if not embeds:
            await interaction.response.send_message("등록된 임베드가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(title="임베드 목록", color=discord.Color.blue())
        
        for name, data in embeds.items():
            kind = data.get("type", "알 수 없음")
            msg_ids = data.get("message_ids", [])
            msg_count = len(msg_ids)
            
            info = [f"**타입**: {kind}"]
            info.append(f"**등록된 메시지**: {msg_count}개")
            
            if kind == "role":
                roles = data.get("data", {}).get("roles", [])
                role_count = len(roles)
                info.append(f"**등록된 역할**: {role_count}개")
            
            embed.add_field(name=f"📄 {name}", value="\n".join(info), inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @is_guild_admin()
    @embed_group.command(name="제거", description="임베드를 시스템에서 제거합니다.")
    @app_commands.describe(name="제거할 임베드 이름")
    async def delete_embed(self, interaction: discord.Interaction, name: str):
        if embed_manager.remove_embed_data(name):
            await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드를 제거함 [길드: {interaction.guild.name}({interaction.guild.id})]")
            await interaction.response.send_message(f"'{name}' 임베드가 제거되었습니다.")
        else:
             await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.")

    @is_guild_admin()
    @embed_group.command(name="색상지정", description="임베드의 색상을 변경합니다.")
    @app_commands.describe(name="임베드 이름", r="Red (0-255)", g="Green (0-255)", b="Blue (0-255)")
    async def set_color(self, interaction: discord.Interaction, name: str, r: int, g: int, b: int):
        data = embed_manager.get_embed_data(name)
        if not data:
            await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.")
            return

        data["color"] = [r, g, b]
        embed_manager.set_embed_data(name, data)
        
        if data["type"] == "role":
             role_embed_cog = self.bot.get_cog("RoleEmbed")
             if role_embed_cog:
                 embed = role_embed_cog.build_role_embed(name, data)
                 view = role_embed_cog.build_role_view(data)
                 await embed_manager.update_embed_messages(self.bot, name, embed, view=view)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드 색상을 ({r},{g},{b})로 변경함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드의 색상이 변경되었습니다.")

    @is_guild_admin()
    @embed_group.command(name="수정", description="임베드를 수정합니다.")
    @app_commands.describe(name="수정할 임베드 이름")
    async def edit_embed(self, interaction: discord.Interaction, name: str):
        data = embed_manager.get_embed_data(name)
        if not data:
            await interaction.response.send_message(f"'{name}' 임베드를 찾을 수 없습니다.", ephemeral=True)
            return
            
        if data["type"] == "entrance":
            entrance_cog = self.bot.get_cog("EntranceEmbed")
            if entrance_cog:
                import src.embed.EntranceEmbed as EntranceEmbed
                view = EntranceEmbed.EntranceEditView(self.bot, name, data)
                embed = entrance_cog.build_entrance_embed(name, data, preview=True)
                content = f"**({name}) 임베드 수정 모드입니다.**"
                await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message("EntranceEmbed 모듈이 로드되지 않았습니다.", ephemeral=True)
        else:
            await interaction.response.send_message(f"해당 타입({data['type']})은 이 명령어를 통한 수정 모드를 지원하지 않습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCommon(bot))
