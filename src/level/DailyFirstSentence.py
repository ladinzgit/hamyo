import os
import json
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import aiosqlite
from openai import AsyncOpenAI
import random
import re

from src.level.LevelConstants import FIRST_SENTENCE_ROLE_ID, EVERYONE_ROLE_ID, FIRST_SENTENCE_FORUM_ID, QUEST_EXP, REACTION_EMOJI_POOL, MAIN_CHAT_CHANNEL_ID
from src.core.admin_utils import is_guild_admin

Promotion_Time = ["12:00", "18:00"]

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
                await logger.log(message, title="⭐ 레벨 시스템 로그", color=discord.Color.gold())
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_sentence_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def _get_recent_questions(self, limit: int = 10) -> list[str]:
        """최근 작성된 첫 문장 질문 목록을 가져옵니다."""
        questions = []
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT question FROM daily_sentence_questions ORDER BY id DESC LIMIT ?", 
                    (limit,)
                )
                rows = await cursor.fetchall()
                questions = [row[0] for row in rows]
        except Exception as e:
            await self.log(f"최근 질문 조회 중 오류: {e}")
        return questions

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
            
            # 일일 홍보 스케줄
            for time_str in Promotion_Time:
                try:
                    h, m = map(int, time_str.split(":"))
                    scheduler.schedule_daily(self.promote_daily_thread, h, m)
                except ValueError:
                    pass

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

        recent_questions = await self._get_recent_questions(limit=30)
        recent_context = ""
        if recent_questions:
            recent_context = "\n[최근에 했던 질문 목록 (다음 주제들은 반드시 피해서 다른 새로운 주제로 만들어줘)]\n" + "\n".join(f"- {q}" for q in recent_questions)

        try:
            prompt = f"디스코드 감성 서버의 유저들에게 던질 따뜻하고 동화 같은 질문 1개를 생성해 줘. 너무 무겁거나 철학적이고 난해한 질문은 피하고, 누구나 일상 속에서 쉽게 대답할 수 있는 가벼운 질문으로 만들어 줘. (예: 가장 좋아하는 간식, 오늘 본 예쁜 풍경 등){recent_context}\n\n20자 이내의 짧은 요약(주제)과, 2~3줄의 질문 본문으로 나누어 JSON 형식으로 반환해 줘. {{\"summary\": \"...\", \"question\": \"...\"}}"
            
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
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
            question = data.get("question", "오늘 하루는 어떤 느낌이었냐묘?")
            
            # DB에 새로 생성한 질문 저장
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("INSERT INTO daily_sentence_questions (question) VALUES (?)", (question,))
                    await db.commit()
            except Exception as e:
                await self.log(f"질문 DB 저장 오류: {e}")

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
            "-# ◟. 이 스레드에 답변을 남겨주시면, 하묘가 짧은 답장과 함께 `25 쪽`을 드려요 !\n\n"
            f"<@&{FIRST_SENTENCE_ROLE_ID}>"
        )
        
        try:
            # DB에서 가장 최근 답변이 있는 thread_id를 조회하여 이전 스레드 확인
            old_thread = None
            old_thread_id = None
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute(
                        "SELECT DISTINCT thread_id FROM daily_sentence_answers ORDER BY id DESC LIMIT 1"
                    )
                    row = await cursor.fetchone()
                    if row:
                        old_thread_id = row[0]
            except Exception as e:
                await self.log(f"DB에서 이전 스레드 ID 조회 중 오류: {e}")

            # DB에서 찾은 thread_id로 스레드 객체 가져오기
            if old_thread_id:
                try:
                    old_thread = self.bot.get_channel(old_thread_id)
                    if not old_thread:
                        old_thread = await self.bot.fetch_channel(old_thread_id)
                    await self.log(f"DB 기반으로 이전 스레드를 찾았습니다: {old_thread.name} (ID: {old_thread_id})")
                except Exception as e:
                    await self.log(f"이전 스레드 fetch 중 오류 (ID: {old_thread_id}): {e}")
                    old_thread = None
            else:
                await self.log("DB에 이전 답변 기록이 없어 이전 스레드를 찾을 수 없습니다.")

            # 기존 열려있는 스레드 마감 처리 (이전 날짜 질문 닫기)
            for thread in forum.threads:
                if not thread.archived and not thread.locked:
                    try:
                        await thread.edit(archived=True, locked=True, reason="새로운 첫 문장 질문 생성으로 인한 마감")
                        await self.log(f"이전 첫 문장 스레드를 마감했습니다: {thread.name}")
                    except Exception as e:
                        pass
        except Exception as e:
            await self.log(f"기존 스레드 마감 중 오류: {e}")

        try:
            thread_with_message = await forum.create_thread(
                name=thread_name,
                content=content,
                auto_archive_duration=1440 # 24시간
            )
            await self.log(f"오늘의 첫 문장 스레드가 생성되었습니다: {thread_name}")
            
            # 자정 브로드캐스트 (메인 채팅에 어제 답변 리뷰 및 오늘 질문 홍보)
            self.bot.loop.create_task(self.send_midnight_broadcast(question, old_thread, old_thread_id, thread_with_message.thread))

            # 봇 메시지(질문) 자체도 DB에 잠깐 올려놓을 순 있지만, 
            # 질문 내용은 parent 메시지를 가져오거나 할 수 있으므로 굳이 필요없음.
        except Exception as e:
            await self.log(f"❌ 포럼 스레드 생성 오류: {e}")

    async def send_midnight_broadcast(self, new_question: str, old_thread: discord.Thread, old_thread_id: int, new_thread: discord.Thread):
        main_channel = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
        if not main_channel:
            return

        answers = []
        old_question_text = "알 수 없는 질문"
        
        # old_thread 객체가 없더라도 old_thread_id가 있으면 DB에서 답변 조회 가능
        lookup_thread_id = old_thread.id if old_thread else old_thread_id
        if lookup_thread_id:
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute("SELECT user_id, answer, question FROM daily_sentence_answers WHERE thread_id = ?", (lookup_thread_id,))
                    rows = await cursor.fetchall()
                    for row in rows:
                        answers.append({"user_id": row[0], "answer": row[1]})
                        old_question_text = row[2]
                await self.log(f"자정 브로드캐스트: thread_id={lookup_thread_id}에서 {len(answers)}개의 답변을 조회했습니다.")
            except Exception as e:
                await self.log(f"자정 브로드캐스트 답변 조회 중 오류: {e}")
        else:
            await self.log("자정 브로드캐스트: 이전 스레드 ID를 알 수 없어 답변을 조회할 수 없습니다.")

        self._ensure_client()
        if not self.client:
            return
            
        try:
            role_mention_text = f"<@&{FIRST_SENTENCE_ROLE_ID}>\n-# ◟. 첫 문장 알림 역할을 받고 싶다면 <#1474014238468083867> 에서 역할을 선택해 달라묘!"
            
            if answers:
                random.shuffle(answers)
                answers = answers[:30]
                answers_context = "\n".join([f"유저 ID: {ans['user_id']}, 답변 내용: {ans['answer']}" for ans in answers])
                
                prompt = \
                    f"어제 하묘가 던진 질문: {old_question_text}\n" \
                    f"유저들의 답변 목록 (일부):\n{answers_context}\n\n" \
                    f"오늘 새롭게 던지는 질문: {new_question}\n\n" \
                    "너는 디스코드 봇 '하묘'야. 말을 하는 토끼 컨셉으로 다정하고 귀여운 반말 문체를 써 줘. " \
                    "말끝에는 자연스럽게 '~다묘', '~거다묘', '~보라묘', '~냐묘'를 붙여줘. '있거다묘' 같은 어색한 어미는 피하고 문맥에 맞게만 써줘.\n\n" \
                    "메인 채팅 채널 유저들에게 보낼 자정 공지 메시지를 작성해 줘. 다음 내용을 포함해야 해:\n" \
                    "1. 어제 질문의 답변 중 가장 인상 깊고 따뜻한 답변 2~3개를 골라서 소개하고 짧은 코멘트 남기기. (유저를 언급할 때는 반드시 디스코드 멘션 `<@유저 ID>` 형식을 사용해). 답변 길이가 꼭 길지 않더라도 하묘의 페르소나와 잘 맞는 따뜻한 내용을 우선으로 골라줘.\n" \
                    "2. 어제 이야기해주고 같이 참여해준 모두에게 고마움을 표현하기.\n" \
                    f"3. 오늘 새롭게 준비한 질문('{new_question}')에 대해서도 궁금해하며, <#{new_thread.id}> 모양의 멘션을 사용해 그곳에 와서 답변해달라고 부탁하기.\n" \
                    "선정된 유저들에게는 30쪽의 추가 보상이 주어졌다는 내용도 귀엽게 한 줄 덧붙여줘."
            else:
                 prompt = \
                    f"오늘 새롭게 던지는 질문: {new_question}\n\n" \
                    "너는 디스코드 봇 '하묘'야. 귀엽고 다정한 토끼 캐릭터. 반말로 말하며 끝은 '~다묘', '~거다묘' 등으로 끝내줘.\n" \
                    "어제는 첫 문장에 대해 새로운 답변이 없어서 조금 아쉬웠다는 귀여운 투정을 아주 짧게 남기고, " \
                    f"오늘 새롭게 준비한 질문('{new_question}')에 대해서는 꼭 많이 대답해주기를 바라며 참여를 유도하는 홍보 메시지를 작성해줘. " \
                    f"채널 멘션은 `<#{new_thread.id}>` 를 사용해줘."
            
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "너는 디스코드 봇 '하묘'야. 다정하고 귀엽고, 따뜻한 마음을 가진 토끼 캐릭터야."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            broadcast_msg = completion.choices[0].message.content.strip()
            
            final_msg = f"{broadcast_msg}\n\n{role_mention_text}"
            await main_channel.send(final_msg)
            await self.log("자정 브로드캐스트 메시지를 메인 채팅 채널에 전송했습니다.")
            
            # 인상깊은 답변으로 선정된 유저(멘션된 유저)에게 30쪽 추가 지급
            level_checker = self.bot.get_cog("LevelChecker")
            if level_checker and answers:
                mentioned_users = re.findall(r'<@(\d+)>', broadcast_msg)
                mentioned_users = list(set(mentioned_users))
                for str_uid in mentioned_users:
                    try:
                        uid = int(str_uid)
                        # 실제로 답변을 단 유저가 맞는지 검증
                        if any(ans['user_id'] == uid for ans in answers):
                            best_exp = 30
                            await level_checker.data_manager.add_exp(uid, best_exp, 'daily', 'first_sentence_best')
                            result = {
                                'success': True,
                                'exp_gained': best_exp,
                                'messages': [f"하묘가 건네는 첫 문장 인상깊은 답변 선정: **+{best_exp} 쪽**"],
                                'quest_completed': ['daily_first_sentence_best']
                            }
                            await level_checker._finalize_quest_result(uid, result)
                            await self.log(f"인상깊은 답변으로 선정된 유저 {uid}에게 {best_exp}쪽을 지급했습니다.")
                    except Exception as e:
                        await self.log(f"보상 지급 중 오류 발생: {e}")

        except Exception as e:
            await self.log(f"❌ 자정 브로드캐스트 생성 중 오류: {e}")

    async def promote_daily_thread(self):
        forum = self.bot.get_channel(FIRST_SENTENCE_FORUM_ID)
        main_channel = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
        if not forum or not main_channel:
            return

        active_thread = None
        for thread in forum.threads:
            if not thread.archived and not thread.locked:
                active_thread = thread
                break
                
        if not active_thread:
            return

        question_text = "알 수 없는 질문"
        try:
            starter_msg = await active_thread.fetch_message(active_thread.id)
            if starter_msg:
                lines = starter_msg.content.split('\n')
                for line in lines:
                    if line.startswith("> **Q."):
                        question_text = line.replace("> **Q. ", "").replace("**", "").strip()
                        break
        except Exception:
            pass

        self._ensure_client()
        if not self.client:
            return

        try:
            # 현재 시간에 따라 식사 관련 멘트 추가
            now_hour = datetime.now(KST).hour
            if now_hour == 12:
                meal_context = "지금은 점심시간이니까, 점심 맛있게 먹으라는 다정한 인사도 함께 넣어줘."
            elif now_hour == 18:
                meal_context = "지금은 저녁시간이니까, 저녁 맛있게 먹으라는 다정한 인사도 함께 넣어줘."
            else:
                meal_context = ""

            prompt = \
                f"오늘의 '하묘가 건네는 첫 문장' 질문은 '{question_text}'야.\n" \
                f"디스코드 메인 채팅 채널 유저들에게 이 주제에 대해 너희들의 이야기가 너무 궁금하다며 오늘 질문 채널(<#{active_thread.id}>)로 와서 답해달라고 홍보하는 " \
                "2~3줄짜리 귀여운 홍보 메시지를 작성해줘. " \
                f"{meal_context}\n" \
                "너는 다정하고 착한 토끼 '하묘'야. 반말을 사용하고 말끝을 '~다묘', '~거다묘', '~보라묘' 등으로 마무리해줘."
            
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "너는 디스코드 봇 하묘야. 귀엽고 다정한 토끼 캐릭터. 친근하게 반말을 쓰고 말끝을 ~다묘로 끝내줘."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            promo_msg = completion.choices[0].message.content.strip()
            role_mention_text = f"<@&{EVERYONE_ROLE_ID}>\n-# ◟. 첫 문장 알림 역할을 받고 싶다면 <#1474014238468083867> 에서 역할을 선택해 달라묘!"
            
            final_msg = f"{promo_msg}\n\n{role_mention_text}"
            await main_channel.send(final_msg)
            await self.log("시간대별 첫 문장 스레드 홍보 메시지를 전송했습니다.")
        except Exception as e:
            await self.log(f"❌ 홍보 메시지 생성 중 오류: {e}")

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
            try:
                await message.add_reaction(random.choice(REACTION_EMOJI_POOL))
            except Exception as e:
                await self.log(f"반응 추가 중 오류: {e}")
            return

        try:
            prompt = f"유저가 다음 질문에 대해 답변을 달았어:\n질문: {question_text}\n유저 답변: {answer_text}\n\n이 답변에 대해 하묘(착하고 다정한 토끼 캐릭터, 말투는 '~다묘', '~거다묘')가 해줄 법한 1~2줄의 따뜻하고 공감 가는 코멘트를 작성해 줘."
            completion = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 디스코드 봇 '하묘'야. 길게 말하지 않고 아주 짧고 따뜻하게 2~3줄로만 대답해줘. 다정한 반말 문체에 말끝을 자연스럽게 '~다묘', '~거다묘', '~냐묘'로 끝내줘. 어색하게 억지로 붙이지 말고 (예: '있거다묘' X), '정말 다행이다묘!', '최고였다묘!' 처럼 자연스럽게 써 줘."},
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
        try:
            await message.add_reaction(random.choice(REACTION_EMOJI_POOL))
        except Exception as e:
            await self.log(f"반응 추가 중 오류: {e}")


    @commands.command(name="첫문장테스트")
    @is_guild_admin()
    async def test_first_sentence(self, ctx):
        await self.generate_daily_thread()
        await ctx.message.add_reaction("✅")
        
    @commands.command(name="자정브로드캐스트실행")
    @is_guild_admin()
    async def test_midnight_broadcast(self, ctx):
        """테스트용 자정 브로드캐스트 강제 실행 (현재 가장 최근 질문을 기준으로 동작)"""
        forum = self.bot.get_channel(FIRST_SENTENCE_FORUM_ID)
        if not forum or not isinstance(forum, discord.ForumChannel):
            await ctx.send("❌ 첫 문장 포럼을 찾을 수 없거나 포럼 채널이 아닙니다.")
            return

        threads = list(forum.threads)
        async for t in forum.archived_threads(limit=10):
            if t not in threads:
                threads.append(t)
                
        threads.sort(key=lambda t: t.id, reverse=True)

        if len(threads) < 2:
            await ctx.send("❌ 비교할 이전 스레드가 충분하지 않습니다. (최소 2개의 활성화/마감 스레드가 필요합니다)")
            return

        # 가장 최근 스레드 = 오늘의 질문, 그 다음 스레드 = 어제의 질문으로 간주
        new_thread = threads[0]
        old_thread = threads[1]

        question_text = "알 수 없는 질문"
        try:
            starter_msg = await new_thread.fetch_message(new_thread.id)
            if starter_msg:
                lines = starter_msg.content.split('\n')
                for line in lines:
                    if line.startswith("> **Q."):
                        question_text = line.replace("> **Q. ", "").replace("**", "").strip()
                        break
        except Exception:
            pass

        await ctx.send(f"자정 브로드캐스트를 실행합니다다묘... (오늘 질문: {question_text})")
        
        # 어제 스레드와 오늘 스레드를 넘겨주고 강제 브로드캐스트 실행
        await self.send_midnight_broadcast(question_text, old_thread, old_thread.id, new_thread)
        await ctx.message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(DailyFirstSentence(bot))
