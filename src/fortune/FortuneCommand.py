import os
import random
import re
from datetime import datetime

import discord
from discord.ext import commands
from openai import AsyncOpenAI

from src.core import birthday_db
from src.core import fortune_db
from src.core.admin_utils import only_in_guild, is_guild_admin
from src.birthday.BirthdayInterface import KST

from dotenv import load_dotenv
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
        """Logger cog를 통해 로그 메시지 전송"""
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message, title="🍀 운세 시스템 로그", color=discord.Color.green())
        except Exception as e:
            print(f"🐾{self.__class__.__name__} 로그 전송 오류 발생: {e}")

    def _ensure_client(self):
        """API 키 변경 시 새 클라이언트를 준비"""
        current_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHATGPT_API_KEY")
        if current_key != self.api_key:
            self.api_key = current_key
            self.client = None
        if not self.client and self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)

    def _get_zodiac_sign(self, month: int, day: int) -> str:
        """월/일 기반 별자리 반환"""
        zodiac_ranges = [
            ((1, 20), "염소자리"),
            ((2, 19), "물병자리"),
            ((3, 21), "물고기자리"),
            ((4, 20), "양자리"),
            ((5, 21), "황소자리"),
            ((6, 22), "쌍둥이자리"),
            ((7, 23), "게자리"),
            ((8, 23), "사자자리"),
            ((9, 24), "처녀자리"),
            ((10, 24), "천칭자리"),
            ((11, 23), "전갈자리"),
            ((12, 22), "사수자리"),
            ((12, 32), "염소자리"),
        ]

        for (m, d), sign in zodiac_ranges:
            if (month, day) < (m, d):
                return sign
        return "염소자리"

    def _get_life_path_number(self, year: int, month: int, day: int):
        """생년월일 숫자합 기반 라이프패스 숫자(1~9)"""
        if not year:
            return None

        total = sum(int(ch) for ch in f"{year}{month:02d}{day:02d}")
        while total > 9:
            total = sum(int(ch) for ch in str(total))
        return total

    def _build_birth_profile(self, birth_year, month: int, day: int) -> dict:
        """생일로부터 개인화 키워드 세트 생성"""
        zodiac = self._get_zodiac_sign(month, day)
        life_path = self._get_life_path_number(int(birth_year), month, day) if birth_year else None

        month_traits = {
            1: ("정리", "속도보다 완성도"),
            2: ("관찰", "감정 소모 관리"),
            3: ("확장", "과한 약속 주의"),
            4: ("실행", "독단 피하기"),
            5: ("변화", "집중 분산 주의"),
            6: ("돌봄", "과책임 경계"),
            7: ("분석", "과몰입 경계"),
            8: ("추진", "무리한 지출 경계"),
            9: ("정리", "미루기 경계"),
            10: ("주도", "강한 표현 완화"),
            11: ("조율", "애매한 표현 정리"),
            12: ("회복", "체력 저하 주의"),
        }

        zodiac_focus = {
            "염소자리": ("장기 계획", "우선순위 재정렬"),
            "물병자리": ("새로운 관점", "검증 없는 시도 자제"),
            "물고기자리": ("공감", "감정 과투입 경계"),
            "양자리": ("결단", "성급한 답변 주의"),
            "황소자리": ("지속성", "고집으로 인한 지연 주의"),
            "쌍둥이자리": ("소통", "핵심 누락 주의"),
            "게자리": ("신뢰", "눈치 보기로 타이밍 놓침 주의"),
            "사자자리": ("표현력", "과한 확신 톤 조절"),
            "처녀자리": ("정밀함", "사소한 완벽주의 완화"),
            "천칭자리": ("균형", "결정 미루기 주의"),
            "전갈자리": ("집중", "강한 단정 표현 완화"),
            "사수자리": ("확장", "마감 전 산만함 주의"),
        }

        relation_style = ["직설형", "경청형", "중재형", "질문형", "공감형"][day % 5]
        mistake_trigger = ["메시지 확인 지연", "일정 과신", "즉흥 지출", "피로 누적", "답변 서두름"][month % 5]
        luck_anchor = ["초반 2시간 집중", "오후 재정비", "짧은 산책", "메모 기반 대화", "작은 정리 루틴"][day % 5]

        month_key, month_caution = month_traits[month]
        zodiac_key, zodiac_caution = zodiac_focus[zodiac]

        return {
            "zodiac": zodiac,
            "life_path": life_path,
            "month_key": month_key,
            "month_caution": month_caution,
            "zodiac_key": zodiac_key,
            "zodiac_caution": zodiac_caution,
            "relation_style": relation_style,
            "mistake_trigger": mistake_trigger,
            "luck_anchor": luck_anchor,
        }

    def _extract_avoid_phrases(self, recent_texts, limit: int = 18):
        """최근 운세에서 반복 가능성이 큰 표현 후보를 추출"""
        if not recent_texts:
            return []

        banned_prefixes = ("**요약:**", "**행운의 상징:**")
        phrases = []
        seen = set()

        for text in recent_texts:
            if not isinstance(text, str):
                continue

            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            for ln in lines:
                if ln.startswith(banned_prefixes):
                    continue

                cleaned = re.sub(r"\s+", " ", ln)
                cleaned = re.sub(r"[\*`#]", "", cleaned).strip(" .")
                if 9 <= len(cleaned) <= 42 and cleaned not in seen:
                    seen.add(cleaned)
                    phrases.append(cleaned)

                if len(phrases) >= limit:
                    return phrases

        return phrases

    @commands.command(name="운세")
    @only_in_guild()
    async def tell_fortune(self, ctx):
        """운세를 생성하여 전송"""
        config = fortune_db.get_guild_config(ctx.guild.id)
        target = fortune_db.get_target(ctx.guild.id, ctx.author.id)

        # 설정된 채널에서만 사용 가능
        channel_id = config.get("channel_id")
        if channel_id and ctx.channel.id != channel_id:
            return

        if not target:
            await ctx.reply("운세 대상에 등록되어 있지 않다묘... 관리자가 등록해줘야 *운세 명령을 쓸 수 있다묘!")
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
            await ctx.reply("등록 기간이 끝난 것 같다묘. 다시 등록받아달라묘!")
            return

        self._ensure_client()
        if not self.api_key:
            await ctx.reply("ChatGPT API 키가 설정되어 있지 않다묘... `OPENAI_API_KEY`(또는 `CHATGPT_API_KEY`) 환경 변수를 넣어달라묘!")
            return

        birthday = await birthday_db.get_birthday(str(ctx.author.id))
        if not birthday:
            await ctx.reply("생일 정보가 없다묘! <#1474014240036749388>에서 생일을 등록해달라묘.")
            return

        birth_year = birthday.get("year")
        month = birthday.get("month")
        day = birthday.get("day")

        if not month or not day:
            await ctx.reply("생일 데이터가 이상하다묘... 다시 등록해달라묘!")
            return

        today = datetime.now(KST)

        if birth_year:
            birth_text = f"{birth_year}년 {month}월 {day}일생"
        else:
            birth_text = f"생년 미기재 {month}월 {day}일생"

        await self._generate_fortune(ctx, birth_text, today, birth_year, int(month), int(day))
        
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

    @commands.command(name="강제운세")
    @is_guild_admin()
    async def force_fortune(self, ctx):
        """관리자 권한으로 제약 없이 운세를 생성"""
        self._ensure_client()
        if not self.api_key:
            await ctx.reply("ChatGPT API 키가 설정되어 있지 않다묘...")
            return

        birthday = await birthday_db.get_birthday(str(ctx.author.id))
        if not birthday:
            await ctx.reply("강제 운세라도 생일 정보는 있어야 한다묘! <#1396829221741002796>에서 등록해달라묘.")
            return
            
        birth_year = birthday.get("year")
        month = birthday.get("month")
        day = birthday.get("day")

        if not month or not day:
            await ctx.reply("생일 데이터가 이상하다묘...")
            return

        today = datetime.now(KST)
        if birth_year:
            birth_text = f"{birth_year}년 {month}월 {day}일생"
        else:
            birth_text = f"생년 미기재 {month}월 {day}일생"

        await self._generate_fortune(ctx, birth_text, today, birth_year, int(month), int(day))
        await self.log(f"{ctx.author}({ctx.author.id})가 관리자 권한으로 강제 운세를 조회함 [길드: {ctx.guild.name}({ctx.guild.id})]")

    async def _generate_fortune(self, ctx, birth_text, today, birth_year, month: int, day: int):
        """공통 운세 생성 로직"""
        today_text = f"{today.year}년 {today.month}월 {today.day}일"
        birth_profile = self._build_birth_profile(birth_year, month, day)
        life_path_text = str(birth_profile["life_path"]) if birth_profile["life_path"] is not None else "미제공"

        recent_texts = fortune_db.get_recent_fortune_texts(ctx.guild.id, ctx.author.id, days=7)
        avoid_phrases = self._extract_avoid_phrases(recent_texts)
        avoid_phrases_text = "\n".join([f"- {p}" for p in avoid_phrases]) if avoid_phrases else "- 없음"

        prompt = (
            f"{birth_text} {today_text} 오늘의 운세를 알려줘.\n"
            "아래 개인화 입력을 반드시 반영해.\n"
            f"- 별자리: {birth_profile['zodiac']}\n"
            f"- 월별 핵심 성향: {birth_profile['month_key']}\n"
            f"- 별자리 핵심 성향: {birth_profile['zodiac_key']}\n"
            f"- 관계 소통 스타일: {birth_profile['relation_style']}\n"
            f"- 오늘 실수 트리거: {birth_profile['mistake_trigger']}\n"
            f"- 행운 루틴 키워드: {birth_profile['luck_anchor']}\n"
            f"- 라이프패스 숫자: {life_path_text}\n\n"
            "최근 7일 운세에서 반복 회피할 표현 목록:\n"
            f"{avoid_phrases_text}"
        )

        # 매 호출마다 문체/리듬을 바꾸기 위한 다양성 지시문
        variant_instruction = random.choice([
            "문장 길이를 짧은 문장과 긴 문장으로 교차하고, 문단 첫 문장은 각각 다른 방식(상황 제시/행동 제안/감각 묘사)으로 시작해",
            "각 문단에 서로 다른 리듬을 사용하고, 같은 어미 반복을 줄이며, 비유는 한 문단에 최대 1회만 사용해",
            "문단마다 시점을 다르게 운용해(관찰->행동->정리), 상투 표현 없이 구체 장면 중심으로 전개해",
            "첫 문단은 현실 장면, 둘째 문단은 대화 맥락, 셋째 문단은 체크리스트형 조언으로 구성하되 문장 흐름은 자연스럽게 이어가",
            "문단 시작어를 모두 다르게 하고, 연결어 남용을 피하며, 핵심 조언은 동사 중심으로 또렷하게 써",
        ])

        system_prompt = (
            "너는 오늘의 운세를 전하는 글을 쓰는 작가형 AI야. 단순 정보 전달이 아니라, 사람이 쓴 듯한 자연스럽고 생생한 문장으로 운세를 작성해.\n\n"
            "【핵심 목표】\n"
            "- 읽는 사람이 '내 이야기 같다'고 느낄 정도로 구체적이고 현실적인 상황을 포함해\n"
            "- 추상적인 표현보다 장면이 떠오르는 묘사를 우선해\n"
            "- 매번 완전히 다른 글처럼 느껴지도록 표현, 리듬, 비유를 바꿔\n\n"
            "【말투 규칙】\n"
            "- 디스코드 봇 '하묘'의 말투를 유지해\n"
            "- 모든 문장은 반드시 '묘'로 끝내고, 평서문은 마침표(.)로 마무리해\n"
            "- 질문문만 물음표(?)를 사용하고, '묘' 바로 뒤에 문장부호를 붙여\n"
            "- 지나치게 꾸민 문장보다 자연스럽고 읽기 편한 문장으로 써\n"
            "- 과장된 긍정은 피하고, 따뜻하지만 담백한 어조를 유지해\n\n"
            "【콘텐츠 규칙】\n"
            "- 반드시 구체적인 상황을 1개 이상 포함해 (예: 메시지를 늦게 확인해 오해가 생기는 상황, 회의에서 의견 타이밍을 놓치는 상황)\n"
            "- 각 문단은 서로 다른 주제를 다루고 내용이 겹치지 않게 작성해\n"
            "- 긍정 70%, 주의/경고 30% 비율을 유지해\n"
            "- 경고를 제시할 때는 반드시 실제 행동 가능한 대응 방법을 함께 제시해\n\n"
            "【생일 기반 개인화 규칙 - 최우선】\n"
            "- 사용자 입력의 별자리/월별 성향/관계 스타일/실수 트리거/행운 루틴을 반드시 본문에 녹여 써\n"
            "- 세 문단 모두 개인화 요소를 각각 1개 이상 반영해\n"
            "- 생일이 다르면 핵심 상황, 조언, 경고 포인트가 명확히 달라지게 작성해\n"
            "- 개인화 키워드는 직접 나열하지 말고 자연스러운 문장 안에 녹여 써\n"
            "- 생년월일 자체 언급은 금지하되, 개인화 해석 결과는 적극 반영해\n\n"
            "【다양성 강화 규칙 - 매우 중요】\n"
            f"- {variant_instruction}\n"
            "- 같은 표현, 문장 구조, 시작 방식 반복을 금지해\n"
            "- '좋은 기운', '무난한 하루', '작은 행운' 같은 상투 표현은 쓰지 마\n"
            "- 사용자 프롬프트에 제공된 '반복 회피 표현 목록'과 동일/유사한 문장을 다시 쓰지 마\n"
            "- 특히 문단 첫 문장과 요약 문장은 과거 7일과 겹치지 않게 새롭게 작성해\n"
            "- 문단 시작 방식은 매번 다르게 구성해 (상황 제시 / 감각 묘사 / 행동 제안 등)\n"
            "- 비유를 쓰더라도 뻔한 비유(cliche)는 피해\n\n"
            "【출력 형식 - 반드시 준수】\n"
            "서론 없이 바로 시작해\n\n"
            "- 본문은 총 3~4개 문단으로 작성해\n"
            "- 각 문단은 3~5줄 분량으로 작성해\n"
            "- 문단별 주제는 모델이 직접 정하되, 문단끼리 주제와 표현이 겹치지 않게 구성\n"
            "- 최소 1개 문단에는 일/학업/할 일 진행 관련 장면을, 최소 1개 문단에는 관계/소통 장면을 포함해\n"
            "- 남은 문단 주제는 컨디션, 소비 습관, 감정 관리, 시간 운영, 공간/환경, 루틴 등에서 자유롭게 선택해\n"
            "- 각 문단에는 반드시 1개 이상의 구체적 상황과 1개 이상의 행동 가능한 조언을 포함해\n\n"
            "(빈 줄)\n\n"
            "**요약:** 한 문장으로 핵심 정리 (자연스럽게)묘.\n\n"
            "**행운의 상징:**\n"
            "- 아래 항목 중 6개 선택\n"
            "- 매번 다른 조합 + 다른 키워드 사용\n"
            "- 절대 반복 금지\n\n"
            "선택 항목:\n"
            "행동, 장소, 색깔, 음식, 숫자, 방향, 동물, 시간대, 날씨, 물건, 꽃, 감정\n\n"
            "출력 형식:\n"
            "항목-(키워드), 항목-(키워드), 항목-(키워드), 항목-(키워드), 항목-(키워드), 항목-(키워드)\n\n"
            "【금지 사항】\n"
            "- 생년월일, 나이, 날짜 언급 금지\n"
            "- 서론/인사말 금지\n"
            "- 같은 표현 반복 금지\n"
            "- 추상적인 말만 하고 끝내는 것 금지\n"
            "- 입력된 개인화 정보를 무시한 일반론 운세 작성 금지\n"
            "- 요약/행운의 상징에서도 띄어쓰기를 철저히 지켜\n\n"
            "【중요】\n"
            "- 형식은 반드시 지키되, 문장은 매번 새롭게 만들어\n"
            "- 사람이 쓴 글처럼 자연스러운 흐름을 최우선으로 해"
        )

        waiting_message = None
        try:
            waiting_message = await ctx.reply("운세를 불러오는 중이다묘... 잠시만 기다려달라묘!", mention_author=False)
            
            response = await self.client.responses.create(
                model="gpt-5.4",
                instructions=system_prompt,
                input=prompt,
                reasoning= {
                    "effort": "medium"
                }
            )
            fortune_text = (getattr(response, "output_text", None) or "").strip()

            if not fortune_text:
                text_parts = []
                for item in (getattr(response, "output", None) or []):
                    for content in (getattr(item, "content", None) or []):
                        text_value = getattr(content, "text", None)
                        if text_value:
                            text_parts.append(text_value)
                fortune_text = "\n".join(text_parts).strip()

            if not fortune_text:
                raise ValueError("Responses API returned empty output")

            fortune_db.add_fortune_history(
                ctx.guild.id,
                ctx.author.id,
                today.strftime("%Y-%m-%d"),
                fortune_text,
                keep_days=7,
            )
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


async def setup(bot):
    await bot.add_cog(FortuneCommand(bot))
