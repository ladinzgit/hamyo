"""
한국어 뮤직봇 — 채널 고정형 단일 embed UI
지정된 채널에 단 하나의 플레이어 embed를 유지하며,
유저가 채널에 텍스트를 입력하면 검색·재생합니다.
"""
import asyncio
import json
import os
import re

import discord
import lavalink
from discord.ext import commands
from lavalink.errors import ClientError
from lavalink.events import QueueEndEvent, TrackExceptionEvent, TrackStartEvent
from lavalink.server import LoadType

url_rx = re.compile(r'https?://(?:www\.)?.+')
CONFIG_PATH = 'config/music_config.json'
COMMAND_PREFIX = '?!'

LOOP_INFO = {
    0: ('🔁', '반복 없음', discord.ButtonStyle.secondary),
    1: ('🔂', '한 곡 반복', discord.ButtonStyle.success),
    2: ('🔁', '전체 반복', discord.ButtonStyle.primary),
}


# ──────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────

def _fmt(ms: int) -> str:
    s = ms // 1000
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _bar(position: int, duration: int, length: int = 17) -> str:
    if not duration:
        return '─' * length
    filled = min(int((position / duration) * length), length - 1)
    return '▬' * filled + '🔘' + '─' * (length - filled - 1)


def load_config() -> dict:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(data: dict):
    os.makedirs('config', exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────
# Lavalink 음성 클라이언트
# ──────────────────────────────────────────

class LavalinkVoiceClient(discord.VoiceProtocol):
    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, 'lavalink'):
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(
                host='localhost', port=2333, password='youshallnotpass',
                region='us', name='default-node',
            )
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        await self.lavalink.voice_update_handler({'t': 'VOICE_SERVER_UPDATE', 'd': data})

    async def on_voice_state_update(self, data):
        channel_id = data['channel_id']
        if not channel_id:
            await self._destroy()
            return
        self.channel = self.client.get_channel(int(channel_id))
        await self.lavalink.voice_update_handler({'t': 'VOICE_STATE_UPDATE', 'd': data})

    async def connect(self, *, timeout: float, reconnect: bool,
                      self_deaf: bool = False, self_mute: bool = False) -> None:
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(
            channel=self.channel, self_mute=self_mute, self_deaf=self_deaf,
        )

    async def disconnect(self, *, force: bool = False) -> None:
        player = self.lavalink.player_manager.get(self.channel.guild.id)
        if not force and not player.is_connected:
            return
        await self.channel.guild.change_voice_state(channel=None)
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()
        if self._destroyed:
            return
        self._destroyed = True
        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass


# ──────────────────────────────────────────
# 고정 플레이어 뷰
# ──────────────────────────────────────────

