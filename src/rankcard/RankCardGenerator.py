"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

수정 사항:
  - 역할별 색상/아이콘 제거 (단일 테마 적용)
  - 텍스트 위주의 심플하고 클래식한 디자인
  - 배경 이미지(rank_bg.png/jpg) 적용
"""

import io
import os
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 2배수 렌더링 스케일 (고화질) ──
S = 2

# ── 캔버스 설정 ──
OUTPUT_WIDTH = 860
OUTPUT_HEIGHT = 280

CANVAS_WIDTH = OUTPUT_WIDTH * S
CANVAS_HEIGHT = OUTPUT_HEIGHT * S
CORNER_RADIUS = 24 * S

# ── 배경 이미지 설정 ──
# assets/images/ 폴더 내의 배경 파일명
IMG_DIR = "assets/images"
BG_IMAGE_NAME = "rank_bg.png"  # .jpg라면 수정하세요

# ── 좌표 설정 (배경 이미지의 '빛나는 원' 위치에 맞춤) ──
AVATAR_CENTER_X = 220 * S
AVATAR_CENTER_Y = 100 * S
AVATAR_DIAMETER = 130 * S

# ── 색상 정의 (단일 테마) ──
# 배경과 어울리는 고급스러운 골드 톤을 메인 테마로 잡았습니다.
THEME_COLOR = (255, 210, 100)        # 파스텔 골드 (메인 강조색)
TEXT_WHITE = (255, 255, 255)
TEXT_LIGHT = (230, 230, 230)
TEXT_GRAY = (170, 170, 175)
TEXT_DIM = (130, 130, 140)

# 프로그레스 바 배경 (아주 어두운 갈색/검정)
MAIN_BAR_BG = (40, 35, 30)

# 글래스모피즘 색상
GLASS_FILL = (0, 0, 0, 100)          # 박스 배경 (어둡게)
GLASS_STROKE = (255, 210, 100, 50)   # 테두리 (은은한 골드)
GLASS_BAR_BG = (0, 0, 0, 150)        # 바 배경
GLASS_BLUR_RADIUS = 10 * S

# ── 파일 경로 설정 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")
IMG_DIR = os.path.join(BASE_DIR, "assets", "images")

# 폰트 파일 (Pretendard 유지)
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
        # 폰트 로드
        self.font_name = _load_font(FONT_BOLD_PATH, 36 * S)
        self.font_exp_val = _load_font(FONT_BOLD_PATH, 22 * S)
        self.font_exp_lbl = _load_font(FONT_MEDIUM_PATH, 16 * S)
        self.font_level = _load_font(FONT_BOLD_PATH, 20 * S)
        self.font_progress = _load_font(FONT_MEDIUM_PATH, 14 * S)
        self.font_badge = _load_font(FONT_BOLD_PATH, 15 * S) # 배지 폰트
        self.font_sub_label = _load_font(FONT_MEDIUM_PATH, 13 * S)
        self.font_sub_val = _load_font(FONT_MEDIUM_PATH, 12 * S)
        self.font_rank = _load_font(FONT_BOLD_PATH, 12 * S)

    def generate(self, data: RankCardData, avatar_bytes: bytes) -> io.BytesIO:
        # ── 1. 배경 이미지 로드 ──
        bg_path = os.path.join(IMG_DIR, BG_IMAGE_NAME)
        try:
            original_bg = Image.open(bg_path).convert('RGBA')
            canvas = ImageOps.fit(original_bg, (CANVAS_WIDTH, CANVAS_HEIGHT), method=Image.LANCZOS)
            
            # 배경 딤처리 (텍스트 가독성 확보)
            dim_overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 30))
            canvas = Image.alpha_composite(canvas, dim_overlay)
        except Exception as e:
            logger.error(f"배경 이미지 로드 실패: {e}")
            canvas = Image.new('RGBA', (CANVAS_WIDTH, CANVAS_HEIGHT), (30, 25, 20, 255))

        # ── 2. 아바타 그리기 ──
        avatar_x = int(AVATAR_CENTER_X - AVATAR_DIAMETER // 2)
        avatar_y = int(AVATAR_CENTER_Y - AVATAR_DIAMETER // 2)
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, AVATAR_DIAMETER)

        # ── 3. 역할 배지 (텍스트만 깔끔하게) ──
        badge_cx = int(AVATAR_CENTER_X)
        badge_y = avatar_y + AVATAR_DIAMETER + 16 * S
        self._draw_simple_badge(canvas, badge_cx, badge_y, data.role_display)

        # ── 4. 정보 영역 ──
        info_x = int(AVATAR_CENTER_X + AVATAR_DIAMETER // 2 + 40 * S)
        info_y = 45 * S
        draw = ImageDraw.Draw(canvas)

        # 이름
        draw.text((info_x, info_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)
        info_y += 44 * S

        # 총 다공 (테마 컬러 강조)
        exp_val = f"{data.total_exp:,}"
        exp_lbl = " 다공"
        draw.text((info_x, info_y), exp_val, fill=THEME_COLOR, font=self.font_exp_val)
        val_bbox = draw.textbbox((0, 0), exp_val, font=self.font_exp_val)
        val_w = val_bbox[2] - val_bbox[0]
        draw.text((info_x + val_w, info_y + 4 * S), exp_lbl, fill=TEXT_GRAY, font=self.font_exp_lbl)
        info_y += 38 * S

        # 메인 진행 바
        bar_width = CANVAS_WIDTH - info_x - 60 * S
        if data.next_role_display:
            progress_label = f"다음 경지 : {data.next_role_display}"
        else:
            progress_label = "최고 경지 달성"
        
        # 라벨
        draw.text((info_x, info_y), progress_label, fill=TEXT_DIM, font=self.font_progress)
        
        # 퍼센트
        pct_text = f"{data.role_progress_pct:.1f}%"
        pct_bbox = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        pct_w = pct_bbox[2] - pct_bbox[0]
        draw.text(
            (info_x + bar_width - pct_w, info_y),
            pct_text, fill=THEME_COLOR, font=self.font_progress
        )
        info_y += 20 * S

        # 진행 바 그리기 (단일 테마 컬러)
        self._draw_bar(draw, info_x, info_y, bar_width, 8 * S, MAIN_BAR_BG, data.role_progress_pct, THEME_COLOR)

        # ── 5. 하단 서브 스탯 (글래스 박스) ──
        sub_y = 186 * S
        available_width = CANVAS_WIDTH - info_x - 120 * S
        sub_box_width = (available_width - 16 * S) // 2

        # 채팅 레벨
        self._draw_glass_stat_box(
            canvas, info_x, sub_y, sub_box_width,
            "채팅 레벨", data.chat_level_info.level, data.chat_level_info.progress_pct,
            data.chat_level_info.current_xp, data.chat_level_info.required_xp,
            data.chat_rank
        )

        # 음성 레벨
        self._draw_glass_stat_box(
            canvas, info_x + sub_box_width + 16 * S, sub_y, sub_box_width,
            "음성 레벨", data.voice_level_info.level, data.voice_level_info.progress_pct,
            data.voice_level_info.current_xp, data.voice_level_info.required_xp,
            data.voice_rank
        )

        # ── 6. 마무리 및 리사이즈 ──
        output = self._apply_rounded_corners(canvas)
        output = output.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)

        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 그리기 헬퍼 함수들
    # ────────────────────────────────────────────────

    def _draw_avatar(self, canvas, avatar_bytes, x, y, size):
        """아바타를 원형으로 그리고, 테마색 테두리를 두릅니다."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
            mask = _make_circle_mask(size)

            draw = ImageDraw.Draw(canvas)
            gap = 4 * S
            stroke = 2 * S
            
            # 테두리 (Theme Color)
            ox = x - stroke
            oy = y - stroke
            outer_size = size + stroke * 2
            draw.ellipse([(ox, oy), (ox + outer_size - 1, oy + outer_size - 1)], fill=THEME_COLOR)

            # 아바타
            canvas.paste(avatar_img, (x, y), mask)
        except Exception:
            pass

    def _draw_simple_badge(self, canvas, cx, cy, text):
        """아이콘 없이 텍스트만 있는 깔끔한 배지를 그립니다."""
        # 임시 레이어
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(badge_layer)

        # 텍스트 크기 측정
        bbox = draw.textbbox((0, 0), text, font=self.font_badge)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = 20 * S  # 좌우 여백 넉넉하게
        pad_y = 6 * S

        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        
        # 위치 (중앙 정렬)
        bx = cx - bw // 2
        by = cy

        # 배경 (어두운 반투명 + 테마색 테두리)
        draw.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=(0, 0, 0, 160), 
            outline=THEME_COLOR, 
            width=2
        )

        # 텍스트 그리기 (중앙)
        text_x = bx + (bw - tw) // 2
        text_y = by + (bh - th) // 2 - (2 * S) # 미세 높이 보정
        draw.text((text_x, text_y), text, fill=THEME_COLOR, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    def _draw_bar(self, draw, x, y, w, h, bg_color, pct, fill_color):
        """프로그레스 바 그리기 공통 함수"""
        draw.rounded_rectangle([(x, y), (x + w, y + h)], h // 2, fill=bg_color)
        fill_w = max(int(w * (pct / 100.0)), h)
        if pct > 0:
            draw.rounded_rectangle([(x, y), (x + fill_w, y + h)], h // 2, fill=fill_color)

    def _draw_glass_stat_box(self, canvas, x, y, width, label, level, progress, curr_xp, req_xp, rank):
        """하단 스탯 박스 (색상 인자 제거 -> 테마색 사용)"""
        box_height = 70 * S
        box_radius = 12 * S

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
        od.rounded_rectangle([(x, y), (x + width, y + box_height)], box_radius, fill=GLASS_FILL, outline=GLASS_STROKE, width=1 * S)

        pad_x = 16 * S

        # 라벨 & 순위
        od.text((x + pad_x, y + 14 * S), label, fill=TEXT_LIGHT, font=self.font_sub_label)
        if rank:
            rank_text = f"{rank}위"
            lbl_w = od.textbbox((0, 0), label, font=self.font_sub_label)[2]
            od.text((x + pad_x + lbl_w + 6 * S, y + 15 * S), rank_text, fill=THEME_COLOR, font=self.font_rank)

        # 레벨
        lv_text = f"Lv.{level}"
        lv_w = od.textbbox((0, 0), lv_text, font=self.font_level)[2]
        od.text((x + width - pad_x - lv_w, y + 12 * S), lv_text, fill=TEXT_WHITE, font=self.font_level)

        # 바
        bar_y = y + 40 * S
        self._draw_bar(od, x + pad_x, bar_y, width - pad_x * 2, 6 * S, GLASS_BAR_BG, progress, THEME_COLOR)

        # XP 텍스트
        xp_text = f"{curr_xp:,}/{req_xp:,}"
        text_y = bar_y + 10 * S
        od.text((x + pad_x, text_y), xp_text, fill=TEXT_DIM, font=self.font_sub_val)

        # 퍼센트
        pct_text = f"{progress:.1f}%"
        pct_w = od.textbbox((0, 0), pct_text, font=self.font_sub_val)[2]
        od.text((x + width - pad_x - pct_w, text_y), pct_text, fill=TEXT_GRAY, font=self.font_sub_val)

        canvas.paste(Image.alpha_composite(canvas, overlay))

    def _apply_rounded_corners(self, canvas: Image.Image) -> Image.Image:
        mask = _make_rounded_rect_mask(canvas.size, CORNER_RADIUS)
        output = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        output.paste(canvas, mask=mask)
        return output