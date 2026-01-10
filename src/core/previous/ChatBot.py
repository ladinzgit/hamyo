# hamyo_cog.py
import os
import json
import asyncio
from collections import defaultdict, deque
from typing import Dict, List, Any, Deque, Tuple, Optional

import discord
from discord.ext import commands

# OpenAI SDK (async)
try:
    from openai import AsyncOpenAI
except Exception:
    raise RuntimeError("`openai` 패키지가 필요해요. pip install -U openai 로 설치해줘요.")

# 토큰 카운트 유틸 (대략치 + tiktoken 폴백)
try:
    import tiktoken
    _HAVE_TIKTOKEN = True
except Exception:
    _HAVE_TIKTOKEN = False


# ---------------------------
# Config Manager
# ---------------------------
class ConfigManager:
    def __init__(self, path: str = "config.json"):
        self.path = path
        self.data = {
            "model": "gpt-5-nano",
            "allowed_channel_ids": [],
            "input_token_budget": 6400,        # ✅ 프롬프트(입력) 토큰 상한
            "short_term_limit": 20,            # 단기 메모리 유지 수
            "summarize_after_messages": 40,    # 이 수 초과 시 오래된 기록 요약
            "top_p": 1.0,
            "memory_dir": "data/hamyo_memory",
            "max_output_tokens_default": 512,
            "reasoning_effort": "low"          # ✅ reasoning 토큰 절약
        }
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            self.data.update(user_data)
        os.makedirs(self.data["memory_dir"], exist_ok=True)

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @property
    def model(self) -> str:
        return self.data["model"]

    @property
    def allowed_channels(self) -> List[int]:
        return list(self.data["allowed_channel_ids"])

    def add_channel(self, cid: int) -> bool:
        if cid not in self.data["allowed_channel_ids"]:
            self.data["allowed_channel_ids"].append(cid)
            self.save()
            return True
        return False

    def remove_channel(self, cid: int) -> bool:
        if cid in self.data["allowed_channel_ids"]:
            self.data["allowed_channel_ids"].remove(cid)
            self.save()
            return True
        return False


# ---------------------------
# Token Utils
# ---------------------------
def _approx_token_count(text: str) -> int:
    return max(1, int(len(text) / 3.5))

def count_tokens_for_messages(messages: List[Dict[str, str]], model_hint: str = "gpt-5-nano") -> int:
    joined = ""
    for m in messages:
        joined += f"{m.get('role','')}: {m.get('content','')}\n"
    if not _HAVE_TIKTOKEN:
        return _approx_token_count(joined)
    try:
        enc = tiktoken.encoding_for_model(model_hint)
    except Exception:
        try:
            enc = tiktoken.get_encoding("o200k_base")
        except Exception:
            return _approx_token_count(joined)
    return len(enc.encode(joined))


# ---------------------------
# Persistence
# ---------------------------
def _channel_state_path(memory_dir: str, channel_id: int) -> str:
    return os.path.join(memory_dir, f"{channel_id}.json")

def load_channel_state(memory_dir: str, channel_id: int) -> Dict[str, Any]:
    path = _channel_state_path(memory_dir, channel_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"long_term_memory": "", "history": []}

