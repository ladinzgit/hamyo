import asyncio
import re
import random

import discord
from discord.ext import commands

MAIN_CHANNEL_ID = 1474014240896585880

class Response(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_ids = [1257636236634488842, 277812129011204097]
        self.welcome_messages = [
            "꿈과 현실의 경계, 비몽책방에 온 걸 환영한다묘! 새로운 고요 {name}, 반갑다묘!",
            "여기는 잠들지 않는 이야기들이 모이는 비몽책방이다묘! 푹 쉬다 가라 고요 {name}!",
            "달빛 스며드는 비몽책방에 잘 찾아왔다묘~ 환영한다 고요 {name}!",
            "비몽책방의 문이 열렸다묘! 새로운 고요 {name}, 재미있는 책 좀 읽으러 왔냐묘?",
            "꿈결을 따라 도착한 곳이 비몽책방이라니, 운명이 틀림없다묘! 반갑다 고요 {name}!",
            "종이 냄새 가득한 비몽책방에서 좋은 시간 보내라묘! 어서 와라 고요 {name}!",
            "삐용삐용 새로운 고요 {name} 입장이다묘! 비몽책방에서는 편하게 누워서 뒹굴거리라묘!"
        ]

    async def log(self, message):
        """로그 메시지를 Logger cog를 통해 전송합니다."""
        logger = self.bot.get_cog('Logger')
        if logger:
            await logger.log(message)

    async def cog_load(self):
        try:
            print(f"✅ {self.__class__.__name__} loaded successfully!")

        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로드 중 오류 발생: {e}")
            
    async def _check_owner(self, ctx):
        """명령어를 실행하는 사용자가 봇의 주인인지 확인"""
        if ctx.author.id not in self.owner_ids:
            await ctx.send("당신은 딘즈가 아니에용ㅠㅠ")
            await self.log(f"권한 없는 사용자의 접근 시도: {ctx.author.name} (ID: {ctx.author.id})")
            return False
        return True

    @commands.command()
    async def copy(self, ctx, *, arg):
        if not await self._check_owner(ctx):
            return
        
        await ctx.message.delete()
        await ctx.send(arg)
        await self.log(f"Copy 명령어 사용됨 - 내용: '{arg}' (사용자: {ctx.author.name})")

    @commands.command()
    async def reply(self, ctx, arg1, *, arg2):
        if not await self._check_owner(ctx):
            return
        
        await ctx.message.delete()
        channel = ctx.channel
        try:
            target = await channel.fetch_message(int(arg1))
            await target.reply(arg2)
            await self.log(f"Reply 명령어 사용됨 - 대상 메시지 ID: {arg1}, 응답: '{arg2}' (사용자: {ctx.author.name})")
        except Exception as e:
            await self.log(f"Reply 명령어 실행 중 오류 발생: {str(e)} (사용자: {ctx.author.name})")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.channel.id != MAIN_CHANNEL_ID:
            return
        
        user_pattern = r"<@(\d+)>"
        user_matches = re.findall(user_pattern, message.content)

        if "꿈과 현실 사이, 책내음이 나는 곳" in message.content and user_matches:
            mentioned_users = []
            
            # 모든 멘션된 유저를 찾아서 리스트에 추가
            for user_id in user_matches:
                user = message.guild.get_member(int(user_id))
                if user:
                    mentioned_users.append(user)
            
            if mentioned_users:
                random_second = random.randrange(3,7)
                await asyncio.sleep(random_second)

                # 모든 멘션을 하나의 문자열로 합치기
                mentions = ", ".join([user.mention for user in mentioned_users])
                
                selected = random.choice(self.welcome_messages)
                await message.channel.send(selected.format(name=mentions))
                
                # 로그에 모든 멘션된 유저 정보 기록
                mentioned_info = ", ".join([f"{user.name}({user.id})" for user in mentioned_users])
                await self.log(f"새로운 유저 환영 문구 전송 완료, 대상자: {mentioned_info}")
                return
            else:
                await self.log(f"새로운 유저 환영 문구는 찾았으나, 유저 특정 불가함. 메시지 ID - {message.id}")
                return

    # Cog error handler
    async def cog_command_error(self, ctx, error):
        print(f"An error occurred in the {self.__class__.__name__} cog: {error}")
        await self.log(f"An error occurred in the {self.__class__.__name__} cog: {error}")

async def setup(bot):
    await bot.add_cog(Response(bot))
