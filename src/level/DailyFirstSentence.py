import os
import json
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import aiosqlite
from openai import AsyncOpenAI

from src.level.LevelConstants import FIRST_SENTENCE_ROLE_ID, FIRST_SENTENCE_FORUM_ID, QUEST_EXP
from src.core.admin_utils import is_guild_admin

KST = pytz.timezone("Asia/Seoul")
DB_PATH = "data/level_system.db"

def get_korean_date_string(days: int) -> str:
    base_names = {
        1: "하룻날", 2: "이튿날", 3: "사흗날", 4: "나흗날", 5: "닷샛날",
        6: "엿샛날", 7: "이렛날", 8: "여드렛날", 9: "아흐렛날", 10: "열흘날"
    }
    
    if days in base_names:
        return base_names[days]
        
    tens = days // 10
    ones = days % 10
    
    tens_prefix = {
        1: "열", 2: "스무", 3: "서른", 4: "마흔", 5: "쉰",
        6: "예순", 7: "일흔", 8: "여든", 9: "아흔"
    }
    
    if tens not in tens_prefix:
        return f"{days}일째 날" # fallback for >= 100 or something

    if ones == 0:
        if days == 20: return "스무날"
        return f"{tens_prefix[tens]}흘날" if days == 30 else f"{tens_prefix[tens]}째 날"
    else:
        # e.g. 11: 열하룻날, 23: 스무사흗날
        return f"{tens_prefix[tens]}{base_names[ones]}"


