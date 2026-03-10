# src/constellation/ConstellationConstants.py
# ============================================================
# 비몽 별자리 수집 이벤트에서 사용하는 상수를 정의합니다.
# 봄철 별자리 5개 (3월 중순~5월 관측 가능)
# ============================================================

from src.level.LevelConstants import MAIN_CHAT_CHANNEL_ID

# ===========================================
# 서울 좌표 (일몰/일출 API용)
# ===========================================
SEOUL_LAT = 37.5665
SEOUL_LNG = 126.9780

# ===========================================
# 기본 설정값
# ===========================================
DEFAULT_OBSERVE_COST = 1000          # 관측 1회 비용 (온)
DEFAULT_OBSERVE_COOLDOWN_HOURS = 1   # 관측 쿨타임 (시간)
DEFAULT_EXCHANGE_FEE = 200           # 별 교환 수수료 (온)
FALLBACK_SUNSET_HOUR = 18           # API 실패 시 폴백 일몰 시각
FALLBACK_SUNRISE_HOUR = 6           # API 실패 시 폴백 일출 시각

# ===========================================
# 서버 커스텀 이모지
# ===========================================
EMOJI_SUN = "<:BM_k_001:1477540744624345198>"
EMOJI_CRESCENT = "<:BM_k_002:1477540746096545843>"
EMOJI_CLOUDY_MOON = "<:BM_k_003:1477540747187326997>"
EMOJI_STAR = "<:BM_k_004:1477540748323979355>"
EMOJI_CLOUD = "<:BM_k_005:1477540750181924928>"
EMOJI_GLITTER1 = "<a:BM_gliter_001:1377696658933940244>"
EMOJI_GLITTER2 = "<a:BM_gliter_003:1377696710855360542>"
EMOJI_GLITTER3 = "<a:BM_gliter_005:1377697008344891572>"
EMOJI_GLITTER4 = "<a:BM_gliter_009:1377708780799918100>"
EMOJI_MOON_OUTLINE = "<a:BM_moon_001:1378716907624202421>"
EMOJI_MOON_WAXING = "<a:BM_moon_002L:1378716746839494736>"
EMOJI_MOON_WANING = "<a:BM_moon_002R:1378716735561011290>"

# ===========================================
# 별자리 데이터
# ===========================================
# 각 별의 x, y 좌표는 0.0~1.0 비율로 정의합니다.
# 이미지 생성 시 캔버스 크기에 맞게 스케일링됩니다.
# lines: 별 인덱스 쌍 (stars 리스트의 인덱스)

CONSTELLATIONS = {
    "leo": {
        "name": "사자자리",
        "emoji": "🦁",
        "description": "봄밤 하늘에서 가장 당당하게 빛나는 별자리. 레굴루스는 사자의 심장이라 불린다.",
        "stars": [
            {"id": "regulus",    "name": "레굴루스",    "x": 0.25, "y": 0.65},
            {"id": "denebola",   "name": "데네볼라",    "x": 0.80, "y": 0.45},
            {"id": "algieba",    "name": "알기에바",    "x": 0.30, "y": 0.40},
            {"id": "zosma",      "name": "조스마",      "x": 0.65, "y": 0.40},
            {"id": "chertan",    "name": "체르탄",      "x": 0.55, "y": 0.55},
            {"id": "eta_leo",    "name": "에타 레오니스", "x": 0.20, "y": 0.30},
        ],
        "lines": [
            (0, 2), (2, 5), (2, 3), (3, 1), (3, 4), (4, 0)
        ],
    },
    "crater": {
        "name": "컵자리",
        "emoji": "🍶",
        "description": "사자자리 아래 놓인 작고 아담한 별자리. 디오니소스의 술잔이라 전해진다.",
        "stars": [
            {"id": "alkes",      "name": "알케스",      "x": 0.30, "y": 0.70},
            {"id": "delta_crt",  "name": "델타 크라테리스", "x": 0.55, "y": 0.35},
            {"id": "gamma_crt",  "name": "감마 크라테리스", "x": 0.40, "y": 0.30},
            {"id": "epsilon_crt","name": "엡실론 크라테리스","x": 0.65, "y": 0.55},
        ],
        "lines": [
            (0, 2), (2, 1), (1, 3), (3, 0)
        ],
    },
    "corvus": {
        "name": "까마귀자리",
        "emoji": "🐦",
        "description": "밤하늘에 날아오른 사다리꼴 형태의 별자리. 아폴론이 보낸 까마귀의 모습이다.",
        "stars": [
            {"id": "gienah",     "name": "기에나",      "x": 0.30, "y": 0.35},
            {"id": "kraz",       "name": "크라즈",      "x": 0.35, "y": 0.70},
            {"id": "algorab",    "name": "알고라브",    "x": 0.70, "y": 0.30},
            {"id": "minkar",     "name": "민카르",      "x": 0.65, "y": 0.65},
        ],
        "lines": [
            (0, 1), (1, 3), (3, 2), (2, 0)
        ],
    },
    "vela": {
        "name": "돛자리",
        "emoji": "⛵",
        "description": "아르고호의 돛을 수놓은 별자리. 남쪽 하늘에서 볼 수 있으면 행운이라 한다.",
        "stars": [
            {"id": "suhail",       "name": "수하일",      "x": 0.20, "y": 0.70},
            {"id": "markeb",       "name": "마르케브",    "x": 0.45, "y": 0.25},
            {"id": "koo_she",      "name": "쿠 셰",       "x": 0.75, "y": 0.40},
            {"id": "delta_vel",    "name": "델타 벨로룸", "x": 0.60, "y": 0.65},
            {"id": "mu_vel",       "name": "뮤 벨로룸",   "x": 0.35, "y": 0.50},
        ],
        "lines": [
            (0, 4), (4, 1), (1, 2), (2, 3), (3, 0)
        ],
    },
    "bootes": {
        "name": "목동자리",
        "emoji": "🧭",
        "description": "봄의 대삼각형의 한 꼭짓점인 아르크투루스를 품은 별자리. 가장 많은 별을 모아야 완성된다.",
        "stars": [
            {"id": "arcturus",    "name": "아르크투루스", "x": 0.50, "y": 0.75},
            {"id": "izar",        "name": "이자르",      "x": 0.55, "y": 0.50},
            {"id": "muphrid",     "name": "무프리드",    "x": 0.40, "y": 0.65},
            {"id": "seginus",     "name": "세기누스",    "x": 0.45, "y": 0.25},
            {"id": "nekkar",      "name": "네카르",      "x": 0.35, "y": 0.20},
            {"id": "rho_boo",     "name": "로 보오티스", "x": 0.65, "y": 0.35},
            {"id": "eta_boo",     "name": "에타 보오티스","x": 0.30, "y": 0.45},
        ],
        "lines": [
            (0, 2), (2, 6), (6, 4), (4, 3), (3, 1), (1, 5), (1, 0), (0, 2)
        ],
    },
}

