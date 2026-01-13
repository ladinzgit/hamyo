import discord
from discord.ext import commands
from src.core.DataManager import DataManager

from discord.ext import commands
import discord
from src.core.DataManager import DataManager
from src.core.admin_utils import GUILD_IDS, is_guild_admin


class HerbConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")

    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        try:
            logger = self.bot.get_cog('Logger')
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def is_owner(self, ctx):
        return ctx.author.id in self.owner_ids
    
    @commands.group(name="허브", invoke_without_command=True)
    @is_guild_admin()
    async def voice(self, ctx):      
        command_name = ctx.invoked_with
        
        embed = discord.Embed(
            title="허브 관리자 명령어", 
            description="허브 관리자 명령어 사용 방법입니다.\n[ *허브 ]로 접근 가능합니다.", 
            colour=discord.Colour.from_rgb(253, 237, 134)
        )
        
        embed.add_field(
            name=f"*{command_name} 채널등록 (채널)", 
            value="기록할 채널/카테고리를 등록합니다. (채널/카테고리 여러 개 지정 가능)", 
            inline=False
        )
        embed.add_field(
            name=f"*{command_name} 채널제거 (채널)", 
            value="기존에 등록되어 있던 채널/카테고리를 제거합니다. (채널/카테고리 여러 개 지정 가능)", 
            inline=False
        ),
        embed.add_field(
            name=f"*{command_name} 채널초기화", 
            value="현재 등록되어 있는 모든 채널/카테고리를 제거합니다.", 
            inline=False
        ),
        embed.add_field(
            name=f"*{command_name} 완전초기화", 
            value="유저 음성 기록을 전부 삭제합니다. **주의! 음성방 기록을 열람하는 다른 명령어가 있는 경우, 그 명령어에서도 모든 기록이 삭제됩니다.**", 
            inline=False
        )

        channel_mentions = []
        
        for channel_id in await self.data_manager.get_tracked_channels("aginari"):
            channel = await self.bot.fetch_channel(channel_id)
            if channel:
                channel_mentions.append(channel.mention)

        if not channel_mentions:
            channel_mentions.append("None")

        embed.add_field(name="||.||", value="**현재 설정**", inline=False)
        embed.add_field(name="기록중인 채널/카테고리", value=", ".join(channel_mentions), inline=False)

        await ctx.reply(embed=embed)
        await self.log(f"관리자 {ctx.author}({ctx.author.id})님께서 명령어 사용 방법을 조회하였습니다.")

    @voice.command(name="채널등록")
    @is_guild_admin()
    async def register_channel(self, ctx, *channels: discord.abc.GuildChannel):
        added = []
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.CategoryChannel)):
                await self.data_manager.register_tracked_channel(ch.id, "aginari")
                added.append(ch.mention)
                await self.log(f"{ctx.author}({ctx.author.id})님에 의해 추적 채널/카테고리에 {ch.mention}({ch.id})를 등록 완료하였습니다.")

        if added:
            await ctx.reply(f"다음 채널/카테고리를 허브 추적에 등록했습니다:\n{', '.join(added)}")
        else:
            await ctx.reply("등록할 유효한 음성 채널이나 카테고리를 찾지 못했습니다.")

    @voice.command(name="채널제거")
    @is_guild_admin()
    async def unregister_channel(self, ctx, *channels: discord.abc.GuildChannel):
        removed = []
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.CategoryChannel)):
                await self.data_manager.unregister_tracked_channel(ch.id, "aginari")
                removed.append(ch.mention)
                await self.log(f"{ctx.author}({ctx.author.id})님에 의해 {ch.mention}({ch.id})채널 추적을 중지하였습니다.")

        if removed:
            await ctx.send(f"다음 채널/카테고리를 허브 추적에서 제거했습니다:\n{', '.join(removed)}")
        else:
            await ctx.send("제거할 유효한 채널을 찾지 못했습니다.")

    @voice.command(name="완전초기화")
    @is_guild_admin()
    async def reset_all(self, ctx):
        await self.data_manager.reset_data()
        await ctx.send("모든 사용자 기록 및 삭제 채널 정보가 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})님에 의해 모든 사용자 기록 및 삭제 채널 정보가 초기화되었습니다.")
        
    @voice.command(name="채널초기화")
    @is_guild_admin()
    async def reset_all_channel(self, ctx):
        await self.data_manager.reset_tracked_channels("aginari")
        await ctx.send("모든 채널 기록이 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})님에 의해 모든 채널 기록이 초기화되었습니다.")
        
        
async def setup(bot: commands.Bot):
    await bot.add_cog(HerbConfig(bot))
