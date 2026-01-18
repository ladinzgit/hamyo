from discord.ext import commands
import discord

GUILD_IDS = [1396829213100605580, 1378632284068122685, 1439281906502865091]

def only_in_guild():
    """
    명령어가 허용된 길드에서 실행되었는지 확인하는 데코레이터입니다.
    """
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id in GUILD_IDS:
            return True
        return False
    return commands.check(predicate)

from discord import app_commands

def is_guild_admin():
    """
    사용자가 허용된 길드의 관리자 권한을 가지고 있는지 확인하는 데코레이터입니다.
    only_in_guild 체크와 관리자 권한 체크를 결합합니다.
    사용자에게 권한이 없는 경우 메시지를 보냅니다.
    """
    async def predicate(ctx):
        if ctx.guild and ctx.guild.id not in GUILD_IDS:
            return False
        
        if ctx.author.guild_permissions.administrator:
            return True
            
        await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        return False
    return commands.check(predicate)

def is_guild_admin_app():
    """
    is_guild_admin의 app_commands 버전입니다.
    """
    async def predicate(interaction: discord.Interaction):
        if interaction.guild and interaction.guild.id not in GUILD_IDS:
            await interaction.response.send_message("허용되지 않은 서버입니다.", ephemeral=True)
            return False
        
        if interaction.user.guild_permissions.administrator:
            return True
            
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        return False
    return app_commands.check(predicate)
