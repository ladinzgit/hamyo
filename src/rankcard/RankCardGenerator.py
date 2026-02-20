"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

비몽책방 테마(몽환 + 책방)
- 잉크(딥 네이비) 바탕 + 종이(웜 베이지) 조명 느낌의 은은한 글로우
- 책갈피(리본) 포인트 + 오픈북 워터마크 + 별가루(미세 스파클)
- 과하지 않은 그라디언트/비네팅/그레인으로 “봇 느낌” 최소화

레이아웃(기존 유지)
  - 캔버스: 860x280px, 라운드 코너
  - 왼쪽: 원형 아바타 + 역할 배지
  - 오른쪽: 이름, 다공, 다음 경지 진행바
  - 하단: 글래스모피즘(블러) 채팅/음성 레벨 박스

※ 명칭/칭호 텍스트(예: 다공, 다음 경지, 채팅 레벨/음성 레벨 등)는 그대로 유지합니다.
"""

import io
import os
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 캔버스 설정 ──
CANVAS_WIDTH = 860
CANVAS_HEIGHT = 280
CORNER_RADIUS = 24

# ── 비몽책방 테마(기본 팔레트) ──
INK_BG = (12, 13, 18)               # 더 잉크 같은 배경
INK_BG_2 = (18, 18, 26)             # 미세한 톤 차
PAPER_GLOW = (235, 224, 200)        # 종이 느낌의 따뜻한 빛
STAR_TINT = (210, 220, 255)         # 차가운 별빛

# ── 색상 정의 ──
TEXT_WHITE = (255, 255, 255)
TEXT_LIGHT = (224, 224, 230)
TEXT_GRAY = (180, 180, 190)
TEXT_DIM = (125, 125, 140)

# 메인 프로그레스 바 배경
MAIN_BAR_BG = (28, 28, 38)          # 더 고급스럽게 조금 어두운 트랙

# 글래스모피즘 색상(조금 더 또렷하게)
GLASS_FILL = (255, 255, 255, 18)
GLASS_STROKE = (255, 255, 255, 40)
GLASS_BAR_BG = (0, 0, 0, 90)
GLASS_BLUR_RADIUS = 10

# 외곽선(카드 테두리)
CARD_BORDER = (255, 255, 255, 22)

# 워터마크(브랜드)
BRAND_WATERMARK_TEXT = "비몽책방"
WATERMARK_ALPHA = 14

# ── 역할별 테마 색상(기존 유지) ──
ROLE_COLORS = {
    'hub':      (74, 222, 128),
    'dado':     (163, 230, 53),
    'daho':     (244, 114, 182),
    'dakyung':  (251, 191, 36),
    'dahyang':  (129, 140, 248),
}

# ── 역할별 아이콘 경로 ──
ICON_DIR = "assets/icons"
ROLE_ICON_FILES = {
    'hub':      'hub.png',
    'dado':     'dado.png',
    'daho':     'daho.png',
    'dakyung':  'dakyung.png',
    'dahyang':  'dahyang.png',
}

# ── 폰트 경로 ──
FONT_BOLD_PATH = "assets/fonts/Pretendard-Bold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/Pretendard-Medium.ttf"


# ────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = _clamp(t, 0.0, 1.0)
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


def _brighten(c: Tuple[int, int, int], amount: float = 0.18) -> Tuple[int, int, int]:
    """amount: 0~1, 흰색으로 섞어 밝게"""
    return _mix(c, (255, 255, 255), _clamp(amount, 0, 1))


def _darken(c: Tuple[int, int, int], amount: float = 0.18) -> Tuple[int, int, int]:
    """amount: 0~1, 검정으로 섞어 어둡게"""
    return _mix(c, (0, 0, 0), _clamp(amount, 0, 1))


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """폰트 파일을 로드합니다. 실패 시 기본 폰트를 반환합니다."""
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}): {e} — 기본 폰트를 사용합니다.")
        return ImageFont.load_default()


def _load_role_icon(role: str, size: int = 18) -> Optional[Image.Image]:
    """역할 아이콘 PNG를 로드하고 지정 크기로 리사이즈합니다."""
    filename = ROLE_ICON_FILES.get(role)
    if not filename:
        return None
    path = os.path.join(ICON_DIR, filename)
    try:
        icon = Image.open(path).convert('RGBA')
        icon = icon.resize((size, size), Image.LANCZOS)
        return icon
    except (IOError, OSError) as e:
        logger.warning(f"아이콘 로드 실패 ({path}): {e}")
        return None


def _make_rounded_rect_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    """라운드 코너 마스크를 생성합니다."""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius, fill=255)
    return mask


def _make_circle_mask(diameter: int) -> Image.Image:
    """원형 마스크를 생성합니다."""
    mask = Image.new('L', (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (diameter - 1, diameter - 1)], fill=255)
    return mask


# ────────────────────────────────────────────────
# 메인 생성기
# ────────────────────────────────────────────────

class RankCardGenerator:
    """랭크 카드 이미지 생성기 (비몽책방 테마)"""

    def __init__(self):
        # 폰트 로드 (가독성/균형 조정)
        self.font_name = _load_font(FONT_BOLD_PATH, 32)
        self.font_exp = _load_font(FONT_MEDIUM_PATH, 15)
        self.font_level = _load_font(FONT_BOLD_PATH, 18)
        self.font_progress = _load_font(FONT_MEDIUM_PATH, 13)
        self.font_badge = _load_font(FONT_BOLD_PATH, 13)
        self.font_sub_label = _load_font(FONT_MEDIUM_PATH, 12)
        self.font_rank = _load_font(FONT_BOLD_PATH, 11)
        self.font_watermark = _load_font(FONT_MEDIUM_PATH, 13)

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        """랭크 카드 이미지를 생성하여 BytesIO로 반환합니다."""

        role_color = ROLE_COLORS.get(data.current_role, ROLE_COLORS['hub'])

        # ── 캔버스 생성 ──
        canvas = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), INK_BG + (255,))

        # ── 배경(잉크+종이 글로우+비네팅+별가루+북 워터마크+책갈피) ──
        self._draw_ink_paper_background(canvas, role_color, seed_key=data.user_name)
        self._draw_book_watermark(canvas, role_color)
        self._draw_bookmark_ribbon(canvas, role_color)
        self._draw_brand_watermark(canvas)
        self._draw_soft_border(canvas)

        # ── 아바타 (원형) ──
        avatar_x, avatar_y = 30, 30
        avatar_size = 140
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, avatar_size, role_color)

        # ── 역할 배지 (아이콘 + 텍스트, 아바타 하단) ──
        badge_cx = avatar_x + avatar_size // 2
        badge_y = avatar_y + avatar_size + 12
        self._draw_badge(canvas, badge_cx, badge_y, data.role_display, data.current_role, role_color)

        # ── 정보 영역 (오른쪽) ──
        info_x = avatar_x + avatar_size + 44
        info_y = 30

        draw = ImageDraw.Draw(canvas)

        # 이름
        draw.text((info_x, info_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)
        info_y += 38

        # 총 다공
        exp_text = f"{data.total_exp:,} 다공"
        draw.text((info_x, info_y), exp_text, fill=TEXT_GRAY, font=self.font_exp)
        info_y += 28

        # 메인 진행 바(다음 경지)
        bar_width = CANVAS_WIDTH - info_x - 40
        if data.next_role_display:
            progress_label = f"다음 경지 : {data.next_role_display}"
        else:
            progress_label = "최고 경지 달성"

        pct_text = f"{data.role_progress_pct:.1f}%"

        draw.text((info_x, info_y), progress_label, fill=TEXT_DIM, font=self.font_progress)
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text((info_x + bar_width - pct_w, info_y), pct_text, fill=_brighten(role_color, 0.18), font=self.font_progress)
        info_y += 20

        self._draw_main_progress_bar(canvas, info_x, info_y, bar_width, 14, data.role_progress_pct, role_color)

        # ── 하단 글래스모피즘 서브 스탯 박스 ──
        sub_y = 190
        sub_box_width = (CANVAS_WIDTH - info_x - 40 - 16) // 2

        # 채팅 레벨 박스
        self._draw_glass_stat_box(
            canvas,
            x=info_x,
            y=sub_y,
            width=sub_box_width,
            label="채팅 레벨",
            level=data.chat_level_info.level,
            progress=data.chat_level_info.progress_pct,
            current_xp=data.chat_level_info.current_xp,
            required_xp=data.chat_level_info.required_xp,
            color=role_color,
            rank=data.chat_rank,
            total_users=data.chat_total_users,
        )

        # 음성 레벨 박스
        self._draw_glass_stat_box(
            canvas,
            x=info_x + sub_box_width + 16,
            y=sub_y,
            width=sub_box_width,
            label="음성 레벨",
            level=data.voice_level_info.level,
            progress=data.voice_level_info.progress_pct,
            current_xp=data.voice_level_info.current_xp,
            required_xp=data.voice_level_info.required_xp,
            color=role_color,
            rank=data.voice_rank,
            total_users=data.voice_total_users,
        )

        # ── 라운드 코너 적용 ──
        output = self._apply_rounded_corners(canvas)

        # ── PNG로 저장 ──
        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 배경 (비몽책방)
    # ────────────────────────────────────────────────

    def _draw_ink_paper_background(self, canvas: Image.Image, role_color: Tuple[int, int, int], seed_key: str = ""):
        """잉크 바탕 위에 종이 글로우/비네팅/그레인/별가루를 얹습니다."""

        # 1) 잉크 톤 미세 그라디언트
        base = Image.new('RGBA', canvas.size, INK_BG + (255,))
        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for y in range(CANVAS_HEIGHT):
            t = y / max(1, CANVAS_HEIGHT - 1)
            col = _mix(INK_BG, INK_BG_2, t)
            d.line([(0, y), (CANVAS_WIDTH, y)], fill=col + (255,))
        canvas.paste(Image.alpha_composite(base, ov))

        # 2) 종이 글로우(책상 스탠드 같은 따뜻한 빛) — 좌하단
        glow = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        # 큰 원 2개를 겹쳐서 자연스럽게
        gd.ellipse([(-220, 80), (280, 520)], fill=PAPER_GLOW + (42,))
        gd.ellipse([(-120, 120), (380, 580)], fill=PAPER_GLOW + (22,))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=28))
        canvas.paste(Image.alpha_composite(canvas, glow))

        # 3) 역할 색감(너무 세지 않게) — 좌→우로 사라지는 오버레이
        role_ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(role_ov)
        for x in range(CANVAS_WIDTH):
            a = int(24 * (1 - x / CANVAS_WIDTH))
            rd.line([(x, 0), (x, CANVAS_HEIGHT)], fill=role_color + (a,))
        role_ov = role_ov.filter(ImageFilter.GaussianBlur(radius=2))
        canvas.paste(Image.alpha_composite(canvas, role_ov))

        # 4) 비네팅(가장자리 어둡게)
        vignette = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        vd = ImageDraw.Draw(vignette)
        # 큰 타원으로 중앙만 살짝 밝게 남기고 가장자리를 어둡게
        vd.ellipse([(-140, -90), (CANVAS_WIDTH + 140, CANVAS_HEIGHT + 140)], fill=(0, 0, 0, 0))
        # 바깥 영역을 어둡게 하기 위해 여러 겹
        for i in range(6):
            a = 26 + i * 10
            inset = 8 + i * 6
            vd.rounded_rectangle(
                [(inset, inset), (CANVAS_WIDTH - inset, CANVAS_HEIGHT - inset)],
                radius=CORNER_RADIUS,
                outline=(0, 0, 0, a),
                width=12,
            )
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=10))
        canvas.paste(Image.alpha_composite(canvas, vignette))

        # 5) 별가루(미세 스파클) — 오른쪽 위쪽 위주
        self._draw_star_dust(canvas, seed_key=seed_key)

        # 6) 그레인(질감) — 아주 은은하게
        self._draw_grain(canvas)

    def _draw_star_dust(self, canvas: Image.Image, seed_key: str = ""):
        import random

        seed = 0
        for ch in (seed_key or ""):
            seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF

        rng = random.Random(seed)

        dust = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(dust)

        # 점(작은 별)
        for _ in range(70):
            x = rng.randint(int(CANVAS_WIDTH * 0.45), CANVAS_WIDTH - 12)
            y = rng.randint(10, int(CANVAS_HEIGHT * 0.55))
            r = rng.choice([1, 1, 1, 2])
            a = rng.randint(18, 42)
            col = _mix(STAR_TINT, (255, 255, 255), rng.random() * 0.35)
            d.ellipse([(x - r, y - r), (x + r, y + r)], fill=col + (a,))

        # 몇 개는 “반짝” (십자)
        for _ in range(10):
            x = rng.randint(int(CANVAS_WIDTH * 0.55), CANVAS_WIDTH - 16)
            y = rng.randint(18, int(CANVAS_HEIGHT * 0.50))
            a = rng.randint(18, 32)
            col = STAR_TINT
            d.line([(x - 3, y), (x + 3, y)], fill=col + (a,))
            d.line([(x, y - 3), (x, y + 3)], fill=col + (a,))

        dust = dust.filter(ImageFilter.GaussianBlur(radius=0.6))
        canvas.paste(Image.alpha_composite(canvas, dust))

    def _draw_grain(self, canvas: Image.Image):
        """픽셀 단위 노이즈 대신, 가벼운 텍스처 레이어(성능/품질 균형)."""
        # 매우 옅은 수평/수직 패턴 + 블러로 ‘종이결’ 느낌만
        tex = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(tex)

        # 얇은 라인 몇 줄
        for y in range(0, CANVAS_HEIGHT, 14):
            d.line([(0, y), (CANVAS_WIDTH, y)], fill=(255, 255, 255, 6))
        for x in range(0, CANVAS_WIDTH, 42):
            d.line([(x, 0), (x, CANVAS_HEIGHT)], fill=(255, 255, 255, 4))

        tex = tex.filter(ImageFilter.GaussianBlur(radius=1.2))
        canvas.paste(Image.alpha_composite(canvas, tex))

    def _draw_book_watermark(self, canvas: Image.Image, role_color: Tuple[int, int, int]):
        """오른쪽에 오픈북 형태 워터마크(과하지 않게)."""
        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # 위치/크기
        cx, cy = 700, 86
        w, h = 250, 160
        a = 22
        ink = _mix(role_color, (255, 255, 255), 0.65)

        # 왼쪽 페이지
        d.rounded_rectangle(
            [(cx - w//2, cy - h//2), (cx - 8, cy + h//2)],
            radius=18,
            outline=ink + (a,),
            width=2,
        )
        # 오른쪽 페이지
        d.rounded_rectangle(
            [(cx + 8, cy - h//2), (cx + w//2, cy + h//2)],
            radius=18,
            outline=ink + (a,),
            width=2,
        )
        # 가운데 책등
        d.line([(cx, cy - h//2 + 10), (cx, cy + h//2 - 10)], fill=ink + (a,), width=2)

        # 페이지 라인(몇 줄)
        line_a = 10
        for i in range(5):
            y = cy - 30 + i * 16
            d.line([(cx - w//2 + 18, y), (cx - 18, y)], fill=ink + (line_a,))
            d.line([(cx + 18, y), (cx + w//2 - 18, y)], fill=ink + (line_a,))

        ov = ov.filter(ImageFilter.GaussianBlur(radius=1.4))
        canvas.paste(Image.alpha_composite(canvas, ov))

    def _draw_bookmark_ribbon(self, canvas: Image.Image, role_color: Tuple[int, int, int]):
        """오른쪽 가장자리에 책갈피 리본 포인트."""
        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        ribbon_w = 18
        x0 = CANVAS_WIDTH - ribbon_w - 18
        y0 = 22
        y1 = CANVAS_HEIGHT - 22

        fill = _darken(role_color, 0.10) + (28,)
        stroke = _brighten(role_color, 0.15) + (40,)

        d.rounded_rectangle([(x0, y0), (x0 + ribbon_w, y1)], radius=8, fill=fill, outline=stroke, width=1)

        # 아래쪽 V-notch
        notch_h = 16
        mid = x0 + ribbon_w // 2
        d.polygon([(x0, y1 - notch_h), (x0 + ribbon_w, y1 - notch_h), (mid, y1 - 2)], fill=_darken(role_color, 0.18) + (34,))

        ov = ov.filter(ImageFilter.GaussianBlur(radius=0.6))
        canvas.paste(Image.alpha_composite(canvas, ov))

    def _draw_brand_watermark(self, canvas: Image.Image):
        if not BRAND_WATERMARK_TEXT:
            return

        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        text = BRAND_WATERMARK_TEXT
        bbox = d.textbbox((0, 0), text, font=self.font_watermark)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        x = CANVAS_WIDTH - tw - 34
        y = CANVAS_HEIGHT - th - 26

        d.text((x + 1, y + 1), text, fill=(0, 0, 0, WATERMARK_ALPHA), font=self.font_watermark)
        d.text((x, y), text, fill=(255, 255, 255, WATERMARK_ALPHA), font=self.font_watermark)

        canvas.paste(Image.alpha_composite(canvas, ov))

    def _draw_soft_border(self, canvas: Image.Image):
        """카드 외곽 얇은 테두리로 완성도 강화."""
        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        d.rounded_rectangle(
            [(1, 1), (CANVAS_WIDTH - 2, CANVAS_HEIGHT - 2)],
            radius=CORNER_RADIUS,
            outline=CARD_BORDER,
            width=1,
        )
        canvas.paste(Image.alpha_composite(canvas, ov))

    # ────────────────────────────────────────────────
    # 아바타 & 배지
    # ────────────────────────────────────────────────

    def _draw_avatar(self, canvas: Image.Image, avatar_bytes: bytes, x: int, y: int, size: int, role_color: Tuple[int, int, int]):
        """원형으로 크롭한 아바타 + 소프트 섀도 + 링."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)

            mask = _make_circle_mask(size)

            # 소프트 섀도
            shadow = Image.new('RGBA', (size + 18, size + 18), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.ellipse([(6, 8), (size + 12, size + 14)], fill=(0, 0, 0, 90))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
            canvas.paste(Image.alpha_composite(canvas, shadow), (x - 9, y - 9))

            # 링(바깥 테두리)
            border_size = size + 8
            ring = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
            rd = ImageDraw.Draw(ring)

            # 바깥 링(화이트)
            rd.ellipse([(0, 0), (border_size - 1, border_size - 1)], outline=(255, 255, 255, 40), width=2)
            # 안쪽 링(역할 컬러)
            rd.ellipse([(3, 3), (border_size - 4, border_size - 4)], outline=_brighten(role_color, 0.10) + (42,), width=2)

            canvas.paste(Image.alpha_composite(canvas, ring), (x - 4, y - 4))

            canvas.paste(avatar_img, (x, y), mask)
        except Exception as e:
            logger.error(f"아바타 그리기 실패: {e}")
            draw = ImageDraw.Draw(canvas)
            draw.ellipse([(x, y), (x + size, y + size)], fill=(60, 60, 70))

    def _draw_badge(self, canvas: Image.Image, cx: int, cy: int, role_name: str, role_key: str, color: Tuple[int, int, int]):
        """아바타 아래 필(pill) 배지 — 종이/유리 느낌을 섞어 조금 더 고급스럽게."""
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge_layer)

        icon_size = 16
        icon_img = _load_role_icon(role_key, icon_size)

        text_bbox = bd.textbbox((0, 0), role_name, font=self.font_badge)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        icon_text_gap = 6
        pad_x = 12
        pad_y = 5

        content_w = (icon_size + icon_text_gap + tw) if icon_img else tw
        bw = content_w + pad_x * 2
        bh = max(th, icon_size) + pad_y * 2

        bx = cx - bw // 2
        by = cy

        fill = _mix((20, 22, 30), color, 0.18) + (150,)
        stroke = _brighten(color, 0.10) + (80,)

        bd.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=bh // 2, fill=fill, outline=stroke, width=1)

        # 상단 하이라이트(얇은 라인)
        bd.arc([(bx + 2, by + 2), (bx + bw - 2, by + bh - 2)], start=200, end=340, fill=(255, 255, 255, 28), width=1)

        content_x = bx + pad_x
        content_cy = by + bh // 2

        if icon_img:
            icon_y = content_cy - icon_size // 2
            badge_layer.paste(icon_img, (int(content_x), int(icon_y)), icon_img)
            text_x = content_x + icon_size + icon_text_gap
        else:
            text_x = content_x

        text_y = content_cy - th // 2 - 1
        bd.text((int(text_x), int(text_y)), role_name, fill=TEXT_WHITE, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    # ────────────────────────────────────────────────
    # 프로그레스 바(메인/서브)
    # ────────────────────────────────────────────────

    def _draw_main_progress_bar(self, canvas: Image.Image, x: int, y: int, width: int, height: int, progress: float, bar_color: Tuple[int, int, int]):
        """메인 진행바: 트랙 + 그라디언트 필 + 하이라이트."""
        progress = _clamp(progress, 0.0, 100.0)

        ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        radius = 7

        # 트랙
        d.rounded_rectangle([(x, y), (x + width, y + height)], radius, fill=MAIN_BAR_BG + (255,))

        # 필
        fill_w = int(width * (progress / 100.0))
        if fill_w > 0:
            grad = self._make_horizontal_gradient((width, height), _brighten(bar_color, 0.22), _darken(bar_color, 0.10))
            mask = Image.new('L', (width, height), 0)
            md = ImageDraw.Draw(mask)
            md.rounded_rectangle([(0, 0), (width - 1, height - 1)], radius, fill=255)

            # 전체를 먼저 그린 뒤, fill_w만큼만 붙여서 오른쪽은 자연스럽게 컷
            grad_part = Image.new('RGBA', (fill_w, height), (0, 0, 0, 0))
            grad_part.paste(grad.crop((0, 0, fill_w, height)), (0, 0))

            mask_part = mask.crop((0, 0, fill_w, height))
            ov.paste(grad_part, (x, y), mask_part)

            # 하이라이트 라인
            d.line([(x + 6, y + 3), (x + fill_w - 6, y + 3)], fill=(255, 255, 255, 36))

        # 살짝 블러로 마감
        ov = ov.filter(ImageFilter.GaussianBlur(radius=0.4))
        canvas.paste(Image.alpha_composite(canvas, ov))

    def _make_horizontal_gradient(self, size: Tuple[int, int], left: Tuple[int, int, int], right: Tuple[int, int, int]) -> Image.Image:
        w, h = size
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for x in range(w):
            t = x / max(1, w - 1)
            col = _mix(left, right, t)
            d.line([(x, 0), (x, h)], fill=col + (255,))
        return img

    @staticmethod
    def _draw_glass_progress_bar(overlay_draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, progress: float, bar_color: Tuple[int, int, int], radius: int = 5):
        """글래스 박스 내부 프로그레스 바."""
        overlay_draw.rounded_rectangle([(x, y), (x + width, y + height)], radius, fill=GLASS_BAR_BG)
        fill_width = int(width * (_clamp(progress, 0.0, 100.0) / 100.0))
        if fill_width > 0:
            overlay_draw.rounded_rectangle([(x, y), (x + fill_width, y + height)], radius, fill=_brighten(bar_color, 0.18) + (255,))
            overlay_draw.line([(x + 4, y + 3), (x + fill_width - 4, y + 3)], fill=(255, 255, 255, 26))

    # ────────────────────────────────────────────────
    # 글래스모피즘 서브 스탯 박스
    # ────────────────────────────────────────────────

    def _draw_glass_stat_box(self, canvas: Image.Image, x: int, y: int, width: int, label: str, level: int, progress: float, current_xp: int, required_xp: int, color: Tuple[int, int, int], rank: Optional[int] = None, total_users: int = 0):
        """글래스 박스 — 대비/여백/하이라이트를 개선."""
        box_height = 70
        box_radius = 12

        # 1) 배경 블러
        box_region = canvas.crop((x, y, x + width, y + box_height))
        blurred = box_region.filter(ImageFilter.GaussianBlur(radius=GLASS_BLUR_RADIUS))

        blur_mask = _make_rounded_rect_mask((width, box_height), box_radius)
        blur_layer = Image.new('RGBA', (width, box_height), (0, 0, 0, 0))
        blur_layer.paste(blurred, mask=blur_mask)
        canvas.paste(Image.alpha_composite(canvas.crop((x, y, x + width, y + box_height)), blur_layer), (x, y))

        # 2) 글래스 오버레이
        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        od.rounded_rectangle([(x, y), (x + width, y + box_height)], box_radius, fill=GLASS_FILL, outline=GLASS_STROKE, width=1)

        # 상단 하이라이트
        od.line([(x + 10, y + 8), (x + width - 10, y + 8)], fill=(255, 255, 255, 18), width=1)

        # 라벨
        od.text((x + 14, y + 11), label, fill=TEXT_LIGHT, font=self.font_sub_label)

        # 라벨 옆 순위
        if rank is not None:
            rank_text = f"#{rank}"
            if total_users > 0:
                rank_text += f" / {total_users}"
            label_bbox = od.textbbox((0, 0), label, font=self.font_sub_label)
            label_w = label_bbox[2] - label_bbox[0]
            od.text((x + 14 + label_w + 8, y + 12), rank_text, fill=_brighten(color, 0.10) + (255,), font=self.font_rank)

        # 레벨
        level_text = f"Lv. {level}"
        level_bbox = od.textbbox((0, 0), level_text, font=self.font_level)
        level_w = level_bbox[2] - level_bbox[0]
        od.text((x + width - level_w - 14, y + 8), level_text, fill=TEXT_WHITE, font=self.font_level)

        # 프로그레스 바
        bar_x = x + 14
        bar_y = y + 40
        bar_width = width - 28
        bar_height = 12
        self._draw_glass_progress_bar(od, bar_x, bar_y, bar_width, bar_height, progress, color, radius=6)

        # XP 텍스트
        xp_text = f"{current_xp:,} / {required_xp:,}"
        od.text((x + 14, y + 55), xp_text, fill=TEXT_DIM, font=self.font_sub_label)

        # 진행률 텍스트
        pct_text = f"{progress:.1f}%"
        pct_bbox = od.textbbox((0, 0), pct_text, font=self.font_sub_label)
        pct_w = pct_bbox[2] - pct_bbox[0]
        od.text((x + width - pct_w - 14, y + 55), pct_text, fill=TEXT_GRAY, font=self.font_sub_label)

        # 합성
        canvas.paste(Image.alpha_composite(canvas, overlay))

    # ────────────────────────────────────────────────
    # 라운드 코너
    # ────────────────────────────────────────────────

    def _apply_rounded_corners(self, canvas: Image.Image) -> Image.Image:
        mask = _make_rounded_rect_mask(canvas.size, CORNER_RADIUS)
        output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        output.paste(canvas, mask=mask)
        return output


async def setup(bot):
    pass  # 유틸리티 모듈 — Cog 없음
