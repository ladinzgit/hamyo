import discord
from discord.ext import commands
import sys
import os
import asyncio

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_load(self):
        # Logger cog를 통해 로그를 전송
        try:
            print(f"✅ {self.__class__.__name__} loaded successfully!")

        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로드 중 오류 발생: {e}")
        
    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        logger = self.bot.get_cog('Logger')
        if logger:
            await logger.log(message)

    @commands.command(name='재시작', aliases=['restart'])
    @commands.is_owner()
    async def restart(self, ctx):
        try:
            await self.log("Bot restart initiated by owner.")
            
            restart_message = await ctx.send("봇을 재시작하는 중입니다...")
            
            await self.bot.change_presence(
                status=discord.Status.idle, 
                activity=discord.Game(name="재시작 중...")
            )
            
            await asyncio.sleep(1)
            
            python = sys.executable
            script = os.path.abspath(sys.argv[0])
            
            await self.bot.close()
            
            os.execl(python, python, script)
            
        except Exception as e:
            error_message = f"재시작 중 오류가 발생했습니다: {str(e)}"
            await self.log(f"Restart error: {str(e)}")
            await ctx.send(error_message)
            
    @commands.command(name='종료', aliases=['shutdown', 'stop'])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """봇을 안전하게 종료합니다."""
        try:
            await self.log("Bot shutdown initiated by owner.")
            
            shutdown_message = await ctx.send("봇을 종료하는 중입니다...")
            
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name="종료 중...")
            )
            
            await asyncio.sleep(1)
            
            await ctx.send("봇이 종료되었습니다. 안녕히 계세요! 👋")
            await self.bot.close()
            
            sys.exit(0)
            
        except Exception as e:
            error_message = f"종료 중 오류가 발생했습니다: {str(e)}"
            await self.log(f"Shutdown error: {str(e)}")
            await ctx.send(error_message)

    @commands.command(name='상태', aliases=['status'])
    @commands.is_owner()
    async def check_status(self, ctx):
        """봇의 현재 상태를 확인합니다."""
        try:
            embed = discord.Embed(
                title="봇 상태",
                color=discord.Color.blue(),
                timestamp=ctx.message.created_at
            )
            
            embed.add_field(
                name="상태", 
                value=str(self.bot.status).capitalize(), 
                inline=True
            )
            embed.add_field(
                name="지연 시간", 
                value=f"{round(self.bot.latency * 1000)}ms", 
                inline=True
            )
            
            guild_count = len(self.bot.guilds)
            embed.add_field(
                name="서버 수", 
                value=str(guild_count), 
                inline=True
            )
            
            if hasattr(self.bot, 'start_time'):
                uptime = ctx.message.created_at - self.bot.start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                embed.add_field(
                    name="업타임",
                    value=f"{hours}시간 {minutes}분 {seconds}초",
                    inline=True
                )
            
            await ctx.send(embed=embed)
            await self.log("Status check performed.")
                
        except Exception as e:
            error_message = f"상태 확인 중 오류가 발생했습니다: {str(e)}"
            await self.log(f"Status check error: {str(e)}")
            await ctx.send(error_message)

    # Cog error handler
    async def cog_command_error(self, ctx, error):
        print(f"An error occurred in the {self.__class__.__name__} cog: {error}")
        await self.log(f"An error occurred in the {self.__class__.__name__} cog: {error}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