class DailyFirstSentence(commands.Cog):
    """미션 2: 하묘가 건네는 첫 문장"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        
    async def cog_load(self):
        await self.init_db()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        self.bot.loop.create_task(self.setup_schedules())

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message)
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_sentence_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    thread_id INTEGER,
                    question TEXT,
                    answer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    async def setup_schedules(self):
        await self.bot.wait_until_ready()
        scheduler = self.bot.get_cog("Scheduler")
        if scheduler:
            # 매일 자정(00:00)에 포럼 스레드 생성
            scheduler.schedule_daily(self.generate_daily_thread, 0, 0)

    async def generate_daily_thread(self):
        forum = self.bot.get_channel(FIRST_SENTENCE_FORUM_ID)
        if not forum or not isinstance(forum, discord.ForumChannel):
            await self.log("❌ 첫 문장 포럼 채널을 찾을 수 없거나 포럼 채널이 아닙니다.")
            return

        self._ensure_client()
        if not self.client:
            await self.log("❌ 첫 문장 스레드 생성 실패: API 키가 없습니다.")
            return

        today = datetime.now(KST)
        start_date = datetime(2026, 3, 2, tzinfo=KST)
        days_diff = (today.date() - start_date.date()).days + 1
        if days_diff <= 0:
            days_diff = 1
            
        korean_date = get_korean_date_string(days_diff)
        date_str = today.strftime("%y.%m.%d")

        try:
            prompt = "디스코드 감성 서버의 유저들에게 던질 따뜻하고 동화 같은 질문 1개를 생성해 줘. 너무 무겁거나 철학적이고 난해한 질문은 피하고, 누구나 일상 속에서 쉽게 대답할 수 있는 가벼운 질문으로 만들어 줘. (예: 가장 좋아하는 간식, 오늘 본 예쁜 풍경 등) 20자 이내의 짧은 요약(주제)과, 2~3줄의 질문 본문으로 나누어 JSON 형식으로 반환해 줘. {\"summary\": \"...\", \"question\": \"...\"}"
            
            completion = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "너는 디스코드 봇 '하묘'야. 말을 하는 토끼 컨셉으로 다정하고 친근한 반말 문체를 써 줘. 말끝에는 자연스럽게 '~다묘', '~거다묘', '~보라묘', '~냐묘'를 붙여줘. (예시: '가장 좋아하는 계절은 언제냐묘?', '정말 예쁘다묘!', '다들 어땠는지 말해보라묘!') 단, '있거다묘'처럼 어색하게 억지로 어미를 조작하지 말고 문맥에 맞게 자연스럽게 연결해 줘. 반드시 JSON 형식만 반환해."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                response_format={ "type": "json_object" }
            )
            
            response_text = completion.choices[0].message.content.strip()
            data = json.loads(response_text)
            summary = data.get("summary", "오늘의 조용한 질문")
            question = data.get("question", "오늘 하루는 어떤 색깔이었냐묘?")
        except Exception as e:
            await self.log(f"❌ 첫 문장 GPT 생성 중 오류: {e}")
            summary = "오늘의 질문"
            question = "오늘 하루는 어떤 색이었냐묘? 다정한 당신의 이야기를 들려달라묘."

        thread_name = f"{korean_date}, {summary}"
        
        # 멘션 역할 가져오기 (문자열로 직접 넣어도 됨)
        content = (
            f"# <:BM_a_000:1477525641623502950> 하묘가 건네는 첫 문장 ､ {date_str} <a:slg12:1378567364844453938>\n"
            "-# *<a:BM_moon_001:1378716907624202421>_오늘의 빈칸을 채워주세요*\n"
            "⠀\n"
            ". ᘏ▸◂ᘏ \n"
            "꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱ 다들 오늘 하루도 따뜻하게 보냈냐묘 ?\n\n"
            f"> **Q. {question}**\n\n"
            "-# ◟. 이 스레드에 답변을 남겨주시면, 하묘가 짧은 답장과 함께 `25 쪽`을 드려요 !\n"
            f"<@&{FIRST_SENTENCE_ROLE_ID}>"
        )
        
        try:
            thread_with_message = await forum.create_thread(
                name=thread_name,
                content=content,
                auto_archive_duration=1440 # 24시간
            )
            await self.log(f"오늘의 첫 문장 스레드가 생성되었습니다: {thread_name}")
            
            # 봇 메시지(질문) 자체도 DB에 잠깐 올려놓을 순 있지만, 
            # 질문 내용은 parent 메시지를 가져오거나 할 수 있으므로 굳이 필요없음.
        except Exception as e:
            await self.log(f"❌ 포럼 스레드 생성 오류: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.Thread):
            return

        # 해당하는 포럼 채널의 스레드인지 확인
        if message.channel.parent_id != FIRST_SENTENCE_FORUM_ID:
            return

        user_id = message.author.id
        level_checker = self.bot.get_cog("LevelChecker")
        if not level_checker:
            return

        # 중복 참여 방지 (오늘 이미 'first_sentence' 퀘스트를 완료했는지 체크)
        today_count = await level_checker.data_manager.get_quest_count(
            user_id, quest_type='daily', quest_subtype='first_sentence', timeframe='day'
        )
        
        if today_count > 0:
            # 이미 오늘 참여함 -> 그냥 리턴 (무시)
            return

        # 포럼의 첫 번째 메시지 (스레드 스타터 메시지) 가져와서 질문 내용 파악
        thread = message.channel
        starter_msg = None
        try:
            # fetch_message 사용시 스레드 id가 첫번째 메시지 id와 같음 (포럼 특성)
            starter_msg = await thread.fetch_message(thread.id)
        except Exception:
            pass
            
        question_text = "알 수 없는 질문"
        if starter_msg:
            # "> **Q. " 부분 파싱
            lines = starter_msg.content.split('\n')
            for line in lines:
                if line.startswith("> **Q."):
                    question_text = line.replace("> **Q. ", "").replace("**", "").strip()
                    break

        answer_text = message.content.strip()

        # DB 기록
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO daily_sentence_answers (user_id, thread_id, question, answer)
                    VALUES (?, ?, ?, ?)
                """, (user_id, thread.id, question_text, answer_text))
                await db.commit()
        except Exception as e:
            await self.log(f"❌ 유저 답변 DB 기록 오류: {e}")

        # 보상 지급
        exp = QUEST_EXP['daily'].get('first_sentence', 25)
        await level_checker.data_manager.add_exp(user_id, exp, 'daily', 'first_sentence')
        result = {
            'success': True,
            'exp_gained': exp,
            'messages': [f"하묘가 건네는 첫 문장 답변 완료: **+{exp} 쪽**"],
            'quest_completed': ['daily_first_sentence']
        }
        await level_checker._finalize_quest_result(user_id, result)

        # GPT API로 코멘트 생성
        self._ensure_client()
        if not self.client:
            reply_msg = (
                "> <a:BM_moon_001:1378716907624202421> **하묘의 코멘트**\n"
                "> 당신의 이야기를 들려줘서 고맙다묘!\n"
                f"> -# ◟. 집필 완료 ! `+{exp} 쪽`"
            )
            await message.reply(reply_msg, mention_author=True)
            return

        try:
            prompt = f"유저가 다음 질문에 대해 답변을 달았어:\n질문: {question_text}\n유저 답변: {answer_text}\n\n이 답변에 대해 하묘(착하고 다정한 토끼 캐릭터, 말투는 '~다묘', '~거다묘')가 해줄 법한 1~2줄의 따뜻하고 공감 가는 코멘트를 작성해 줘."
            completion = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 디스코드 봇 '하묘'야. 길게 말하지 않고 아주 짧고 따뜻하게 1~2줄로만 대답해줘. 다정한 반말 문체에 말끝을 자연스럽게 '~다묘', '~거다묘', '~냐묘'로 끝내줘. 어색하게 억지로 붙이지 말고 (예: '있거다묘' X), '정말 다행이다묘!', '최고였다묘!' 처럼 자연스럽게 써 줘."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            comment = completion.choices[0].message.content.strip()
        except Exception as e:
            await self.log(f"❌ 코멘트 GPT 생성 중 오류: {e}")
            comment = "소중한 이야기를 들려줘서 정말 고맙다묘! 앞으로의 여정도 응원할거다묘."

        # 최종 코멘트 답장
        lines = comment.split('\n')
        comment_formatted = "\n".join([f"> {line}" for line in lines])
        
        reply_msg = (
            "> <a:BM_moon_001:1378716907624202421> **하묘의 코멘트**\n"
            f"{comment_formatted}\n"
            f"> -# ◟. 집필 완료 ! `+{exp} 쪽`"
        )
        await message.reply(reply_msg, mention_author=True)


    @commands.command(name="첫문장테스트")
    @is_guild_admin()
    async def test_first_sentence(self, ctx):
        await self.generate_daily_thread()
        await ctx.message.add_reaction("✅")

    @commands.command(name="질문생성테스트")
    @is_guild_admin()
    async def test_generate_question(self, ctx):
        """GPT 프롬프트를 통해 첫 문장 질문 생성을 테스트합니다."""
        await ctx.send("질문을 생성 중이다묘... 잠시만 기다려달라묘!")
        self._ensure_client()
        if not self.client:
            await ctx.send("❌ API 키가 없습니다.")
            return

        prompt = "디스코드 감성 서버의 유저들에게 던질 따뜻하고 동화 같은 질문 1개를 생성해 줘. 너무 무겁거나 철학적이고 난해한 질문은 피하고, 누구나 일상 속에서 쉽게 대답할 수 있는 가벼운 질문으로 만들어 줘. (예: 가장 좋아하는 간식, 오늘 본 예쁜 풍경 등) 20자 이내의 짧은 요약(주제)과, 2~3줄의 질문 본문으로 나누어 JSON 형식으로 반환해 줘. {\"summary\": \"...\", \"question\": \"...\"}"
        
        try:
            completion = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "너는 디스코드 봇 '하묘'야. 말을 하는 토끼 컨셉으로 다정하고 친근한 반말 문체를 써 줘. 말끝에는 자연스럽게 '~다묘', '~거다묘', '~보라묘', '~냐묘'를 붙여줘. (예시: '가장 좋아하는 계절은 언제냐묘?', '정말 예쁘다묘!', '다들 어땠는지 말해보라묘!') 단, '있거다묘'처럼 어색하게 억지로 어미를 조작하지 말고 문맥에 맞게 자연스럽게 연결해 줘. 반드시 JSON 형식만 반환해."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                response_format={ "type": "json_object" }
            )
            
            response_text = completion.choices[0].message.content.strip()
            data = json.loads(response_text)
            summary = data.get("summary", "요약 없음")
            question = data.get("question", "질문 없음")
            
            embed = discord.Embed(title="📝 첫 문장 질문 생성 테스트", color=0xedccff)
            embed.add_field(name="주제 (summary)", value=summary, inline=False)
            embed.add_field(name="질문 본문 (question)", value=question, inline=False)
            embed.add_field(name="Raw JSON", value=f"```json\n{response_text}\n```", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 첫 문장 GPT 생성 중 오류: {e}")
            await self.log(f"❌ 질문생성테스트 오류: {e}")


async def setup(bot):
    await bot.add_cog(DailyFirstSentence(bot))
