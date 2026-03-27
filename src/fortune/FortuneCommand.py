import os
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

    def _extract_avoid_phrases(self, recent_texts, limit: int = 24):
        """최근 운세에서 반복 가능성이 큰 표현 후보를 추출 (상투 표현 + 실제 사용 문장)"""
        if not recent_texts:
            return []

        # dinzbot 스타일: 자주 반복되는 상투 표현 목록
        cliche_candidates = [
            "좋은 기운", "무난한 하루", "작은 행운", "기회를 잡", "흐름을 타",
            "균형을 유지", "여유를 가져", "신중하게", "서두르지", "천천히",
            "타이밍", "소통이 중요", "컨디션 관리", "지출 관리", "에너지가",
            "기분 전환", "새로운 시작", "한 걸음", "마음의 여유", "리듬을 찾",
        ]

        joined = "\n".join(t for t in recent_texts if isinstance(t, str))
        found: list[str] = []
        seen = set()

        # 1) 상투 표현 중 실제로 사용된 것 수집
        for phrase in cliche_candidates:
            if re.search(re.escape(phrase), joined) and phrase not in seen:
                seen.add(phrase)
                found.append(phrase)

        # 2) 실제 문장에서 핵심 표현 추출 (문단 첫 문장, 요약 등)
        banned_prefixes = ("**요약:**", "**행운의 상징:**")
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
                    found.append(cleaned)
                if len(found) >= limit:
                    return found

        return found

    def _build_recent_fortune_summary(self, recent_texts):
        """최근 운세 각각의 핵심 소재/장면을 요약 목록으로 반환 (중복 방지용)"""
        if not recent_texts:
            return ""

        summaries = []
        for i, text in enumerate(recent_texts, 1):
            if not isinstance(text, str):
                continue
            # 각 운세에서 첫 3줄(핵심 소재/장면)을 추출
            content_lines = []
            for ln in text.splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("**요약:**") or ln.startswith("**행운의 상징:**"):
                    continue
                cleaned = re.sub(r"[\*`#]", "", ln).strip()
                if len(cleaned) >= 8:
                    content_lines.append(cleaned)
                if len(content_lines) >= 3:
                    break
            if content_lines:
                summaries.append(f"[{i}일전 운세 핵심 소재]\n" + "\n".join(f"  - {c}" for c in content_lines))

        return "\n".join(summaries)

    @commands.command(name="운세")
    @only_in_guild()
    async def tell_fortune(self, ctx):
        """운세를 생성하여 전송"""
        config = fortune_db.get_guild_config(ctx.guild.id)

        # 설정된 채널에서만 사용 가능
        channel_id = config.get("channel_id")
        if channel_id and ctx.channel.id != channel_id:
            return

        user_record = fortune_db.get_user_record(ctx.guild.id, ctx.author.id)

        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        if user_record and user_record.get("last_used_date") == today_str:
            await ctx.reply("오늘은 이미 운세를 봤다묘! 내일 다시 찾아와달라묘.", mention_author=False)
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
        fortune_db.mark_user_used(ctx.guild.id, ctx.author.id, today_str)

        await self.log(
            f"{ctx.author}({ctx.author.id})가 운세를 조회함 "
            f"[길드: {ctx.guild.name}({ctx.guild.id})]"
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
        recent_summary = self._build_recent_fortune_summary(recent_texts)

        prompt = (
            "다음 정보를 반영해 오늘의 개인화 운세를 작성해.\n"
            f"- 기준 정보: {birth_text}, {today_text}\n"
            f"- 별자리: {birth_profile['zodiac']}\n"
            f"- 월별 키워드: {birth_profile['month_key']}\n"
            f"- 별자리 키워드: {birth_profile['zodiac_key']}\n"
            f"- 관계 스타일: {birth_profile['relation_style']}\n"
            f"- 실수 트리거: {birth_profile['mistake_trigger']}\n"
            f"- 행운 루틴: {birth_profile['luck_anchor']}\n"
            f"- 라이프패스: {life_path_text}\n\n"
            "최근 7일 반복 금지 표현:\n"
            f"{avoid_phrases_text}\n\n"
        )

        if recent_summary:
            prompt += (
                "=== 최근 7일간 사용된 운세 핵심 소재 (절대 재사용 금지) ===\n"
                f"{recent_summary}\n\n"
                "위 소재들과 겹치지 않는 완전히 새로운 장면과 조언으로 작성해.\n"
            )

        system_prompt = (
            "너는 디스코드 봇 하묘의 운세 작성자다. 간결하지만 생생한 한국어로 개인화 운세를 작성해.\n\n"
            "[말투]\n"
            "- 모든 문장은 '묘'로 끝내고, 평서문은 마침표로 끝내\n"
            "- 과장된 미사여구는 피하고 따뜻하고 담백한 톤 유지\n\n"
            "[내용]\n"
            "- 3개 문단 작성, 문단마다 주제를 다르게 유지\n"
            "- 최소 1개 문단은 일/학업/할 일, 최소 1개 문단은 관계/소통 장면 포함\n"
            "- 각 문단에 구체적 상황 1개 이상 + 실행 가능한 조언 1개 이상 포함\n"
            "- 긍정:주의 비중은 약 7:3\n"
            "- 입력된 개인화 요소(별자리/성향/트리거/루틴)를 직접 나열하지 말고 문장 속에 자연스럽게 반영\n\n"
            "[중복 방지]\n"
            "- 제공된 반복 금지 표현/최근 7일 핵심 소재와 동일하거나 유사한 표현, 장면, 비유를 사용하지 마\n"
            "- 문단 시작 문장 3개는 서로 완전히 다르게 작성\n\n"
            "[출력 형식]\n"
            "- 인사말 없이 본문부터 시작\n"
            "- 본문 3문단 작성 후 한 줄 띄우고 아래 2개 블록 추가\n"
            "- **요약:** 한 문장\n"
            "- **행운의 상징:** 행동, 장소, 색깔, 음식, 숫자, 물건 형식으로 6개\n"
            "- 상징 출력 예시: 행동-(...), 장소-(...), 색깔-(...), 음식-(...), 숫자-(...), 물건-(...)\n\n"
            "[금지]\n"
            "- 생년월일/나이/날짜 직접 언급\n"
            "- 일반론만 있는 추상적 조언\n"
            "- 같은 표현 반복"
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
