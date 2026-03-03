import discord
from discord.ext import commands
import datetime
import json
import os
import inspect
import pytz

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = self._load_log_channel()

    async def cog_load(self):
        # Logger cog를 가져와서 로그를 전송
        try:
            print(f"✅ {self.__class__.__name__} loaded successfully!")

        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로드 중 오류 발생: {e}")
        
    def _load_log_channel(self):
        """설정 파일에서 로그 채널 ID를 로드합니다."""
        try:
            if os.path.exists('config/logger_config.json'):
                with open('config/logger_config.json', 'r') as f:
                    data = json.load(f)
                    return data.get('log_channel_id')
        except Exception as e:
            print(f"로그 채널 설정 로드 중 오류 발생: {e}")
        return None
    
    def _save_log_channel(self, channel_id):
        """로그 채널 ID를 설정 파일에 저장합니다."""
        os.makedirs('config', exist_ok=True)
        with open('config/logger_config.json', 'w') as f:
            json.dump({'log_channel_id': channel_id}, f)
    
    @commands.command(name='로그채널설정')
    @commands.is_owner()
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """로그를 전송할 채널을 설정합니다."""
        if channel is None:
            channel = ctx.channel
            
        self.log_channel_id = channel.id
        self._save_log_channel(channel.id)
        await ctx.send(f"로그 채널이 {channel.mention}로 설정되었습니다.")
        await self.log(f"로그 채널이 {channel.name} ({channel.id})로 설정되었습니다. [길드: {ctx.guild.name if ctx.guild else 'DM'}({ctx.guild.id if ctx.guild else 'N/A'}), 채널: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'}({ctx.channel.id})]")
    
    async def log(self, message=None, file_name=None, title="📝 시스템 로그", color=discord.Color.blue(), embed=None):
        """로그 메시지를 지정된 채널에 전송합니다."""
        if not self.log_channel_id:
            return
            
        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            return
            
        # 파일명이 지정되지 않은 경우 호출한 파일의 이름을 가져옵니다
        if file_name is None:
            try:
                frame = inspect.currentframe().f_back
                file_name = os.path.basename(frame.f_code.co_filename)
            except Exception:
                file_name = "Unknown"
        
        # 한국 시간대로 변환
        kr_tz = pytz.timezone("Asia/Seoul")
        kr_time = datetime.datetime.now(kr_tz)
        
        if embed is None:
            log_embed = discord.Embed(
                title=title,
                description=str(message) if message else "",
                color=color,
                timestamp=kr_time
            )
            log_embed.set_footer(text=f"모듈: {file_name}")
        else:
            log_embed = embed
            if message and not log_embed.description:
                log_embed.description = str(message)
            if not log_embed.timestamp:
                log_embed.timestamp = kr_time
            if not log_embed.footer.text:
                log_embed.set_footer(text=f"모듈: {file_name}")

        try:
            await channel.send(embed=log_embed) 
        except Exception as e:
            print(f"로그 전송 중 오류 발생: {e}")

    # Cog error handler
    async def cog_command_error(self, ctx, error):
        print(f"An error occurred in the {self.__class__.__name__} cog: {error}")
        await self.log(f"An error occurred in the {self.__class__.__name__} cog: {error} [길드: {ctx.guild.name if ctx.guild else 'DM'}, 채널: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'}({ctx.channel.id})]")

async def setup(bot):
    await bot.add_cog(Logger(bot))