# ===========================================
# 별자리 순서 (표시용)
# ===========================================
CONSTELLATION_ORDER = ["leo", "crater", "corvus", "vela", "bootes"]

# ===========================================
# 관측 결과 메시지 템플릿
# ===========================================
OBSERVE_NEW_STAR_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_GLITTER1} 밤하늘에서 새로운 별을 찾았다묘! ᝰꪑ\n"
    "( つ🔭O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {{constellation_emoji}} **{{constellation_name}}**의 {EMOJI_STAR} **{{star_name}}** 을 발견했다묘!"
)

OBSERVE_DUP_STAR_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_CLOUDY_MOON} 앗... 이 별은 이미 찾았던 별이다묘... ᝰꪑ\n"
    "( つ🔭O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {{constellation_emoji}} **{{constellation_name}}**의 {EMOJI_STAR} **{{star_name}}** — 이미 수집했다묘!"
)

OBSERVE_COMPLETE_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_GLITTER2} 대단하다묘!! {{constellation_emoji}} **{{constellation_name}}**를 완성했다묘!! ᝰꪑ\n"
    "( つ🎉O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {EMOJI_GLITTER3} 비몽책방의 밤하늘에 {{mention}}의 별자리가 빛나기 시작한다묘! {EMOJI_GLITTER4}"
)

OBSERVE_DAYTIME_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_SUN} 아직 해가 떠 있어서 별이 안 보인다묘... ᝰꪑ\n"
    "( つ🔭O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {EMOJI_SUN} 해가 지면 다시 찾아와달라묘!"
)

SUNSET_ANNOUNCE_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_MOON_WAXING} 해가 졌다묘! 비몽책방의 밤하늘에 별이 보이기 시작한다묘! ᝰꪑ\n"
    "( つ🔭O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {EMOJI_STAR} `*별자리 관측`으로 오늘 밤의 별을 찾아보라묘! {EMOJI_GLITTER1}"
)

OBSERVE_COOLDOWN_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_CLOUD} 아직 망원경이 식지 않았다묘... ᝰꪑ\n"
    "( つ🔭O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    "-# ◟. {remaining} 후에 다시 관측할 수 있다묘!"
)

OBSERVE_NO_BALANCE_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_CLOUD} 온이 부족해서 망원경을 빌릴 수 없다묘... ᝰꪑ\n"
    "( つ💸O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    "-# ◟. 관측하려면 **{cost}온**이 필요하다묘! (현재 잔액: **{balance}온**)"
)

OBSERVE_ALL_COMPLETE_MSG = (
    ". ᘏ▸◂ᘏ        ╭◜◝     ◜◝     ◜◝     ◜◝     ◜◝╮\n"
    f"꒰   ɞ̴̶̷ ·̮ ɞ̴̶̷ ꒱   .oO {EMOJI_GLITTER3} 대단하다묘!! 모든 별자리를 완성한 비몽의 천문관이다묘!! ᝰꪑ\n"
    f"( つ{EMOJI_MOON_OUTLINE}O        ╰◟◞     ◟◞     ◟◞     ◟◞     ◟◞╯\n\n"
    f"-# ◟. {EMOJI_GLITTER1} 더 이상 관측할 별이 없다묘! 축하한다묘! {EMOJI_GLITTER4}"
)
