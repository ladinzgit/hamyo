"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

수정 사항:
  - 캔버스 크기를 원본 배경 이미지(3:2 비율)에 맞춰 1200x800으로 확대 (찌그러짐 방지)
  - 좌측 상단 파티클 원형 위치에 아바타 정밀 배치
  - 우측 하단 마법서 그림을 가리지 않도록 레이아웃 최적화
  - 역할별 색상/아이콘 제외, 골드 & 화이트 단일 테마 유지
"""

import io
import os
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 캔버스 설정 (배경 이미지 원본 비율에 맞춘 1200x800) ──
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 800
CORNER_RADIUS = 36

# ── 배경 이미지 설정 ──
IMG_DIR = "assets/images"
BG_IMAGE_NAME = "rank_bg.jpg"  # 원본 확장자에 맞게 변경 (jpg/png)

# ── 아바타 좌표 설정 (왼쪽 파티클 원의 중심점) ──
AVATAR_CENTER_X = 220
AVATAR_CENTER_Y = 310
AVATAR_DIAMETER = 240   # 원 안에 쏙 들어가는 크기

# ── 색상 정의 (단일 테마 - 매직 골드) ──
THEME_COLOR = (255, 210, 100)        # 파스텔 골드 (메인 강조색)
TEXT_WHITE = (255, 255, 255)
TEXT_LIGHT = (230, 230, 230)
TEXT_GRAY = (180, 180, 185)
TEXT_DIM = (140, 140, 150)

# 프로그레스 바 배경 (어두운 브라운/블랙)
MAIN_BAR_BG = (40, 35, 30)

# 글래스모피즘 색상 (가독성을 위해 배경을 조금 더 어둡게 누름)
GLASS_FILL = (0, 0, 0, 140)          
GLASS_STROKE = (255, 210, 100, 60)   
GLASS_BAR_BG = (0, 0, 0, 160)        
GLASS_BLUR_RADIUS = 15

# ── 파일 경로 설정 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")
IMG_DIR = os.path.join(BASE_DIR, "assets", "images")

# 폰트 파일
FONT_BOLD_PATH = os.path.join(FONT_DIR, "Pretendard-Bold.ttf")
FONT_MEDIUM_PATH = os.path.join(FONT_DIR, "Pretendard-Medium.ttf")


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}): {e}")
        return ImageFont.load_default()

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
        # 1200x800 해상도에 맞게 폰트 크기 대폭 상향
        self.font_name = _load_font(FONT_BOLD_PATH, 52)
        self.font_exp_val = _load_font(FONT_BOLD_PATH, 34)
        self.font_exp_lbl = _load_font(FONT_MEDIUM_PATH, 24)
        self.font_level = _load_font(FONT_BOLD_PATH, 32)
        self.font_progress = _load_font(FONT_MEDIUM_PATH, 22)
        self.font_badge = _load_font(FONT_BOLD_PATH, 22) 
        self.font_sub_label = _load_font(FONT_MEDIUM_PATH, 20)
        self.font_sub_val = _load_font(FONT_MEDIUM_PATH, 18)
        self.font_rank = _load_font(FONT_BOLD_PATH, 18)

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        # ── 1. 배경 이미지 로드 및 핏 ──
        bg_path = os.path.join(IMG_DIR, BG_IMAGE_NAME)
        try:
            original_bg = Image.open(bg_path).convert('RGBA')
            # 1200x800 비율에 꽉 차게 리사이즈 (찌그러짐 방지)
            canvas = ImageOps.fit(original_bg, (CANVAS_WIDTH, CANVAS_HEIGHT), method=Image.LANCZOS)
            
            # 별빛이 텍스트를 가리지 않도록 전체적으로 아주 살짝만 어둡게 오버레이
            dim_overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 50))
            canvas = Image.alpha_composite(canvas, dim_overlay)
        except Exception as e:
            logger.error(f"배경 이미지 로드 실패: {e}")
            canvas = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), (30, 25, 20, 255))

        # ── 2. 아바타 그리기 (파티클 원 위치) ──
        avatar_x = int(AVATAR_CENTER_X - AVATAR_DIAMETER // 2)
        avatar_y = int(AVATAR_CENTER_Y - AVATAR_DIAMETER // 2)
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, AVATAR_DIAMETER)

        # ── 3. 역할 배지 (아바타 바로 밑) ──
        badge_cx = AVATAR_CENTER_X
        badge_y = avatar_y + AVATAR_DIAMETER + 25
        self._draw_simple_badge(canvas, badge_cx, badge_y, data.role_display)

        # ── 4. 정보 영역 (아바타 우측) ──
        info_x = 450
        info_y = 200
        draw = ImageDraw.Draw(canvas)

        # 이름
        draw.text((info_x, info_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)
        info_y += 75

        # 총 다공 
        exp_val = f"{data.total_exp:,}"
        exp_lbl = " 다공"
        draw.text((info_x, info_y), exp_val, fill=THEME_COLOR, font=self.font_exp_val)
        val_bbox = draw.textbbox((0, 0), exp_val, font=self.font_exp_val)
        val_w = val_bbox[2] - val_bbox[0]
        draw.text((info_x + val_w, info_y + 8), exp_lbl, fill=TEXT_GRAY, font=self.font_exp_lbl)
        info_y += 65

        # 메인 진행 바 (상단)
        bar_width = CANVAS_WIDTH - info_x - 120  # 우측 여백 확보 (리본 피하기)
        if data.next_role_display:
            progress_label = f"다음 경지 : {data.next_role_display}"
        else:
            progress_label = "최고 경지 달성"
        
        # 라벨 & 퍼센트
        draw.text((info_x, info_y), progress_label, fill=TEXT_DIM, font=self.font_progress)
        pct_text = f"{data.role_progress_pct:.1f}%"
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text((info_x + bar_width - pct_w, info_y), pct_text, fill=THEME_COLOR, font=self.font_progress)
        
        info_y += 35
        # 진행 바 그리기
        self._draw_bar(draw, info_x, info_y, bar_width, 12, MAIN_BAR_BG, data.role_progress_pct, THEME_COLOR)

        # ── 5. 하단 서브 스탯 (우측 책을 가리지 않게 좌/중앙 배치) ──
        sub_y = 580
        box_width = 340
        
        # 채팅 레벨 (Box 1) - X: 150
        self._draw_glass_stat_box(
            canvas, 150, sub_y, box_width,
            "채팅 레벨", data.chat_level_info.level, data.chat_level_info.progress_pct,
            data.chat_level_info.current_xp, data.chat_level_info.required_xp,
            data.chat_rank
        )

        # 음성 레벨 (Box 2) - X: 520 (책 그림 시작 전인 860 부근에서 끝남)
        self._draw_glass_stat_box(
            canvas, 520, sub_y, box_width,
            "음성 레벨", data.voice_level_info.level, data.voice_level_info.progress_pct,
            data.voice_level_info.current_xp, data.voice_level_info.required_xp,
            data.voice_rank
        )

        # ── 6. 마무리 ──
        output = self._apply_rounded_corners(canvas)

        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 그리기 헬퍼 함수들
    # ────────────────────────────────────────────────

    def _draw_avatar(self, canvas, avatar_bytes, x, y, size):
        """아바타를 원형으로 그리고, 얇고 세련된 테마색 테두리를 두릅니다."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
            mask = _make_circle_mask(size)

            draw = ImageDraw.Draw(canvas)
            stroke = 3
            
            # 테두리
            ox, oy = x - stroke, y - stroke
            outer_size = size + stroke * 2
            draw.ellipse([(ox, oy), (ox + outer_size - 1, oy + outer_size - 1)], fill=THEME_COLOR)

            # 아바타
            canvas.paste(avatar_img, (x, y), mask)
        except Exception:
            pass

    def _draw_simple_badge(self, canvas, cx, cy, text):
        """배경에 잘 어울리는 클래식한 텍스트 배지"""
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(badge_layer)

        bbox = draw.textbbox((0, 0), text, font=self.font_badge)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = 24
        pad_y = 8

        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        bx = cx - bw // 2
        by = cy

        draw.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=(0, 0, 0, 180), 
            outline=THEME_COLOR, 
            width=2
        )

        text_x = bx + (bw - tw) // 2
        text_y = by + (bh - th) // 2 - 3 
        draw.text((text_x, text_y), text, fill=THEME_COLOR, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    def _draw_bar(self, draw, x, y, w, h, bg_color, pct, fill_color):
        """진행 바 렌더링"""
        draw.rounded_rectangle([(x, y), (x + w, y + h)], h // 2, fill=bg_color)
        fill_w = max(int(w * (pct / 100.0)), h)
        if pct > 0:
            draw.rounded_rectangle([(x, y), (x + fill_w, y + h)], h // 2, fill=fill_color)

    def _draw_glass_stat_box(self, canvas, x, y, width, label, level, progress, curr_xp, req_xp, rank):
        """하단 스탯 박스"""
        box_height = 130
        box_radius = 20

        # 배경 블러
        box_region = canvas.crop((x, y, x + width, y + box_height))
        blurred = box_region.filter(ImageFilter.GaussianBlur(radius=GLASS_BLUR_RADIUS))
        blur_mask = _make_rounded_rect_mask((width, box_height), box_radius)
        blur_layer = Image.new('RGBA', (width, box_height), (0, 0, 0, 0))
        blur_layer.paste(blurred, mask=blur_mask)
        canvas.paste(Image.alpha_composite(canvas.crop((x, y, x + width, y + box_height)), blur_layer), (x, y))

        # 오버레이 
        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle([(x, y), (x + width, y + box_height)], box_radius, fill=GLASS_FILL, outline=GLASS_STROKE, width=2)

        pad_x = 24

        # 라벨 & 순위
        od.text((x + pad_x, y + 24), label, fill=TEXT_LIGHT, font=self.font_sub_label)
        if rank:
            rank_text = f"{rank}위"
            lbl_w = od.textbbox((0, 0), label, font=self.font_sub_label)[2]
            od.text((x + pad_x + lbl_w + 12, y + 26), rank_text, fill=THEME_COLOR, font=self.font_rank)

        # 레벨
        lv_text = f"Lv.{level}"
        lv_w = od.textbbox((0, 0), lv_text, font=self.font_level)[2]
        od.text((x + width - pad_x - lv_w, y + 20), lv_text, fill=TEXT_WHITE, font=self.font_level)

        # 바
        bar_y = y + 75
        self._draw_bar(od, x + pad_x, bar_y, width - pad_x * 2, 8, GLASS_BAR_BG, progress, THEME_COLOR)

        # XP / 퍼센트
        xp_text = f"{curr_xp:,}/{req_xp:,}"
        text_y = bar_y + 18
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