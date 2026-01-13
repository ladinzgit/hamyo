import discord
from discord.ext import commands
from src.core.DataManager import DataManager

from src.core.admin_utils import GUILD_IDS, only_in_guild, is_guild_admin


class VoiceConfig(commands.Cog):
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

    @commands.group(name="보이스", invoke_without_command=True)
    @is_guild_admin()
    async def voice(self, ctx):  
        command_name = ctx.invoked_with
        
        embed = discord.Embed(
            title="보이스 관리자 명령어", 
            description="보이스 관리자 명령어 사용 방법입니다.\n[*보이스]로 접근 가능합니다.", 
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
            name=f"*{command_name} ID제거 (채널ID)", 
            value="삭제된 채널/카테고리를 ID로 직접 제거합니다. (ID 여러 개 지정 가능)", 
            inline=False
        ),
        embed.add_field(
            name=f"*{command_name} 채널초기화", 
            value="현재 등록되어 있는 모든 채널/카테고리를 제거합니다.", 
            inline=False
        ),
        embed.add_field(
            name=f"*{command_name} 완전초기화", 
            value="유저 음성 기록을 전부 삭제합니다. **주의! 보이스 기록을 열람하는 다른 명령어가 있는 경우, 그 명령어에서도 모든 기록이 삭제됩니다.**", 
            inline=False
        )

        channel_mentions = []
        
        for channel_id in await self.data_manager.get_tracked_channels("voice"):
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            
            if channel:
                channel_mentions.append(channel.mention)
            else:
                # 삭제된 카테고리/채널 처리
                channel_mentions.append(f"삭제된 카테고리(ID: {channel_id})")

        if not channel_mentions:
            channel_mentions.append("None")

        embed.add_field(name="||.||", value="**현재 설정**", inline=False)
        embed.add_field(name="기록중인 채널/카테고리", value=", ".join(channel_mentions), inline=False)

        await ctx.reply(embed=embed)
        await self.log(f"관리자 {ctx.author}({ctx.author.id})님께서 명령어 사용 방법을 조회하였습니다.")

    @voice.command(name="채널등록")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def register_channel(self, ctx, *channels: discord.abc.GuildChannel):
        added = []
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.CategoryChannel)):
                await self.data_manager.register_tracked_channel(ch.id, "voice")
                added.append(ch.mention)
                await self.log(f"{ctx.author}({ctx.author.id})님에 의해 추적 채널/카테고리에 {ch.mention}({ch.id})를 등록 완료하였습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

        if added:
            await ctx.reply(f"다음 채널/카테고리를 보이스 추적에 등록했습니다:\n{', '.join(added)}")
        else:
            await ctx.reply("등록할 유효한 음성 채널이나 카테고리를 찾지 못했습니다.")

    @voice.command(name="채널제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def unregister_channel(self, ctx, *channels: discord.abc.GuildChannel):
        removed = []
        for ch in channels:
            if isinstance(ch, (discord.VoiceChannel, discord.CategoryChannel)):
                await self.data_manager.unregister_tracked_channel(ch.id, "voice")
                removed.append(ch.mention)
                await self.log(f"{ctx.author}({ctx.author.id})님에 의해 {ch.mention}({ch.id})채널 추적을 중지하였습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

        if removed:
            await ctx.send(f"다음 채널/카테고리를 보이스 추적에서 제거했습니다:\n{', '.join(removed)}")
        else:
            await ctx.send("제거할 유효한 채널을 찾지 못했습니다.")

    @voice.command(name="ID제거")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def unregister_channel_by_id(self, ctx, *channel_ids: int):
        """삭제된 카테고리/채널을 ID로 직접 제거합니다."""
        removed = []
        not_found = []
        tracked_channels = await self.data_manager.get_tracked_channels("voice")
        
        for cid in channel_ids:
            if cid in tracked_channels:
                await self.data_manager.unregister_tracked_channel(cid, "voice")
                removed.append(str(cid))
                await self.log(f"{ctx.author}({ctx.author.id})님에 의해 ID {cid} 채널/카테고리 추적을 중지하였습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")
            else:
                not_found.append(str(cid))

        msg_parts = []
        if removed:
            msg_parts.append(f"다음 ID의 채널/카테고리를 보이스 추적에서 제거했습니다: {', '.join(removed)}")
        if not_found:
            msg_parts.append(f"다음 ID는 등록되어 있지 않습니다: {', '.join(not_found)}")
        
        if msg_parts:
            await ctx.send("\n".join(msg_parts))
        else:
            await ctx.send("제거할 ID를 입력해주세요.")

    @voice.command(name="완전초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_all(self, ctx):
        await self.data_manager.reset_data()
        await ctx.send("모든 사용자 기록 및 삭제 채널 정보가 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})님에 의해 모든 사용자 기록 및 삭제 채널 정보가 초기화되었습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")
        
    @voice.command(name="채널초기화")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def reset_all_channel(self, ctx):
        await self.data_manager.reset_tracked_channels("voice")
        await ctx.send("모든 채널 기록이 초기화되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})님에 의해 모든 채널 기록이 초기화되었습니다. [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

    @voice.command(name="데이터통합")
    @only_in_guild()
    @commands.has_permissions(administrator=True)
    async def migrate_all_data(self, ctx):
        user_paths = ["src/florence/jsons/user_times.json", "src/florence/voice_sub/user_times.json"]
        deleted_path = "src/florence/jsons/deleted_channels.json"
        await self.data_manager.migrate_multiple_user_times(user_paths, deleted_path)
        await ctx.send("데이터 통합 마이그레이션이 완료되었습니다.")
        await self.log(f"{ctx.author}({ctx.author.id})님에 의해 데이터 통합 마이그레이션 실행 [길드: {ctx.guild.name}({ctx.guild.id}), 채널: {ctx.channel.name}({ctx.channel.id})]")

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceConfig(bot))
