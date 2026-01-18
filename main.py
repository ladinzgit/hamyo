import discord
from discord.ext import commands
import os
import asyncio
import typing
from dotenv import load_dotenv

load_dotenv()
import logging

# logging.basicConfig(level=logging.DEBUG)

application_id = os.environ.get("APPLICATION_ID")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="*", intents=intents, help_command=None, owner_id = 277812129011204097, application_id = application_id)
bot_token = os.environ.get("DISCORD_BOT_TOKEN")

# load cogs

async def load():
    success = [] 
    fail = []
    why = {}
    
    # Root source directory
    src_path = os.path.join(os.path.dirname(__file__), "src")
    
    # List of directories to ignore
    ignored_dirs = {"core", "__pycache__"}

    # 1. Priority Load: utils (for Scheduler, Logger)
    utils_path = os.path.join(src_path, "utils")
    if os.path.isdir(utils_path):
        for filename in os.listdir(utils_path):
             if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = f"src.utils.{filename[:-3]}"
                try:
                    await bot.load_extension(cog_name)
                    success.append(cog_name)
                except Exception as e:
                    print(f"Failed to load priority cog {cog_name}: {e}")
                    fail.append(cog_name)
                    why[cog_name] = e
    
    # 2. Load other cogs
    for item in os.listdir(src_path):
        # Skip utils as it's already loaded, and skipped ignored dirs
        if item == "utils" or item in ignored_dirs:
            continue
            
        item_path = os.path.join(src_path, item)
        if os.path.isdir(item_path):
            # Load all .py files in this directory as cogs
            for filename in os.listdir(item_path):
                if filename.endswith(".py") and not filename.startswith("__"):
                    cog_name = f"src.{item}.{filename[:-3]}"
                    try:
                        await bot.load_extension(cog_name)
                        success.append(cog_name)
                    except Exception as e:
                        print(f"Failed to load {cog_name}: {e}")
                        fail.append(cog_name)
                        why[cog_name] = e

    logger = bot.get_cog('Logger')
    
    if logger:  # Logger might be one of the loaded cogs
        if fail:
            for cog in fail:
                await logger.log(f"{cog} cog가 로드에 실패하였습니다. 오류: {why[cog]}", cog)
        
        await logger.log("모든 cog가 로드되었습니다.", "main.py")
    else:
        print("Logger cog not loaded.")

# server start

async def main():
    # DB 초기화 선행
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

    print("Syncing commands to all guilds...")
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            
            bot.tree.clear_commands(guild=ctx.guild)
            await bot.tree.sync(guild=guild)

            print(f"Synced to {guild.name} ({guild.id})")
        except Exception as e:
            print(f"Failed to sync to {guild.name}: {e}")
    
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
