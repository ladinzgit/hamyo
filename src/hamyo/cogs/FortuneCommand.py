import os
from datetime import datetime

import discord
from discord.ext import commands
from openai import AsyncOpenAI
from dotenv import load_dotenv

import birthday_db
import fortune_db
from .BirthdayInterface import KST, only_in_guild

load_dotenv()


class FortuneCommand(commands.Cog):
    """*운세 명령어를 처리하는 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def cog_load(self):
        print(f"🐾{self.__class__.__name__} loaded successfully!")

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    def _ensure_client(self):
        current_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        if current_key != self.api_key:
            self.api_key = current_key
            self.client = None
        if not self.client and self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)

    @commands.command(name="운세")
    @only_in_guild()
    async def tell_fortune(self, ctx):
        """운세를 생성하여 전송"""
        config = fortune_db.get_guild_config(ctx.guild.id)
        target = fortune_db.get_target(ctx.guild.id, ctx.author.id)

        channel_id = config.get("channel_id")
        if channel_id and ctx.channel.id != channel_id:
            await ctx.reply("여기는 운세 채널이 아니라묘! 설정된 채널에서 *운세를 써달라묘.", mention_author=False)
            return

        if not target:
            await ctx.reply("운세 대상에 등록되어 있지 않다묘... 관리자가 등록해줘야 *운세 명령을 쓸 수 있다묘!", mention_author=False)
            return

        try:
            remaining_count = int(target.get("count", 0))
        except (ValueError, TypeError):
            remaining_count = 0

        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        if target.get("last_used_date") == today_str:
            await ctx.reply("오늘은 이미 운세를 봤다묘! 내일 다시 찾아와달라묘.", mention_author=False)
            return

        if remaining_count <= 0:
            fortune_db.remove_target(ctx.guild.id, ctx.author.id)
            await ctx.reply("등록 기간이 끝난 것 같다묘. 다시 등록받아달라묘!", mention_author=False)
            return

        self._ensure_client()
        if not self.api_key:
            await ctx.reply("ChatGPT API 키가 설정되어 있지 않다묘... `OPENAI_API_KEY`(또는 `CHATGPT_API_KEY`) 환경 변수를 넣어달라묘!", mention_author=False)
            return

        birthday = await birthday_db.get_birthday(str(ctx.author.id))
        if not birthday:
            await ctx.reply("생일 정보가 없다묘! `*생일` 명령으로 먼저 등록해달라묘.", mention_author=False)
            return

        birth_year = birthday.get("year")
        month = birthday.get("month")
        day = birthday.get("day")

        if not month or not day:
            await ctx.reply("생일 데이터가 이상하다묘... 다시 등록해달라묘!", mention_author=False)
            return

        today = datetime.now(KST)

        if birth_year:
            birth_text = f"{birth_year}년 {month}월 {day}일생"
        else:
            birth_text = f"생년 미기재 {month}월 {day}일생"

        today_text = f"{today.year}년 {today.month}월 {today.day}일"
        prompt = f"{birth_text} {today_text} 오늘의 운세를 알려줘"

        waiting_message = None
        try:
            waiting_message = await ctx.reply("하묘가 오늘의 운세를 가져오는 중이다묘... 잠시만 기다려달라묘!", mention_author=False)

            completion = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 디스코드 봇 \"하묘\"야.\n"
                            "문장 끝은 반드시 \"묘\"로 끝내고, 단어와 \"묘\" 사이에 공백을 두지 마.\n"
                            "고양이 콘셉트는 말투에만 살짝 반영하고, 고양이 내용은 전체의 10% 이하로 제한해.\n"
                            "친근하지만 예의 바른 톤으로, 과도한 부정·공포·오싹한 내용은 절대 금지해.\n\n"
                            "오늘의 운세 작성 규칙:\n"
                            "- 총 8~10줄로 작성해\n"
                            "- 가벼운 조언과 격려를 포함해\n"
                            "- 정보성 + 일상 조언 + 기분 좋은 방향성 중심으로\n"
                            "- 생일, 나이, 날짜(연·월·일)는 절대 언급하지 마\n"
                            "- 한국어 띄어쓰기를 자연스럽게 유지해(문장 끝의 '묘'만 붙여쓰기)\n"
                            "- 한 문장은 25~60자 정도로 읽기 편하게 써줘"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=600,
            )
            fortune_text = completion.choices[0].message.content.strip()
            fortune_text = fortune_text.replace(" 묘", "묘")
        except Exception as e:
            if waiting_message:
                try:
                    await waiting_message.edit(content="운세를 불러오다 미끄러졌다묘... 잠시 후 다시 시도해달라묘!")
                except Exception:
                    await ctx.reply("운세를 불러오다 미끄러졌다묘... 잠시 후 다시 시도해달라묘!", mention_author=False)
            else:
                await ctx.reply("운세를 불러오다 미끄러졌다묘... 잠시 후 다시 시도해달라묘!", mention_author=False)
            await self.log(f"운세 생성 오류: {e} [길드: {ctx.guild.name}({ctx.guild.id}), 사용자: {ctx.author}({ctx.author.id})]")
            return

        try:
            if waiting_message:
                await waiting_message.edit(content=fortune_text)
            else:
                await ctx.reply(fortune_text, mention_author=False)
        except Exception:
            await ctx.reply(fortune_text, mention_author=False)

        fortune_db.mark_target_used(ctx.guild.id, ctx.author.id, today_str)

        # 운세 역할 회수 (사용 중에는 멘션 대상에서 제외)
        role_id = config.get("role_id")
        if role_id:
            role = ctx.guild.get_role(role_id)
            if role:
                try:
                    await ctx.author.remove_roles(role, reason="운세 사용 완료로 역할 회수")
                except Exception as e:
                    await self.log(f"{ctx.author}({ctx.author.id}) 운세 역할 회수 실패: {e}")

        await self.log(
            f"{ctx.author}({ctx.author.id})가 운세를 조회함 "
            f"[길드: {ctx.guild.name}({ctx.guild.id}), 남은 일수: {remaining_count}]"
        )


async def setup(bot):
    await bot.add_cog(FortuneCommand(bot))
