import json
import discord
from discord.ext import commands
from pathlib import Path

CONFIG_PATH = Path('config/herbconfig.json')

class HerbConfig(commands.Cog):
    """Cog for managing herb configuration commands (admin only)."""
    def __init__(self, bot):
        self.bot = bot
        # Load or initialize config file
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump({'log_channel': None}, f)
        with open(CONFIG_PATH, encoding='utf-8') as f:
            self.config = json.load(f)

    @commands.group(name='허브설정', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def herbconfig(self, ctx):
        """Display available herb settings subcommands."""
        await ctx.send('사용 가능한 서브명령어: `로그채널`, `되살리기지급`')

    @herbconfig.command(name='로그채널')
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where admin logs/errors are sent."""
        self.config['log_channel'] = channel.id
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        await ctx.send(f'✅ 로그 채널이 {channel.mention} 으로 설정되었습니다.')

    @herbconfig.command(name='되살리기지급')
    @commands.has_permissions(administrator=True)
    async def give_revive(self, ctx, member: discord.Member, amount: int = 1):
        """Give revive items to a user."""
        storage = self.bot.get_cog('HerbStorageCog')
        # Add `revive` items to inventory
        for _ in range(amount):
            await storage.add_revive_item(member.id)
        await ctx.send(f'✅ {member.mention}님께 되살리기 아이템을 지급했습니다. x{amount}')

async def setup(bot: commands.Bot):
    await bot.add_cog(HerbConfig(bot))