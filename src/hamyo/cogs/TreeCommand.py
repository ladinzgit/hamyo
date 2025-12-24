import discord
from discord.ext import commands
from TreeDataManager import TreeDataManager
import json
import logging
from datetime import datetime
import pytz
import os

KST = pytz.timezone("Asia/Seoul")
CONFIG_PATH = "config/tree_config.json"
GUILD_ID = [1396829213100605580, 1378632284068122685, 1439281906502865091]

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id in GUILD_ID:
            return True
        return False
    return commands.check(predicate)

def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class TreeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = TreeDataManager()
        
    async def cog_load(self):
        await self.data_manager.ensure_initialized()
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    def _is_valid_period(self):
        cfg = _load_config()
        period = cfg.get("period", {})
        start_str = period.get("start_date")
        end_str = period.get("end_date")
        
        if not start_str or not end_str:
            return False 
        
        try:
            now = datetime.now(KST).date()
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
            return start <= now <= end
        except:
            return False

    def _is_auth_user(self, member):
        if member.guild_permissions.administrator:
            return True
        
        cfg = _load_config()
        auth_roles = cfg.get("roles", {}).get("auth_roles", [])
        for role in member.roles:
            if role.id in auth_roles:
                return True
        return False

    def _get_korean_mission_name(self, mission_name: str) -> str:
        mapping = {
            'attendance': '출석체크',
            'voice_1h': '자유 또는 허브키우기 음성방에서 1시간 활동하기',
            'game_play': '게임모집글 통해 게임하기',
            'recommend': '추천',
            'invite': '지인초대',
            'ranking': '랭크',
            'up': '업'
        }
        return mapping.get(mission_name, mission_name)


    @commands.Cog.listener()
    async def on_mission_completion(self, user_id: int, mission_name: str, channel: discord.TextChannel = None, auth_user: discord.Member = None):
        if not self._is_valid_period():
            return
        
        if channel and channel.guild.id not in GUILD_ID:
            return
        
        cfg = _load_config()
        missions = cfg.get("missions", {})
        
        mapping = {
            'daily_attendance': 'attendance',
            'attendance': 'attendance',
            'weekly_recommend_3': 'recommend',
            'recommend': 'recommend',
            'invite': 'invite',
            'voice_1h': 'voice_1h',
            'game_play': 'game_play',
            'ranking': 'ranking'
        }
        
        target_mission = mapping.get(mission_name, mission_name)
        
        if target_mission not in missions:
            # Debug log to Discord
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(f"DEBUG: {target_mission} not in missions config")
            return 
            
        amount = missions[target_mission]
        
        one_time_list = ['review', 'song', 'event_recom', 'snowman', 'diary', 'beverage']
        
        if target_mission in one_time_list:
            periodicity = 'one_time'
        else:
            periodicity = 'daily' 
        
        # 'recommend', 'up', 'invite' are allowed multiple times per day
        if target_mission in ['recommend', 'up', 'invite']:
             already_completed = False
        else:
             already_completed = await self.data_manager.check_mission_completion(user_id, target_mission, periodicity)
        
        if already_completed:
            # Debug log to Discord
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(f"DEBUG: {target_mission} already completed for {user_id}")
            return 
            
        success = await self.data_manager.add_snowflake(user_id, amount, target_mission, periodicity)
        
        if success:
            # Determine target channel: Priority to Configured Notification Channel
            noti_channel_id = cfg.get("channels", {}).get("notification_channel")
            target_channel = None
            
            if noti_channel_id:
                 target_channel = self.bot.get_channel(noti_channel_id)
            
            # Fallback to passed channel (e.g. context) if notification channel not set
            if not target_channel:
                 target_channel = channel
            
            if target_channel:
                korean_name = self._get_korean_mission_name(target_mission)
                
                # Unified Notification Design (Manual & Generic)
                # Fetch data for footer
                data = await self.data_manager.get_user_snowflake(user_id)
                total_snowflakes = data['total_gathered'] if data else amount
                
                member = target_channel.guild.get_member(user_id)
                member_mention = member.mention if member else f"<@{user_id}>"

                description_art = f"""
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO <:BM_evt_002:1326463567838547968> {member_mention} 님 **({korean_name})** 미션 완료다묘 *!*
( つ❄️O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯
"""
                embed = discord.Embed(
                    title="<a:BM_evt_001:1449016605169156166>､ 눈송이 지급",
                    description=description_art,
                    color=0xBFDAF7
                )
                
                footer_text = f"지급 눈송이: {amount} 눈송이 • 보유 눈송이 {total_snowflakes} 눈송이"
                if auth_user:
                     footer_text += f" • 관리자: {auth_user.display_name}"
                     
                embed.set_footer(text=footer_text)
                
                try:
                    await target_channel.send(content=member_mention, embed=embed)
                except Exception as e:
                    print(f"Failed to send notification: {e}")

            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(f"눈송이 지급: {user_id} - {target_mission} ({amount})")

            self.bot.dispatch('tree_updated')

    @commands.group(name='눈송이', invoke_without_command=True)
    @only_in_guild()
    async def snowflake_group(self, ctx):
        """눈송이 명령어 그룹"""
        embed = discord.Embed(
            title="❄️ 눈송이 명령어",
            description="비몽트리 눈송이 관련 명령어입니다.",
            color=0xBFDAF7
        )
        embed.add_field(name="🔍 확인", value="`*눈송이 확인` - 내 눈송이 보유량과 순위 확인", inline=False)
        
        if self._is_auth_user(ctx.author):
            embed.add_field(name="✅ 인증 (관리자/인증자)", value="`*눈송이 인증 (유저) (미션이름)` - 수동 인증", inline=False)
            
        await ctx.send(embed=embed)

    @snowflake_group.command(name='확인')
    @only_in_guild()
    async def check_snowflake(self, ctx):
        """내 눈송이 확인"""
        if not self._is_valid_period():
            await ctx.send("⌛ 지금은 눈송이 기간이 아닙니다.")
            return

        cfg = _load_config()
        cmd_channel_id = cfg.get("channels", {}).get("command_channel")
        
        if cmd_channel_id and ctx.channel.id != cmd_channel_id:
            cmd_channel = self.bot.get_channel(cmd_channel_id)
            ch_name = cmd_channel.mention if cmd_channel else "지정된 채널"
            await ctx.send(f"❌ 이 명령어는 {ch_name}에서만 사용할 수 있습니다.", delete_after=5)
            return

        data = await self.data_manager.get_user_snowflake(ctx.author.id)
        rank = await self.data_manager.get_user_rank(ctx.author.id)
        
        amount = data['total_gathered'] if data else 0
        
        # 커스텀 ASCII 아트 임베드 생성 (One-line format)
        description_art = f"""
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO <:BM_evt_002:1326463567838547968> {ctx.author.mention} 님은 **눈송이 {amount}개** 가지고 있다묘 *!* **{rank}등**이다묘 *!!*
( つ❄️O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯ 
        """
        
        embed = discord.Embed(
            title="<a:BM_evt_001:1449016605169156166>､ 눈송이 확인",
            description=description_art,
            color=0xBFDAF7
        )
        await ctx.send(embed=embed)
        
    @snowflake_group.command(name='인증')
    @only_in_guild()
    async def manual_auth(self, ctx, member: discord.Member, mission_name: str):
        """수동 인증: *눈송이 인증 (유저) (미션이름)"""
        if not self._is_valid_period():
            await ctx.send("⌛ 지금은 눈송이 기간이 아닙니다.")
            return

        if not self._is_auth_user(ctx.author):
            await ctx.send("❌ 권한이 없습니다.")
            return

        cfg = _load_config()
        if mission_name not in cfg.get("missions", {}):
            await ctx.send(f"❌ '{mission_name}' 미션을 찾을 수 없습니다.")
            return
            
        # 수동 인증 실행 with auth_user
        await self.on_mission_completion(member.id, mission_name, ctx.channel, auth_user=ctx.author)
        await ctx.message.add_reaction("✅")

    @commands.Cog.listener()
    async def on_message(self, message):
        """게임 인증 채널 감지"""
        if message.author.bot:
            return
            
        if not self._is_valid_period():
            return
        
        if message.guild and message.guild.id not in GUILD_ID:
            return

        cfg = _load_config()
        game_channel_id = cfg.get("channels", {}).get("game_auth_channel")
        
        if not game_channel_id or message.channel.id != game_channel_id:
            return
            
        game_roles = cfg.get("game_auth_roles", [])
        if not game_roles:
            return
            
        mentioned_role_ids = [r.id for r in message.role_mentions]
        
        matched = False
        for rid in game_roles:
            if rid in mentioned_role_ids:
                matched = True
                break
        
        if matched:
            # Pass None for channel to force usage of Notification Channel
            await self.on_mission_completion(message.author.id, "game_play", None)

async def setup(bot):
    await bot.add_cog(TreeCommand(bot))
