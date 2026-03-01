import discord
from discord.ext import commands
import json
import os
import re
from typing import Optional, List, Dict
from src.core.admin_utils import is_guild_admin

# Configuration
CONFIG_PATH = "config/prefix_config.json"

def extract_name(text: str) -> Optional[str]:
    """
    닉네임에서 칭호(《 ... 》 또는 『 ... 』) 부분을 추출합니다.
    """
    match = re.search(r"[《『]\s*([^》』]+)\s*[》』]", text or "")
    return match.group(1).strip() if match else None

class PrefixChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rules: List[Dict[str, str]] = [] # [{'role_id': int, 'title': str}, ...]
        self.exceptions: List[int] = [] # [role_id, ...]
        self._load_config()

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            self.rules = []
            self.exceptions = []
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.rules = data.get("rules", [])
                self.exceptions = data.get("exceptions", [])
        except Exception as e:
            print(f"❌ PrefixChanger 설정 로드 실패: {e}")
            self.rules = []
            self.exceptions = []

    def _save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "rules": self.rules,
                "exceptions": self.exceptions
            }, f, ensure_ascii=False, indent=2)

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} 로드 완료!")

    async def log(self, message: str):
        """Logger cog를 통해 로그 메시지를 전송"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    def _get_pure_name(self, display_name: str) -> str:
        """
        닉네임에서 칭호나 접두어를 제거한 순수 이름을 추출합니다.
        """
        # 1. 칭호 《 ... 》 또는 『 ... 』 제거
        name = re.sub(r"^[《『][^》』]+[》』]\s*", "", display_name)
        
        # 2. 접두어 &, ! 등 제거
        name = re.sub(r"^[&!]\s*", "", name)
            
        return name.strip() or display_name

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # 봇은 무시
        if after.bot:
            return

        # 1단계: 예외 역할 확인
        user_role_ids = [r.id for r in after.roles]
        if any(rid in self.exceptions for rid in user_role_ids):
            return

        # 2단계: 형식 확인
        # 칭호(『 ... 』)가 없는 경우(예: & 닉네임) 무시
        current_title = extract_name(after.display_name)
        if current_title is None:
            return

        # 3단계: 규칙 매칭
        # 나중에 추가된 규칙(리스트의 뒤쪽)이 우선순위가 높음
        target_rule = None
        for rule in reversed(self.rules):
            if rule['role_id'] in user_role_ids:
                target_rule = rule
                break
        
        # 적용할 규칙이 없으면 중단
        if not target_rule:
            return

        target_title = target_rule['title']

        # 4단계: 닉네임 업데이트
        if current_title != target_title:
            pure_name = self._get_pure_name(after.display_name)
            new_nick = f"《 {target_title} 》 {pure_name}"
            
            try:
                await after.edit(nick=new_nick[:32], reason="칭호 규칙 자동 변경")
                msg = f"📝 {after}({after.id}) 닉네임 변경: {after.display_name} -> {new_nick}"
                print(msg)
                await self.log(msg)
            except discord.Forbidden:
                msg = f"⚠️ {after}({after.id}) 닉네임 변경 권한 부족"
                print(msg)
                await self.log(msg)
            except Exception as e:
                msg = f"❌ {after}({after.id}) 닉네임 변경 실패: {e}"
                print(msg)
                await self.log(msg)

    # 명령어 그룹
    @commands.group(name="칭호규칙", invoke_without_command=True)
    @is_guild_admin()
    async def prefix_rules(self, ctx):
        """칭호 변경 규칙을 관리합니다."""
        await ctx.send("`추가`, `예외추가`, `확인`, `일괄제거` 하위 명령어를 사용하세요.")

    @prefix_rules.command(name="추가")
    @is_guild_admin()
    async def add_rule(self, ctx, role: discord.Role, *, title: str):
        """
        칭호 규칙을 추가합니다. 나중에 추가된 규칙이 높은 우선순위를 가집니다.
        사용법: *칭호규칙 추가 @역할 칭호
        """
        self.rules.append({
            "role_id": role.id,
            "title": title,
            "role_name": role.name
        })
        self._save_config()
        await ctx.reply(f"✅ 규칙 추가됨: {role.mention} -> 《 {title} 》 (우선순위: {len(self.rules)})")
        await self.log(f"{ctx.author}({ctx.author.id})가 칭호 규칙 추가: {role.name}({role.id}) -> 《 {title} 》 [우선순위: {len(self.rules)}]")

    @prefix_rules.command(name="예외추가")
    @is_guild_admin()
    async def add_exception(self, ctx, role: discord.Role):
        """
        예외 역할을 추가합니다. 이 역할을 가진 유저는 칭호 변경이 동작하지 않습니다.
        사용법: *칭호규칙 예외추가 @역할
        """
        if role.id not in self.exceptions:
            self.exceptions.append(role.id)
            self._save_config()
            await ctx.reply(f"✅ 예외 역할 추가됨: {role.mention}")
            await self.log(f"{ctx.author}({ctx.author.id})가 칭호 예외 역할 추가: {role.name}({role.id})")
        else:
            await ctx.reply("이미 예외 목록에 있는 역할입니다.")

    @prefix_rules.command(name="확인")
    @is_guild_admin()
    async def list_rules(self, ctx):
        """현재 등록된 규칙과 예외를 확인합니다."""
        embed = discord.Embed(
            title="칭호 규칙 현황",
            description="규칙은 아래 목록의 **하단**에 있을수록 높은 우선순위를 가집니다.",
            color=discord.Color.gold()
        )

        # 규칙 목록
        rules_text = ""
        if self.rules:
            for i, rule in enumerate(self.rules, 1):
                role_mention = f"<@&{rule['role_id']}>"
                rules_text += f"{i}. {role_mention} → 《 {rule['title']} 》\n"
        else:
            rules_text = "등록된 규칙이 없습니다."
        
        embed.add_field(name="📋 우선순위 규칙 (번호가 클수록 높음)", value=rules_text, inline=False)

        # 예외 역할 목록
        exceptions_text = ""
        if self.exceptions:
            exceptions_text = ", ".join([f"<@&{rid}>" for rid in self.exceptions])
        else:
            exceptions_text = "등록된 예외 역할이 없습니다."
        
        embed.add_field(name="🛡️ 예외 역할", value=exceptions_text, inline=False)

        await ctx.send(embed=embed)

    @prefix_rules.command(name="일괄제거")
    @is_guild_admin()
    async def clear_rules(self, ctx):
        """저장된 모든 규칙과 예외를 삭제합니다."""
        self.rules = []
        self.exceptions = []
        self._save_config()
        await ctx.reply("🗑️ 모든 규칙과 예외 설정이 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})가 모든 칭호 규칙 및 예외를 초기화함")

async def setup(bot):
    await bot.add_cog(PrefixChanger(bot))