def save_channel_state(memory_dir: str, channel_id: int, state: Dict[str, Any]):
    path = _channel_state_path(memory_dir, channel_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------
# Hamyo Cog
# ---------------------------
class HamyoCog(commands.Cog):
    """비몽다방 '하묘' 컨셉 챗봇 Cog (Responses API)"""

    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config
        self.oa = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # per-channel histories
        self.conversation_history: Dict[int, Deque[Dict[str, str]]] = defaultdict(lambda: deque(maxlen=1000))
        self.long_term_memory: Dict[int, str] = defaultdict(str)

        self._restore_all_allowed_channels()

    # ---------- lifecycle ----------
    def _restore_all_allowed_channels(self):
        for cid in self.config.allowed_channels:
            st = load_channel_state(self.config.data["memory_dir"], cid)
            self.long_term_memory[cid] = st.get("long_term_memory", "")
            self.conversation_history[cid] = deque(st.get("history", []), maxlen=1000)

    def _persist_channel(self, channel_id: int):
        st = {
            "long_term_memory": self.long_term_memory.get(channel_id, ""),
            "history": list(self.conversation_history.get(channel_id, deque()))
        }
        save_channel_state(self.config.data["memory_dir"], channel_id, st)

    # ---------- prompts ----------
    @property
    def base_system_prompt(self) -> str:
        # 프롬프트 요구사항 그대로
        return (
            "너는 꿈과 현실의 경계에 있는 다방인 비몽다방에서 차를 끓여주는 봉제인형 토끼 하묘야.\n"
            "평소엔 장난꾸러기지만, 차를 끓일 때만큼은 진심이야. 찻잎을 고를 때도 신중해.\n"
            "말은 짧고 평범한 일상톤으로, 특별히 요청하지 않으면 간단하게 대답해.\n"
            "말투는 슈가슈가룬의 듀크처럼 장난기 가득한 반말로, 과한 예의 금지. 모든 문장은 기본적으로 '묘'로 끝내되, 자연스럽지 않은 경우는 사용하지 마.\n"
            "짧고 툭툭, 가볍게 도발하되 무례/비하는 금지. 감탄사(헤헤, 킥킥 등)는 문장당 1회 이내\n"
            "한국어로 답해."
        )

    def _system_memory_prompt(self, channel_id: int) -> str:
        mem = self.long_term_memory.get(channel_id, "").strip()
        if not mem:
            return "현재까지의 장기 메모리는 없음."
        return f"### 장기 메모리 요약\n{mem}"

    # ---------- message building ----------
    def _build_messages(self, channel_id: int, user_content: str) -> Tuple[List[Dict[str, str]], int]:
        """
        Responses API의 input에 들어갈 chat-style 메시지 목록 구성
        (입력 토큰 상한 self.config.input_token_budget 내로 잘라냄)
        """
        model = self.config.model
        input_budget = int(self.config.data["input_token_budget"])

        # 최근 short_term_limit만 기본 사용
        short_lim = int(self.config.data["short_term_limit"])
        hist = list(self.conversation_history[channel_id])[-short_lim:]

        # Responses API에서는 persona는 instructions로, 장기메모리는 system 메시지로 주입
        prompt_msgs = [
            {"role": "system", "content": self._system_memory_prompt(channel_id)},
            *hist,
            {"role": "user", "content": user_content},
        ]

        tokens_now = count_tokens_for_messages(
            [{"role": "system", "content": self.base_system_prompt}] + prompt_msgs,
            model_hint=model
        )

        # 입력 토큰 상한 넘으면 과거부터 제거
        while tokens_now > input_budget and len(hist) > 0:
            hist.pop(0)
            prompt_msgs = [
                {"role": "system", "content": self._system_memory_prompt(channel_id)},
                *hist,
                {"role": "user", "content": user_content},
            ]
            tokens_now = count_tokens_for_messages(
                [{"role": "system", "content": self.base_system_prompt}] + prompt_msgs,
                model_hint=model
            )

        # 그래도 크면 장기 메모리 축약
        if tokens_now > input_budget:
            ltm = self.long_term_memory.get(channel_id, "")
            if ltm:
                self.long_term_memory[channel_id] = ltm[: max(0, len(ltm)//2)].rstrip()
                prompt_msgs = [
                    {"role": "system", "content": self._system_memory_prompt(channel_id)},
                    *hist,
                    {"role": "user", "content": user_content},
                ]
                tokens_now = count_tokens_for_messages(
                    [{"role": "system", "content": self.base_system_prompt}] + prompt_msgs,
                    model_hint=model
                )

        # 최후 방어: 시스템+유저만
        if tokens_now > input_budget:
            prompt_msgs = [{"role": "user", "content": user_content}]
            tokens_now = count_tokens_for_messages(
                [{"role": "system", "content": self.base_system_prompt}] + prompt_msgs,
                model_hint=model
            )

        return prompt_msgs, tokens_now

    # ---------- safe output extractor (Responses API) ----------
    @staticmethod
    def _extract_output_text(resp) -> str:
        """
        우선 resp.output_text 사용.
        간헐적 SDK 이슈로 빈 문자열일 때를 대비해 resp.output[*].content[*].text 폴백. 
        """
        try:
            txt = (getattr(resp, "output_text", None) or "").strip()
            if txt:
                return txt
        except Exception:
            pass

        # 폴백: 구조 탐색
        try:
            chunks = []
            for item in getattr(resp, "output", []) or []:
                contents = getattr(item, "content", []) or []
                for seg in contents:
                    # seg가 dict 또는 pydantic-like object일 수 있음
                    if isinstance(seg, dict):
                        t = seg.get("text") or seg.get("output_text") or ""
                    else:
                        t = getattr(seg, "text", "") or getattr(seg, "output_text", "")
                    if t:
                        chunks.append(t)
            return "".join(chunks).strip()
        except Exception:
            return ""

    # ---------- summarization ----------
    async def _maybe_summarize_history(self, channel_id: int):
        hist_dq = self.conversation_history[channel_id]
        limit = int(self.config.data["summarize_after_messages"])
        short_lim = int(self.config.data["short_term_limit"])

        if len(hist_dq) <= limit:
            return

        old_chunk = list(hist_dq)[:-short_lim]
        if not old_chunk:
            return

        # 간결 요약 프롬프트
        instructions = "다음 대화에서 장기적으로 유용한 사실·선호·규칙만 한국어 불릿으로 간결 요약해."
        summary_input = [
            {"role": "user", "content": "\n".join([f"{m['role']}: {m['content']}" for m in old_chunk])}
        ]

        try:
            resp = await self.oa.responses.create(
                model=self.config.model,
                instructions=instructions,
                input=summary_input,
                temperature=1,
                top_p=self.config.data["top_p"],
                reasoning={"effort": self.config.data.get("reasoning_effort", "low")},
                max_output_tokens=256,
            )
            summary = self._extract_output_text(resp)
            if summary:
                if self.long_term_memory[channel_id]:
                    self.long_term_memory[channel_id] += "\n\n" + summary
                else:
                    self.long_term_memory[channel_id] = summary
        except Exception as e:
            print(f"[summarize] failed for ch {channel_id}: {e}")

        # 최근 short_lim만 유지
        self.conversation_history[channel_id] = deque(list(hist_dq)[-short_lim:], maxlen=1000)
        self._persist_channel(channel_id)

    # ---------- Discord events ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel_id = message.channel.id
        if channel_id not in self.config.allowed_channels:
            return

        if message.content.strip().startswith(("!hadd", "!hremove", "!hlist", "!hreset")):
            return

        # 사용자 메시지 기록
        self.conversation_history[channel_id].append({"role": "user", "content": message.content})

        # 필요 시 요약
        await self._maybe_summarize_history(channel_id)

        # 응답 생성
        planned_out = int(self.config.data["max_output_tokens_default"])
        msgs, _ = self._build_messages(channel_id, message.content)

        try:
            print(msgs)
            resp = await self.oa.responses.create(
                model=self.config.model,
                # 하묘 페르소나는 instructions로
                instructions=self.base_system_prompt,
                # 장기 메모리는 system 메시지로, 단기 히스토리 + 현재 유저
                input=msgs,
                temperature=1,                                # gpt-5-nano 고정
                top_p=self.config.data["top_p"],
                reasoning={"effort": self.config.data.get("reasoning_effort", "low")},
                max_output_tokens=planned_out
            )
            print(resp)

            reply = self._extract_output_text(resp)
            if not reply:
                await message.channel.send("음… 말문이 잠깐 막혔나 봐. 한 번만 다시 물어봐줘 묘")
                self._persist_channel(channel_id)
                return

            await message.channel.send(reply)

            # 어시스턴트 응답 기록
            self.conversation_history[channel_id].append({"role": "assistant", "content": reply})
            self._persist_channel(channel_id)

        except Exception as e:
            print(f"[OpenAI error] {e}")
            await message.channel.send("앗, 잠깐 미끄러졌어. 다시 한 번 말해줄래 묘?")

    # ---------- Admin Commands ----------
    @commands.command(name="hadd")
    @commands.has_permissions(manage_channels=True)
    async def add_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        ch = channel or ctx.channel
        if self.config.add_channel(ch.id):
            self._persist_channel(ch.id)
            await ctx.send(f"이제 <#{ch.id}> 에서 하묘가 대화하고 기억할게 묘")
        else:
            await ctx.send("이미 등록된 채널이야 묘")

    @commands.command(name="hremove")
    @commands.has_permissions(manage_channels=True)
    async def remove_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        ch = channel or ctx.channel
        if self.config.remove_channel(ch.id):
            await ctx.send(f"<#{ch.id}> 채널은 더 이상 응답/기억하지 않을게 묘")
        else:
            await ctx.send("등록되어 있지 않아 묘")

    @commands.command(name="hlist")
    async def list_channels(self, ctx: commands.Context):
        ids = self.config.allowed_channels
        if not ids:
            await ctx.send("등록된 채널이 아직 없어 묘")
            return
        mention = " ".join([f"<#{i}>" for i in ids])
        await ctx.send(f"하묘가 활동하는 채널: {mention} 묘")

    @commands.command(name="hreset")
    @commands.has_permissions(manage_channels=True)
    async def reset_memory(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        ch = channel or ctx.channel
        self.long_term_memory[ch.id] = ""
        self.conversation_history[ch.id].clear()
        self._persist_channel(ch.id)
        await ctx.send(f"<#{ch.id}> 장기/단기 메모리를 비웠어 묘")


# ---------- Cog setup ----------
async def setup(bot: commands.Bot):
    cfg = ConfigManager()
    await bot.add_cog(HamyoCog(bot, cfg))
