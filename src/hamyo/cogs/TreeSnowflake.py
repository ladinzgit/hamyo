import discord
from discord.ext import commands, tasks
from TreeDataManager import TreeDataManager
import asyncio
import random
from datetime import datetime, timedelta, time
import pytz
import json
import os

KST = pytz.timezone("Asia/Seoul")
CONFIG_PATH = "config/tree_config.json"

def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class SnowflakeButton(discord.ui.Button):
    def __init__(self, view_ref):
        super().__init__(style=discord.ButtonStyle.primary, label="눈송이 줍기", emoji="❄️")
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction):
        await self.view_ref.process_click(interaction)

class SnowflakeView(discord.ui.View):
    def __init__(self, bot, channel, message_content):
        super().__init__(timeout=60) # 1분 제한
        self.bot = bot
        self.channel = channel
        self.message_content = message_content
        self.winners = []
        self.max_winners = 6
        self.reward = 220
        self.data_manager = TreeDataManager()
        
        button = SnowflakeButton(self)
        self.add_item(button)

    async def process_click(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id in self.winners:
            await interaction.response.send_message("이미 눈송이를 주웠다묘!", ephemeral=True)
            return
            
        if len(self.winners) >= self.max_winners:
            await interaction.response.send_message("선착순 마감되었다묘...", ephemeral=True)
            return

        self.winners.append(user_id)
        
        # 보상 지급
        await self.data_manager.add_snowflake(user_id, self.reward, "snowflake_game", "daily")
        self.bot.dispatch('tree_updated')
        
        # 멘션 메시지
        success_msg = f"""
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO <a:BM_evt_002:1449016646680449055> {self.reward} 눈송이를 쌓았다묘! ᝰꪑ
( つ🎉O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯
"""
        await interaction.response.send_message(f"{interaction.user.mention} {success_msg}", ephemeral=False)

        if len(self.winners) >= self.max_winners:
            await self.finish(end_reason="sold_out")
            self.stop()

    async def on_timeout(self):
        if len(self.winners) < self.max_winners:
            await self.finish(end_reason="timeout")

    async def finish(self, end_reason):
        try:
             # 메시지 수정
            if end_reason == "sold_out":
                final_msg = """
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO  눈송이를 모두 나눠줬다묘.. ᝰꪑ
( つ📦O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯ 
"""
            else:
                final_msg = """
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO  눈송이가 녹아버렸다묘.. ᝰꪑ
( つ💧O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯ 
""" 
            # 버튼 비활성화
            for child in self.children:
                child.disabled = True
                
            if self.message:
                await self.message.edit(content=final_msg, view=self)
        except Exception as e:
            print(f"Error finishing view: {e}")


class TreeSnowflake(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduled_times = []
        self.today_date = None
        self.event_lock = asyncio.Lock()
        self.current_view = None
        self.check_schedule_loop.start()

    def cog_unload(self):
        self.check_schedule_loop.cancel()

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        self._schedule_events()

    def _schedule_events(self):
        # 하루 2회 랜덤 스케줄링 (Persistence logic added)
        # 제외: 01:00 - 09:00
        
        now = datetime.now(KST)
        date_str = now.strftime("%Y-%m-%d")
        
        cfg = _load_config()
        saved_schedule = cfg.get("daily_schedule", {})
        
        # Check if saved schedule exists for today
        if saved_schedule.get("date") == date_str:
            times = saved_schedule.get("times", [])
            if times:
                self.scheduled_times = []
                for t_str in times:
                    try:
                        # Reconstruct datetime object
                        dt = datetime.strptime(f"{date_str} {t_str}", "%Y-%m-%d %H:%M")
                        dt = KST.localize(dt)
                        self.scheduled_times.append(dt)
                    except ValueError:
                        pass
                
                if self.scheduled_times:
                    self.today_date = date_str
                    print(f"📅 Loaded Snowflake Schedule: {[t.strftime('%H:%M') for t in self.scheduled_times]}")
                    return

        # If no valid schedule, generate new one
        self.today_date = date_str
        self.scheduled_times = []

        start_hour = 9
        end_hour = 24 
        
        attempts = 0
        while len(self.scheduled_times) < 2 and attempts < 100:
            attempts += 1
            h = random.randint(start_hour, 23)
            m = random.randint(0, 59)
            
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            
            if t < now:
                # If generated time is in the past for today, skip it?
                # Ideally yes, but if we reboot at 10PM, we might miss the morning one.
                # Requirement: "Set at 00:00". If generating late, should we schedule for remaining time?
                # Or just schedule anyway and let the loop handle "missed" events?
                # Original logic: "if t < now: continue". This means if bot restarts late, no events for today.
                # That's acceptable for random drops.
                continue 
                
            conflict = False
            for st in self.scheduled_times:
                diff = abs((t - st).total_seconds())
                if diff < 3600: 
                    conflict = True
                    break
            
            if not conflict:
                self.scheduled_times.append(t)
        
        self.scheduled_times.sort()
        
        # Save to config
        # Helper to save (TreeConfig logic duplicated or we import? TreeConfig owns file)
        # We will duplicate save logic locally to avoid dependency mess or circular import.
        # TreeSnowflake already loads config.
        
        simple_times = [t.strftime('%H:%M') for t in self.scheduled_times]
        
        cfg["daily_schedule"] = {
            "date": date_str,
            "times": simple_times
        }
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        print(f"📅 Generated & Saved Snowflake Schedule: {simple_times}")

    @tasks.loop(minutes=1)
    async def check_schedule_loop(self):
        now = datetime.now(KST)
        
        # 날짜 변경 체크 및 재스케줄링
        if self.today_date != now.strftime("%Y-%m-%d"):
            self._schedule_events()
            
        # 이벤트 트리거 확인
        to_remove = []
        for st in self.scheduled_times:
            # Check if time match (within 1 min margin)
             diff = (now - st).total_seconds()
             if 0 <= diff < 60:
                 await self.trigger_event()
                 to_remove.append(st)
             elif diff >= 60:
                 # Passed without trigger (bot was off?)
                 to_remove.append(st)
        
        for r in to_remove:
            self.scheduled_times.remove(r)

    @check_schedule_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def trigger_event(self):
        cfg = _load_config()
        channel_id = cfg.get("channels", {}).get("snowflake_channel")
        
        if not channel_id:
            print("⚠️ Snowflake channel not set.")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # 이전 이벤트 정리
        if self.current_view and not self.current_view.is_finished():
            await self.current_view.finish("timeout") # Force finish old one

        msg_content = """
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO <a:BM_evt_002:1449016646680449055> 220 눈송이 받을 다도! ᝰꪑ
( つ<a:BM_evt_002:1449016646680449055>O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯ 
"""
        view = SnowflakeView(self.bot, channel, msg_content)
        message = await channel.send(msg_content, view=view)
        view.message = message
        self.current_view = view
        
        # 1분 후 타임아웃 처리는 View 내부 timeout으로 처리됨.

async def setup(bot):
    await bot.add_cog(TreeSnowflake(bot))
