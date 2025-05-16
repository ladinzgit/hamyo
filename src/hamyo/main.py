import discord
from discord.ext import commands
import os
import asyncio
import typing
# import logging

# logging.basicConfig(level=logging.DEBUG)

# application_id = os.environ.get("FLORENCE_APPLICATION_ID")
application_id = os.environ.get("SUB_APPLICATION_ID")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="*", intents=intents, help_command=None, owner_id = 277812129011204097, application_id = application_id)

# bot_token = os.environ.get("FLORENCE_TOKEN") # main
bot_token = os.environ.get("SUB_DISCORD_BOT_TOKEN")

# load cogs

async def load():
    success = []
    fail = []
    why = {}
    
    cog_path = os.path.join(os.path.dirname(__file__), "cogs")

    for filename in os.listdir(cog_path):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                success.append(filename)
            except Exception as e:
                print(e)
                fail.append(filename)
                why[str(filename)] = e

    logger = bot.get_cog('Logger')

    if success:
        for cog in success:
            await logger.log(f"{cog[:-3]} cog가 성공적으로 로드되었습니다", cog)
    if fail:
        for cog in fail:
            await logger.log(f"{cog[:-3]} cog가 로드에 실패하였습니다. 오류: {why[cog]}", cog)
    
    await logger.log("모든 cog가 로드되었습니다.", "main.py")

# server start

async def main():
    async with bot:
        await bot.start(bot_token)

 # bot ready

@bot.event
async def on_ready():
    await load()

    if logger := bot.get_cog('Logger'):
        await logger.log("봇이 성공적으로 시작되었습니다.", "main.py")

    print("Online!")
    
    activity = discord.CustomActivity(name="오늘의 차를 우리고 있어요...")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
 # slash command sync

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
    ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: typing.Optional[typing.Literal["~","*","^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@sync.error
async def sync_error(error):
    print(f"error in sync: {error}")

asyncio.run(main())
