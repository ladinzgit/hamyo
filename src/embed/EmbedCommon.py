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
    @app_commands.describe(kind="임베드 종류 (현재는 '역할'만 지원)", name="임베드 이름")
    @app_commands.choices(kind=[
        app_commands.Choice(name="역할", value="role")
    ])
    async def create_embed(self, interaction: discord.Interaction, kind: str, name: str):
        if embed_manager.get_embed_data(name):
            await interaction.response.send_message(f"이미 '{name}'이라는 이름의 임베드가 존재합니다.")
            return

        # 타입에 따른 데이터 초기화
        data = {
            "type": kind,
            "color": [255, 255, 255], # 기본 흰색
            "message_ids": [],
            "data": {}
        }

        if kind == "role":
            data["data"]["roles"] = []
        
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
        
        # 타입에 따라 임베드 생성
        role_embed_cog = None
        if data["type"] == "role":
            role_embed_cog = self.bot.get_cog("RoleEmbed")
            if role_embed_cog:
                embed = role_embed_cog.build_role_embed(name, data)
            else:
                 await interaction.response.send_message("RoleEmbed 모듈이 로드되지 않았습니다.", ephemeral=True)
                 return
        else:
             await interaction.response.send_message(f"알 수 없는 임베드 타입입니다: {data['type']}", ephemeral=True)
             return

        # 채널에 직접 전송
        msg = await interaction.channel.send(embed=embed)
        
        # 메시지 ID 저장
        await embed_manager.add_message_id(name, interaction.channel_id, msg.id)

        # 역할 임베드의 경우 반응 추가
        if data["type"] == "role" and role_embed_cog:
            # 데이터 갱신 (ID 추가된 것 반영)
            updated_data = embed_manager.get_embed_data(name)
            await role_embed_cog.update_reactions(name, updated_data)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드를 채널 {interaction.channel.name}({interaction.channel.id})에 출력함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message("출력이 완료되었습니다.", ephemeral=True)

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
        
        # 업데이트 트리거
        if data["type"] == "role":
             role_embed_cog = self.bot.get_cog("RoleEmbed")
             if role_embed_cog:
                 embed = role_embed_cog.build_role_embed(name, data)
                 await embed_manager.update_embed_messages(self.bot, name, embed)

        await self.log(f"{interaction.user}({interaction.user.id})가 '{name}' 임베드 색상을 ({r},{g},{b})로 변경함 [길드: {interaction.guild.name}({interaction.guild.id})]")
        await interaction.response.send_message(f"'{name}' 임베드의 색상이 변경되었습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCommon(bot))
