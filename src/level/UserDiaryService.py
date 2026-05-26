import os
import json
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import aiosqlite
from openai import AsyncOpenAI

class UserDiaryService(commands.Cog):
    """유저의 과거 답변을 분석하여 평생 단 한 번 하묘의 일기를 보여주는 서비스"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        
    async def cog_load(self):
        await self.init_db()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        
    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message, title="⭐ 일기 서비스 로그", color=discord.Color.blue())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def init_db(self):
        async with aiosqlite.connect("data/level_system.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_diary_views (
                    user_id INTEGER PRIMARY KEY,
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    diary_content TEXT
                )
            """)
            await db.commit()

    def _ensure_client(self):
        current_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        if current_key != self.api_key:
            self.api_key = current_key
            self.client = None
        if not self.client and self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)

    @commands.command(name="일기보기")
    async def view_diary(self, ctx):
        TARGET_CHANNEL_ID = 1508658612883427428
        if ctx.channel.id != TARGET_CHANNEL_ID:
            # 타 채널에서 사용 시 즉시 안내 후 5초 뒤 삭제하여 채널 청결 유지
            msg = await ctx.reply("이 명령어는 전용 채널(<#1508658612883427428>)에서만 사용할 수 있다묘!", delete_after=5)
            try:
                await ctx.message.delete(delay=5)
            except Exception:
                pass
            return

        user_id = ctx.author.id
        
        # 이미 일기를 보았는지 확인
        async with aiosqlite.connect("data/level_system.db") as db:
            cursor = await db.execute("SELECT diary_content FROM user_diary_views WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return await ctx.reply("일기는 평생 딱 한 번만 볼 수 있다묘! 이미 확인하셨다묘.")
        
        # 유저의 예전 답변 목록 불러오기
        async with aiosqlite.connect("data/level_system.db") as db:
            cursor = await db.execute(
                "SELECT question, answer FROM daily_sentence_answers WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            )
            rows = await cursor.fetchall()
            
        if not rows:
            return await ctx.reply("아직 하묘의 첫 문장에 대답해준 적이 없어서 일기를 쓸 수 없다묘... 흑흑.")

        status_msg = await ctx.reply("<a:BM_moon_001:1378716907624202421> 하묘가 열심히 당신의 이야기를 모아 일기를 쓰고 있다묘... 잠시만 기다려 달라묘!")

        # 답변 데이터 포맷팅
        qa_list = []
        for q, a in rows:
            qa_list.append(f"질문: {q}\n답변: {a}")
        qa_str = "\n\n".join(qa_list)

        prompt = (
            f"유저 이름: {ctx.author.display_name}\n"
            f"유저가 그동안 대답했던 문장 목록:\n"
            f"{qa_str}\n\n"
            f"위 대답들을 세심하게 살펴보고, 유저의 성격, 생각, 감정, 취향(좋아하는 것들)을 깊이 있게 분석해 줘. "
            f"그리고 분석한 성격과 답변 내용들을 자연스럽게 엮어서, '하묘'가 유저에 대해 적은 비밀 일기(편지 형식의 일기)를 1편 써 줘.\n\n"
            f"하묘의 페르소나 및 작성 규칙:\n"
            f"- 너는 디스코드 서버의 다정하고 귀여운 아기 토끼 '하묘'야.\n"
            f"- 유저를 깊이 아끼고 세심하게 관찰하며, 유저가 남겼던 사소한 대답 하나하나를 소중히 간직해 온 느낌을 주어야 해.\n"
            f"- 문체는 친근하고 다정한 반말(구어체)을 사용하고, 말끝에는 자연스럽게 '~다묘', '~거다묘', '~보라묘', '~냐묘' 등을 어울리게 사용해 줘. 단, '있거다묘' 같이 어색하고 억지스러운 표현은 피하고 문맥에 맞게 매끄럽게 써줘.\n"
            f"- 일기의 분위기는 한 편의 동화 같으면서도 깊은 감동과 따뜻한 힐링을 선사해야 해.\n"
            f"- 분량은 한글 기준 400~600자 내외로 정성스럽게 작성해 줘.\n"
            f"- 마크다운 형식을 사용하여 가독성 있게 구조를 잡아 줘."
        )

        self._ensure_client()
        if not self.client:
            await status_msg.edit(content="❌ API 키가 없어서 일기를 쓸 수 없다묘... 관리자에게 문의해 달라묘.")
            return

        try:
            # GPT-4o를 이용해 고품질 일기 텍스트 작성
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "너는 디스코드 서버의 다정하고 따뜻한 마음을 가진 아기 토끼 캐릭터 '하묘'야. 유저가 그동안 건네준 소중한 답변들을 기억하고, 이를 바탕으로 유저의 성격과 내면을 예쁘게 그려내며 세상에 단 하나뿐인 감동적인 일기를 써 주는 역할을 수행해."
                      },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            diary_content = completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI GPT API 호출 중 오류 발생: {e}")
            await status_msg.edit(content="❌ 일기를 쓰는 중에 문제가 생겼다묘... 다시 시도해 달라묘.")
            return

        # 조회 여부 및 일기 내용 데이터베이스에 기록 (중복 조회 방지용)
        try:
            async with aiosqlite.connect("data/level_system.db") as db:
                await db.execute(
                    "INSERT OR IGNORE INTO user_diary_views (user_id, diary_content) VALUES (?, ?)",
                    (user_id, diary_content)
                )
                await db.commit()
        except Exception as e:
            print(f"❌ DB 일기 뷰 저장 중 오류: {e}")

        # 다정한 임베드 전송
        KST = pytz.timezone("Asia/Seoul")
        embed = discord.Embed(
            title=f"🌸 、하묘가 {ctx.author.display_name}에게 전하는 비밀 일기",
            description=diary_content,
            color=discord.Color.from_rgb(255, 192, 203)
        )
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="이 일기는 평생 단 한 번만 열어볼 수 있는 하묘의 선물이다묘. ˚‧ 📔")
        embed.timestamp = datetime.now(KST)

        await status_msg.delete()
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(UserDiaryService(bot))
