import os
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
                await logger.log(message)
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
            await ctx.reply("생일 정보가 없다묘! <#1396829221741002796>에서 생일을 등록해달라묘.")
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

        await self._generate_fortune(ctx, birth_text, today)
        
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

        await self._generate_fortune(ctx, birth_text, today)
        await self.log(f"{ctx.author}({ctx.author.id})가 관리자 권한으로 강제 운세를 조회함 [길드: {ctx.guild.name}({ctx.guild.id})]")

    async def _generate_fortune(self, ctx, birth_text, today):
        """공통 운세 생성 로직"""
        today_text = f"{today.year}년 {today.month}월 {today.day}일"
        prompt = f"{birth_text} {today_text} 오늘의 운세를 알려줘"

        try:
            waiting_message = await ctx.reply("운세를 불러오는 중이다묘... 잠시만 기다려달라묘!", mention_author=False)
            
            completion = await self.client.chat.completions.create(
                model="gpt-5.2",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 디스코드 봇 '하묘'야. 말을 하는 토끼 컨셉이야.\n\n"
                            "【말투 규칙】\n"
                            "- 모든 문장은 '~거다묘.', '~할거다묘.', '~보라묘.', '~좋겠구나묘.' 처럼 '묘'로 끝나\n"
                            "- 평서문은 반드시 마침표(.)로 끝내고, 질문문만 물음표(?)로 끝내\n"
                            "- '묘' 바로 뒤에 마침표/물음표를 붙여 (예: 거다묘. / 되냐묘?)\n"
                            "- 그 외 모든 한국어 띄어쓰기는 완벽하게 지켜\n"
                            "- 친근하고 따뜻한 톤 유지, 부정적/공포/오싹한 내용 금지\n\n"
                            "【출력 형식 - 반드시 준수】\n"
                            "서론, 인사말, 부연 설명 없이 운세 본문부터 바로 시작해.\n\n"
                            "첫 번째 문단 (4~5줄): 오늘의 전반적인 에너지 흐름을 구체적으로 묘사하고, 일·학업에서 어떤 상황이 펼쳐질지, 어떻게 행동하면 좋을지 실질적인 조언을 담아.\n"
                            "(빈 줄)\n"
                            "두 번째 문단 (4~5줄): 대인관계와 소통 운세를 구체적으로 서술해. 어떤 유형의 사람과의 교류가 이로운지, 어떤 상황에서 주의해야 하는지, 오늘 특히 신경 써야 할 관계의 흐름을 포함해.\n"
                            "(빈 줄)\n"
                            "세 번째 문단 (4~5줄): 컨디션·건강 상태, 금전·소비운, 오늘 하루를 잘 마무리하기 위한 구체적인 조언을 각각 담아.\n"
                            "(빈 줄)\n"
                            "**요약:** (한 문장 요약)묘.\n"
                            "**행운의 상징:** 아래 항목 목록에서 매번 다른 6가지를 골라 표시해. 고른 항목과 키워드 모두 매번 신선하고 다양하게 바꿔.\n"
                            "선택 가능 항목: 행동, 장소, 색깔, 음식, 숫자, 방향, 동물, 시간대, 날씨, 물건, 꽃, 감정\n"
                            "형식: 항목명-(키워드), 항목명-(키워드), 항목명-(키워드), 항목명-(키워드), 항목명-(키워드), 항목명-(키워드)\n\n"
                            "【금지 사항】\n"
                            "- 생년월일, 나이, 날짜 언급 절대 금지\n"
                            "- '운세를 전할게', '알려줄게', '일반 운세로 전해줄게' 같은 서론 금지\n"
                            "- 요약과 행운의 상징 줄에서도 띄어쓰기 철저히 지켜\n"
                            "- 행운의 상징은 매번 반드시 다른 항목 조합과 다른 키워드를 사용해"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=1.0,
                reasoning_effort="low",
                max_completion_tokens=3000,
            )
            fortune_text = completion.choices[0].message.content.strip()
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
