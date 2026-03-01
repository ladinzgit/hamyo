import discord
from discord.ext import commands
from discord import app_commands
from .EmbedUtils import embed_manager

class EntranceBasicModal(discord.ui.Modal, title="기본 설정 수정"):
    embed_color = discord.ui.TextInput(
        label="색상 (Hex 코드, 예: FF0000, 빈칸: 기본치)",
        style=discord.TextStyle.short,
        required=False,
        max_length=7
    )
    embed_title = discord.ui.TextInput(
        label="제목 (Title)",
        style=discord.TextStyle.short,
        required=False,
        max_length=256
    )
    embed_description = discord.ui.TextInput(
        label="설명 (Description)",
        style=discord.TextStyle.long,
        required=True,
        max_length=4000,
        placeholder="{user.mention}, {user.name}, {server.name}, {member_count} 지원"
    )

    def __init__(self, bot, name, embed_data, view):
        super().__init__()
        self.bot = bot
        self.embed_name = name
        self.embed_data = embed_data
        self.parent_view = view
        
        # 기본값 세팅
        color_list = self.embed_data.get("color", [255, 255, 255])
        self.embed_color.default = f"#{color_list[0]:02x}{color_list[1]:02x}{color_list[2]:02x}"
        self.embed_title.default = self.embed_data["data"].get("title", "")
        self.embed_description.default = self.embed_data["data"].get("description", "")

    async def on_submit(self, interaction: discord.Interaction):
        # Hex To RGB
        color_val = self.embed_color.value.strip() if self.embed_color.value else "#FFFFFF"
        if color_val.startswith("#"):
            color_val = color_val[1:]
        try:
            r, g, b = tuple(int(color_val[i:i+2], 16) for i in (0, 2, 4))
            self.embed_data["color"] = [r, g, b]
        except ValueError:
            pass # 잘못된 색상 무시
        
        self.embed_data["data"]["title"] = self.embed_title.value
        self.embed_data["data"]["description"] = self.embed_description.value
        
        embed_manager.set_embed_data(self.embed_name, self.embed_data)
        
        # 뷰 업데이트 반영
        await self.parent_view.update_message(interaction)

class EntranceAuthorModal(discord.ui.Modal, title="Author 설정 수정"):
    author_name = discord.ui.TextInput(
        label="이름",
        style=discord.TextStyle.short,
        required=False,
        max_length=256
    )
    author_icon = discord.ui.TextInput(
        label="아이콘 URL (http://... 형식)",
        style=discord.TextStyle.short,
        required=False
    )

    def __init__(self, bot, name, embed_data, view):
        super().__init__()
        self.bot = bot
        self.embed_name = name
        self.embed_data = embed_data
        self.parent_view = view
        
        author_data = self.embed_data["data"].get("author", {})
        self.author_name.default = author_data.get("name", "")
        self.author_icon.default = author_data.get("icon_url", "")

    async def on_submit(self, interaction: discord.Interaction):
        self.embed_data["data"]["author"] = {
            "name": self.author_name.value,
            "icon_url": self.author_icon.value
        }
        embed_manager.set_embed_data(self.embed_name, self.embed_data)
        await self.parent_view.update_message(interaction)

class EntranceFooterModal(discord.ui.Modal, title="Footer 설정 수정"):
    footer_text = discord.ui.TextInput(
        label="텍스트",
        style=discord.TextStyle.short,
        required=False,
        max_length=2048
    )
    footer_icon = discord.ui.TextInput(
        label="아이콘 URL (http://... 형식)",
        style=discord.TextStyle.short,
        required=False
    )

    def __init__(self, bot, name, embed_data, view):
        super().__init__()
        self.bot = bot
        self.embed_name = name
        self.embed_data = embed_data
        self.parent_view = view
        
        footer_data = self.embed_data["data"].get("footer", {})
        self.footer_text.default = footer_data.get("text", "")
        self.footer_icon.default = footer_data.get("icon_url", "")

    async def on_submit(self, interaction: discord.Interaction):
        self.embed_data["data"]["footer"] = {
            "text": self.footer_text.value,
            "icon_url": self.footer_icon.value
        }
        embed_manager.set_embed_data(self.embed_name, self.embed_data)
        await self.parent_view.update_message(interaction)

