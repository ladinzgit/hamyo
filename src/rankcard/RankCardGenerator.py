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

# 기존 서비스에서 사용하는 데이터 클래스 임포트 (경로는 기존 파일과 동일하게 유지)
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
        # 폰트 로드
        # 기본 폰트가 밋밋하다면 'assets/fonts/KoPubBatangMedium.ttf' 등으로 변경하세요.
        font_path_main = "assets/fonts/Pretendard-Medium.ttf"
        font_path_bold = "assets/fonts/Pretendard-Bold.ttf"
        
        try:
            self.font_name = ImageFont.truetype(font_path_bold, 56 * S)
            self.font_role = ImageFont.truetype(font_path_main, 32 * S)
            self.font_label = ImageFont.truetype(font_path_bold, 28 * S)
            self.font_value = ImageFont.truetype(font_path_main, 24 * S)
            self.font_level = ImageFont.truetype(font_path_bold, 40 * S)
        except OSError:
            logger.warning("지정된 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")
            self.font_name = ImageFont.load_default()
            self.font_role = ImageFont.load_default()
            self.font_label = ImageFont.load_default()
            self.font_value = ImageFont.load_default()
            self.font_level = ImageFont.load_default()

    async def generate(self, data: 'RankCardData', avatar_bytes: Optional[bytes] = None) -> io.BytesIO:
        """데이터를 바탕으로 비몽책방 테마 랭크카드 이미지를 생성합니다."""
        
        # 1. 배경 레이어 (딥 네이비)
        base_img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base_img)
        draw.rounded_rectangle((0, 0, CANVAS_WIDTH, CANVAS_HEIGHT), radius=CORNER_RADIUS, fill=BG_NAVY)

        # 2. 웜 베이지 조명 (Glow)
        self._draw_soft_glow(base_img)

        # 3. 오픈북 워터마크
        self._draw_book_watermark(base_img)

        # 4. 별가루 (미세 스파클) - 유저 ID를 시드로 사용하여 항상 같은 별자리 유지
        user_id_seed = getattr(data, 'user_id', 12345)
        self._draw_sparkles(base_img, seed=user_id_seed) 

        # 메인 드로우 객체
        main_draw = ImageDraw.Draw(base_img)

        # 5. 오른쪽 상단 책갈피 (Ribbon)
        self._draw_bookmark(main_draw)

        # 6. 아바타 렌더링 (아바타 주변 은은한 빛)
        avatar_x = 60 * S
        avatar_y = 60 * S
        avatar_size = 160 * S
        if avatar_bytes:
            self._draw_avatar(base_img, avatar_bytes, avatar_x, avatar_y, avatar_size)
        else:
            # 아바타가 없을 경우 기본 자리표시자
            main_draw.ellipse([avatar_x, avatar_y, avatar_x+avatar_size, avatar_y+avatar_size], fill=(40, 45, 60, 255))

        # 7. 텍스트 레이아웃 설정
        text_start_x = avatar_x + avatar_size + 40 * S
        
        # 유저 이름
        main_draw.text((text_start_x, avatar_y + 10 * S), getattr(data, 'name', 'Unknown'), fill=TEXT_TITLE, font=self.font_name)
        
        # 칭호/역할 (예: 다도, 다향 등)
        role_display = getattr(data, 'role_display', '허브')
        role_text = f"✨ 칭호 : {role_display}"
        main_draw.text((text_start_x, avatar_y + 85 * S), role_text, fill=TEXT_GOLD, font=self.font_role)

        # 8. 진행 바 영역 (음성 & 채팅)
        bar_x = text_start_x
        bar_width = CANVAS_WIDTH - bar_x - (80 * S) # 책갈피 고려 여백
        
        # 음성 데이터
        voice_y = avatar_y + 140 * S
        self._draw_stat_section(
            main_draw, "음성", 
            getattr(data, 'voice_rank', None), getattr(data, 'total_users', 0), 
            getattr(data, 'voice_level', 0), getattr(data, 'voice_curr_xp', 0), 
            getattr(data, 'voice_req_xp', 1), getattr(data, 'voice_xp', 0), getattr(data, 'voice_prog', 0.0),
            bar_x, voice_y, bar_width, BAR_VOICE
        )

        # 채팅 데이터
        chat_y = voice_y + 70 * S
        self._draw_stat_section(
            main_draw, "채팅", 
            getattr(data, 'chat_rank', None), getattr(data, 'total_users', 0), 
            getattr(data, 'chat_level', 0), getattr(data, 'chat_curr_xp', 0), 
            getattr(data, 'chat_req_xp', 1), getattr(data, 'chat_xp', 0), getattr(data, 'chat_prog', 0.0),
            bar_x, chat_y, bar_width, BAR_CHAT
        )

        # 9. 최종 다운스케일링 및 반환
        final_img = base_img.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        final_img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def _draw_soft_glow(self, base_img: Image.Image):
        """배경에 은은한 웜 베이지 조명을 추가합니다."""
        glow_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        
        # 아바타와 텍스트 뒷부분을 밝혀주는 타원형 조명
        cx, cy = 400 * S, CANVAS_HEIGHT // 2
        max_radius = 450 * S
        
        # 부드러운 그라데이션 원 그리기
        for i in range(max_radius, 0, -5 * S):
            alpha = int(15 * (1 - (i / max_radius))) # 최대 투명도 15 (매우 은은하게)
            color = (*GLOW_BEIGE, alpha)
            glow_draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=color)
            
        base_img.alpha_composite(glow_layer)

    def _draw_book_watermark(self, base_img: Image.Image):
        """우측 배경에 펼쳐진 책 모양의 미니멀한 라인 워터마크를 그립니다."""
        watermark_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        cx = CANVAS_WIDTH - 300 * S
        cy = CANVAS_HEIGHT // 2 + 50 * S
        w = 250 * S
        h = 100 * S
        
        color = (*GLOW_BEIGE, 10) # 투명도 10
        line_w = 3 * S
        
        # 왼쪽 페이지
        draw.arc([cx - w, cy - h, cx, cy + h], 180, 270, fill=color, width=line_w)
        draw.arc([cx - w, cy, cx, cy + h * 2], 180, 270, fill=color, width=line_w)
        draw.line([cx - w, cy, cx - w, cy + h], fill=color, width=line_w)
        
        # 오른쪽 페이지
        draw.arc([cx, cy - h, cx + w, cy + h], 270, 360, fill=color, width=line_w)
        draw.arc([cx, cy, cx + w, cy + h * 2], 270, 360, fill=color, width=line_w)
        draw.line([cx + w, cy, cx + w, cy + h], fill=color, width=line_w)
        
        # 책등(가운데 선)
        draw.line([cx, cy - h, cx, cy + h], fill=color, width=line_w)

        base_img.alpha_composite(watermark_layer)

    def _draw_sparkles(self, base_img: Image.Image, seed: int):
        """별가루(스파클) 이펙트를 배경에 흩뿌립니다."""
        sparkle_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sparkle_layer)
        
        # 안전한 시드 생성 (만약 string이면 hash로 변환)
        safe_seed = hash(seed) if isinstance(seed, str) else seed
        random.seed(safe_seed)
        
        for _ in range(35): # 별 갯수
            x = random.randint(0, CANVAS_WIDTH)
            y = random.randint(0, CANVAS_HEIGHT)
            size = random.randint(1 * S, 3 * S)
            alpha = random.randint(50, 150)
            
            # 십자가 형태의 반짝임
            if random.random() > 0.5:
                draw.line([x-size, y, x+size, y], fill=(*GLOW_BEIGE, alpha), width=1*S)
                draw.line([x, y-size, x, y+size], fill=(*GLOW_BEIGE, alpha), width=1*S)
            else:
                draw.ellipse([x, y, x+size, y+size], fill=(*GLOW_BEIGE, alpha))
                
        base_img.alpha_composite(sparkle_layer)

    def _draw_bookmark(self, draw: ImageDraw.ImageDraw):
        """우측 상단에 엣지있는 책갈피(Ribbon) 포인트를 그립니다."""
        ribbon_w = 60 * S
        ribbon_h = 140 * S
        x = CANVAS_WIDTH - 120 * S
        y = 0
        
        points = [
            (x, y),
            (x + ribbon_w, y),
            (x + ribbon_w, y + ribbon_h),
            (x + ribbon_w // 2, y + ribbon_h - 25 * S),
            (x, y + ribbon_h)
        ]
        draw.polygon(points, fill=RIBBON_RED)
        
        # 금색 스티치 포인트
        draw.line([x + 10*S, y + ribbon_h - 30*S, x + ribbon_w // 2, y + ribbon_h - 45*S], fill=TEXT_GOLD, width=2*S)
        draw.line([x + ribbon_w - 10*S, y + ribbon_h - 30*S, x + ribbon_w // 2, y + ribbon_h - 45*S], fill=TEXT_GOLD, width=2*S)

    def _draw_avatar(self, base_img: Image.Image, avatar_bytes: bytes, x: int, y: int, size: int):
        """아바타 이미지를 원형으로 마스킹하고 은은한 테두리를 적용합니다."""
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
            
            # 원형 마스크 생성
            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            
            # 아바타 테두리 글로우
            glow_size = size + 10 * S
            glow_x = x - 5 * S
            glow_y = y - 5 * S
            glow_layer = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0,0,0,0))
            ImageDraw.Draw(glow_layer).ellipse([glow_x, glow_y, glow_x + glow_size, glow_y + glow_size], fill=(*GLOW_BEIGE, 60))
            base_img.alpha_composite(glow_layer)
            
            # 아바타 합성
            base_img.paste(avatar, (x, y), mask)
            
            # 아바타 외곽선
            main_draw = ImageDraw.Draw(base_img)
            main_draw.arc([x, y, x + size, y + size], 0, 360, fill=(*GLOW_BEIGE, 150), width=2*S)
            
        except Exception as e:
            logger.error(f"아바타 렌더링 실패: {e}")

    def _draw_stat_section(self, draw: ImageDraw.ImageDraw, label: str, rank: Optional[int], total_users: int, 
                           level: int, curr_xp: int, req_xp: int, total_xp: int, progress: float, 
                           x: int, y: int, width: int, color: Tuple[int, int, int, int]):
        """음성/채팅 섹션 (텍스트 + 얇고 우아한 프로그레스 바)을 그립니다."""
        
        # 상단 텍스트 (타이틀 & 랭크)
        rank_text = f"상위 {rank}위" if rank else "Unranked"
        if total_users > 0 and rank:
            rank_text += f" / {total_users}명"
            
        label_full = f"{label}  |  {rank_text}"
        draw.text((x, y), label_full, fill=TEXT_SUB, font=self.font_label)
        
        # 레벨 텍스트 (우측 정렬)
        level_text = f"Lv.{level}"
        
        # Pillow 버전에 따른 분기 처리 (textbbox 혹은 textsize)
        try:
            level_bbox = draw.textbbox((0, 0), level_text, font=self.font_level)
            level_w = level_bbox[2] - level_bbox[0]
        except AttributeError:
            level_w, _ = draw.textsize(level_text, font=self.font_level)
            
        draw.text((x + width - level_w, y - 10 * S), level_text, fill=TEXT_TITLE, font=self.font_level)
        
        # 얇고 세련된 프로그레스 바 (선형)
        bar_y = y + 45 * S
        bar_height = 6 * S 
        
        # 바 배경
        draw.rounded_rectangle([x, bar_y, x + width, bar_y + bar_height], radius=bar_height//2, fill=BAR_BG)
        
        # 바 채우기
        fill_width = max(bar_height, int(width * (progress / 100)))
        if fill_width > bar_height:
            draw.rounded_rectangle([x, bar_y, x + fill_width, bar_y + bar_height], radius=bar_height//2, fill=color)
            
            # 프로그레스 바 끝부분 빛나는 포인트 (Glow dot)
            dot_r = 5 * S
            dot_x = x + fill_width
            dot_y = bar_y + bar_height // 2
            draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=(255, 255, 255, 255))
        
        # 하단 XP 텍스트 (총 XP 포함)
        xp_text = f"{curr_xp:,} / {req_xp:,}  (총 {total_xp:,})"
        
        try:
            xp_bbox = draw.textbbox((0, 0), xp_text, font=self.font_value)
            xp_w = xp_bbox[2] - xp_bbox[0]
        except AttributeError:
            xp_w, _ = draw.textsize(xp_text, font=self.font_value)
            
        draw.text((x + width - xp_w, bar_y + 15 * S), xp_text, fill=TEXT_SUB, font=self.font_value)