"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

수정 사항 (최신):
  - 프로그레스 바: 화살표 모양 제거 후 부드러운 둥근(Round) 형태로 변경
  - 텍스트 크기: 전반적인 폰트 사이즈 대폭 확대 (이름, 레벨, 경험치 등)
  - 랭크 배지: 불필요한 별(★) 아이콘 제거 후 텍스트만 깔끔하게 표시
"""

import io
import os
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 2배수 렌더링 스케일 ──
S = 2  # 내부 렌더링 배율

# ── 배경 이미지 설정 ──
BG_IMAGE_PATH = "assets/images/rank_bg.png" # 실제 배경 이미지 경로로 변경

# ── 색상 정의 ──
THEME_COLOR_MAIN = (255, 180, 50)     # 시안에 맞춘 따뜻한 골드/오렌지
THEME_COLOR_SUB = (218, 165, 32)      
THEME_COLOR_BAR_BG = (35, 30, 35)     # 바 배경 (어두운 회색/갈색)

TEXT_WHITE = (245, 245, 245)
TEXT_LIGHT = (210, 210, 210)
TEXT_GRAY = (150, 150, 150)
TEXT_DARK_GOLD = (180, 140, 70)

# ── 폰트 경로 ──
# FONT_BOLD_PATH = "assets/fonts/Pretendard-Bold.ttf"
# FONT_MEDIUM_PATH = "assets/fonts/Pretendard-Medium.ttf"

FONT_BOLD_PATH = "assets/fonts/NanumMyeongjoExtraBold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/NanumMyeongjoBold.ttf"

def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}, {size}px): {e}")
        return ImageFont.load_default()

def _make_circle_mask(diameter: int) -> Image.Image:
    mask = Image.new('L', (diameter, diameter), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (diameter - 1, diameter - 1)], fill=255)
    return mask

class RankCardGenerator:
    def __init__(self):
        # 폰트 사이즈 대폭 확대 적용
        self.base_font_scale = S
        self.font_name = _load_font(FONT_BOLD_PATH, int(100 * self.base_font_scale))      # 42 -> 56
        self.font_exp_val = _load_font(FONT_MEDIUM_PATH, int(50 * self.base_font_scale)) # 22 -> 28
        self.font_exp_lbl = _load_font(FONT_MEDIUM_PATH, int(30 * self.base_font_scale)) # 22 -> 24
        self.font_next_role = _load_font(FONT_MEDIUM_PATH, int(30 * self.base_font_scale)) # 18 -> 22
        
        self.font_badge = _load_font(FONT_BOLD_PATH, int(28 * self.base_font_scale))       # 18 -> 24
        
        self.font_box_label = _load_font(FONT_BOLD_PATH, int(30 * self.base_font_scale)) # 18 -> 20
        self.font_box_rank = _load_font(FONT_MEDIUM_PATH, int(24 * self.base_font_scale))  # 16 -> 18
        self.font_box_level = _load_font(FONT_BOLD_PATH, int(36 * self.base_font_scale))   # 28 -> 36
        self.font_box_val = _load_font(FONT_MEDIUM_PATH, int(24 * self.base_font_scale))   # 16 -> 18

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        # 1. 원본 배경 이미지 로드 및 논리적/물리적 크기 설정
        try:
            bg_image = Image.open(BG_IMAGE_PATH).convert('RGBA')
            OUTPUT_WIDTH, OUTPUT_HEIGHT = bg_image.size
        except (IOError, OSError) as e:
            logger.error(f"배경 이미지 로드 실패: {e}")
            OUTPUT_WIDTH, OUTPUT_HEIGHT = 1000, 660 # Fallback
            bg_image = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (30, 30, 35))

        CANVAS_WIDTH = OUTPUT_WIDTH * S
        CANVAS_HEIGHT = OUTPUT_HEIGHT * S
        canvas = bg_image.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.LANCZOS)
        draw = ImageDraw.Draw(canvas)

        # ── 좌표 비율 정의 ──
        POS = {
            'avatar_cx': 0.156,  'avatar_cy': 0.358,  'avatar_radius': 0.098,
            'badge_y': 0.500,
            'info_x': 0.305,     
            'name_y': 0.220,     'exp_y': 0.340,      'next_role_y': 0.430,
            'main_bar_y': 0.470, 'main_bar_w': 0.600, 'main_bar_h': 0.025,
            'box1_x': 0.295,     'box2_x': 0.615,     'box_y': 0.685,
            'box_w': 0.300,      'box_h': 0.175
        }

        # ── 1. 아바타 ──
        avatar_r = int(CANVAS_WIDTH * POS['avatar_radius'])
        avatar_size = avatar_r * 2
        avatar_x = int(CANVAS_WIDTH * POS['avatar_cx']) - avatar_r
        avatar_y = int(CANVAS_HEIGHT * POS['avatar_cy']) - avatar_r
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, avatar_size)

        # ── 2. 배지 (별 아이콘 제거) ──
        badge_cx = int(CANVAS_WIDTH * POS['avatar_cx'])
        badge_y = int(CANVAS_HEIGHT * POS['badge_y'])
        self._draw_badge(canvas, badge_cx, badge_y, data.role_display) # 별(★) 제거됨

        # ── 3. 상단 텍스트 정보 ──
        info_x = int(CANVAS_WIDTH * POS['info_x'])
        
        # 이름
        name_y = int(CANVAS_HEIGHT * POS['name_y'])
        draw.text((info_x - 20, name_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)

        # 총 페이지(쪽)
        exp_y = int(CANVAS_HEIGHT * POS['exp_y'])
        exp_val = f"{data.total_exp:,}"
        draw.text((info_x, exp_y), exp_val, fill=TEXT_LIGHT, font=self.font_exp_val)
        val_w = draw.textbbox((0, 0), exp_val, font=self.font_exp_val)[2]
        draw.text((info_x + val_w + 8 * S, exp_y + 18 * S), "쪽", fill=TEXT_GRAY, font=self.font_exp_lbl)

        # 다음 단계
        next_y = int(CANVAS_HEIGHT * POS['next_role_y'])
        next_text = f"다음 단계 : {data.next_role_display}" if data.next_role_display else "최고 단계 달성"
        draw.text((info_x, next_y), next_text, fill=TEXT_GRAY, font=self.font_next_role)

        # ── 4. 메인 진행 바 ──
        main_bar_y = int(CANVAS_HEIGHT * POS['main_bar_y'])
        main_bar_w = int(CANVAS_WIDTH * POS['main_bar_w'])
        main_bar_h = int(CANVAS_HEIGHT * POS['main_bar_h'])

        # 메인 진행 % 텍스트
        pct_text = f"{data.role_progress_pct:.1f}%"
        pct_w = draw.textbbox((0, 0), pct_text, font=self.font_box_val)[2]
        draw.text(
            (info_x + main_bar_w - pct_w, main_bar_y - int(30 * S)), 
            pct_text, fill=THEME_COLOR_MAIN, font=self.font_box_val
        )

        self._draw_rounded_progress_bar(
            draw, info_x, main_bar_y, main_bar_w, main_bar_h, data.role_progress_pct
        )

        # ── 5. 하단 스탯 박스 (채팅/음성) ──
        box1_x = int(CANVAS_WIDTH * POS['box1_x'])
        box2_x = int(CANVAS_WIDTH * POS['box2_x'])
        box_y = int(CANVAS_HEIGHT * POS['box_y'])
        box_w = int(CANVAS_WIDTH * POS['box_w'])
        box_h = int(CANVAS_HEIGHT * POS['box_h'])

        # 채팅 레벨 (왼쪽 박스)
        self._draw_stat_box_content(
            draw, box1_x, box_y, box_w, box_h,
            "채팅 레벨", data.chat_level_info.level, data.chat_level_info.progress_pct,
            data.chat_level_info.current_xp, data.chat_level_info.required_xp,
            data.chat_rank, data.chat_total_users
        )

        # 음성 레벨 (오른쪽 박스)
        self._draw_stat_box_content(
            draw, box2_x, box_y, box_w, box_h,
            "음성 레벨", data.voice_level_info.level, data.voice_level_info.progress_pct,
            data.voice_level_info.current_xp, data.voice_level_info.required_xp,
            data.voice_rank, data.voice_total_users
        )

        # ── 2배 → 원래 크기로 다운스케일 (LANCZOS) ──
        output = canvas.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)

        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 아바타 & 배지
    # ────────────────────────────────────────────────
    def _draw_avatar(self, canvas: Image.Image, avatar_bytes: bytes, x: int, y: int, size: int):
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
            mask = _make_circle_mask(size)
            canvas.paste(avatar_img, (x, y), mask)
        except Exception as e:
            logger.error(f"아바타 로드 실패: {e}")

    def _draw_badge(self, canvas: Image.Image, cx: int, cy: int, text: str):
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge_layer)

        text_bbox = bd.textbbox((0, 0), text, font=self.font_badge)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        pad_x = 22 * S
        pad_y = 10 * S
        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        bx, by = cx - bw // 2, cy

        bd.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=(20, 15, 10, 220),
            outline=THEME_COLOR_MAIN,
            width=max(1, 1 * S)
        )

        text_x = bx + pad_x
        text_y = by + pad_y - (2 * S)
        bd.text((text_x, text_y), text, fill=TEXT_WHITE, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    # ────────────────────────────────────────────────
    # 둥근 형태 프로그레스 바 (화살표 대체)
    # ────────────────────────────────────────────────
    @staticmethod
    def _draw_rounded_progress_bar(
        draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        progress: float
    ):
        """양끝이 둥근 일반적인 프로그레스 바를 그립니다."""
        # 1. 배경 바
        draw.rounded_rectangle([(x, y), (x + width, y + height)], height // 2, fill=THEME_COLOR_BAR_BG)
        
        # 2. 진행 바
        if progress > 0:
            fill_w = max(int(width * (progress / 100.0)), height)
            draw.rounded_rectangle([(x, y), (x + fill_w, y + height)], height // 2, fill=THEME_COLOR_MAIN)

    # ────────────────────────────────────────────────
    # 하단 스탯 박스 콘텐츠
    # ────────────────────────────────────────────────
    def _draw_stat_box_content(
        self, draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        label: str, level: int, progress: float,
        current_xp: int, required_xp: int,
        rank: Optional[int], total_users: int
    ):
        pad_x = 24 * S
        inner_y = y + int(height * 0.15)
        
        # [상단 좌측] 라벨 & 순위
        draw.text((x + pad_x, inner_y), label, fill=TEXT_LIGHT, font=self.font_box_label)
        
        if rank is not None:
            rank_text = f"{rank}등 / {total_users}명"
            label_w = draw.textbbox((0, 0), label, font=self.font_box_label)[2]
            draw.text((x + pad_x, inner_y + 40 * S), rank_text, fill=TEXT_DARK_GOLD, font=self.font_box_rank)

        # [상단 우측] 레벨
        level_text = f"Lv. {level}"
        level_w = draw.textbbox((0, 0), level_text, font=self.font_box_level)[2]
        draw.text((x + width - pad_x - level_w, inner_y - 8 * S), level_text, fill=TEXT_WHITE, font=self.font_box_level)

        # [중앙] 프로그레스 바
        bar_y = inner_y + int(height * 0.45)
        bar_w = width - (pad_x * 2)
        bar_h = int(height * 0.15)
        self._draw_rounded_progress_bar(draw, x + pad_x, bar_y, bar_w, bar_h, progress)

        # [하단 좌/우측] XP / 퍼센트
        bottom_y = bar_y + bar_h + 12 * S
        xp_text = f"{current_xp:,} / {required_xp:,}"
        draw.text((x + pad_x, bottom_y), xp_text, fill=TEXT_GRAY, font=self.font_box_val)

        pct_text = f"{progress:.1f}%"
        pct_w = draw.textbbox((0, 0), pct_text, font=self.font_box_val)[2]
        draw.text((x + width - pad_x - pct_w, bottom_y), pct_text, fill=TEXT_GRAY, font=self.font_box_val)