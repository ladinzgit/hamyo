"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

레이아웃 구성:
  - 캔버스: 860x280px, 다크 배경(#0f0f13), 라운드 코너(24px)
  - 왼쪽: 원형 아바타(140x140px) + 경지 배지
  - 오른쪽: 이름, 다공, 다음 경지 진행바
  - 하단: 채팅 레벨 / 음성 레벨 박스
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

# ── 색상 정의 ──
BG_COLOR = (15, 15, 19)              # #0f0f13
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (180, 180, 185)
TEXT_DIM = (120, 120, 130)
BAR_BG = (40, 40, 50)
BADGE_BG = (30, 30, 40)

# ── 역할별 테마 색상 ──
ROLE_COLORS = {
    'hub':      (74, 222, 128),       # #4ade80  초록
    'dado':     (163, 230, 53),       # #a3e635  라임
    'daho':     (244, 114, 182),      # #f472b6  핑크
    'dakyung':  (251, 191, 36),       # #fbbf24  골드
    'dahyang':  (129, 140, 248),      # #818cf8  보라
}

# ── 역할별 배경 장식 문자 ──
ROLE_DECO_CHAR = {
    'hub':      '허',
    'dado':     '다',
    'daho':     '호',
    'dakyung':  '경',
    'dahyang':  '향',
}

# ── 폰트 경로 ──
FONT_BOLD_PATH = "assets/fonts/Pretendard-Bold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/Pretendard-Medium.ttf"


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """폰트 파일을 로드합니다. 실패 시 기본 폰트를 반환합니다."""
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}): {e} — 기본 폰트를 사용합니다.")
        return ImageFont.load_default()


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


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, width: int, height: int,
    progress: float,
    bar_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int] = BAR_BG,
    radius: int = 6,
):
    """
    프로그레스 바를 그립니다.

    Args:
        draw: ImageDraw 객체
        x, y: 좌상단 좌표
        width, height: 바 크기
        progress: 진행률 (0.0 ~ 100.0)
        bar_color: 채워진 부분 색상
        bg_color: 배경 색상
        radius: 라운드 코너 반경
    """
    # 배경
    draw.rounded_rectangle(
        [(x, y), (x + width, y + height)],
        radius, fill=bg_color
    )
    # 채움
    fill_width = max(int(width * (progress / 100.0)), radius * 2)
    if progress > 0:
        draw.rounded_rectangle(
            [(x, y), (x + fill_width, y + height)],
            radius, fill=bar_color
        )


