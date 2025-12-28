import discord
from discord.ext import commands
import json
import os
from typing import Optional, Dict, Any, List
import logging
import pytz

KST = pytz.timezone("Asia/Seoul")
CONFIG_PATH = "config/tree_config.json"
GUILD_ID = [1396829213100605580, 1378632284068122685, 1439281906502865091]

def only_in_guild():
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id in GUILD_ID:
            return True
        return False
    return commands.check(predicate)

def _ensure_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "guilds": {},
                "missions": {},
                "roles": {"auth_roles": []},
                "channels": {
                    "notification_channel": None,
                    "snowflake_channel": None,
                    "game_auth_channel": None,
                    "command_channel": None,
                    "dashboard_channel": None
                },
                "game_auth_roles": [],
                "period": {"start_date": None, "end_date": None}
            }, f, ensure_ascii=False, indent=2)

def _load_config():
    _ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError:
            return {}
            
    # Migration/Default Check
    changed = False
    
    default_structure = {
        "guilds": {},
        "missions": {},
        "roles": {"auth_roles": []},
        "channels": {
            "notification_channel": None,
            "snowflake_channel": None,
            "game_auth_channel": None,
            "command_channel": None,
            "dashboard_channel": None
        },
        "game_auth_roles": [],
        "period": {"start_date": None, "end_date": None},
        "daily_schedule": {}
    }
    
    for key, value in default_structure.items():
        if key not in cfg:
            cfg[key] = value
            changed = True
            
    # Check default missions
    default_missions = {
        "up": 10,
        "recommend": 30,
        "invite": 100,
        "daily_attendance": 50,
        "attendance": 50,
        "voice_1h": 100,
        "game_play": 50,
        "ranking": 0
    }
    for m, amount in default_missions.items():
        if m not in cfg["missions"]:
            cfg["missions"][m] = amount
            changed = True
            
    # Check nested 'channels'
    if "channels" in cfg:
        for k, v in default_structure["channels"].items():
            if k not in cfg["channels"]:
                cfg["channels"][k] = v
                changed = True
                
    # Check nested 'period'
    if "period" in cfg:
         if "start_date" not in cfg["period"]:
             cfg["period"]["start_date"] = None
             changed = True
         if "end_date" not in cfg["period"]:
             cfg["period"]["end_date"] = None
             changed = True
            
    if changed:
        _save_config(cfg)
        
    return cfg

def _save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin_or_auth_role():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        
        cfg = _load_config()
        auth_roles = cfg.get("roles", {}).get("auth_roles", [])
        
        for role in ctx.author.roles:
            if role.id in auth_roles:
                return True
        return False
    return commands.check(predicate)


class TreeConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")



    @commands.group(name='눈송이설정', invoke_without_command=True)
    @is_admin_or_auth_role() 
    @only_in_guild()
    async def tree_config_group(self, ctx):
        """눈송이 시스템 설정 명령어 그룹"""
        embed = discord.Embed(
            title="❄️ 눈송이 시스템 설정",
            description="눈송이 시스템을 설정하는 명령어입니다.",
            color=0xBFDAF7
        )
        embed.add_field(
            name="📝 미션 관리",
            value="`*눈송이설정 미션추가 (이름) (량)`\n`*눈송이설정 미션제거 (이름)`\n`*눈송이설정 미션목록`",
            inline=False
        )
        embed.add_field(
            name="⚙️ 설정",
            value="`*눈송이설정 역할지정 (역할)`\n`*눈송이설정 알림채널지정 (채널)`\n`*눈송이설정 눈송이채널지정 (채널)`\n`*눈송이설정 명령어채널 (채널)`\n`*눈송이설정 상태채널지정 (채널)`",
            inline=False
        )
        embed.add_field(
            name="🎮 게임 인증 설정",
            value="`*눈송이설정 게임인증 채널 (채널)`\n`*눈송이설정 게임인증 역할 (역할)`",
            inline=False
        )
        embed.add_field(
            name="📅 기간 설정",
            value="`*눈송이설정 기간설정 (시작일) (종료일)`\n(*형식: YYYY-MM-DD)",
            inline=False
        )
        
        # 현재 설정 정보 표시
        cfg = _load_config()
        
        # Helper to get mention or None
        def get_channel_mention(key):
            cid = cfg.get("channels", {}).get(key)
            if cid:
                ch = self.bot.get_channel(cid)
                return ch.mention if ch else f"(Deleted: {cid})"
            return "None"

        current_settings = []
        
        # 기간
        period = cfg.get("period", {})
        start = period.get("start_date") or "None"
        end = period.get("end_date") or "None"
        current_settings.append(f"• **기간**: {start} ~ {end}")
        
        # 채널
        current_settings.append(f"• **알림 채널**: {get_channel_mention('notification_channel')}")
        current_settings.append(f"• **눈송이 채널**: {get_channel_mention('snowflake_channel')}")
        current_settings.append(f"• **명령어 채널**: {get_channel_mention('command_channel')}")
        current_settings.append(f"• **상태 채널**: {get_channel_mention('dashboard_channel')}")
        current_settings.append(f"• **게임 인증 채널**: {get_channel_mention('game_auth_channel')}")
        
        # 역할 (개수 표시)
        auth_roles_count = len(cfg.get("roles", {}).get("auth_roles", []))
        game_roles_count = len(cfg.get("game_auth_roles", []))
        current_settings.append(f"• **인증 역할 수**: {auth_roles_count}개")
        current_settings.append(f"• **게임 인증 역할 수**: {game_roles_count}개")

        embed.add_field(
            name="🛠️ 현재 설정값",
            value="\n".join(current_settings),
            inline=False
        )

        await ctx.send(embed=embed)

    @tree_config_group.command(name='미션추가')
    @is_admin_or_auth_role()
    async def add_mission(self, ctx, name: str, amount: int):
        """미션 추가: *눈송이설정 미션추가 (이름) (량)"""
        cfg = _load_config()
        cfg["missions"][name] = amount
        _save_config(cfg)
        await ctx.send(f"✅ 미션 **{name}** ({amount} 눈송이)가 추가/수정되었습니다.")

    @tree_config_group.command(name='미션제거')
    @is_admin_or_auth_role()
    async def remove_mission(self, ctx, name: str):
        """미션 제거: *눈송이설정 미션제거 (이름)"""
        cfg = _load_config()
        if name in cfg["missions"]:
            del cfg["missions"][name]
            _save_config(cfg)
            await ctx.send(f"✅ 미션 **{name}**가 제거되었습니다.")
        else:
            await ctx.send(f"❌ 미션 **{name}**을(를) 찾을 수 없습니다.")

    @tree_config_group.command(name='미션목록')
    async def list_missions(self, ctx):
        """미션 목록 조회"""
        cfg = _load_config()
        missions = cfg.get("missions", {})
        
        if not missions:
            await ctx.send("📝 등록된 미션이 없습니다.")
            return
            
        embed = discord.Embed(title="📝 눈송이 미션 목록", color=0xBFDAF7)
        desc = ""
        for name, amount in missions.items():
            desc += f"• **{name}**: {amount} 눈송이\n"
        embed.description = desc
        await ctx.send(embed=embed)

    @tree_config_group.command(name='역할지정')
    @is_admin_or_auth_role()
    async def set_auth_role(self, ctx, role: discord.Role):
        """인증 가능 역할 지정: *눈송이설정 역할지정 (역할)"""
        cfg = _load_config()
        if "roles" not in cfg:
            cfg["roles"] = {"auth_roles": []}
        
        if role.id not in cfg["roles"]["auth_roles"]:
            cfg["roles"]["auth_roles"].append(role.id)
            _save_config(cfg)
            await ctx.send(f"✅ {role.mention} 역할이 인증 가능 역할로 지정되었습니다.")
        else:
            await ctx.send(f"ℹ️ {role.mention} 역할은 이미 인증 가능 역할입니다.")

    @tree_config_group.command(name='알림채널지정')
    @is_admin_or_auth_role()
    async def set_noti_channel(self, ctx, channel: discord.TextChannel):
        """알림 채널 지정: *눈송이설정 알림채널지정 (채널)"""
        cfg = _load_config()
        if "channels" not in cfg:
            cfg["channels"] = {}
        cfg["channels"]["notification_channel"] = channel.id
        _save_config(cfg)
        await ctx.send(f"✅ 알림 채널이 {channel.mention}으로 설정되었습니다.")

    @tree_config_group.command(name='눈송이채널지정')
    @is_admin_or_auth_role()
    async def set_snowflake_channel(self, ctx, channel: discord.TextChannel):
        """눈송이 줍기 채널 지정: *눈송이설정 눈송이채널지정 (채널)"""
        cfg = _load_config()
        if "channels" not in cfg:
            cfg["channels"] = {}
        cfg["channels"]["snowflake_channel"] = channel.id
        _save_config(cfg)
        await ctx.send(f"✅ 눈송이 줍기 채널이 {channel.mention}으로 설정되었습니다.")

    @tree_config_group.command(name='명령어채널')
    @is_admin_or_auth_role()
    async def set_command_channel(self, ctx, channel: discord.TextChannel):
        """명령어 사용 가능 채널 설정: *눈송이설정 명령어채널 (채널)"""
        cfg = _load_config()
        if "channels" not in cfg:
            cfg["channels"] = {}
        cfg["channels"]["command_channel"] = channel.id
        _save_config(cfg)
        await ctx.send(f"✅ 명령어 사용 채널이 {channel.mention}으로 설정되었습니다.")

    @tree_config_group.command(name='상태채널지정')
    @is_admin_or_auth_role()
    async def set_dashboard_channel(self, ctx, channel: discord.TextChannel):
        """상태(대시보드) 채널 지정: *눈송이설정 상태채널지정 (채널)"""
        cfg = _load_config()
        if "channels" not in cfg:
            cfg["channels"] = {}
        cfg["channels"]["dashboard_channel"] = channel.id
        _save_config(cfg)
        await ctx.send(f"✅ 비몽트리 상태(대시보드) 채널이 {channel.mention}으로 설정되었습니다.")

    @tree_config_group.group(name='게임인증', invoke_without_command=True)
    @is_admin_or_auth_role()
    async def game_auth_group(self, ctx):
        await ctx.send("사용법: `*눈송이설정 게임인증 채널 (채널)` 또는 `*눈송이설정 게임인증 역할 (역할)`")

    @game_auth_group.command(name='채널')
    @is_admin_or_auth_role()
    async def set_game_auth_channel(self, ctx, channel: discord.TextChannel):
        cfg = _load_config()
        if "channels" not in cfg:
            cfg["channels"] = {}
        cfg["channels"]["game_auth_channel"] = channel.id
        _save_config(cfg)
        await ctx.send(f"✅ 게임 인증 채널이 {channel.mention}으로 설정되었습니다.")

    @game_auth_group.command(name='역할')
    @is_admin_or_auth_role()
    async def set_game_auth_role(self, ctx, role: discord.Role):
        cfg = _load_config()
        if "game_auth_roles" not in cfg:
            cfg["game_auth_roles"] = []
        
        if role.id not in cfg["game_auth_roles"]:
            cfg["game_auth_roles"].append(role.id)
            _save_config(cfg)
            await ctx.send(f"✅ {role.mention} 역할이 게임 인증 역할로 추가되었습니다.")
        else:
            await ctx.send("ℹ️ 이미 추가된 역할입니다.")

    @tree_config_group.command(name='기간설정')
    @is_admin_or_auth_role()
    async def set_period(self, ctx, start_date: str, end_date: str):
        """기간 설정: *눈송이설정 기간설정 (시작일) (종료일)"""
        cfg = _load_config()
        cfg["period"]["start_date"] = start_date
        cfg["period"]["end_date"] = end_date
        _save_config(cfg)
        await ctx.send(f"✅ 기간이 **{start_date} ~ {end_date}**로 설정되었습니다.")

    @tree_config_group.command(name='스케줄초기화')
    @is_admin_or_auth_role()
    async def reset_schedule(self, ctx):
        """강제 스케줄 재설정: *눈송이설정 스케줄초기화"""
        cfg = _load_config()
        # Remove schedule, TreeSnowflake will regenerate
        if "daily_schedule" in cfg:
            del cfg["daily_schedule"]
            _save_config(cfg)
        
        await ctx.send("✅ 오늘 눈송이 스케줄이 초기화되었습니다. 잠시 후 자동으로 재설정됩니다.")

    @tree_config_group.command(name='완전초기화')
    @is_admin_or_auth_role()
    async def reset_all_data(self, ctx):
        """데이터베이스 완전 초기화: *눈송이설정 완전초기화"""
        embed = discord.Embed(
            title="⚠️ 데이터베이스 완전 초기화",
            description="모든 유저의 눈송이 보유량, 퀘스트 기록이 영구적으로 삭제됩니다.\n설정(채널, 역할 등)은 유지됩니다.\n\n진행하시려면 **1분 내에** `확인`을 입력해주세요.",
            color=0xFF0000
        )
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "확인"
        
        try:
            await self.bot.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send("❌ 시간이 초과되어 초기화가 취소되었습니다.")
            return
            
        from TreeDataManager import TreeDataManager # Dynamic import to avoid circular dependency if any
        data_manager = TreeDataManager()
        success = await data_manager.reset_database()
        
        if success:
             # Dispatch tree_updated to refresh dashboard (level 0)
            self.bot.dispatch('tree_updated')
            await ctx.send("✅ 데이터베이스가 성공적으로 초기화되었습니다.")
        else:
            await ctx.send("❌ 데이터베이스 초기화 중 오류가 발생했습니다.")

    @tree_config_group.command(name='전체기록열람')
    @is_admin_or_auth_role()
    async def view_all_records(self, ctx):
        """전체 유저 눈송이 기록 열람: *눈송이설정 전체기록열람"""
        from TreeDataManager import TreeDataManager
        data_manager = TreeDataManager()
        rankings = await data_manager.get_all_rankings()
        
        if not rankings:
            await ctx.send("📝 기록된 유저 정보가 없습니다.")
            return

        header = "📄 **전체 유저 눈송이 현황**\n\n"
        messages = []
        current_msg = header
        
        for i, rank in enumerate(rankings):
            line = f"{i+1}. <@{rank['user_id']}> ({rank['user_id']}): {rank['total_gathered']} 눈송이\n"
            
            if len(current_msg) + len(line) > 1900:
                messages.append(current_msg)
                current_msg = line
            else:
                current_msg += line
        
        if current_msg:
            messages.append(current_msg)
            
        for msg in messages:
            # 멘션 방지
            allowed = discord.AllowedMentions(users=False, roles=False, everyone=False)
            await ctx.send(msg, allowed_mentions=allowed)

async def setup(bot):
    await bot.add_cog(TreeConfig(bot))
