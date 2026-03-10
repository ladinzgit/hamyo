# src/constellation/ConstellationCog.py
# ============================================================
# 비몽 별자리 수집 디스코드 명령어 Cog
# 관측, 도감, 교환, 설정 명령어를 제공합니다.
# ============================================================

import discord
from discord.ext import commands
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
import pytz

from src.core.admin_utils import only_in_guild, is_guild_admin
from src.core.balance_data_manager import balance_manager
from src.level.LevelConstants import MAIN_CHAT_CHANNEL_ID

from src.constellation.ConstellationConstants import (
    CONSTELLATIONS, CONSTELLATION_ORDER,
    SEOUL_LAT, SEOUL_LNG,
    FALLBACK_SUNSET_HOUR, FALLBACK_SUNRISE_HOUR,
    OBSERVE_NEW_STAR_MSG, OBSERVE_DUP_STAR_MSG,
    OBSERVE_COMPLETE_MSG, OBSERVE_DAYTIME_MSG,
    SUNSET_ANNOUNCE_MSG, SUNRISE_ANNOUNCE_MSG,
    OBSERVE_COOLDOWN_MSG,
    OBSERVE_NO_BALANCE_MSG, OBSERVE_ALL_COMPLETE_MSG,
    EMOJI_SUN, EMOJI_CRESCENT, EMOJI_STAR, EMOJI_CLOUD,
    EMOJI_GLITTER1, EMOJI_GLITTER2, EMOJI_MOON_WAXING,
)
from src.constellation.ConstellationData import ConstellationData
from src.constellation.ConstellationImageGen import ConstellationImageGen

KST = pytz.timezone("Asia/Seoul")