class RankCardGenerator:
    """랭크 카드 이미지 생성기"""

    def __init__(self):
        # 폰트 로드 (다양한 크기)
        self.font_name = _load_font(FONT_BOLD_PATH, 26)
        self.font_exp = _load_font(FONT_MEDIUM_PATH, 16)
        self.font_label = _load_font(FONT_MEDIUM_PATH, 13)
        self.font_level = _load_font(FONT_BOLD_PATH, 18)
        self.font_progress = _load_font(FONT_MEDIUM_PATH, 13)
        self.font_badge = _load_font(FONT_BOLD_PATH, 14)
        self.font_deco = _load_font(FONT_BOLD_PATH, 160)
        self.font_sub_label = _load_font(FONT_MEDIUM_PATH, 12)
        self.font_rank = _load_font(FONT_BOLD_PATH, 11)

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        """
        랭크 카드 이미지를 생성하여 BytesIO로 반환합니다.

        Args:
            data: RankCardData (서비스에서 수집한 모든 데이터)
            avatar_bytes: 유저 아바타 이미지 바이트

        Returns:
            io.BytesIO: PNG 이미지 데이터
        """
        role_color = ROLE_COLORS.get(data.current_role, ROLE_COLORS['hub'])

        # ── 캔버스 생성 ──
        canvas = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR + (255,))
        draw = ImageDraw.Draw(canvas)

        # ── 배경 그라디언트 오버레이 ──
        self._draw_background_gradient(canvas, role_color)

        # ── 배경 장식 문자 ──
        self._draw_deco_character(canvas, draw, data.current_role, role_color)

        # ── 아바타 (원형) ──
        avatar_x, avatar_y = 30, 30
        avatar_size = 140
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, avatar_size)

        # ── 역할 배지 (아바타 하단) ──
        badge_text = f"{data.role_emoji} {data.role_display}"
        badge_cx = avatar_x + avatar_size // 2
        badge_y = avatar_y + avatar_size + 12
        self._draw_badge(draw, badge_cx, badge_y, badge_text, role_color)

        # ── 정보 영역 (오른쪽) ──
        info_x = avatar_x + avatar_size + 32
        info_y = 32

        # 이름
        draw.text((info_x, info_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)
        info_y += 36

        # 총 다공
        exp_text = f"{data.total_exp:,} 다공"
        draw.text((info_x, info_y), exp_text, fill=TEXT_GRAY, font=self.font_exp)
        info_y += 28

        # 메인 진행 바 (다음 경지)
        bar_width = CANVAS_WIDTH - info_x - 40
        if data.next_role_display:
            progress_label = f"다음 경지 : {data.next_role_display}"
        else:
            progress_label = "최고 경지 달성"
        pct_text = f"{data.role_progress_pct:.1f}%"

        draw.text((info_x, info_y), progress_label, fill=TEXT_DIM, font=self.font_progress)
        # 퍼센트 텍스트를 오른쪽 정렬
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text(
            (info_x + bar_width - pct_w, info_y),
            pct_text, fill=role_color, font=self.font_progress
        )
        info_y += 20

        _draw_progress_bar(
            draw, info_x, info_y, bar_width, 14,
            data.role_progress_pct, role_color
        )

        # ── 하단 서브 스탯 박스 ──
        sub_y = 190
        sub_box_width = (CANVAS_WIDTH - info_x - 40 - 16) // 2  # 두 박스 사이 16px 간격

        # 채팅 레벨 박스 (왼쪽)
        self._draw_sub_stat_box(
            draw,
            x=info_x,
            y=sub_y,
            width=sub_box_width,
            label="채팅 레벨",
            level=data.chat_level_info.level,
            progress=data.chat_level_info.progress_pct,
            color=role_color,
            rank=data.chat_rank,
            total_users=data.chat_total_users,
        )

        # 음성 레벨 박스 (오른쪽)
        self._draw_sub_stat_box(
            draw,
            x=info_x + sub_box_width + 16,
            y=sub_y,
            width=sub_box_width,
            label="음성 레벨",
            level=data.voice_level_info.level,
            progress=data.voice_level_info.progress_pct,
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

    def _draw_background_gradient(
        self, canvas: Image.Image, color: Tuple[int, int, int]
    ):
        """역할 색상 기반의 그라디언트 오버레이를 배경에 적용합니다."""
        overlay = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # 왼쪽 상단에서 오른쪽으로 fade되는 그라디언트
        for x in range(CANVAS_WIDTH):
            alpha = int(30 * (1 - x / CANVAS_WIDTH))  # 최대 약 12% 불투명도
            draw_ov.line([(x, 0), (x, CANVAS_HEIGHT)], fill=color + (alpha,))

        canvas.paste(Image.alpha_composite(canvas, overlay))

    def _draw_deco_character(
        self, canvas: Image.Image, draw: ImageDraw.ImageDraw,
        role: str, color: Tuple[int, int, int]
    ):
        """배경에 반투명 장식 문자를 그립니다."""
        char = ROLE_DECO_CHAR.get(role, '경')

        # 반투명 텍스트를 별도 레이어에 그림
        text_layer = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        # 글자 크기 계산 → 오른쪽 배치
        bbox = text_draw.textbbox((0, 0), char, font=self.font_deco)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        tx = CANVAS_WIDTH - tw - 20
        ty = (CANVAS_HEIGHT - th) // 2 - 20

        # 약 10% 불투명도
        text_draw.text((tx, ty), char, fill=color + (25,), font=self.font_deco)

        canvas.paste(Image.alpha_composite(canvas, text_layer))

    def _draw_avatar(
        self, canvas: Image.Image,
        avatar_bytes: bytes, x: int, y: int, size: int
    ):
        """원형으로 크롭한 아바타를 캔버스에 배치합니다."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)

            # 원형 마스크
            mask = _make_circle_mask(size)

            # 테두리용 배경 원 (살짝 큰 원)
            border_size = size + 6
            border_circle = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border_circle)
            border_draw.ellipse(
                [(0, 0), (border_size - 1, border_size - 1)],
                fill=(40, 40, 50, 200)
            )

            # 테두리 원 배치
            canvas.paste(
                Image.alpha_composite(
                    canvas.crop((x - 3, y - 3, x - 3 + border_size, y - 3 + border_size)),
                    border_circle
                ),
                (x - 3, y - 3)
            )

            # 아바타 배치
            canvas.paste(avatar_img, (x, y), mask)
        except Exception as e:
            logger.error(f"아바타 그리기 실패: {e}")
            # 실패 시 회색 원으로 대체
            draw = ImageDraw.Draw(canvas)
            draw.ellipse(
                [(x, y), (x + size, y + size)],
                fill=(60, 60, 70)
            )

    def _draw_badge(
        self, draw: ImageDraw.ImageDraw,
        cx: int, cy: int, text: str,
        color: Tuple[int, int, int]
    ):
        """아바타 아래에 필(pill) 모양 역할 배지를 그립니다."""
        bbox = draw.textbbox((0, 0), text, font=self.font_badge)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x, pad_y = 14, 5
        bw = tw + pad_x * 2
        bh = th + pad_y * 2

        bx = cx - bw // 2
        by = cy

        # 배경 필
        draw.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=color + (50,) if len(color) == 3 else color,
            outline=color + (100,) if len(color) == 3 else color,
        )

        # 텍스트
        draw.text(
            (bx + pad_x, by + pad_y),
            text, fill=TEXT_WHITE, font=self.font_badge
        )

    def _draw_sub_stat_box(
        self, draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int,
        label: str, level: int, progress: float,
        color: Tuple[int, int, int],
        rank: Optional[int] = None,
        total_users: int = 0,
    ):
        """채팅/음성 레벨 서브 스탯 박스를 그립니다."""
        box_height = 68
        box_radius = 10

        # 박스 배경
        draw.rounded_rectangle(
            [(x, y), (x + width, y + box_height)],
            box_radius, fill=(25, 25, 35, 180)
        )

        # 라벨
        draw.text(
            (x + 14, y + 10),
            label, fill=TEXT_DIM, font=self.font_sub_label
        )

        # 라벨 옛에 순위 표시 (ex: "#3 / 15")
        if rank is not None:
            rank_text = f"#{rank}"
            if total_users > 0:
                rank_text += f" / {total_users}"
            label_bbox = draw.textbbox((0, 0), label, font=self.font_sub_label)
            label_w = label_bbox[2] - label_bbox[0]
            draw.text(
                (x + 14 + label_w + 8, y + 11),
                rank_text, fill=color, font=self.font_rank
            )

        # 레벨 값
        level_text = f"Lv. {level}"
        level_bbox = draw.textbbox((0, 0), level_text, font=self.font_level)
        level_w = level_bbox[2] - level_bbox[0]
        draw.text(
            (x + width - level_w - 14, y + 7),
            level_text, fill=TEXT_WHITE, font=self.font_level
        )

        # 프로그레스 바
        bar_x = x + 14
        bar_y = y + 38
        bar_width = width - 28
        bar_height = 12

        _draw_progress_bar(
            draw, bar_x, bar_y, bar_width, bar_height,
            progress, color, radius=6
        )

        # 진행률 텍스트
        pct_text = f"{progress:.1f}%"
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_sub_label)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text(
            (x + width - pct_w - 14, y + 53),
            pct_text, fill=TEXT_GRAY, font=self.font_sub_label
        )

    def _apply_rounded_corners(self, canvas: Image.Image) -> Image.Image:
        """캔버스에 라운드 코너를 적용합니다."""
        # RGB로 변환 후 라운드 마스크 적용
        mask = _make_rounded_rect_mask(canvas.size, CORNER_RADIUS)

        # 검정 배경에 마스크 적용
        output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        output.paste(canvas, mask=mask)
        return output


async def setup(bot):
    pass  # 유틸리티 모듈 — Cog 없음
