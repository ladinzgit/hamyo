import json
import os
import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "embed_config.json")

class EmbedUtils:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        """설정 파일을 로드합니다."""
        if not os.path.exists(CONFIG_PATH):
            return {"embeds": {}}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"embeds": {}}

    def save_config(self):
        """설정을 파일에 저장합니다."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"CRITICAL: 설정 파일 저장 실패! {e}")

    def get_embed_data(self, name, reload=False):
        """임베드 데이터를 가져옵니다. 메모리에 없으면 파일을 다시 읽습니다. reload=True일 경우 강제로 디스크에서 읽어옵니다."""
        if reload:
            self.config = self.load_config()

        data = self.config.get("embeds", {}).get(name)
        if data is None:
            # 메모리 미스 시 디스크 로드
            current_keys = list(self.config.get('embeds', {}).keys())
            self.config = self.load_config()
            data = self.config.get("embeds", {}).get(name)
        return data

    def set_embed_data(self, name, data):
        """임베드 데이터를 저장합니다. 항상 최신 파일을 로드하여 병합합니다."""
        self.config = self.load_config()
        if "embeds" not in self.config:
            self.config["embeds"] = {}
        self.config["embeds"][name] = data
        self.save_config()

    def remove_embed_data(self, name):
        """임베드 데이터를 삭제합니다."""
        self.config = self.load_config()
        if "embeds" in self.config and name in self.config["embeds"]:
            del self.config["embeds"][name]
            self.save_config()
            return True
        return False

    async def update_embed_messages(self, bot: commands.Bot, embed_name: str, embed_object: discord.Embed, view: discord.ui.View = None):
        """등록된 모든 메시지를 업데이트합니다. 유효하지 않은 메시지는 목록에서 제거합니다."""
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
                        to_remove.append([channel_id, message_id])
                        continue
                
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed_object, view=view)
                except discord.NotFound:
                    to_remove.append([channel_id, message_id])
                except discord.Forbidden:
                    to_remove.append([channel_id, message_id])
                except Exception as e:
                    print(f"채널 {channel_id}의 메시지 {message_id} 업데이트 중 오류 발생: {e}")

            except Exception as e:
                print(f"채널 {channel_id} 처리 중 오류 발생: {e}")
                to_remove.append([channel_id, message_id])

        if to_remove:
            data["message_ids"] = [msg for msg in data["message_ids"] if msg not in to_remove]
            self.set_embed_data(embed_name, data)

    async def add_message_id(self, name, channel_id, message_id):
        """임베드 메시지 ID를 추적 목록에 추가합니다."""
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
