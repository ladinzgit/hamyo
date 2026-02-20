"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

2배수 렌더링 기법 적용:
  내부적으로 2배 크기(1720x560)로 렌더링한 뒤,
  최종 출력 시 원래 크기(860x280)로 LANCZOS 다운스케일하여
  폰트와 그래픽의 선명도를 극대화합니다.
"""

import io
import os
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 2배수 렌더링 스케일 ──
S = 2  # 내부 렌더링 배율

# ── 캔버스 설정 (논리 크기) ──
OUTPUT_WIDTH = 860
OUTPUT_HEIGHT = 280

# 실제 렌더링 크기 (2배)
CANVAS_WIDTH = OUTPUT_WIDTH * S    # 1720
CANVAS_HEIGHT = OUTPUT_HEIGHT * S  # 560
CORNER_RADIUS = 24 * S

# ── 색상 정의 ──
BG_COLOR = (15, 15, 19)              # #0f0f13
TEXT_WHITE = (255, 255, 255)
TEXT_LIGHT = (221, 221, 221)         # #dddddd
TEXT_GRAY = (170, 170, 175)
TEXT_DIM = (120, 120, 130)

# 메인 프로그레스 바 배경
MAIN_BAR_BG = (35, 35, 45)

# 글래스모피즘 색상
GLASS_FILL = (255, 255, 255, 10)
GLASS_STROKE = (255, 255, 255, 20)
GLASS_BAR_BG = (0, 0, 0, 120)
GLASS_BLUR_RADIUS = 12 * S

# ── 역할별 테마 색상 ──
ROLE_COLORS = {
    'hub':      (74, 222, 128),       # #4ade80  초록
    'dado':     (163, 230, 53),       # #a3e635  라임
    'daho':     (244, 114, 182),      # #f472b6  핑크
    'dakyung':  (251, 191, 36),       # #fbbf24  골드
    'dahyang':  (129, 140, 248),      # #818cf8  보라
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


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}, {size}px): {e}")
        return ImageFont.load_default()


def _load_role_icon(role: str, size: int = 18) -> Optional[Image.Image]:
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
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius, fill=255)
    return mask


def _make_circle_mask(diameter: int) -> Image.Image:
    mask = Image.new('L', (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (diameter - 1, diameter - 1)], fill=255)
    return mask


class RankCardGenerator:
    def __init__(self):
        # 폰트 사이즈 (2배수 적용)
        self.font_name = _load_font(FONT_BOLD_PATH, 34 * S)
        self.font_exp_val = _load_font(FONT_BOLD_PATH, 22 * S)
        self.font_exp_lbl = _load_font(FONT_MEDIUM_PATH, 16 * S)
        self.font_level = _load_font(FONT_BOLD_PATH, 20 * S)
        self.font_progress = _load_font(FONT_MEDIUM_PATH, 13 * S)
        self.font_badge = _load_font(FONT_BOLD_PATH, 14 * S)
        self.font_sub_label = _load_font(FONT_MEDIUM_PATH, 13 * S)
        self.font_sub_val = _load_font(FONT_MEDIUM_PATH, 12 * S)
        self.font_rank = _load_font(FONT_BOLD_PATH, 12 * S)

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        role_color = ROLE_COLORS.get(data.current_role, ROLE_COLORS['hub'])

        # ── 캔버스 생성 (2배 크기) ──
        canvas = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR + (255,))

        # ── 배경 앰비언트 글로우 ──
        self._draw_ambient_glow(canvas, role_color)

        # ── 아바타 (원형 + 역할 테두리) ──
        avatar_x, avatar_y = 36 * S, 30 * S
        avatar_size = 140 * S
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, avatar_size, role_color)

        # ── 역할 배지 ──
        badge_cx = avatar_x + avatar_size // 2
        badge_y = avatar_y + avatar_size + 16 * S
        self._draw_badge(canvas, badge_cx, badge_y, data.role_display, data.current_role, role_color)

        # ── 정보 영역 (오른쪽) ──
        info_x = avatar_x + avatar_size + 48 * S
        info_y = 36 * S

        draw = ImageDraw.Draw(canvas)

        # 이름
        draw.text((info_x, info_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)
        info_y += 42 * S

        # 총 다공 (수치와 단위 폰트 분리하여 강조)
        exp_val = f"{data.total_exp:,}"
        exp_lbl = " 다공"
        draw.text((info_x, info_y), exp_val, fill=role_color, font=self.font_exp_val)
        val_bbox = draw.textbbox((0, 0), exp_val, font=self.font_exp_val)
        val_w = val_bbox[2] - val_bbox[0]
        draw.text((info_x + val_w, info_y + 4 * S), exp_lbl, fill=TEXT_GRAY, font=self.font_exp_lbl)
        info_y += 36 * S

        # 메인 진행 바 (얇게)
        bar_width = CANVAS_WIDTH - info_x - 36 * S
        if data.next_role_display:
            progress_label = f"다음 경지 : {data.next_role_display}"
        else:
            progress_label = "최고 경지 달성"
        pct_text = f"{data.role_progress_pct:.1f}%"

        draw.text((info_x, info_y), progress_label, fill=TEXT_DIM, font=self.font_progress)
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text(
            (info_x + bar_width - pct_w, info_y),
            pct_text, fill=role_color, font=self.font_progress
        )
        info_y += 20 * S

        # 메인 진행 바
        self._draw_main_progress_bar(
            draw, info_x, info_y, bar_width, 8 * S,
            data.role_progress_pct, role_color
        )

        # ── 하단 글래스모피즘 박스 ──
        sub_y = 186 * S
        sub_box_width = (CANVAS_WIDTH - info_x - 36 * S - 16 * S) // 2

        self._draw_glass_stat_box(
            canvas, info_x, sub_y, sub_box_width,
            "채팅 레벨", data.chat_level_info.level, data.chat_level_info.progress_pct,
            data.chat_level_info.current_xp, data.chat_level_info.required_xp,
            data.chat_level_info.total_xp,
            role_color, data.chat_rank, data.chat_total_users
        )

        self._draw_glass_stat_box(
            canvas, info_x + sub_box_width + 16 * S, sub_y, sub_box_width,
            "음성 레벨", data.voice_level_info.level, data.voice_level_info.progress_pct,
            data.voice_level_info.current_xp, data.voice_level_info.required_xp,
            data.voice_level_info.total_xp,
            role_color, data.voice_rank, data.voice_total_users
        )

        # ── 라운드 코너 적용 ──
        output = self._apply_rounded_corners(canvas)

        # ── 2배 → 원래 크기로 다운스케일 (LANCZOS) ──
        output = output.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)

        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 배경
    # ────────────────────────────────────────────────
    def _draw_ambient_glow(self, canvas: Image.Image, color: Tuple[int, int, int]):
        """가장자리에 부드러운 빛 번짐(Glow) 효과를 줍니다."""
        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # 좌측 상단 큰 글로우
        draw_ov.ellipse([(-150 * S, -150 * S), (350 * S, 350 * S)], fill=color + (30,))
        # 우측 하단 큰 글로우
        draw_ov.ellipse([(500 * S, 50 * S), (1000 * S, 450 * S)], fill=color + (20,))

        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=80 * S))
        canvas.paste(Image.alpha_composite(canvas, overlay))

    # ────────────────────────────────────────────────
    # 아바타 & 배지
    # ────────────────────────────────────────────────
    def _draw_avatar(
        self, canvas: Image.Image,
        avatar_bytes: bytes, x: int, y: int, size: int,
        role_color: Tuple[int, int, int]
    ):
        """아바타에 여백이 있는 프리미엄 테두리를 추가합니다."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
            mask = _make_circle_mask(size)

            draw = ImageDraw.Draw(canvas)
            gap = 6 * S
            stroke = 4 * S
            outer_size = size + gap * 2 + stroke * 2

            # 1. 역할 색상 바깥 테두리
            ox = x - gap - stroke
            oy = y - gap - stroke
            draw.ellipse([(ox, oy), (ox + outer_size - 1, oy + outer_size - 1)], fill=role_color)

            # 2. 배경색 이너 갭 (배경과 분리되는 효과)
            ix = x - gap
            iy = y - gap
            inner_size = size + gap * 2
            draw.ellipse([(ix, iy), (ix + inner_size - 1, iy + inner_size - 1)], fill=BG_COLOR)

            # 3. 아바타 붙이기
            canvas.paste(avatar_img, (x, y), mask)

        except Exception as e:
            logger.error(f"아바타 그리기 실패: {e}")
            draw = ImageDraw.Draw(canvas)
            draw.ellipse([(x, y), (x + size, y + size)], fill=(60, 60, 70))

    def _draw_badge(
        self, canvas: Image.Image,
        cx: int, cy: int, role_name: str,
        role_key: str, color: Tuple[int, int, int]
    ):
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge_layer)

        icon_size = 18 * S
        icon_img = _load_role_icon(role_key, icon_size)

        text_bbox = bd.textbbox((0, 0), role_name, font=self.font_badge)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        icon_text_gap = 6 * S
        pad_x = 16 * S
        pad_y = 6 * S

        content_w = (icon_size + icon_text_gap + tw) if icon_img else tw
        bw = content_w + pad_x * 2
        bh = max(th, icon_size) + pad_y * 2
        bx, by = cx - bw // 2, cy

        # 배경 필: 역할 색상의 20% 투명도로 은은하고 세련되게
        bd.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=color + (40,)
        )

        content_x = bx + pad_x
        content_cy = by + bh // 2

        if icon_img:
            icon_y = content_cy - icon_size // 2
            badge_layer.paste(icon_img, (int(content_x), int(icon_y)), icon_img)
            text_x = content_x + icon_size + icon_text_gap
        else:
            text_x = content_x

        text_y = content_cy - th // 2 - 1
        # 텍스트는 역할 색상 그대로 써서 일체감 부여
        bd.text((int(text_x), int(text_y)), role_name, fill=color, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    # ────────────────────────────────────────────────
    # 프로그레스 바
    # ────────────────────────────────────────────────
    @staticmethod
    def _draw_main_progress_bar(
        draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        progress: float, bar_color: Tuple[int, int, int]
    ):
        draw.rounded_rectangle([(x, y), (x + width, y + height)], height // 2, fill=MAIN_BAR_BG)
        fill_width = max(int(width * (progress / 100.0)), height)
        if progress > 0:
            draw.rounded_rectangle([(x, y), (x + fill_width, y + height)], height // 2, fill=bar_color)

    @staticmethod
    def _draw_glass_progress_bar(
        overlay_draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        progress: float, bar_color: Tuple[int, int, int]
    ):
        overlay_draw.rounded_rectangle([(x, y), (x + width, y + height)], height // 2, fill=GLASS_BAR_BG)
        fill_width = max(int(width * (progress / 100.0)), height)
        if progress > 0:
            overlay_draw.rounded_rectangle([(x, y), (x + fill_width, y + height)], height // 2, fill=bar_color)

    # ────────────────────────────────────────────────
    # 글래스모피즘 서브 스탯 박스
    # ────────────────────────────────────────────────
    def _draw_glass_stat_box(
        self, canvas: Image.Image,
        x: int, y: int, width: int,
        label: str, level: int, progress: float,
        current_xp: int, required_xp: int, total_xp: int,
        color: Tuple[int, int, int], rank: Optional[int], total_users: int
    ):
        box_height = 70 * S
        box_radius = 12 * S

        box_region = canvas.crop((x, y, x + width, y + box_height))
        blurred = box_region.filter(ImageFilter.GaussianBlur(radius=GLASS_BLUR_RADIUS))

        blur_mask = _make_rounded_rect_mask((width, box_height), box_radius)
        blur_layer = Image.new('RGBA', (width, box_height), (0, 0, 0, 0))
        blur_layer.paste(blurred, mask=blur_mask)
        canvas.paste(
            Image.alpha_composite(canvas.crop((x, y, x + width, y + box_height)), blur_layer),
            (x, y)
        )

        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        od.rounded_rectangle(
            [(x, y), (x + width, y + box_height)],
            box_radius, fill=GLASS_FILL, outline=GLASS_STROKE, width=1 * S,
        )

        pad_x = 16 * S

        # 상단 왼쪽: 라벨 & 순위
        od.text((x + pad_x, y + 14 * S), label, fill=TEXT_LIGHT, font=self.font_sub_label)
        if rank is not None:
            rank_text = f"{rank}등"
            if total_users > 0:
                rank_text += f" / 총 {total_users}명"
            label_w = od.textbbox((0, 0), label, font=self.font_sub_label)[2]
            od.text((x + pad_x + label_w + 6 * S, y + 15 * S), rank_text, fill=color, font=self.font_rank)

        # 상단 오른쪽: 레벨
        level_text = f"Lv. {level}"
        level_w = od.textbbox((0, 0), level_text, font=self.font_level)[2]
        od.text((x + width - pad_x - level_w, y + 12 * S), level_text, fill=TEXT_WHITE, font=self.font_level)

        # 중앙: 진행 바
        bar_y = y + 40 * S
        bar_width = width - (pad_x * 2)
        self._draw_glass_progress_bar(od, x + pad_x, bar_y, bar_width, 6 * S, progress, color)

        # 하단: XP / 퍼센트
        text_y = bar_y + 10 * S
        xp_text = f"{current_xp:,} / {required_xp:,}  (총 {total_xp:,})"
        od.text((x + pad_x, text_y), xp_text, fill=TEXT_DIM, font=self.font_sub_val)

        pct_text = f"{progress:.1f}%"
        pct_w = od.textbbox((0, 0), pct_text, font=self.font_sub_val)[2]
        od.text((x + width - pad_x - pct_w, text_y), pct_text, fill=TEXT_GRAY, font=self.font_sub_val)

        canvas.paste(Image.alpha_composite(canvas, overlay))

    def _apply_rounded_corners(self, canvas: Image.Image) -> Image.Image:
        mask = _make_rounded_rect_mask(canvas.size, CORNER_RADIUS)
        output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        output.paste(canvas, mask=mask)
        return output


async def setup(bot):
    pass
