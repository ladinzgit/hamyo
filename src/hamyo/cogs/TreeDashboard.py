import discord
from discord.ext import commands
from TreeDataManager import TreeDataManager
import json
import os
import asyncio

CONFIG_PATH = "config/tree_config.json"
IMAGE_DIR = "src/hamyo/images"

def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class TreeDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = TreeDataManager()
        self.last_level = -1
        self.message_id = None
        self.channel_id = None

    async def cog_load(self):
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        # 초기화 시 설정 로드
        cfg = _load_config()

    @commands.Cog.listener()
    async def on_tree_updated(self):
        """트리 상태 업데이트 이벤트 수신"""
        await self.update_dashboard()

    async def update_dashboard(self):
        cfg = _load_config()
        # Changed to use 'dashboard_channel'
        channel_id = cfg.get("channels", {}).get("dashboard_channel")
        if not channel_id:
            # Fallback not requested, but good to handle graceful failure or log?
            # User explicitly asked to separate.
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        status = await self.data_manager.get_tree_status()
        rankings = await self.data_manager.get_rankings(limit=4)
        
        current_level = status['level']
        total_snowflakes = status['total_snowflakes']
        next_exp = status['next_level_exp']
        
        # 메시지 구성
        msg_header = "# <a:BM_m_001:1399387800373301319> 비몽트리 상태창 <a:BM_m_002:1399387809772470342>"
        
        level_str = f"> 🎄 : 비몽트리 {current_level}단계"
        next_str = f"> -# ．╰୧：다음 단계까지 {max(0, next_exp - total_snowflakes) if next_exp > 0 else 0} 눈송이"
        if next_exp == 0:
             next_str = "> -# ．╰୧：최고 단계 도달!"

        rank_header = "> <a:BM_evt_002:1449016646680449055>  : 비몽트리 눈송이 기여도 순위\n> "
        rank_lines = []
        for i, rank in enumerate(rankings):
            rank_lines.append(f"> -# ╰୧：<@{rank['user_id']}>  : {rank['total_gathered']} 눈송이")
        
        # Fill empty ranks
        while len(rank_lines) < 4:
            rank_lines.append("> -# ╰୧：-  : 0 눈송이")
            
        full_content = f"{msg_header}\n\n\n{level_str}\n{next_str}\n\n{rank_header}\n" + "\n".join(rank_lines)

        # 이미지 파일
        image_path = os.path.join(IMAGE_DIR, f"{current_level}.png")
        if not os.path.exists(image_path):
            image_path = None # or default?

        # 레벨 변화 확인
        is_level_changed = (self.last_level != -1) and (self.last_level != current_level)
        self.last_level = current_level


        # 메시지 전송/수정 로직
        try:
            old_text_id = cfg.get("dashboard_message_id")
            old_image_id = cfg.get("dashboard_image_id")
            
            should_recreate = False
            
            # Need recreation if:
            # 1. Level changed (Image might change)
            # 2. Messages don't exist in config
            if is_level_changed or not old_text_id or not old_image_id:
                should_recreate = True
            
            text_msg = None
            
            if not should_recreate:
                # Try to fetch and edit existing messages
                try:
                    text_msg = await channel.fetch_message(old_text_id)
                    await text_msg.edit(content=full_content)
                    
                    # Verify image message exists
                    await channel.fetch_message(old_image_id)
                    # Image message exists and level hasn't changed -> Good.
                    
                except discord.NotFound:
                    # Message missing, force recreate
                    should_recreate = True
                except Exception as e:
                    print(f"Error editing dashboard: {e}")
                    should_recreate = True

            if should_recreate:
                # Delete old messages if they exist
                if old_text_id:
                    try:
                        msg = await channel.fetch_message(old_text_id)
                        await msg.delete()
                    except:
                        pass
                if old_image_id:
                    try:
                        msg = await channel.fetch_message(old_image_id)
                        await msg.delete()
                    except:
                        pass

                # Send New Messages (Image First)
                image_msg = None
                if image_path:
                    file = discord.File(image_path, filename=f"tree_{current_level}.png")
                    image_msg = await channel.send(file=file)

                # 2. Text
                text_msg = await channel.send(content=full_content)
                
                # Update Config
                cfg["dashboard_message_id"] = text_msg.id
                cfg["dashboard_image_id"] = image_msg.id if image_msg else None

                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)

            
            if is_level_changed:
                    # 레벨업 공지
                    snowflake_channel_id = cfg.get("channels", {}).get("snowflake_channel")
                    if snowflake_channel_id:
                        sf_channel = self.bot.get_channel(snowflake_channel_id)
                        if sf_channel:
                            # 레벨업 알림 (ASCII Art Plain Text)
                            level_up_msg = f"""
. ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮
꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO <a:BM_evt_002:1449016646680449055> **비몽트리가 {current_level}단계로 성장했다묘 *!!* **
( つ<a:BM_evt_001:1449016605169156166>O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯
"""
                            await sf_channel.send(level_up_msg)

        except Exception as e:
            print(f"Error updating dashboard: {e}")

async def setup(bot):
    await bot.add_cog(TreeDashboard(bot))
