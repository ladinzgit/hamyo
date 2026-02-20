"""
비몽책방(Dream Bookstore) 테마 랭크 카드 생성 모듈
몽환적인 딥 네이비 배경, 웜 베이지 조명, 책갈피 포인트, 별가루 이펙트가 적용되었습니다.

2배수 렌더링 기법 적용:
  내부적으로 2배 크기(1720x560)로 렌더링한 뒤,
  최종 출력 시 원래 크기(860x280)로 LANCZOS 다운스케일하여
  폰트와 그래픽의 선명도를 극대화합니다.
"""

import io
import os
import random
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# 기존 서비스에서 사용하는 데이터 클래스 임포트
from src.rankcard.RankCardService import RankCardData

logger = logging.getLogger(__name__)

# ── 2배수 렌더링 스케일 ──
S = 2

# ── 캔버스 설정 (논리 크기) ──
OUTPUT_WIDTH = 860
OUTPUT_HEIGHT = 280

CANVAS_WIDTH = OUTPUT_WIDTH * S    # 1720
CANVAS_HEIGHT = OUTPUT_HEIGHT * S  # 560
CORNER_RADIUS = 24 * S

# ── 테마 색상 정의 (비몽책방 테마) ──
BG_NAVY = (15, 20, 35, 255)          # 딥 네이비 (잉크)
GLOW_BEIGE = (235, 215, 175)         # 웜 베이지 (종이 조명)
RIBBON_RED = (140, 45, 55, 240)      # 딥 버건디 (책갈피)

TEXT_TITLE = (245, 240, 230, 255)    # 아주 밝은 베이지 (주요 텍스트)
TEXT_SUB = (160, 170, 190, 255)      # 은은한 블루 그레이 (서브 텍스트)
TEXT_GOLD = (212, 175, 55, 255)      # 앤틱 골드 (강조 텍스트)

BAR_BG = (30, 35, 55, 180)           # 프로그레스 바 배경
BAR_VOICE = (212, 175, 55, 255)      # 음성 바 (골드)
BAR_CHAT = (130, 180, 220, 255)      # 채팅 바 (몽환적인 스카이블루)


