"""
랭크 카드 이미지 생성 모듈입니다.
Pillow를 사용하여 유저의 레벨/경지 정보를 시각화한 카드 이미지를 생성합니다.

수정 사항:
  - 배경 이미지(rank_bg.png)의 자체 디자인(테두리, 아바타 링, 박스)을 그대로 활용하도록 불필요한 그래픽 렌더링 제거.
  - 배경 이미지의 해상도에 구애받지 않도록 비율(%) 기반 좌표 시스템 적용.
  - 시안과 동일한 화살표(>) 모양의 프로그레스 바 디자인 적용.
  - 텍스트 폰트 크기, 색상, 배치(좌/우 정렬 등) 시안과 동일하게 동기화.
  - 2배수 렌더링 유지로 최상의 텍스트 선명도 보장.
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
FONT_BOLD_PATH = "assets/fonts/Pretendard-Bold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/Pretendard-Medium.ttf"

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
        # 폰트 사이즈 (비율 기반 캔버스 기준이므로, 기본 1000px 너비라고 가정하고 스케일링)
        self.base_font_scale = S
        self.font_name = _load_font(FONT_BOLD_PATH, int(42 * self.base_font_scale))
        self.font_exp_val = _load_font(FONT_MEDIUM_PATH, int(22 * self.base_font_scale))
        self.font_exp_lbl = _load_font(FONT_MEDIUM_PATH, int(22 * self.base_font_scale))
        self.font_next_role = _load_font(FONT_MEDIUM_PATH, int(18 * self.base_font_scale))
        
        self.font_badge = _load_font(FONT_BOLD_PATH, int(18 * self.base_font_scale))
        
        self.font_box_label = _load_font(FONT_MEDIUM_PATH, int(18 * self.base_font_scale))
        self.font_box_rank = _load_font(FONT_MEDIUM_PATH, int(16 * self.base_font_scale))
        self.font_box_level = _load_font(FONT_BOLD_PATH, int(28 * self.base_font_scale))
        self.font_box_val = _load_font(FONT_MEDIUM_PATH, int(16 * self.base_font_scale))

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

        # ── 좌표 비율 정의 (배경 이미지 해상도에 맞춰 자동 계산) ──
        # rank_bg.jpg 이미지의 시각적 요소 위치를 백분율(%)로 측정한 값입니다.
        # 위치가 미세하게 안 맞는다면 이 퍼센트 값들을 소수점 단위로 조절해 주세요.
        POS = {
            'avatar_cx': 0.165,  'avatar_cy': 0.360,  'avatar_radius': 0.106,
            'badge_y': 0.550,
            'info_x': 0.305,     
            'name_y': 0.220,     'exp_y': 0.300,      'next_role_y': 0.360,
            'main_bar_y': 0.420, 'main_bar_w': 0.600, 'main_bar_h': 0.025,
            'box1_x': 0.305,     'box2_x': 0.615,     'box_y': 0.685,
            'box_w': 0.290,      'box_h': 0.180
        }

        # ── 1. 아바타 ──
        avatar_r = int(CANVAS_WIDTH * POS['avatar_radius'])
        avatar_size = avatar_r * 2
        avatar_x = int(CANVAS_WIDTH * POS['avatar_cx']) - avatar_r
        avatar_y = int(CANVAS_HEIGHT * POS['avatar_cy']) - avatar_r
        self._draw_avatar(canvas, avatar_bytes, avatar_x, avatar_y, avatar_size)

        # ── 2. 배지 ──
        badge_cx = int(CANVAS_WIDTH * POS['avatar_cx'])
        badge_y = int(CANVAS_HEIGHT * POS['badge_y'])
        self._draw_badge(canvas, badge_cx, badge_y, f"★ {data.role_display}")

        # ── 3. 상단 텍스트 정보 ──
        info_x = int(CANVAS_WIDTH * POS['info_x'])
        
        # 이름
        name_y = int(CANVAS_HEIGHT * POS['name_y'])
        draw.text((info_x, name_y), data.user_name, fill=TEXT_WHITE, font=self.font_name)

        # 총 다공
        exp_y = int(CANVAS_HEIGHT * POS['exp_y'])
        exp_val = f"{data.total_exp:,}"
        draw.text((info_x, exp_y), exp_val, fill=TEXT_LIGHT, font=self.font_exp_val)
        val_w = draw.textbbox((0, 0), exp_val, font=self.font_exp_val)[2]
        draw.text((info_x + val_w + 8 * S, exp_y), "다공", fill=TEXT_GRAY, font=self.font_exp_lbl)

        # 다음 경지
        next_y = int(CANVAS_HEIGHT * POS['next_role_y'])
        next_text = f"다음 경지 : {data.next_role_display}" if data.next_role_display else "최고 경지 달성"
        draw.text((info_x, next_y), next_text, fill=TEXT_GRAY, font=self.font_next_role)

        # ── 4. 메인 진행 바 ──
        main_bar_y = int(CANVAS_HEIGHT * POS['main_bar_y'])
        main_bar_w = int(CANVAS_WIDTH * POS['main_bar_w'])
        main_bar_h = int(CANVAS_HEIGHT * POS['main_bar_h'])

        # 메인 진행 % 텍스트 (바 우측 상단)
        pct_text = f"{data.role_progress_pct:.1f}%"
        pct_w = draw.textbbox((0, 0), pct_text, font=self.font_box_val)[2]
        draw.text(
            (info_x + main_bar_w - pct_w, next_y), # 다음 경지와 같은 Y선상 우측
            pct_text, fill=THEME_COLOR_MAIN, font=self.font_box_val
        )

        self._draw_angled_progress_bar(
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
        """테두리 없이 아바타를 원형으로 잘라 배경의 기존 링 안에 배치합니다."""
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
            mask = _make_circle_mask(size)
            canvas.paste(avatar_img, (x, y), mask)
        except Exception as e:
            logger.error(f"아바타 로드 실패: {e}")

    def _draw_badge(self, canvas: Image.Image, cx: int, cy: int, text: str):
        """시안에 맞춘 다크 배경 + 얇은 골드 테두리 배지"""
        badge_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge_layer)

        text_bbox = bd.textbbox((0, 0), text, font=self.font_badge)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        pad_x = 20 * S
        pad_y = 8 * S
        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        bx, by = cx - bw // 2, cy

        # 배경 및 테두리 (시안처럼 어두운 배경에 얇은 테두리)
        bd.rounded_rectangle(
            [(bx, by), (bx + bw, by + bh)],
            radius=bh // 2,
            fill=(20, 15, 10, 220),       # 어두운 반투명 배경
            outline=THEME_COLOR_MAIN,     # 골드 테두리
            width=max(1, 1 * S)
        )

        text_x = bx + pad_x
        text_y = by + pad_y - (2 * S) # 시각적 중앙 정렬 보정
        bd.text((text_x, text_y), text, fill=TEXT_WHITE, font=self.font_badge)

        canvas.paste(Image.alpha_composite(canvas, badge_layer))

    # ────────────────────────────────────────────────
    # 화살표 모양 프로그레스 바
    # ────────────────────────────────────────────────
    @staticmethod
    def _draw_angled_progress_bar(
        draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        progress: float
    ):
        """시안에 있는 우측이 뾰족한(>) 화살표 모양의 프로그레스 바를 그립니다."""
        # 1. 배경 바 (어두운 회색, 기본 라운드)
        draw.rounded_rectangle([(x, y), (x + width, y + height)], height // 2, fill=THEME_COLOR_BAR_BG)
        
        # 2. 진행 바 (골드, 끝부분 화살표 처리)
        if progress <= 0:
            return
            
        fill_w = int(width * (progress / 100.0))
        slope = height  # 뾰족한 부분의 너비
        
        if fill_w < slope * 2:
            # 게이지가 너무 작을 때는 그냥 둥근 형태로 표시
            draw.rounded_rectangle([(x, y), (x + max(fill_w, height), y + height)], height // 2, fill=THEME_COLOR_MAIN)
        else:
            # a. 왼쪽 반원 (시작 부분 둥글게)
            draw.pieslice([(x, y), (x + height, y + height)], 90, 270, fill=THEME_COLOR_MAIN)
            
            # b. 중간 직사각형
            rect_w = fill_w - (height // 2) - slope
            if rect_w > 0:
                draw.rectangle([(x + height // 2, y), (x + height // 2 + rect_w, y + height)], fill=THEME_COLOR_MAIN)
                
            # c. 오른쪽 뾰족한 폴리곤 (화살표 끝)
            tip_start_x = x + height // 2 + max(0, rect_w)
            draw.polygon([
                (tip_start_x, y), 
                (tip_start_x + slope, y + height // 2), 
                (tip_start_x, y + height)
            ], fill=THEME_COLOR_MAIN)

    # ────────────────────────────────────────────────
    # 하단 스탯 박스 콘텐츠 (배경 제외, 텍스트/바만)
    # ────────────────────────────────────────────────
    def _draw_stat_box_content(
        self, draw: ImageDraw.ImageDraw,
        x: int, y: int, width: int, height: int,
        label: str, level: int, progress: float,
        current_xp: int, required_xp: int,
        rank: Optional[int], total_users: int
    ):
        """배경 이미지에 이미 그려진 박스 영역 '안에' 텍스트와 게이지 바를 배치합니다."""
        
        # 박스 내부 여백
        pad_x = 24 * S
        inner_y = y + int(height * 0.15) # 상단 여백
        
        # [상단 좌측] 라벨 (예: "채팅 레벨") 및 순위
        draw.text((x + pad_x, inner_y), label, fill=TEXT_LIGHT, font=self.font_box_label)
        
        if rank is not None:
            rank_text = f"#{rank} / {total_users}"
            label_w = draw.textbbox((0, 0), label, font=self.font_box_label)[2]
            draw.text((x + pad_x + label_w + 12 * S, inner_y + 2 * S), rank_text, fill=TEXT_DARK_GOLD, font=self.font_box_rank)

        # [상단 우측] 레벨 (예: "Lv. 6")
        level_text = f"Lv. {level}"
        level_w = draw.textbbox((0, 0), level_text, font=self.font_box_level)[2]
        draw.text((x + width - pad_x - level_w, inner_y - 8 * S), level_text, fill=TEXT_WHITE, font=self.font_box_level)

        # [중앙] 프로그레스 바
        bar_y = inner_y + int(height * 0.4)
        bar_w = width - (pad_x * 2)
        bar_h = int(height * 0.15)
        self._draw_angled_progress_bar(draw, x + pad_x, bar_y, bar_w, bar_h, progress)

        # [하단 좌측/우측] XP 및 퍼센트
        bottom_y = bar_y + bar_h + 12 * S
        xp_text = f"{current_xp:,} / {required_xp:,}"
        draw.text((x + pad_x, bottom_y), xp_text, fill=TEXT_GRAY, font=self.font_box_val)

        pct_text = f"{progress:.1f}%"
        pct_w = draw.textbbox((0, 0), pct_text, font=self.font_box_val)[2]
        draw.text((x + width - pad_x - pct_w, bottom_y), pct_text, fill=TEXT_GRAY, font=self.font_box_val)