class ConstellationCog(commands.Cog):
    """비몽 별자리 수집 이벤트 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.data = ConstellationData()
        self.image_gen = ConstellationImageGen()

        # 일몰/일출 캐시
        self._sunset_time = None   # datetime (KST)
        self._sunrise_time = None  # datetime (KST)
        self._sun_times_date = None  # 캐시된 날짜

    async def cog_load(self):
        await self.data.ensure_initialized()
        print(f"✅ {self.__class__.__name__} loaded successfully!")
        self.bot.loop.create_task(self._setup_schedules())

    async def log(self, message: str):
        try:
            logger = self.bot.get_cog("Logger")
            if logger:
                await logger.log(message, title="🌌 별자리 시스템 로그", color=discord.Color.dark_blue())
        except Exception as e:
            print(f"❌ {self.__class__.__name__} 로그 전송 중 오류 발생: {e}")

    # ===========================================
    # 일몰/일출 API
    # ===========================================

    async def _fetch_sun_times(self, date_str: str = "today") -> tuple:
        """
        sunrise-sunset.org API로 서울의 일몰/일출 시간을 조회합니다.
        Returns: (sunset_dt, sunrise_dt) — KST datetime 객체
        실패 시 폴백값 사용.
        """
        url = (
            f"https://api.sunrise-sunset.org/json"
            f"?lat={SEOUL_LAT}&lng={SEOUL_LNG}"
            f"&formatted=0&date={date_str}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "OK":
                            results = data["results"]
                            # API는 UTC ISO 8601 반환
                            sunset_utc = datetime.fromisoformat(results["sunset"].replace("Z", "+00:00"))
                            sunset_kst = sunset_utc.astimezone(KST)

                            # 다음날 일출을 위해 tomorrow 조회
                            tomorrow = (datetime.now(KST) + timedelta(days=1)).strftime("%Y-%m-%d")
                            url_tomorrow = (
                                f"https://api.sunrise-sunset.org/json"
                                f"?lat={SEOUL_LAT}&lng={SEOUL_LNG}"
                                f"&formatted=0&date={tomorrow}"
                            )
                            async with session.get(url_tomorrow, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                                if resp2.status == 200:
                                    data2 = await resp2.json()
                                    if data2.get("status") == "OK":
                                        sunrise_utc = datetime.fromisoformat(
                                            data2["results"]["sunrise"].replace("Z", "+00:00")
                                        )
                                        sunrise_kst = sunrise_utc.astimezone(KST)
                                        return (sunset_kst, sunrise_kst)
        except Exception as e:
            print(f"일몰/일출 API 조회 실패: {e}")

        # 폴백
        now = datetime.now(KST)
        sunset_fb = now.replace(hour=FALLBACK_SUNSET_HOUR, minute=0, second=0, microsecond=0)
        sunrise_fb = (now + timedelta(days=1)).replace(hour=FALLBACK_SUNRISE_HOUR, minute=0, second=0, microsecond=0)
        return (sunset_fb, sunrise_fb)

    async def _ensure_sun_times(self):
        """오늘의 일몰/일출 시간을 캐시합니다. 날짜가 바뀌면 갱신합니다."""
        today = datetime.now(KST).date()
        if self._sun_times_date != today:
            self._sunset_time, self._sunrise_time = await self._fetch_sun_times()
            self._sun_times_date = today
            await self.log(
                f"일몰/일출 시간 갱신: 일몰 {self._sunset_time.strftime('%H:%M')}, "
                f"일출 {self._sunrise_time.strftime('%H:%M')}"
            )

    def _is_nighttime(self) -> bool:
        """현재 관측 가능한 시간대(일몰~일출)인지 확인합니다."""
        if self._sunset_time is None or self._sunrise_time is None:
            # 캐시 없으면 폴백
            now = datetime.now(KST)
            hour = now.hour
            return hour >= FALLBACK_SUNSET_HOUR or hour < FALLBACK_SUNRISE_HOUR

        now = datetime.now(KST)
        return now >= self._sunset_time and now < self._sunrise_time

    # ===========================================
    # 스케줄러 설정
    # ===========================================

    async def _setup_schedules(self):
        await self.bot.wait_until_ready()

        # 일몰/일출 시간 초기 로드
        await self._ensure_sun_times()

        # 일몰 알림 스케줄 등록
        await self._schedule_sunset_announce()

        # 일출 알림 스케줄 등록
        await self._schedule_sunrise_announce()

        # 매일 자정에 일몰/일출 갱신 + 재스케줄
        scheduler = self.bot.get_cog("Scheduler")
        if scheduler:
            scheduler.schedule_daily(self._daily_refresh, 0, 1)

    async def _daily_refresh(self):
        """매일 자정에 일몰/일출 시간을 갱신하고 알림을 재스케줄합니다."""
        self._sun_times_date = None  # 캐시 무효화
        await self._ensure_sun_times()
        await self._schedule_sunset_announce()
        await self._schedule_sunrise_announce()

    async def _schedule_sunset_announce(self):
        """오늘의 일몰 시간에 알림을 전송하도록 스케줄합니다."""
        scheduler = self.bot.get_cog("Scheduler")
        if not scheduler or not self._sunset_time:
            return

        now = datetime.now(KST)
        if self._sunset_time > now:
            scheduler.schedule_once(self._send_sunset_announce, self._sunset_time)
            await self.log(f"일몰 알림 스케줄 등록: {self._sunset_time.strftime('%H:%M')} KST")

    async def _schedule_sunrise_announce(self):
        """다음날 일출 시간에 알림을 전송하도록 스케줄합니다."""
        scheduler = self.bot.get_cog("Scheduler")
        if not scheduler or not self._sunrise_time:
            return

        now = datetime.now(KST)
        if self._sunrise_time > now:
            scheduler.schedule_once(self._send_sunrise_announce, self._sunrise_time)
            await self.log(f"일출 알림 스케줄 등록: {self._sunrise_time.strftime('%H:%M')} KST")

    def _get_announce_channel(self):
        """알림 채널을 반환합니다. 설정된 채널 > MAIN_CHAT_CHANNEL_ID 순으로 폴백."""
        announce_id = self.data.get_announce_channel_id()
        if announce_id:
            ch = self.bot.get_channel(announce_id)
            if ch:
                return ch
        return self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)

    async def _send_sunset_announce(self):
        """일몰 시 알림 메시지를 전송합니다."""
        channel = self._get_announce_channel()
        if channel:
            try:
                await channel.send(SUNSET_ANNOUNCE_MSG)
                await self.log("일몰 알림 전송 완료")
            except Exception as e:
                await self.log(f"일몰 알림 전송 실패: {e}")

    async def _send_sunrise_announce(self):
        """일출 시 관측 종료 + 아침 인사 메시지를 전송합니다."""
        channel = self._get_announce_channel()
        if channel:
            try:
                await channel.send(SUNRISE_ANNOUNCE_MSG)
                await self.log("일출 알림 전송 완료")
            except Exception as e:
                await self.log(f"일출 알림 전송 실패: {e}")

    # ===========================================
    # 채널 제한 체크
    # ===========================================

    def _check_channel(self, ctx) -> bool:
        """허용된 채널에서만 명령어가 실행되는지 확인합니다."""
        allowed = self.data.get_allowed_channels()
        if not allowed:
            return True  # 채널 제한 없음
        return ctx.channel.id in allowed

    # ===========================================
    # 관측 로직
    # ===========================================

    def _pick_random_star(self, collected_stars: dict) -> tuple:
        """
        수집 가능한 별 중 가중치 랜덤으로 하나를 선택합니다.
        이미 완성된 별자리는 제외하고, 별 수가 적은 별자리의 별을 더 높은 확률로 뽑습니다.
        Returns: (constellation_id, star_id, is_duplicate)
        """
        # 미완성 별자리만 추출
        candidates = []
        for cid in CONSTELLATION_ORDER:
            constellation = CONSTELLATIONS[cid]
            user_collected = set(collected_stars.get(cid, []))
            total = len(constellation["stars"])
            if len(user_collected) >= total:
                continue  # 완성된 별자리 제외

            # 각 별에 가중치 부여 (별 수가 적을수록 높은 가중치)
            weight = 1.0 / total
            for star in constellation["stars"]:
                candidates.append({
                    "constellation_id": cid,
                    "star": star,
                    "weight": weight,
                    "is_collected": star["id"] in user_collected,
                })

        if not candidates:
            return None

        # 가중치 기반 랜덤 선택
        weights = [c["weight"] for c in candidates]
        chosen = random.choices(candidates, weights=weights, k=1)[0]
        return (
            chosen["constellation_id"],
            chosen["star"]["id"],
            chosen["is_collected"]  # True면 중복
        )

    # ===========================================
    # 보상 처리
    # ===========================================

    async def _check_and_grant_rewards(self, ctx, user_id: int, constellation_id: str):
        """별자리 완성 시 마일스톤 보상을 확인하고 지급합니다."""
        completed_count = await self.data.get_completed_count(user_id)
        rewards = self.data.get_completion_rewards()

        key = str(completed_count)
        if key not in rewards:
            return

        reward = rewards[key]
        role_id = reward.get("role_id")
        bonus_on = reward.get("bonus_on", 0)
        guild = ctx.guild

        # 온 지급
        if bonus_on > 0:
            await balance_manager.give(str(user_id), bonus_on)

        # 역할 부여
        role_granted = False
        if role_id and guild:
            role = guild.get_role(role_id)
            if role:
                try:
                    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    if member:
                        await member.add_roles(role, reason=f"별자리 {completed_count}개 완성 보상")
                        role_granted = True
                except Exception as e:
                    await self.log(f"보상 역할 부여 실패: {e}")

        # 축하 메시지 (메인 채팅)
        channel = self.bot.get_channel(MAIN_CHAT_CHANNEL_ID)
        if channel:
            member = guild.get_member(user_id) if guild else None
            mention = member.mention if member else f"<@{user_id}>"

            reward_desc = []
            if bonus_on > 0:
                unit = await self._get_currency_unit()
                reward_desc.append(f"**{bonus_on}**{unit}")
            if role_granted:
                reward_desc.append(f"<@&{role_id}> 역할")

            reward_text = " + ".join(reward_desc) if reward_desc else ""

            congrats = (
                f"🎊 **별자리 마일스톤 달성!** 🎊\n"
                f"{mention}님이 {completed_count}개의 별자리를 완성했다묘!\n"
            )
            if reward_text:
                congrats += f"보상: {reward_text}"

            try:
                await channel.send(congrats)
            except Exception as e:
                await self.log(f"마일스톤 축하 메시지 전송 실패: {e}")

        await self.log(
            f"마일스톤 보상 지급: user={user_id}, "
            f"completed={completed_count}, bonus={bonus_on}, role={role_id}"
        )

    async def _get_currency_unit(self) -> str:
        unit = await balance_manager.get_currency_unit()
        return unit['emoji'] if unit else "온"

    # ===========================================
    # 일반 명령어
    # ===========================================

    @commands.group(name="별자리", invoke_without_command=True)
    @only_in_guild()
    async def constellation(self, ctx):
        """별자리 수집 도움말"""
        if not self._check_channel(ctx):
            return

        await self._ensure_sun_times()
        is_night = self._is_nighttime()
        cost = self.data.get_observe_cost()
        unit = await self._get_currency_unit()
        cooldown = self.data.get_observe_cooldown_hours()

        night_status = f"{EMOJI_CRESCENT} 현재 관측 가능" if is_night else f"{EMOJI_SUN} 현재 관측 불가 (낮)"
        sunset_str = self._sunset_time.strftime("%H:%M") if self._sunset_time else "18:00"
        sunrise_str = self._sunrise_time.strftime("%H:%M") if self._sunrise_time else "06:00"

        embed = discord.Embed(
            title=f"{EMOJI_STAR} 비몽 별자리 수집 {EMOJI_STAR}",
            description=(
                f"비몽책방의 밤하늘에서 별을 관측하고 별자리를 완성하라묘!\n\n"
                f"**{night_status}**\n"
                f"관측 시간: {EMOJI_MOON_WAXING} 일몰 {sunset_str} ~ {EMOJI_SUN} 일출 {sunrise_str}"
            ),
            color=discord.Color.from_rgb(25, 25, 80)
        )
        embed.add_field(
            name=f"{EMOJI_CRESCENT} 일반 명령어",
            value=(
                f"`*별자리 관측` — 별 관측 ({cost}{unit}, 쿨타임 {cooldown}시간)\n"
                f"`*별자리 도감` — 전체 수집 현황\n"
                f"`*별자리 도감 [별자리명]` — 특정 별자리 상세\n"
                f"`*별자리 교환 @유저 [별이름]` — 별 교환"
            ),
            inline=False
        )
        embed.add_field(
            name=f"{EMOJI_STAR} 별자리 목록",
            value="\n".join(
                f"{CONSTELLATIONS[cid]['emoji']} **{CONSTELLATIONS[cid]['name']}** — {EMOJI_STAR} {len(CONSTELLATIONS[cid]['stars'])}개"
                for cid in CONSTELLATION_ORDER
            ),
            inline=False
        )
        embed.set_footer(text=f"관리자 설정: *별자리설정")
        await ctx.reply(embed=embed)

    @constellation.command(name="관측")
    @only_in_guild()
    async def observe(self, ctx):
        """별을 관측합니다. 온이 소모되며, 밤에만 가능합니다."""
        if not self._check_channel(ctx):
            return

        await self._ensure_sun_times()
        user_id = ctx.author.id

        # 1. 밤인지 체크
        if not self._is_nighttime():
            await ctx.reply(OBSERVE_DAYTIME_MSG)
            return

        # 2. 모든 별자리 완성 체크
        collected = await self.data.get_user_stars(user_id)
        all_complete = True
        for cid in CONSTELLATION_ORDER:
            if not await self.data.is_constellation_complete(user_id, cid):
                all_complete = False
                break
        if all_complete:
            await ctx.reply(OBSERVE_ALL_COMPLETE_MSG)
            return

        # 3. 쿨타임 체크
        cooldown_hours = self.data.get_observe_cooldown_hours()
        last_observe = await self.data.get_last_observe_time(user_id)
        if last_observe:
            last_dt = datetime.strptime(last_observe, "%Y-%m-%d %H:%M:%S")
            last_dt = KST.localize(last_dt)
            next_available = last_dt + timedelta(hours=cooldown_hours)
            now = datetime.now(KST)
            if now < next_available:
                remaining = next_available - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                if hours > 0:
                    remaining_str = f"{hours}시간 {minutes}분"
                else:
                    remaining_str = f"{minutes}분"
                await ctx.reply(OBSERVE_COOLDOWN_MSG.format(remaining=remaining_str))
                return

        # 4. 잔액 체크
        cost = self.data.get_observe_cost()
        balance = await balance_manager.get_balance(str(user_id))
        if balance < cost:
            unit = await self._get_currency_unit()
            await ctx.reply(OBSERVE_NO_BALANCE_MSG.format(
                cost=f"{cost:,}", balance=f"{balance:,}"
            ))
            return

        # 5. 온 차감
        await balance_manager.take(str(user_id), cost)

        # 6. 별 선택
        result = self._pick_random_star(collected)
        if result is None:
            # 이론상 도달 불가 (위에서 체크)
            await ctx.reply("관측할 별이 없다묘...")
            return

        constellation_id, star_id, is_duplicate = result
        constellation = CONSTELLATIONS[constellation_id]
        star = next(s for s in constellation["stars"] if s["id"] == star_id)

        # 7. 쿨타임 기록
        await self.data.set_last_observe_time(user_id)

        # 8. 별 수집 처리
        is_new = False
        if not is_duplicate:
            added = await self.data.add_star(user_id, constellation_id, star_id)
            is_new = added

        # 9. 이미지 생성
        user_name = ctx.author.display_name
        image_buffer = self.image_gen.generate_observe_result(
            constellation_id, star_id, is_new, user_name
        )
        file = discord.File(fp=image_buffer, filename="observe_result.png")

        # 10. 메시지 전송
        if is_new:
            msg_text = OBSERVE_NEW_STAR_MSG.format(
                constellation_emoji=constellation["emoji"],
                constellation_name=constellation["name"],
                star_name=star["name"]
            )
        else:
            msg_text = OBSERVE_DUP_STAR_MSG.format(
                constellation_emoji=constellation["emoji"],
                constellation_name=constellation["name"],
                star_name=star["name"]
            )
        await ctx.reply(msg_text, file=file)

        # 11. 별자리 완성 체크
        if is_new and await self.data.is_constellation_complete(user_id, constellation_id):
            complete_msg = OBSERVE_COMPLETE_MSG.format(
                constellation_emoji=constellation["emoji"],
                constellation_name=constellation["name"],
                mention=ctx.author.mention
            )
            await ctx.send(complete_msg)
            await self._check_and_grant_rewards(ctx, user_id, constellation_id)

        await self.log(
            f"{ctx.author}({user_id}) 관측: {constellation['name']}/{star['name']} "
            f"({'신규' if is_new else '중복'}), 비용: {cost}"
        )

    @constellation.command(name="도감")
    @only_in_guild()
    async def collection(self, ctx, *, constellation_name: str = None):
        """별자리 도감을 확인합니다."""
        if not self._check_channel(ctx):
            return

        user_id = ctx.author.id
        collected = await self.data.get_user_stars(user_id)
        user_name = ctx.author.display_name

        # 특정 별자리
        target_cid = None
        if constellation_name:
            constellation_name = constellation_name.strip()
            for cid, cdata in CONSTELLATIONS.items():
                if cdata["name"] == constellation_name or cid == constellation_name.lower():
                    target_cid = cid
                    break
            if not target_cid:
                await ctx.reply(
                    f"'{constellation_name}'라는 별자리를 찾을 수 없다묘! "
                    f"사용 가능한 별자리: {', '.join(c['name'] for c in CONSTELLATIONS.values())}"
                )
                return

        # 이미지 생성
        loading = await ctx.reply("별자리 도감을 펼치는 중이다묘... 🔭")
        try:
            image_buffer = self.image_gen.generate_collection_card(
                user_name, collected, target_cid
            )
            file = discord.File(fp=image_buffer, filename="constellation_card.png")
            await loading.edit(content=None, attachments=[file])
        except Exception as e:
            await loading.edit(content="도감 이미지 생성 중 오류가 발생했다묘...")
            await self.log(f"도감 이미지 생성 오류: {e}")

    @constellation.command(name="교환")
    @only_in_guild()
    async def exchange(self, ctx, member: discord.Member, *, star_name: str):
        """다른 유저와 별을 교환합니다. (수수료 적용)"""
        if not self._check_channel(ctx):
            return

        if member.bot or member.id == ctx.author.id:
            await ctx.reply("자기 자신이나 봇과는 교환할 수 없다묘!")
            return

        # 별 이름으로 별 찾기
        found = None
        for cid, cdata in CONSTELLATIONS.items():
            for star in cdata["stars"]:
                if star["name"] == star_name.strip():
                    found = (cid, star["id"], star["name"])
                    break
            if found:
                break

        if not found:
            await ctx.reply(f"'{star_name}'라는 별을 찾을 수 없다묘!")
            return

        cid, sid, sname = found

        # 자신이 해당 별을 가지고 있는지 확인
        if not await self.data.has_star(ctx.author.id, cid, sid):
            await ctx.reply(f"'{sname}' 별을 가지고 있지 않다묘!")
            return

        # 수수료 확인
        fee = self.data.get_exchange_fee()
        unit = await self._get_currency_unit()
        balance = await balance_manager.get_balance(str(ctx.author.id))
        if balance < fee:
            await ctx.reply(f"교환 수수료 **{fee:,}**{unit}이 부족하다묘! (현재 잔액: {balance:,}{unit})")
            return

        # 상대방 확인 메시지
        confirm_embed = discord.Embed(
            title="🔄 별 교환 요청",
            description=(
                f"{ctx.author.mention}님이 {member.mention}님에게\n"
                f"✦ **{sname}** ({CONSTELLATIONS[cid]['emoji']} {CONSTELLATIONS[cid]['name']})\n"
                f"을 교환하고 싶어한다묘!\n\n"
                f"수수료: **{fee:,}**{unit} (요청자 부담)\n\n"
                f"{member.mention}님, 수락하시려면 ✅ 를 눌러달라묘!"
            ),
            color=discord.Color.from_rgb(25, 25, 80)
        )
        confirm_msg = await ctx.send(embed=confirm_embed)
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user.id == member.id
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == confirm_msg.id
            )

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await confirm_msg.edit(embed=discord.Embed(
                title="⏳ 교환 시간 초과", description="교환 요청이 만료되었다묘.",
                color=discord.Color.greyple()
            ))
            return

        if str(reaction.emoji) == "❌":
            await confirm_msg.edit(embed=discord.Embed(
                title="❌ 교환 거절", description=f"{member.mention}님이 교환을 거절했다묘.",
                color=discord.Color.red()
            ))
            return

        # 교환 실행
        # 수수료 차감
        await balance_manager.take(str(ctx.author.id), fee)
        # 별 이동
        await self.data.remove_star(ctx.author.id, cid, sid)
        await self.data.add_star(member.id, cid, sid)

        result_embed = discord.Embed(
            title="✅ 교환 완료!",
            description=(
                f"✦ **{sname}** 이(가)\n"
                f"{ctx.author.mention} → {member.mention}\n"
                f"에게 교환되었다묘!"
            ),
            color=discord.Color.green()
        )
        await confirm_msg.edit(embed=result_embed)

        await self.log(
            f"별 교환: {ctx.author}→{member}, {CONSTELLATIONS[cid]['name']}/{sname}, 수수료: {fee}"
        )

    # ===========================================
    # 관리자 명령어
    # ===========================================

    @commands.group(name="별자리설정", invoke_without_command=True)
    @only_in_guild()
    @is_guild_admin()
    async def settings(self, ctx):
        """현재 별자리 수집 설정을 표시합니다."""
        cost = self.data.get_observe_cost()
        cooldown = self.data.get_observe_cooldown_hours()
        fee = self.data.get_exchange_fee()
        rewards = self.data.get_completion_rewards()
        unit = await self._get_currency_unit()

        channel_ids = self.data.get_allowed_channels()
        if channel_ids:
            mentions = []
            for cid in channel_ids:
                ch = ctx.guild.get_channel(cid)
                mentions.append(ch.mention if ch else f"`{cid}`(삭제됨)")
            channel_text = ", ".join(mentions)
        else:
            channel_text = "제한 없음 (모든 채널)"

        embed = discord.Embed(
            title="⚙️ 별자리 수집 설정",
            color=discord.Color.from_rgb(25, 25, 80)
        )
        embed.add_field(name="관측 비용", value=f"{cost:,}{unit}", inline=True)
        embed.add_field(name="관측 쿨타임", value=f"{cooldown}시간", inline=True)
        embed.add_field(name="교환 수수료", value=f"{fee:,}{unit}", inline=True)
        embed.add_field(name="허용 채널", value=channel_text, inline=True)

        announce_id = self.data.get_announce_channel_id()
        announce_text = f"<#{announce_id}>" if announce_id else f"<#{MAIN_CHAT_CHANNEL_ID}> (기본)"

        if self._sunset_time and self._sunrise_time:
            embed.add_field(
                name="관측 시간",
                value=f"일몰 {self._sunset_time.strftime('%H:%M')} ~ 일출 {self._sunrise_time.strftime('%H:%M')}",
                inline=True
            )

        embed.add_field(name="알림 채널", value=announce_text, inline=True)

        if rewards:
            reward_lines = []
            for count_str in sorted(rewards.keys(), key=int):
                r = rewards[count_str]
                parts = [f"**{count_str}개 완성:**"]
                if r.get("role_id"):
                    parts.append(f"<@&{r['role_id']}>")
                if r.get("bonus_on", 0) > 0:
                    parts.append(f"{r['bonus_on']:,}{unit}")
                reward_lines.append(" ".join(parts))
            embed.add_field(
                name="완성 보상",
                value="\n".join(reward_lines),
                inline=False
            )
        else:
            embed.add_field(name="완성 보상", value="설정 없음", inline=False)

        embed.add_field(
            name="관리 명령어",
            value=(
                "`*별자리설정 관측비용 [금액]`\n"
                "`*별자리설정 쿨타임 [시간]`\n"
                "`*별자리설정 교환수수료 [금액]`\n"
                "`*별자리설정 알림채널 [#채널]`\n"
                "`*별자리설정 채널추가 [#채널]`\n"
                "`*별자리설정 채널제거 [#채널]`\n"
                "`*별자리설정 채널목록`\n"
                "`*별자리설정 보상추가 [완성수] @역할 [온]`\n"
                "`*별자리설정 보상제거 [완성수]`\n"
                "`*별자리설정 보상목록`\n"
                "`*별자리설정 초기화`"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)

    @settings.command(name="관측비용")
    @is_guild_admin()
    async def set_cost(self, ctx, amount: int):
        """관측 비용을 설정합니다."""
        if amount < 0:
            await ctx.reply("금액은 0 이상이어야 합니다.")
            return
        self.data.set_observe_cost(amount)
        unit = await self._get_currency_unit()
        await ctx.reply(f"✅ 관측 비용이 **{amount:,}**{unit}으로 설정되었다묘!")
        await self.log(f"{ctx.author}({ctx.author.id})가 관측 비용을 {amount}으로 변경")

    @settings.command(name="쿨타임")
    @is_guild_admin()
    async def set_cooldown(self, ctx, hours: int):
        """관측 쿨타임을 설정합니다. (시간 단위)"""
        if hours < 0:
            await ctx.reply("쿨타임은 0 이상이어야 합니다.")
            return
        self.data.set_observe_cooldown_hours(hours)
        await ctx.reply(f"✅ 관측 쿨타임이 **{hours}시간**으로 설정되었다묘!")
        await self.log(f"{ctx.author}({ctx.author.id})가 관측 쿨타임을 {hours}시간으로 변경")

    @settings.command(name="교환수수료")
    @is_guild_admin()
    async def set_exchange_fee(self, ctx, fee: int):
        """교환 수수료를 설정합니다."""
        if fee < 0:
            await ctx.reply("수수료는 0 이상이어야 합니다.")
            return
        self.data.set_exchange_fee(fee)
        unit = await self._get_currency_unit()
        await ctx.reply(f"✅ 교환 수수료가 **{fee:,}**{unit}으로 설정되었다묘!")
        await self.log(f"{ctx.author}({ctx.author.id})가 교환 수수료를 {fee}으로 변경")

    @settings.command(name="알림채널")
    @is_guild_admin()
    async def set_announce_channel(self, ctx, channel: discord.TextChannel = None):
        """일몰/일출 알림이 전송될 채널을 설정합니다. 채널 미지정 시 기본값 사용."""
        if channel:
            self.data.set_announce_channel_id(channel.id)
            await ctx.reply(f"✅ 일몰/일출 알림 채널이 {channel.mention}으로 설정되었다묘!")
        else:
            self.data.set_announce_channel_id(None)
            await ctx.reply(f"✅ 알림 채널이 기본값(<#{MAIN_CHAT_CHANNEL_ID}>)으로 초기화되었다묘!")
        await self.log(f"{ctx.author}({ctx.author.id})가 알림 채널을 {channel}으로 변경")

    @settings.command(name="채널추가")
    @is_guild_admin()
    async def add_channel(self, ctx, channel: discord.TextChannel):
        """별자리 명령어 허용 채널을 추가합니다."""
        if self.data.add_allowed_channel(channel.id):
            await ctx.reply(f"✅ 별자리 허용 채널에 {channel.mention} 추가됨!")
        else:
            await ctx.reply(f"ℹ️ 이미 허용 목록에 있는 채널이다묘: {channel.mention}")
        await self.log(f"{ctx.author}({ctx.author.id})가 허용 채널 추가: {channel}")

    @settings.command(name="채널제거")
    @is_guild_admin()
    async def remove_channel(self, ctx, channel: discord.TextChannel):
        """별자리 명령어 허용 채널을 제거합니다."""
        if self.data.remove_allowed_channel(channel.id):
            await ctx.reply(f"✅ 별자리 허용 채널에서 {channel.mention} 제거됨!")
        else:
            await ctx.reply(f"ℹ️ 허용 목록에 없는 채널이다묘: {channel.mention}")
        await self.log(f"{ctx.author}({ctx.author.id})가 허용 채널 제거: {channel}")

    @settings.command(name="채널목록")
    @is_guild_admin()
    async def list_channels(self, ctx):
        """별자리 명령어 허용 채널 목록을 표시합니다."""
        channel_ids = self.data.get_allowed_channels()
        if not channel_ids:
            await ctx.reply("🔓 현재 별자리 명령어는 **모든 채널 허용** 상태다묘!")
            return
        mentions = []
        for cid in channel_ids:
            ch = ctx.guild.get_channel(cid)
            mentions.append(ch.mention if ch else f"`{cid}`(삭제됨)")
        await ctx.reply("✅ 허용 채널 목록: " + ", ".join(mentions))

    @settings.command(name="보상추가")
    @is_guild_admin()
    async def add_reward(self, ctx, required_count: int, role: discord.Role, bonus_on: int = 0):
        """별자리 완성 보상을 추가합니다."""
        if required_count < 1 or required_count > len(CONSTELLATION_ORDER):
            await ctx.reply(f"완성 수는 1~{len(CONSTELLATION_ORDER)} 사이여야 합니다.")
            return
        if bonus_on < 0:
            await ctx.reply("보상 온은 0 이상이어야 합니다.")
            return

        self.data.set_completion_reward(required_count, role.id, bonus_on)
        unit = await self._get_currency_unit()
        await ctx.reply(
            f"✅ 별자리 **{required_count}개** 완성 보상 설정:\n"
            f"역할: {role.mention}, 보상: **{bonus_on:,}**{unit}"
        )
        await self.log(
            f"{ctx.author}({ctx.author.id})가 보상 추가: "
            f"{required_count}개 완성 → {role.name}, {bonus_on}온"
        )

    @settings.command(name="보상제거")
    @is_guild_admin()
    async def remove_reward(self, ctx, required_count: int):
        """별자리 완성 보상을 제거합니다."""
        if self.data.remove_completion_reward(required_count):
            await ctx.reply(f"✅ 별자리 **{required_count}개** 완성 보상이 제거되었다묘!")
        else:
            await ctx.reply(f"해당 완성 수({required_count})에 설정된 보상이 없다묘.")
        await self.log(f"{ctx.author}({ctx.author.id})가 보상 제거: {required_count}개 완성")

    @settings.command(name="보상목록")
    @is_guild_admin()
    async def list_rewards(self, ctx):
        """설정된 완성 보상 목록을 표시합니다."""
        rewards = self.data.get_completion_rewards()
        unit = await self._get_currency_unit()

        if not rewards:
            await ctx.reply("설정된 보상이 없다묘. `*별자리설정 보상추가 [완성수] @역할 [온]`으로 추가해달라묘!")
            return

        embed = discord.Embed(
            title="🏆 별자리 완성 보상 목록",
            color=discord.Color.from_rgb(25, 25, 80)
        )
        for count_str in sorted(rewards.keys(), key=int):
            r = rewards[count_str]
            parts = []
            if r.get("role_id"):
                parts.append(f"역할: <@&{r['role_id']}>")
            if r.get("bonus_on", 0) > 0:
                parts.append(f"보상: {r['bonus_on']:,}{unit}")
            embed.add_field(
                name=f"별자리 {count_str}개 완성",
                value="\n".join(parts) if parts else "보상 없음",
                inline=False
            )
        await ctx.reply(embed=embed)

    @settings.command(name="초기화")
    @is_guild_admin()
    async def reset_data(self, ctx):
        """모든 유저의 별자리 수집 데이터를 초기화합니다."""
        await ctx.send(
            "⚠️ **경고:** 모든 유저의 별자리 수집 데이터가 삭제됩니다.\n"
            "정말로 초기화하시겠습니까? `확인`이라고 입력해주세요. (15초 이내)"
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "확인"

        try:
            await self.bot.wait_for('message', check=check, timeout=15.0)
        except asyncio.TimeoutError:
            await ctx.send("⏳ 시간 초과로 초기화가 취소되었다묘!")
            return

        await self.data.reset_all_data()
        await ctx.send("✅ 모든 유저의 별자리 수집 데이터가 초기화되었다묘!")
        await self.log(f"🚨 {ctx.author}({ctx.author.id})가 모든 별자리 데이터를 초기화했습니다.")


async def setup(bot):
    await bot.add_cog(ConstellationCog(bot))
