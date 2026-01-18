import json
import os
import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "embed_config.json")

class EmbedUtils:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return {"embeds": {}}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"embeds": {}}

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get_embed_data(self, name):
        return self.config.get("embeds", {}).get(name)

    def set_embed_data(self, name, data):
        if "embeds" not in self.config:
            self.config["embeds"] = {}
        self.config["embeds"][name] = data
        self.save_config()

    def remove_embed_data(self, name):
        if "embeds" in self.config and name in self.config["embeds"]:
            del self.config["embeds"][name]
            self.save_config()
            return True
        return False

    async def update_embed_messages(self, bot: commands.Bot, embed_name: str, embed_object: discord.Embed):
        data = self.get_embed_data(embed_name)
        if not data or "message_ids" not in data:
            return

        to_remove = []
        for channel_id, message_id in data["message_ids"]:
            try:
                channel = bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await bot.fetch_channel(channel_id)
                    except:
                        # 채널을 찾을 수 없거나 접근할 수 없음
                        to_remove.append([channel_id, message_id])
                        continue
                
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed_object)
                except discord.NotFound:
                    # 메시지가 삭제됨
                    to_remove.append([channel_id, message_id])
                except discord.Forbidden:
                    # 메시지를 수정할 수 없음
                    to_remove.append([channel_id, message_id])
                except Exception as e:
                    print(f"채널 {channel_id}의 메시지 {message_id} 업데이트 중 오류 발생: {e}")

            except Exception as e:
                print(f"채널 {channel_id} 처리 중 오류 발생: {e}")
                to_remove.append([channel_id, message_id])

        if to_remove:
            # 삭제되거나 접근 불가능한 메시지를 설정에서 제거하여 향후 오류 방지
            data["message_ids"] = [msg for msg in data["message_ids"] if msg not in to_remove]
            self.set_embed_data(embed_name, data)

    async def add_message_id(self, name, channel_id, message_id):
        data = self.get_embed_data(name)
        if data:
            if "message_ids" not in data:
                data["message_ids"] = []
            if [channel_id, message_id] not in data["message_ids"]:
                data["message_ids"].append([channel_id, message_id])
                self.set_embed_data(name, data)

embed_manager = EmbedUtils()

async def setup(bot: commands.Bot):
    pass