class EntranceImageModal(discord.ui.Modal, title="이미지 설정 수정"):
    thumbnail_url = discord.ui.TextInput(
        label="썸네일 URL (우측 상단 작은 이미지)",
        style=discord.TextStyle.short,
        required=False
    )
    image_url = discord.ui.TextInput(
        label="메인 이미지 URL (하단 큰 이미지)",
        style=discord.TextStyle.short,
        required=False
    )

    def __init__(self, bot, name, embed_data, view):
        super().__init__()
        self.bot = bot
        self.embed_name = name
        self.embed_data = embed_data
        self.parent_view = view
        
        images_data = self.embed_data["data"].get("images", {})
        self.thumbnail_url.default = images_data.get("thumbnail", "")
        self.image_url.default = images_data.get("image", "")

    async def on_submit(self, interaction: discord.Interaction):
        self.embed_data["data"]["images"] = {
            "thumbnail": self.thumbnail_url.value,
            "image": self.image_url.value
        }
        embed_manager.set_embed_data(self.embed_name, self.embed_data)
        await self.parent_view.update_message(interaction)


class ChannelSelectView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="전송할 채널을 선택하세요")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        self.parent_view.embed_data["data"]["channel_id"] = channel.id
        embed_manager.set_embed_data(self.parent_view.embed_name, self.parent_view.embed_data)
        await interaction.response.send_message(f"입장 메시지 전송 채널이 {channel.mention}으로 설정되었습니다.", ephemeral=True)
        # 본 뷰 업데이트
        await self.parent_view.update_message_no_interaction(interaction.message)

class RoleSelectView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="지급할 역할을 선택하세요 (최대 5개)", max_values=5)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        roles = [role.id for role in select.values]
        self.parent_view.embed_data["data"]["roles"] = roles
        embed_manager.set_embed_data(self.parent_view.embed_name, self.parent_view.embed_data)
        
        role_mentions = ", ".join([role.mention for role in select.values])
        await interaction.response.send_message(f"입장 시 지급될 역할이 {role_mentions}로 설정되었습니다.", ephemeral=True)
        # 본 뷰 업데이트
        await self.parent_view.update_message_no_interaction(interaction.message)


class EntranceEditView(discord.ui.View):
    def __init__(self, bot, name, embed_data):
        super().__init__(timeout=None)
        self.bot = bot
        self.embed_name = name
        self.embed_data = embed_data
        
    async def update_message(self, interaction: discord.Interaction):
        entrance_cog = self.bot.get_cog("EntranceEmbed")
        if entrance_cog:
            embed = entrance_cog.build_entrance_embed(self.embed_name, self.embed_data, preview=True)
            await interaction.response.edit_message(embed=embed, view=self)
            
    async def update_message_no_interaction(self, message: discord.Message):
        entrance_cog = self.bot.get_cog("EntranceEmbed")
        if entrance_cog:
            embed = entrance_cog.build_entrance_embed(self.embed_name, self.embed_data, preview=True)
            await message.edit(embed=embed, view=self)

    @discord.ui.button(label="기본 설정", style=discord.ButtonStyle.primary, row=0)
    async def btn_basic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EntranceBasicModal(self.bot, self.embed_name, self.embed_data, self))

    @discord.ui.button(label="Author 설정", style=discord.ButtonStyle.secondary, row=0)
    async def btn_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EntranceAuthorModal(self.bot, self.embed_name, self.embed_data, self))

    @discord.ui.button(label="Footer 설정", style=discord.ButtonStyle.secondary, row=0)
    async def btn_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EntranceFooterModal(self.bot, self.embed_name, self.embed_data, self))

    @discord.ui.button(label="이미지 설정", style=discord.ButtonStyle.secondary, row=0)
    async def btn_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EntranceImageModal(self.bot, self.embed_name, self.embed_data, self))

    @discord.ui.button(label="보낼 채널 설정", style=discord.ButtonStyle.success, row=1)
    async def btn_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelSelectView(self)
        await interaction.response.send_message("입장 임베드를 보낼 채널을 아래에서 선택하세요.", view=view, ephemeral=True)

    @discord.ui.button(label="지급 역할 설정", style=discord.ButtonStyle.success, row=1)
    async def btn_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleSelectView(self)
        await interaction.response.send_message("유저 입장 시 자동으로 지급할 역할을 아래에서 선택하세요.", view=view, ephemeral=True)

    @discord.ui.button(label="테스트 해보기", style=discord.ButtonStyle.danger, row=1)
    async def btn_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        entrance_cog = self.bot.get_cog("EntranceEmbed")
        if entrance_cog:
            await entrance_cog.send_entrance_embed(interaction.channel, interaction.user, self.embed_name, self.embed_data)
            await interaction.response.send_message("테스트 임베드를 전송했습니다!", ephemeral=True)


class EntranceEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_entrance_embed(self, name: str, embed_data: dict, preview: bool = False, member: discord.Member = None) -> discord.Embed:
        data = embed_data.get("data", {})
        
        color_list = embed_data.get("color", [255, 255, 255])
        color = discord.Color.from_rgb(*color_list)
        
        title = data.get("title", "")
        description = data.get("description", "")
        
        if member:
            server = member.guild
            member_count = server.member_count if server else 0
            
            # 텍스트 치환
            if title:
                title = title.replace("{user.mention}", member.mention)
                title = title.replace("{user.name}", member.name)
                title = title.replace("{server.name}", server.name if server else "")
                title = title.replace("{member_count}", str(member_count))
                
            if description:
                description = description.replace("{user.mention}", member.mention)
                description = description.replace("{user.name}", member.name)
                description = description.replace("{server.name}", server.name if server else "")
                description = description.replace("{member_count}", str(member_count))

        embed = discord.Embed(title=title, description=description, color=color)
        
        author = data.get("author", {})
        if author.get("name"):
            embed.set_author(name=author.get("name"), icon_url=author.get("icon_url") or None)
            
        footer = data.get("footer", {})
        if footer.get("text"):
            embed.set_footer(text=footer.get("text"), icon_url=footer.get("icon_url") or None)
            
        images = data.get("images", {})
        if images.get("thumbnail"):
            try:
                embed.set_thumbnail(url=images.get("thumbnail"))
            except:
                pass
        if images.get("image"):
            try:
                embed.set_image(url=images.get("image"))
            except:
                pass
                
        if preview:
            channel_id = data.get("channel_id")
            channel_str = f"<#{channel_id}>" if channel_id else "설정되지 않음"
            
            roles = data.get("roles", [])
            roles_str = ", ".join([f"<@&{r}>" for r in roles]) if roles else "설정되지 않음"
            
            embed.add_field(name="[설정 정보 (현재 페이지에서만 보입니다)]", value=f"**전송 채널**: {channel_str}\n**지급 역할**: {roles_str}", inline=False)
            
        return embed

    async def send_entrance_embed(self, dest_channel, member: discord.Member, name: str, embed_data: dict):
        embed = self.build_entrance_embed(name, embed_data, preview=False, member=member)
        content = f"{member.mention}"
        try:
            msg = await dest_channel.send(content=content, embed=embed)
            await embed_manager.add_message_id(name, dest_channel.id, msg.id)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass
            
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embeds = embed_manager.config.get("embeds", {})
        
        for name, data in embeds.items():
            if data.get("type") == "entrance":
                # entrance 임베드 발견
                e_data = data.get("data", {})
                channel_id = e_data.get("channel_id")
                
                if channel_id:
                    channel = member.guild.get_channel(channel_id)
                    if channel:
                        await self.send_entrance_embed(channel, member, name, data)
                
                # 역할 지급
                roles_to_give = e_data.get("roles", [])
                if roles_to_give:
                    role_objs = [member.guild.get_role(r) for r in roles_to_give if member.guild.get_role(r) is not None]
                    if role_objs:
                        try:
                            await member.add_roles(*role_objs)
                        except discord.Forbidden:
                            pass
                        except discord.HTTPException:
                            pass
                break # 단 1개만 동작하면 됨

async def setup(bot: commands.Bot):
    await bot.add_cog(EntranceEmbed(bot))