class RankCardGenerator:
    def __init__(self):
        # 1순위: 폴더 내 폰트 / 2순위: 시스템 기본 폰트
        self.primary_font_main = "assets/fonts/Pretendard-Medium.ttf"
        self.primary_font_bold = "assets/fonts/Pretendard-Bold.ttf"
        
        self.fallback_fonts = [
            "malgun.ttf",       # Windows 맑은 고딕
            "malgunbd.ttf",     # Windows 맑은 고딕 볼드
            "NanumGothic.ttf",  # Linux/Windows 나눔고딕
            "AppleGothic.ttf",  # Mac 애플고딕
            "Arial.ttf",        
            "DejaVuSans.ttf"    
        ]
        
        # [수정됨] 좁은 공간에 텍스트가 짓눌리지 않도록 폰트 크기 최적화
        self.font_name = self._load_font(self.primary_font_bold, 40 * S)
        self.font_role = self._load_font(self.primary_font_main, 20 * S)
        self.font_label = self._load_font(self.primary_font_bold, 18 * S)
        self.font_value = self._load_font(self.primary_font_main, 16 * S)
        self.font_level = self._load_font(self.primary_font_bold, 32 * S)

    def _load_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            for fallback in self.fallback_fonts:
                try:
                    return ImageFont.truetype(fallback, size)
                except OSError:
                    continue
            logger.warning(f"폰트를 찾을 수 없습니다: {font_path}")
            return ImageFont.load_default()

    async def generate(self, data: 'RankCardData', avatar_bytes: Optional[bytes] = None) -> io.BytesIO:
        # 1. 배경 레이어
        base_img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base_img)
        draw.rounded_rectangle((0, 0, CANVAS_WIDTH, CANVAS_HEIGHT), radius=CORNER_RADIUS, fill=BG_NAVY)

        # 2. 웜 베이지 조명 (Glow)
        self._draw_soft_glow(base_img)

        # 3. 오픈북 워터마크
        self._draw_book_watermark(base_img)

        # 4. 별가루 (미세 스파클)
        user_id_seed = getattr(data, 'user_id', 12345)
        self._draw_sparkles(base_img, seed=user_id_seed) 

        main_draw = ImageDraw.Draw(base_img)

        # 5. 오른쪽 상단 책갈피
        self._draw_bookmark(main_draw)

        # 6. 아바타 렌더링 (중앙 정렬 위치로 조정)
        avatar_size = 160 * S
        avatar_x = 50 * S
        avatar_y = (CANVAS_HEIGHT - avatar_size) // 2  # 세로 중앙 정렬 (60 * S)
        
        if avatar_bytes:
            self._draw_avatar(base_img, avatar_bytes, avatar_x, avatar_y, avatar_size)
        else:
            main_draw.ellipse([avatar_x, avatar_y, avatar_x+avatar_size, avatar_y+avatar_size], fill=(40, 45, 60, 255))

        # 7. 텍스트 레이아웃 설정 (비율에 맞춰 Y 좌표 전면 재배치)
        text_start_x = avatar_x + avatar_size + 40 * S
        bar_width = CANVAS_WIDTH - text_start_x - (50 * S)  # 우측 여백 50
        
        name_y = 50 * S
        role_y = 95 * S
        voice_y = 135 * S
        chat_y = 205 * S
        
        # 유저 이름
        main_draw.text((text_start_x, name_y), getattr(data, 'name', 'Unknown'), fill=TEXT_TITLE, font=self.font_name)
        
        # 칭호/역할
        role_display = getattr(data, 'role_display', '허브')
        role_text = f"✨ 칭호 : {role_display}"
        main_draw.text((text_start_x, role_y), role_text, fill=TEXT_GOLD, font=self.font_role)

        # 8. 진행 바 영역 (음성 & 채팅) - 캔버스 밖으로 나가지 않도록 좌표 수정
        self._draw_stat_section(
            main_draw, "음성", 
            getattr(data, 'voice_rank', None), getattr(data, 'total_users', 0), 
            getattr(data, 'voice_level', 0), getattr(data, 'voice_curr_xp', 0), 
            getattr(data, 'voice_req_xp', 1), getattr(data, 'voice_xp', 0), getattr(data, 'voice_prog', 0.0),
            text_start_x, voice_y, bar_width, BAR_VOICE
        )

        self._draw_stat_section(
            main_draw, "채팅", 
            getattr(data, 'chat_rank', None), getattr(data, 'total_users', 0), 
            getattr(data, 'chat_level', 0), getattr(data, 'chat_curr_xp', 0), 
            getattr(data, 'chat_req_xp', 1), getattr(data, 'chat_xp', 0), getattr(data, 'chat_prog', 0.0),
            text_start_x, chat_y, bar_width, BAR_CHAT
        )

        # 9. 최종 다운스케일링
        final_img = base_img.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        final_img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def _draw_soft_glow(self, base_img: Image.Image):
        glow_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        
        cx, cy = 400 * S, CANVAS_HEIGHT // 2
        max_radius = 450 * S
        
        for i in range(max_radius, 0, -5 * S):
            alpha = int(15 * (1 - (i / max_radius)))
            color = (*GLOW_BEIGE, alpha)
            glow_draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=color)
            
        base_img.alpha_composite(glow_layer)

    def _draw_book_watermark(self, base_img: Image.Image):
        watermark_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        cx = CANVAS_WIDTH - 250 * S
        cy = CANVAS_HEIGHT // 2 + 50 * S
        w = 200 * S
        h = 80 * S
        
        color = (*GLOW_BEIGE, 10)
        line_w = 3 * S
        
        # 책 워터마크 그리기
        draw.arc([cx - w, cy - h, cx, cy + h], 180, 270, fill=color, width=line_w)
        draw.arc([cx - w, cy, cx, cy + h * 2], 180, 270, fill=color, width=line_w)
        draw.line([cx - w, cy, cx - w, cy + h], fill=color, width=line_w)
        
        draw.arc([cx, cy - h, cx + w, cy + h], 270, 360, fill=color, width=line_w)
        draw.arc([cx, cy, cx + w, cy + h * 2], 270, 360, fill=color, width=line_w)
        draw.line([cx + w, cy, cx + w, cy + h], fill=color, width=line_w)
        
        draw.line([cx, cy - h, cx, cy + h], fill=color, width=line_w)

        base_img.alpha_composite(watermark_layer)

    def _draw_sparkles(self, base_img: Image.Image, seed: int):
        sparkle_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sparkle_layer)
        
        safe_seed = hash(seed) if isinstance(seed, str) else seed
        random.seed(safe_seed)
        
        for _ in range(35):
            x = random.randint(0, CANVAS_WIDTH)
            y = random.randint(0, CANVAS_HEIGHT)
            size = random.randint(1 * S, 3 * S)
            alpha = random.randint(50, 150)
            
            if random.random() > 0.5:
                draw.line([x-size, y, x+size, y], fill=(*GLOW_BEIGE, alpha), width=1*S)
                draw.line([x, y-size, x, y+size], fill=(*GLOW_BEIGE, alpha), width=1*S)
            else:
                draw.ellipse([x, y, x+size, y+size], fill=(*GLOW_BEIGE, alpha))
                
        base_img.alpha_composite(sparkle_layer)

    def _draw_bookmark(self, draw: ImageDraw.ImageDraw):
        # 책갈피 크기도 아담하게 조정하여 텍스트와 겹치지 않게 함
        ribbon_w = 40 * S
        ribbon_h = 100 * S
        x = CANVAS_WIDTH - 80 * S
        y = 0
        
        points = [
            (x, y),
            (x + ribbon_w, y),
            (x + ribbon_w, y + ribbon_h),
            (x + ribbon_w // 2, y + ribbon_h - 20 * S),
            (x, y + ribbon_h)
        ]
        draw.polygon(points, fill=RIBBON_RED)
        
        draw.line([x + 8*S, y + ribbon_h - 25*S, x + ribbon_w // 2, y + ribbon_h - 35*S], fill=TEXT_GOLD, width=2*S)
        draw.line([x + ribbon_w - 8*S, y + ribbon_h - 25*S, x + ribbon_w // 2, y + ribbon_h - 35*S], fill=TEXT_GOLD, width=2*S)

    def _draw_avatar(self, base_img: Image.Image, avatar_bytes: bytes, x: int, y: int, size: int):
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
            
            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            
            glow_size = size + 10 * S
            glow_x = x - 5 * S
            glow_y = y - 5 * S
            glow_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
            ImageDraw.Draw(glow_layer).ellipse([glow_x, glow_y, glow_x + glow_size, glow_y + glow_size], fill=(*GLOW_BEIGE, 60))
            base_img.alpha_composite(glow_layer)
            
            base_img.paste(avatar, (x, y), mask)
            
            main_draw = ImageDraw.Draw(base_img)
            main_draw.arc([x, y, x + size, y + size], 0, 360, fill=(*GLOW_BEIGE, 150), width=2*S)
            
        except Exception as e:
            logger.error(f"아바타 렌더링 실패: {e}")

    def _get_text_width(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
        """안전하게 텍스트의 가로 너비를 구합니다."""
        try:
            return int(draw.textlength(text, font=font))
        except AttributeError:
            return draw.textsize(text, font=font)[0]

    def _draw_stat_section(self, draw: ImageDraw.ImageDraw, label: str, rank: Optional[int], total_users: int, 
                           level: int, curr_xp: int, req_xp: int, total_xp: int, progress: float, 
                           x: int, y: int, width: int, color: Tuple[int, int, int, int]):
        
        # 1. 상단 라벨 (음성/채팅 | 순위)
        rank_text = f"상위 {rank}위" if rank else "Unranked"
        if total_users > 0 and rank:
            rank_text += f" / {total_users}명"
            
        label_full = f"{label}  |  {rank_text}"
        draw.text((x, y), label_full, fill=TEXT_SUB, font=self.font_label)
        
        # 2. 우측 상단 레벨 (Lv. 0)
        level_text = f"Lv.{level}"
        level_w = self._get_text_width(draw, level_text, self.font_level)
        draw.text((x + width - level_w, y - 8 * S), level_text, fill=TEXT_TITLE, font=self.font_level)
        
        # 3. 진행도 바
        bar_y = y + 30 * S
        bar_height = 8 * S 
        
        draw.rounded_rectangle([x, bar_y, x + width, bar_y + bar_height], radius=bar_height//2, fill=BAR_BG)
        
        fill_width = max(bar_height, int(width * (progress / 100)))
        if fill_width > bar_height:
            draw.rounded_rectangle([x, bar_y, x + fill_width, bar_y + bar_height], radius=bar_height//2, fill=color)
            
            # 진행 바 끝에 반짝이는 점 추가
            dot_r = 4 * S
            dot_x = x + fill_width
            dot_y = bar_y + bar_height // 2
            draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=(255, 255, 255, 255))
        
        # 4. 우측 하단 경험치 텍스트
        xp_text = f"{curr_xp:,} / {req_xp:,}  (총 {total_xp:,})"
        xp_w = self._get_text_width(draw, xp_text, self.font_value)
        draw.text((x + width - xp_w, bar_y + 16 * S), xp_text, fill=TEXT_SUB, font=self.font_value)