class MusicPlayerView(discord.ui.View):
    """채널에 하나만 존재하는 음악 컨트롤 패널"""

    def __init__(self, cog: 'Music', guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self._refresh_buttons()

    # ── 내부 헬퍼 ──────────────────────────

    def _player(self):
        try:
            return self.cog.bot.lavalink.player_manager.get(self.guild_id)
        except Exception:
            return None

    def _btn(self, custom_id: str):
        for item in self.children:
            if getattr(item, 'custom_id', None) == custom_id:
                return item
        return None

    def _refresh_buttons(self):
        player = self._player()
        active = bool(player and player.current)
        paused = getattr(player, 'paused', False) if player else False
        loop = getattr(player, 'loop', 0) if player else 0
        shuffled = getattr(player, 'shuffle', False) if player else False

        # 재생/일시정지
        if btn := self._btn('mp:pause'):
            btn.disabled = not active
            btn.emoji = '▶️' if paused else '⏸️'
            btn.label = '재생' if paused else '일시정지'
            btn.style = discord.ButtonStyle.success if paused else discord.ButtonStyle.secondary

        # 건너뛰기 / 정지
        for cid in ('mp:skip', 'mp:stop'):
            if btn := self._btn(cid):
                btn.disabled = not active

        # 볼륨
        for cid in ('mp:vol_down', 'mp:vol_up'):
            if btn := self._btn(cid):
                btn.disabled = not active

        # 루프
        if btn := self._btn('mp:loop'):
            emoji, label, style = LOOP_INFO.get(loop, LOOP_INFO[0])
            btn.emoji = emoji
            btn.label = label
            btn.style = style

        # 셔플
        if btn := self._btn('mp:shuffle'):
            btn.style = discord.ButtonStyle.success if shuffled else discord.ButtonStyle.secondary

    # ── embed 빌더 ─────────────────────────

    def build_embed(self) -> discord.Embed:
        player = self._player()

        # ─ 대기 상태 ─
        if not player or not player.current:
            embed = discord.Embed(
                title='🎵  선율이 흐르는 서재',
                description=(
                    '> 음악 제목이나 YouTube URL을 채널에 입력하면\n'
                    '> 비몽책방 서재에 선율이 흐르기 시작합니다.'
                ),
                color=0x2b2d31,
            )
            embed.add_field(
                name='📖 지원 형식',
                value='• YouTube 검색어\n• YouTube URL / 재생목록 URL',
                inline=False,
            )
            embed.set_footer(text='비몽책방 · 하묘')
            return embed

        # ─ 재생 상태 ─
        track = player.current
        paused = getattr(player, 'paused', False)
        loop = getattr(player, 'loop', 0)
        shuffled = getattr(player, 'shuffle', False)
        volume = getattr(player, 'volume', 100)

        color = 0xf4d03f if paused else 0xc8a96e
        status = '⏸️  선율이 잠시 멈췄어요' if paused else '▶️  선율이 흐르는 중'

        embed = discord.Embed(title=status, color=color)

        # 제목 + 아티스트
        embed.add_field(
            name='🎵 제목',
            value=f'[{track.title}]({track.uri})',
            inline=False,
        )
        embed.add_field(
            name='🎤 아티스트',
            value=track.author or '알 수 없음',
            inline=True,
        )

        # 진행 바
        if track.stream:
            embed.add_field(name='📡 유형', value='🔴 라이브 스트림', inline=True)
        else:
            pos = getattr(player, 'position', 0)
            dur = track.duration
            embed.add_field(
                name='⏱️ 진행',
                value=f'`{_fmt(pos)}` {_bar(pos, dur)} `{_fmt(dur)}`',
                inline=False,
            )

        # 설정 한 줄 요약
        loop_emoji, loop_label, _ = LOOP_INFO.get(loop, LOOP_INFO[0])
        embed.add_field(
            name='⚙️ 설정',
            value=(
                f'{loop_emoji} {loop_label}　　'
                f'{"🔀 셔플 켜짐" if shuffled else "➡️ 순서 재생"}　　'
                f'🔊 {volume}%'
            ),
            inline=False,
        )

        # 대기열 미리보기 (최대 5곡)
        queue = list(getattr(player, 'queue', []))
        if queue:
            lines = [
                f'`{i+1}.`  {t.title}　`{_fmt(t.duration)}`'
                for i, t in enumerate(queue[:5])
            ]
            if len(queue) > 5:
                lines.append(f'*... 외 {len(queue) - 5}곡*')
            embed.add_field(
                name=f'📋 다음 대기  ({len(queue)}곡)',
                value='\n'.join(lines),
                inline=False,
            )

        artwork = getattr(track, 'artwork_url', None)
        if artwork:
            embed.set_thumbnail(url=artwork)

        embed.set_footer(text='비몽책방 · 채널에 제목이나 링크를 입력하면 대기열에 추가됩니다')
        return embed

    # ── 버튼 — 행 0: 재생 제어 ────────────

    @discord.ui.button(emoji='⏸️', label='일시정지', style=discord.ButtonStyle.secondary,
                       custom_id='mp:pause', row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            return await interaction.response.send_message(
                '음성 채널에 먼저 입장해주세요.', ephemeral=True,
            )
        player = self._player()
        if not player or not player.is_playing:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        await player.set_pause(not player.paused)
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji='⏭️', label='건너뛰기', style=discord.ButtonStyle.secondary,
                       custom_id='mp:skip', row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            return await interaction.response.send_message(
                '음성 채널에 먼저 입장해주세요.', ephemeral=True,
            )
        player = self._player()
        if not player or not player.current:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        await player.skip()
        await interaction.response.send_message('⏭️ 다음 곡으로 넘어갑니다.', ephemeral=True)

    @discord.ui.button(emoji='⏹️', label='정지', style=discord.ButtonStyle.danger,
                       custom_id='mp:stop', row=0)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice:
            return await interaction.response.send_message(
                '음성 채널에 먼저 입장해주세요.', ephemeral=True,
            )
        player = self._player()
        if not player:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        player.queue.clear()
        await player.stop()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # ── 버튼 — 행 1: 설정 ──────────────────

    @discord.ui.button(emoji='🔀', label='셔플', style=discord.ButtonStyle.secondary,
                       custom_id='mp:shuffle', row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        player.shuffle = not getattr(player, 'shuffle', False)
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji='🔁', label='반복 없음', style=discord.ButtonStyle.secondary,
                       custom_id='mp:loop', row=1)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        player.loop = (getattr(player, 'loop', 0) + 1) % 3
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji='🔉', label='-10%', style=discord.ButtonStyle.secondary,
                       custom_id='mp:vol_down', row=1)
    async def vol_down_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        await player.set_volume(max(0, getattr(player, 'volume', 100) - 10))
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji='🔊', label='+10%', style=discord.ButtonStyle.secondary,
                       custom_id='mp:vol_up', row=1)
    async def vol_up_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player:
            return await interaction.response.send_message(
                '재생 중인 음악이 없습니다.', ephemeral=True,
            )
        await player.set_volume(min(200, getattr(player, 'volume', 100) + 10))
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# ──────────────────────────────────────────
# Music Cog
# ──────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):
            bot.lavalink = lavalink.Client(bot.user.id)
            bot.lavalink.add_node(
                host='localhost', port=2333, password='youshallnotpass',
                region='us', name='default-node',
            )
        self.lavalink: lavalink.Client = bot.lavalink
        self.lavalink.add_event_hooks(self)

    async def cog_load(self):
        print(f'✅ {self.__class__.__name__} loaded successfully!')
        asyncio.create_task(self._restore_embeds())

    def cog_unload(self):
        self.lavalink._event_hooks.clear()

    # ── 로깅 헬퍼 ──────────────────────────

    async def _log(self, message: str, code: str, color: discord.Color = discord.Color.red()):
        """Logger cog를 통해 에러 로그를 전송합니다."""
        print(f'[{code}] {message}')
        logger = self.bot.get_cog('Logger')
        if logger:
            await logger.log(
                message=f'`[{code}]` {message}',
                file_name='music.py',
                title='🎵 뮤직봇 오류',
                color=color,
            )

    # ── 채널 관리 ───────────────────────────

    async def setup_channel(self, guild: discord.Guild, channel: discord.TextChannel):
        """음악 채널 초기화: 기존 메시지 삭제 후 플레이어 embed 게시."""
        # 권한 확인
        perms = channel.permissions_for(guild.me)
        if not perms.manage_messages:
            raise discord.Forbidden(None, '메시지 관리 권한이 없습니다.')  # type: ignore

        await channel.purge(limit=None)

        view = MusicPlayerView(self, guild.id)
        msg = await channel.send(embed=view.build_embed(), view=view)

        cfg = load_config()
        guild_key = str(guild.id)
        cfg.setdefault(guild_key, {})['channel_id'] = channel.id
        cfg[guild_key]['message_id'] = msg.id
        save_config(cfg)

    async def _update_embed(self, guild_id: int):
        """플레이어 embed를 현재 상태로 갱신합니다."""
        guild_cfg = load_config().get(str(guild_id), {})
        channel_id = guild_cfg.get('channel_id')
        message_id = guild_cfg.get('message_id')
        if not channel_id or not message_id:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        try:
            msg = await channel.fetch_message(message_id)
            view = MusicPlayerView(self, guild_id)
            await msg.edit(embed=view.build_embed(), view=view)
        except discord.NotFound:
            # embed가 삭제된 경우 재생성
            await self.setup_channel(guild, channel)
        except Exception as e:
            await self._log(
                f'embed 갱신 실패 (guild={guild_id}): {type(e).__name__}: {e}',
                code='MUSIC-006',
            )

    async def _restore_embeds(self):
        """봇 재시작 시 설정된 모든 길드의 embed를 복원합니다."""
        await self.bot.wait_until_ready()
        for guild_id_str, guild_cfg in load_config().items():
            if not guild_cfg.get('channel_id') or not guild_cfg.get('message_id'):
                continue
            try:
                await self._update_embed(int(guild_id_str))
            except Exception as e:
                await self._log(
                    f'embed 복원 실패 (guild={guild_id_str}): {type(e).__name__}: {e}',
                    code='MUSIC-007',
                )

    # ── on_message: 텍스트 입력 → 음악 재생 ──

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_cfg = load_config().get(str(message.guild.id), {})
        channel_id = guild_cfg.get('channel_id')
        if not channel_id or message.channel.id != channel_id:
            return

        # 모든 유저 메시지 즉시 삭제 (채널 무결성 유지)
        try:
            await message.delete()
        except Exception:
            pass

        # 명령어 접두사로 시작하면 음악 검색 처리 안 함
        if message.content.startswith(COMMAND_PREFIX):
            return

        query = message.content.strip()
        if not query:
            return

        channel = message.channel
        guild = message.guild

        async def _err(text: str, code: str):
            embed = discord.Embed(title='❌ 오류 발생', color=0xff4444)
            embed.add_field(name='내용', value=text, inline=False)
            embed.add_field(name='오류 코드', value=f'`{code}`', inline=True)
            embed.set_footer(text='비몽책방 · 문제가 지속되면 관리자에게 문의하세요')
            await channel.send(embed=embed, delete_after=10)

        # 음성 채널 확인
        if not message.author.voice or not message.author.voice.channel:
            return await _err('음성 채널에 먼저 입장해주세요.', 'MUSIC-000')

        voice_ch = message.author.voice.channel
        voice_client = guild.voice_client

        # 봇 음성 연결
        if voice_client is None:
            perms = voice_ch.permissions_for(guild.me)
            if not perms.connect or not perms.speak:
                return await _err('음성 채널 접속 또는 말하기 권한이 없습니다.', 'MUSIC-000')
            try:
                await voice_ch.connect(cls=LavalinkVoiceClient)
            except Exception as e:
                await _err('음성 채널 연결에 실패했습니다.', 'MUSIC-002')
                await self._log(
                    f'음성 채널 연결 실패 (guild={guild.id}, ch={voice_ch.id}): {type(e).__name__}: {e}',
                    code='MUSIC-002',
                )
                return
        elif voice_client.channel.id != voice_ch.id:
            return await _err('봇이 있는 음성 채널에 입장해주세요.', 'MUSIC-000')

        player = self.bot.lavalink.player_manager.create(guild.id)
        player.store('channel', channel_id)

        # 새 세션 시작 시 기본 볼륨 30%로 설정
        if not player.is_playing and not player.queue:
            await player.set_volume(30)

        # Lavalink 노드 확인
        if player.node is None:
            await _err('음악 서버(Lavalink)에 연결되어 있지 않습니다. 잠시 후 다시 시도해주세요.', 'MUSIC-001')
            await self._log(
                f'Lavalink 노드 미연결 (guild={guild.id}): player.node is None',
                code='MUSIC-001',
            )
            return

        # 트랙 검색
        search = query if url_rx.match(query) else f'ytsearch:{query}'
        try:
            results = await player.node.get_tracks(search)
        except Exception as e:
            await _err('트랙 검색 중 오류가 발생했습니다.', 'MUSIC-003')
            await self._log(
                f'트랙 검색 실패 (guild={guild.id}, query="{query}"): {type(e).__name__}: {e}',
                code='MUSIC-003',
            )
            return

        if results.load_type == LoadType.ERROR:
            await _err('트랙을 불러오는 중 오류가 발생했습니다.', 'MUSIC-003')
            await self._log(
                f'LoadType.ERROR (guild={guild.id}, query="{query}")',
                code='MUSIC-003',
            )
            return

        if results.load_type == LoadType.EMPTY:
            return await _err('검색 결과가 없습니다. 다른 검색어를 시도해보세요.', 'MUSIC-000')

        was_playing = player.is_playing

        if results.load_type == LoadType.PLAYLIST:
            for t in results.tracks:
                t.extra['requester'] = message.author.id
                player.add(track=t)
            confirm = f'📋 **{results.playlist_info.name}** ({len(results.tracks)}곡) 대기열에 추가됨'
        else:
            track = results.tracks[0]
            track.extra['requester'] = message.author.id
            player.add(track=track)
            confirm = f'🎵 **{track.title}** 대기열에 추가됨'

        if was_playing:
            await channel.send(
                embed=discord.Embed(description=confirm, color=0x1db954),
                delete_after=5,
            )
            await self._update_embed(guild.id)
        else:
            try:
                await player.play()
            except Exception as e:
                await _err('트랙 재생을 시작하는 데 실패했습니다.', 'MUSIC-004')
                await self._log(
                    f'player.play() 실패 (guild={guild.id}): {type(e).__name__}: {e}',
                    code='MUSIC-004',
                )

    # ── Lavalink 이벤트 ─────────────────────

    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        try:
            await self._update_embed(event.player.guild_id)
        except Exception as e:
            await self._log(
                f'TrackStartEvent embed 갱신 실패 (guild={event.player.guild_id}): {type(e).__name__}: {e}',
                code='MUSIC-006',
            )

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect(force=True)
        await self._update_embed(guild_id)

    @lavalink.listener(TrackExceptionEvent)
    async def on_track_exception(self, event: TrackExceptionEvent):
        guild_id = event.player.guild_id
        exception = getattr(event, 'exception', None) or getattr(event, 'error', '알 수 없는 오류')

        await self._log(
            f'트랙 재생 중 예외 발생 (guild={guild_id}): {exception}',
            code='MUSIC-005',
        )

        cfg = load_config().get(str(guild_id), {})
        channel_id = cfg.get('channel_id')
        if not channel_id:
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(title='❌ 재생 오류', color=0xff4444)
        embed.add_field(name='내용', value='트랙 재생 중 오류가 발생하여 해당 곡을 건너뜁니다.', inline=False)
        embed.add_field(name='오류 코드', value='`MUSIC-005`', inline=True)
        embed.set_footer(text='비몽책방 · 문제가 지속되면 관리자에게 문의하세요')
        await channel.send(embed=embed, delete_after=10)


async def setup(bot):
    await bot.add_cog(Music(bot))
