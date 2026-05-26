import os
import json
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import aiosqlite
from openai import AsyncOpenAI

from src.core.admin_utils import is_guild_admin

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

        system_prompt = (
            "너는 디스코드 봇 '하묘'야. 다정하고 귀여운 아기 토끼 캐릭터로, 유저가 그동안 남겨준 따뜻한 답변들을 기억하고 분석하여, "
            "그 사람의 성격과 답변 내용들을 엮어 세상에 단 하나뿐인 일기(편지 형식)를 써 주는 역할을 수행해.\n\n"
            "[말투 및 톤앤매너]\n"
            "- 친근하고 다정한 반말(구어체)을 사용해 줘.\n"
            "- 문장 끝에는 자연스럽게 '~다묘', '~거다묘', '~보라묘', '~냐묘' 등을 붙여서 토끼 컨셉을 완벽하게 살려줘.\n"
            "- 어색하게 어미를 조작(예: '있거다묘' X)하지 말고 문맥에 맞게 매끄럽게 연결해 줘.\n"
            "- 과장되거나 상투적인 미사여구는 피하고, 진심으로 유저를 아끼고 관찰해 온 담백하고 따뜻한 톤을 유지해 줘.\n\n"
            "[내용 구성 규칙]\n"
            "- 유저가 그동안 대답했던 내용들을 세심하게 짚으며, 유저의 취향, 생각, 성격을 정성스럽게 묘사해 줘.\n"
            "- 한 편의 예쁜 동화 같은 감동과 힐링을 유저에게 선사해 줘.\n"
            "- 분량은 한글 기준 1000~1500자 내외로 풍성하고 짜임새 있게 작성해 줘.\n\n"
            "[출력 형식]\n"
            "- 다른 인사말이나 잡담 없이 곧바로 본문 첫 문장부터 시작해 줘.\n"
            "- 마크다운 형식을 사용하여 가독성 있게 작성해 줘.\n\n"
            "[금지 사항]\n"
            "- 생년월일, 나이, 구체적인 날짜는 일기 본문에 언급하지 마.\n"
            "- 뻔한 일반론이나 추상적인 문구는 사용하지 마."
        )

        prompt = (
            f"다음은 유저(이름: {ctx.author.display_name})가 그동안 하묘의 첫 문장에 대답했던 질문과 답변 목록이야. "
            f"이 내용들을 정성껏 엮어서 하묘의 비밀 일기를 작성해 줘.\n\n"
            f"[유저 답변 목록]\n"
            f"{qa_str}"
        )

        self._ensure_client()
        if not self.client:
            await status_msg.edit(content="❌ API 키가 없어서 일기를 쓸 수 없다묘... 관리자에게 문의해 달라묘.")
            return

        try:
            # gpt-5.4 모델과 responses.create 호출 형식을 벤치마크하여 작성
            response = await self.client.responses.create(
                model="gpt-5.4",
                instructions=system_prompt,
                input=prompt,
                reasoning={
                    "effort": "medium"
                }
            )
            diary_content = (getattr(response, "output_text", None) or "").strip()

            if not diary_content:
                text_parts = []
                for item in (getattr(response, "output", None) or []):
                    for content in (getattr(item, "content", None) or []):
                        text_value = getattr(content, "text", None)
                        if text_value:
                            text_parts.append(text_value)
                diary_content = "\n".join(text_parts).strip()

            if not diary_content:
                raise ValueError("Responses API returned empty output")

        except Exception as e:
            print(f"❌ OpenAI GPT responses API 호출 중 오류 발생: {e}")
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

    @commands.command(name="일기초기화")
    @is_guild_admin()
    async def reset_diary_view(self, ctx, member: discord.Member):
        """특정 유저의 일기보기 조회 권한을 초기화합니다 (관리자 전용)"""
        user_id = member.id
        try:
            async with aiosqlite.connect("data/level_system.db") as db:
                cursor = await db.execute("SELECT 1 FROM user_diary_views WHERE user_id = ?", (user_id,))
                exists = await cursor.fetchone()
                if not exists:
                    return await ctx.reply(f"이전 일기 조회 기록이 없다묘! ({member.display_name})")
                
                await db.execute("DELETE FROM user_diary_views WHERE user_id = ?", (user_id,))
                await db.commit()
            
            await ctx.reply(f"성공적으로 {member.display_name} 님의 일기 조회 권한을 초기화했다묘! 🌸")
            await self.log(f"관리자 {ctx.author}({ctx.author.id})가 {member}({user_id})의 일기 조회 권한을 초기화함.")
        except Exception as e:
            print(f"❌ 일기 초기화 오류: {e}")
            await ctx.reply("일기 조회 권한 초기화 중에 오류가 발생했다묘...")

async def setup(bot):
    await bot.add_cog(UserDiaryService(bot))
