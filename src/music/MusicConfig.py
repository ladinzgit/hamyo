"""
음악봇 설정 Cog — 관리자 전용
?!음악설정 : 음악 채널 지정, 채널 초기화, 비활성화
"""
import discord
from discord.ext import commands

from src.core.admin_utils import is_guild_admin, GUILD_IDS
from src.music.music import load_config, save_config


# ──────────────────────────────────────────
# 채널 ID 입력 모달
# ──────────────────────────────────────────

class ChannelModal(discord.ui.Modal, title='음악 채널 설정'):
    channel_input = discord.ui.TextInput(
        label='채널 ID',
        placeholder='텍스트 채널 ID를 입력하세요 (예: 123456789012345678)',
        required=True,
        min_length=17,
        max_length=20,
    )

    def __init__(self, parent_view: 'MusicConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.channel_input.value.strip()
        try:
            channel_id = int(raw)
        except ValueError:
            return await interaction.response.send_message(
                '❌ 올바른 채널 ID를 입력해주세요.', ephemeral=True,
            )

        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                '❌ 해당 ID의 텍스트 채널을 찾을 수 없습니다.', ephemeral=True,
            )

        # 권한 확인
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.manage_messages or not perms.send_messages:
            return await interaction.response.send_message(
                f'❌ {channel.mention}에서 메시지 관리 및 전송 권한이 필요합니다.', ephemeral=True,
            )

        # 설정 패널을 먼저 업데이트 (작업이 오래 걸릴 수 있으므로)
        await interaction.response.edit_message(
            embed=discord.Embed(
                description=f'⏳ {channel.mention} 채널을 초기화하는 중...',
                color=0xf0c040,
            ),
            view=None,
        )

        music_cog = interaction.client.get_cog('Music')
        try:
            if music_cog:
                await music_cog.setup_channel(interaction.guild, channel)
            else:
                # Music cog 없이 config만 저장
                cfg = load_config()
                cfg.setdefault(str(interaction.guild.id), {})['channel_id'] = channel.id
                save_config(cfg)
        except discord.Forbidden:
            return await interaction.edit_original_response(
                embed=discord.Embed(
                    description=f'❌ {channel.mention}에서 메시지를 관리할 권한이 없습니다.',
                    color=0xff4444,
                )
            )
        except Exception as e:
            return await interaction.edit_original_response(
                embed=discord.Embed(
                    description=f'❌ 채널 설정 중 오류가 발생했습니다: {e}',
                    color=0xff4444,
                )
            )

        # 완료 후 설정 패널 다시 표시
        view = MusicConfigView()
        await interaction.edit_original_response(
            embed=MusicConfigView.build_embed(interaction.guild),
            view=view,
        )


# ──────────────────────────────────────────
# 설정 패널 뷰
# ──────────────────────────────────────────

class MusicConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @staticmethod
    def build_embed(guild: discord.Guild) -> discord.Embed:
        cfg = load_config().get(str(guild.id), {})
        channel_id = cfg.get('channel_id')
        message_id = cfg.get('message_id')

        embed = discord.Embed(
            title='🎵 선율이 흐르는 서재 — 설정',
            description='음악 채널을 지정하면 해당 채널에 비몽책방 서재 플레이어가 생성됩니다.',
            color=0xc8a96e,
        )

        if channel_id:
            ch = guild.get_channel(channel_id)
            ch_text = ch.mention if ch else f'알 수 없는 채널 (ID: `{channel_id}`)'
            status = '🟢 선율이 흐르는 중'
        else:
            ch_text = '설정되지 않음'
            status = '🔴 고요한 서재'

        embed.add_field(name='📻 상태', value=status, inline=True)
        embed.add_field(name='📚 음악 채널', value=ch_text, inline=True)

        if message_id:
            embed.add_field(
                name='📌 플레이어 메시지',
                value=f'ID: `{message_id}`',
                inline=False,
            )

        embed.set_footer(text='비몽책방 · 아래 버튼으로 설정을 변경하세요  •  관리자 전용')
        return embed

    @staticmethod
    async def _check_admin(interaction: discord.Interaction) -> bool:
        """버튼 사용자가 허용된 서버의 관리자인지 확인합니다."""
        if interaction.guild and interaction.guild.id not in GUILD_IDS:
            await interaction.response.send_message('허용되지 않은 서버입니다.', ephemeral=True)
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message('이 기능은 서버 관리자만 사용할 수 있습니다.', ephemeral=True)
        return False

    @discord.ui.button(label='채널 설정', emoji='📚', style=discord.ButtonStyle.primary, row=0)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_modal(ChannelModal(self))

    @discord.ui.button(label='채널 초기화', emoji='🔄', style=discord.ButtonStyle.secondary, row=0)
    async def reset_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """현재 설정된 채널의 메시지를 모두 삭제하고 플레이어 embed를 재생성합니다."""
        if not await self._check_admin(interaction):
            return
        cfg = load_config().get(str(interaction.guild.id), {})
        channel_id = cfg.get('channel_id')
        if not channel_id:
            return await interaction.response.send_message(
                '❌ 설정된 음악 채널이 없습니다.', ephemeral=True,
            )

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message(
                '❌ 설정된 채널을 찾을 수 없습니다.', ephemeral=True,
            )

        await interaction.response.edit_message(
            embed=discord.Embed(
                description=f'⏳ {channel.mention} 채널을 초기화하는 중...',
                color=0xf0c040,
            ),
            view=None,
        )

        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.setup_channel(interaction.guild, channel)

        view = MusicConfigView()
        await interaction.edit_original_response(
            embed=self.build_embed(interaction.guild),
            view=view,
        )

    @discord.ui.button(label='비활성화', emoji='🔕', style=discord.ButtonStyle.danger, row=0)
    async def disable_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """음악 채널 지정을 해제합니다. (채널 내용은 유지)"""
        if not await self._check_admin(interaction):
            return
        cfg = load_config()
        guild_key = str(interaction.guild.id)
        cfg.setdefault(guild_key, {}).pop('channel_id', None)
        cfg[guild_key].pop('message_id', None)
        save_config(cfg)

        await interaction.response.edit_message(
            embed=self.build_embed(interaction.guild), view=self,
        )

    @discord.ui.button(label='닫기', emoji='✖️', style=discord.ButtonStyle.secondary, row=0)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description='✅ 설정을 닫았습니다.', color=0x2b2d31),
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ──────────────────────────────────────────
# MusicConfig Cog
# ──────────────────────────────────────────

class MusicConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print(f'✅ {self.__class__.__name__} loaded successfully!')

    @commands.command(name='음악설정', aliases=['musicconfig', 'mc'])
    @is_guild_admin()
    @commands.guild_only()
    async def music_config(self, ctx: commands.Context):
        """음악봇 설정 패널을 엽니다. (관리자 전용)"""
        view = MusicConfigView()
        await ctx.send(embed=MusicConfigView.build_embed(ctx.guild), view=view)

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                embed=discord.Embed(
                    description='❌ 이 명령어는 서버 관리자만 사용할 수 있습니다.',
                    color=0xff4444,
                ),
                delete_after=6,
            )


async def setup(bot):
    await bot.add_cog(MusicConfig(bot))
