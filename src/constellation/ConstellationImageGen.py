# src/constellation/ConstellationImageGen.py
# ============================================================
# 비몽 별자리 수집 이미지 생성 모듈
# Pillow를 사용하여 관측 결과 및 별자리 도감 카드를 생성합니다.
# ============================================================

import io
import os
import math
import logging
from typing import Optional, List, Set

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.constellation.ConstellationConstants import CONSTELLATIONS, CONSTELLATION_ORDER

logger = logging.getLogger(__name__)

# ── 2배 렌더링 스케일 ──
S = 2

# ── 색상 정의 ──
COLOR_STAR_GLOW_CENTER = (255, 245, 200, 255)     # 별 중심 (밝은 황금빛)
COLOR_STAR_GLOW_OUTER = (255, 200, 80, 0)          # 별 글로우 외곽 (투명)
COLOR_STAR_DIM = (80, 80, 100, 150)                 # 미수집 별 (회색빛)
COLOR_STAR_DIM_BORDER = (60, 60, 80, 200)           # 미수집 별 테두리
COLOR_LINE_ACTIVE = (255, 220, 120, 180)            # 수집된 별 사이 연결선
COLOR_LINE_INACTIVE = (60, 60, 80, 80)              # 미수집 별 사이 연결선
COLOR_TEXT_WHITE = (245, 245, 245)
COLOR_TEXT_LIGHT = (210, 210, 210)
COLOR_TEXT_GRAY = (130, 130, 150)
COLOR_TEXT_GOLD = (255, 200, 80)
COLOR_TEXT_DIM = (90, 90, 110)
COLOR_PROGRESS_BG = (35, 30, 40)
COLOR_PROGRESS_FILL = (255, 200, 80)
COLOR_BG_FALLBACK = (10, 8, 25)                     # 배경 이미지 없을 때 어두운 남색

# ── 에셋 경로 ──
CONSTELLATION_BG_PATH = "assets/constellation/constellation_bg.png"
OBSERVE_BG_PATH = "assets/constellation/observe_bg.png"
STAR_GLOW_PATH = "assets/constellation/star_glow.png"
STAR_DIM_PATH = "assets/constellation/star_dim.png"

# ── 폰트 경로 ──
FONT_BOLD_PATH = "assets/fonts/NanumMyeongjoExtraBold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/NanumMyeongjoBold.ttf"


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError) as e:
        logger.warning(f"폰트 로드 실패 ({path}, {size}px): {e}")
        return ImageFont.load_default()


def _generate_star_glow(size: int) -> Image.Image:
    """
    Pillow로 자연스러운 빛나는 별 이미지를 생성합니다.
    방사형 그라데이션 + 가우시안 블러로 따뜻한 글로우 효과.
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    center = size // 2
    max_r = size // 2

    # 방사형 그라데이션
    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= max_r:
                ratio = dist / max_r
                # 부드러운 감쇄 곡선 (가운데 밝고 가장자리 투명)
                alpha = int(255 * max(0, (1 - ratio ** 1.5)))
                r = int(255 - (255 - 255) * ratio)
                g = int(245 - (245 - 180) * ratio)
                b = int(200 - (200 - 60) * ratio)
                img.putpixel((x, y), (r, g, b, alpha))

    # 가우시안 블러로 부드럽게
    img = img.filter(ImageFilter.GaussianBlur(radius=size // 8))

    # 중심에 밝은 점 추가
    draw = ImageDraw.Draw(img)
    core_r = max(2, size // 10)
    draw.ellipse(
        [(center - core_r, center - core_r), (center + core_r, center + core_r)],
        fill=(255, 255, 240, 255)
    )
    # 코어도 약간 블러
    img = img.filter(ImageFilter.GaussianBlur(radius=max(1, core_r // 2)))

    return img


def _generate_star_dim(size: int) -> Image.Image:
    """
    Pillow로 미수집 별 이미지를 생성합니다.
    어두운 원 + 테두리 + ? 마크.
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    center = size // 2
    r = size // 2 - 2

    # 어두운 원
    draw.ellipse(
        [(center - r, center - r), (center + r, center + r)],
        fill=COLOR_STAR_DIM,
        outline=COLOR_STAR_DIM_BORDER,
        width=max(1, size // 16)
    )

    # ? 마크
    font_size = max(8, size // 3)
    font = _load_font(FONT_BOLD_PATH, font_size)
    bbox = draw.textbbox((0, 0), "?", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (center - tw // 2, center - th // 2 - 2),
        "?",
        fill=(120, 120, 140, 200),
        font=font
    )

    return img


def _load_or_generate_star_glow(size: int) -> Image.Image:
    """에셋이 있으면 로드, 없으면 자동 생성."""
    if os.path.exists(STAR_GLOW_PATH):
        try:
            img = Image.open(STAR_GLOW_PATH).convert('RGBA')
            return img.resize((size, size), Image.LANCZOS)
        except Exception:
            pass
    return _generate_star_glow(size)


def _load_or_generate_star_dim(size: int) -> Image.Image:
    """에셋이 있으면 로드, 없으면 자동 생성."""
    if os.path.exists(STAR_DIM_PATH):
        try:
            img = Image.open(STAR_DIM_PATH).convert('RGBA')
            return img.resize((size, size), Image.LANCZOS)
        except Exception:
            pass
    return _generate_star_dim(size)


def _load_bg(path: str, fallback_size: tuple) -> Image.Image:
    """배경 이미지를 로드하고, 없으면 폴백 색상으로 생성."""
    if os.path.exists(path):
        try:
            return Image.open(path).convert('RGBA')
        except Exception:
            pass
    return Image.new('RGBA', fallback_size, COLOR_BG_FALLBACK)


class ConstellationImageGen:
    """별자리 이미지 생성기"""

    def __init__(self):
        self.font_title = _load_font(FONT_BOLD_PATH, int(48 * S))
        self.font_subtitle = _load_font(FONT_BOLD_PATH, int(32 * S))
        self.font_star_name = _load_font(FONT_MEDIUM_PATH, int(18 * S))
        self.font_star_name_big = _load_font(FONT_MEDIUM_PATH, int(22 * S))
        self.font_info = _load_font(FONT_MEDIUM_PATH, int(20 * S))
        self.font_progress = _load_font(FONT_BOLD_PATH, int(24 * S))
        self.font_desc = _load_font(FONT_MEDIUM_PATH, int(16 * S))

    # ────────────────────────────────────────────────
    # 1. 관측 결과 이미지
    # ────────────────────────────────────────────────

    def generate_observe_result(
        self,
        constellation_id: str,
        star_id: str,
        is_new: bool,
        user_name: str,
    ) -> io.BytesIO:
        """별 관측 결과 이미지를 생성합니다."""
        constellation = CONSTELLATIONS[constellation_id]
        star = next(s for s in constellation["stars"] if s["id"] == star_id)

        # 배경 로드
        bg = _load_bg(OBSERVE_BG_PATH, (800, 600))
        OUTPUT_W, OUTPUT_H = bg.size
        CANVAS_W = OUTPUT_W * S
        CANVAS_H = OUTPUT_H * S
        canvas = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

        # 반투명 오버레이 (어둡게)
        overlay = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 80))
        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        # 중앙에 별 글로우
        star_size = int(min(CANVAS_W, CANVAS_H) * 0.25)
        star_img = _load_or_generate_star_glow(star_size) if is_new else _load_or_generate_star_dim(star_size)
        # 글로우 별은 좀 더 크게
        if is_new:
            large_glow = _load_or_generate_star_glow(int(star_size * 1.8))
            glow_x = CANVAS_W // 2 - large_glow.width // 2
            glow_y = int(CANVAS_H * 0.35) - large_glow.height // 2
            canvas.paste(large_glow, (glow_x, glow_y), large_glow)

        star_x = CANVAS_W // 2 - star_img.width // 2
        star_y = int(CANVAS_H * 0.35) - star_img.height // 2
        canvas.paste(star_img, (star_x, star_y), star_img)

        # 별 이름
        star_text = f"✦ {star['name']}"
        bbox = draw.textbbox((0, 0), star_text, font=self.font_subtitle)
        tw = bbox[2] - bbox[0]
        draw.text(
            (CANVAS_W // 2 - tw // 2, int(CANVAS_H * 0.58)),
            star_text,
            fill=COLOR_TEXT_GOLD if is_new else COLOR_TEXT_DIM,
            font=self.font_subtitle
        )

        # 별자리 정보
        info_text = f"{constellation['emoji']} {constellation['name']}"
        bbox2 = draw.textbbox((0, 0), info_text, font=self.font_info)
        tw2 = bbox2[2] - bbox2[0]
        draw.text(
            (CANVAS_W // 2 - tw2 // 2, int(CANVAS_H * 0.68)),
            info_text,
            fill=COLOR_TEXT_LIGHT if is_new else COLOR_TEXT_GRAY,
            font=self.font_info
        )

        # 상태 텍스트
        status_text = "새로운 별 발견!" if is_new else "이미 수집한 별..."
        bbox3 = draw.textbbox((0, 0), status_text, font=self.font_info)
        tw3 = bbox3[2] - bbox3[0]
        draw.text(
            (CANVAS_W // 2 - tw3 // 2, int(CANVAS_H * 0.78)),
            status_text,
            fill=COLOR_TEXT_GOLD if is_new else COLOR_TEXT_GRAY,
            font=self.font_info
        )

        # 관측자 이름
        observer_text = f"관측자: {user_name}"
        bbox4 = draw.textbbox((0, 0), observer_text, font=self.font_desc)
        tw4 = bbox4[2] - bbox4[0]
        draw.text(
            (CANVAS_W // 2 - tw4 // 2, int(CANVAS_H * 0.88)),
            observer_text,
            fill=COLOR_TEXT_GRAY,
            font=self.font_desc
        )

        # 다운스케일
        output = canvas.resize((OUTPUT_W, OUTPUT_H), Image.LANCZOS)
        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ────────────────────────────────────────────────
    # 2. 별자리 도감 카드 (전체 or 개별)
    # ────────────────────────────────────────────────

    def generate_collection_card(
        self,
        user_name: str,
        collected_stars: dict,
        constellation_id: Optional[str] = None,
    ) -> io.BytesIO:
        """
        별자리 도감 카드를 생성합니다.
        constellation_id가 None이면 전체 도감, 지정하면 해당 별자리만.
        collected_stars: {constellation_id: [star_id, ...]}
        """
        if constellation_id:
            return self._generate_single_constellation_card(
                user_name, collected_stars, constellation_id
            )
        else:
            return self._generate_full_collection_card(user_name, collected_stars)

    def _generate_single_constellation_card(
        self,
        user_name: str,
        collected_stars: dict,
        constellation_id: str,
    ) -> io.BytesIO:
        """단일 별자리 상세 카드를 생성합니다."""
        constellation = CONSTELLATIONS[constellation_id]
        user_collected = set(collected_stars.get(constellation_id, []))

        bg = _load_bg(CONSTELLATION_BG_PATH, (1200, 800))
        OUTPUT_W, OUTPUT_H = bg.size
        CANVAS_W = OUTPUT_W * S
        CANVAS_H = OUTPUT_H * S
        canvas = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

        # 반투명 오버레이
        overlay = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 100))
        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        # ── 영역 정의 ──
        # 상단: 제목 (0~15%)
        # 중앙: 별자리 그림 (15~80%)
        # 하단: 진행률 바 (80~100%)

        star_area_x = int(CANVAS_W * 0.1)
        star_area_y = int(CANVAS_H * 0.18)
        star_area_w = int(CANVAS_W * 0.8)
        star_area_h = int(CANVAS_H * 0.58)

        # ── 제목 ──
        title_text = f"{constellation['emoji']} {constellation['name']}"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_title)
        tw = bbox[2] - bbox[0]
        draw.text(
            (CANVAS_W // 2 - tw // 2, int(CANVAS_H * 0.04)),
            title_text,
            fill=COLOR_TEXT_WHITE,
            font=self.font_title
        )

        # 설명
        desc_text = constellation["description"]
        bbox_d = draw.textbbox((0, 0), desc_text, font=self.font_desc)
        tw_d = bbox_d[2] - bbox_d[0]
        draw.text(
            (CANVAS_W // 2 - tw_d // 2, int(CANVAS_H * 0.11)),
            desc_text,
            fill=COLOR_TEXT_GRAY,
            font=self.font_desc
        )

        # ── 연결선 그리기 (별 뒤에) ──
        stars = constellation["stars"]
        for i, j in constellation["lines"]:
            if i >= len(stars) or j >= len(stars):
                continue
            sx1 = star_area_x + int(stars[i]["x"] * star_area_w)
            sy1 = star_area_y + int(stars[i]["y"] * star_area_h)
            sx2 = star_area_x + int(stars[j]["x"] * star_area_w)
            sy2 = star_area_y + int(stars[j]["y"] * star_area_h)

            both_collected = stars[i]["id"] in user_collected and stars[j]["id"] in user_collected
            line_color = COLOR_LINE_ACTIVE if both_collected else COLOR_LINE_INACTIVE
            line_width = 3 * S if both_collected else 1 * S
            draw.line([(sx1, sy1), (sx2, sy2)], fill=line_color, width=line_width)

        # ── 별 그리기 ──
        star_glow_size = int(64 * S)
        star_dim_size = int(40 * S)
        star_glow_img = _load_or_generate_star_glow(star_glow_size)
        star_dim_img = _load_or_generate_star_dim(star_dim_size)

        for star in stars:
            sx = star_area_x + int(star["x"] * star_area_w)
            sy = star_area_y + int(star["y"] * star_area_h)
            is_collected = star["id"] in user_collected

            if is_collected:
                img = star_glow_img
                px = sx - img.width // 2
                py = sy - img.height // 2
                canvas.paste(img, (px, py), img)
                # 별 이름
                name_bbox = draw.textbbox((0, 0), star["name"], font=self.font_star_name)
                name_w = name_bbox[2] - name_bbox[0]
                draw.text(
                    (sx - name_w // 2, sy + img.height // 2 + 4 * S),
                    star["name"],
                    fill=COLOR_TEXT_GOLD,
                    font=self.font_star_name
                )
            else:
                img = star_dim_img
                px = sx - img.width // 2
                py = sy - img.height // 2
                canvas.paste(img, (px, py), img)

        # ── 하단 진행률 ──
        total = len(stars)
        collected_count = len(user_collected)
        progress = collected_count / total if total > 0 else 0

        bar_x = int(CANVAS_W * 0.15)
        bar_y = int(CANVAS_H * 0.84)
        bar_w = int(CANVAS_W * 0.7)
        bar_h = int(20 * S)

        # 프로그레스 바 배경
        draw.rounded_rectangle(
            [(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)],
            radius=bar_h // 2,
            fill=COLOR_PROGRESS_BG
        )
        # 프로그레스 바 채우기
        if progress > 0:
            fill_w = max(int(bar_w * progress), bar_h)
            draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h)],
                radius=bar_h // 2,
                fill=COLOR_PROGRESS_FILL
            )

        # 진행률 텍스트
        pct_text = f"{collected_count}/{total} ({progress * 100:.0f}%)"
        bbox_p = draw.textbbox((0, 0), pct_text, font=self.font_progress)
        tw_p = bbox_p[2] - bbox_p[0]
        draw.text(
            (CANVAS_W // 2 - tw_p // 2, bar_y + bar_h + 10 * S),
            pct_text,
            fill=COLOR_TEXT_GOLD if collected_count == total else COLOR_TEXT_LIGHT,
            font=self.font_progress
        )

        # 완성 여부
        if collected_count == total:
            complete_text = "✨ 별자리 완성! ✨"
            bbox_c = draw.textbbox((0, 0), complete_text, font=self.font_progress)
            tw_c = bbox_c[2] - bbox_c[0]
            draw.text(
                (CANVAS_W // 2 - tw_c // 2, bar_y - int(30 * S)),
                complete_text,
                fill=COLOR_TEXT_GOLD,
                font=self.font_progress
            )

        # 관측자
        user_text = f"관측자: {user_name}"
        bbox_u = draw.textbbox((0, 0), user_text, font=self.font_desc)
        tw_u = bbox_u[2] - bbox_u[0]
        draw.text(
            (CANVAS_W // 2 - tw_u // 2, int(CANVAS_H * 0.94)),
            user_text,
            fill=COLOR_TEXT_GRAY,
            font=self.font_desc
        )

        # 다운스케일
        output = canvas.resize((OUTPUT_W, OUTPUT_H), Image.LANCZOS)
        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    def _generate_full_collection_card(
        self,
        user_name: str,
        collected_stars: dict,
    ) -> io.BytesIO:
        """전체 별자리 도감 카드를 생성합니다 (5개 별자리 요약)."""
        bg = _load_bg(CONSTELLATION_BG_PATH, (1200, 800))
        OUTPUT_W, OUTPUT_H = bg.size
        CANVAS_W = OUTPUT_W * S
        CANVAS_H = OUTPUT_H * S
        canvas = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

        # 반투명 오버레이
        overlay = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 120))
        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        # ── 제목 ──
        title = "🌌 비몽 별자리 도감"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        tw = bbox[2] - bbox[0]
        draw.text(
            (CANVAS_W // 2 - tw // 2, int(CANVAS_H * 0.04)),
            title,
            fill=COLOR_TEXT_WHITE,
            font=self.font_title
        )

        # ── 각 별자리 미니 카드 ──
        # 5개를 2행으로 배치: 1행에 3개, 2행에 2개
        positions = [
            # 1행: 3개
            (0.18, 0.20), (0.50, 0.20), (0.82, 0.20),
            # 2행: 2개
            (0.34, 0.55), (0.66, 0.55),
        ]
        mini_w = int(CANVAS_W * 0.28)
        mini_h = int(CANVAS_H * 0.28)

        total_stars_all = 0
        collected_stars_all = 0
        completed_count = 0

        for idx, cid in enumerate(CONSTELLATION_ORDER):
            constellation = CONSTELLATIONS[cid]
            cx_ratio, cy_ratio = positions[idx]
            cx = int(CANVAS_W * cx_ratio)
            cy = int(CANVAS_H * cy_ratio)

            user_collected = set(collected_stars.get(cid, []))
            total = len(constellation["stars"])
            collected = len(user_collected)
            is_complete = collected >= total

            total_stars_all += total
            collected_stars_all += collected
            if is_complete:
                completed_count += 1

            # 미니 카드 배경
            card_x = cx - mini_w // 2
            card_y = cy - mini_h // 2
            card_layer = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            card_draw = ImageDraw.Draw(card_layer)
            card_draw.rounded_rectangle(
                [(card_x, card_y), (card_x + mini_w, card_y + mini_h)],
                radius=int(15 * S),
                fill=(20, 15, 30, 180),
                outline=COLOR_TEXT_GOLD if is_complete else (60, 60, 80, 150),
                width=max(1, 2 * S) if is_complete else max(1, 1 * S)
            )
            canvas = Image.alpha_composite(canvas, card_layer)
            draw = ImageDraw.Draw(canvas)

            # 별자리 이름
            name_text = f"{constellation['emoji']} {constellation['name']}"
            name_bbox = draw.textbbox((0, 0), name_text, font=self.font_star_name_big)
            name_w = name_bbox[2] - name_bbox[0]
            draw.text(
                (cx - name_w // 2, card_y + int(12 * S)),
                name_text,
                fill=COLOR_TEXT_GOLD if is_complete else COLOR_TEXT_LIGHT,
                font=self.font_star_name_big
            )

            # 미니 별자리 그림 (연결선 + 별)
            mini_star_area_x = card_x + int(mini_w * 0.1)
            mini_star_area_y = card_y + int(mini_h * 0.25)
            mini_star_area_w = int(mini_w * 0.8)
            mini_star_area_h = int(mini_h * 0.45)

            stars = constellation["stars"]
            # 연결선
            for i, j in constellation["lines"]:
                if i >= len(stars) or j >= len(stars):
                    continue
                sx1 = mini_star_area_x + int(stars[i]["x"] * mini_star_area_w)
                sy1 = mini_star_area_y + int(stars[i]["y"] * mini_star_area_h)
                sx2 = mini_star_area_x + int(stars[j]["x"] * mini_star_area_w)
                sy2 = mini_star_area_y + int(stars[j]["y"] * mini_star_area_h)
                both = stars[i]["id"] in user_collected and stars[j]["id"] in user_collected
                draw.line(
                    [(sx1, sy1), (sx2, sy2)],
                    fill=COLOR_LINE_ACTIVE if both else COLOR_LINE_INACTIVE,
                    width=2 * S if both else 1 * S
                )

            # 미니 별
            mini_glow = _load_or_generate_star_glow(int(24 * S))
            mini_dim_s = int(14 * S)
            for star in stars:
                sx = mini_star_area_x + int(star["x"] * mini_star_area_w)
                sy = mini_star_area_y + int(star["y"] * mini_star_area_h)
                if star["id"] in user_collected:
                    px = sx - mini_glow.width // 2
                    py = sy - mini_glow.height // 2
                    canvas.paste(mini_glow, (px, py), mini_glow)
                    draw = ImageDraw.Draw(canvas)
                else:
                    draw.ellipse(
                        [(sx - mini_dim_s // 2, sy - mini_dim_s // 2),
                         (sx + mini_dim_s // 2, sy + mini_dim_s // 2)],
                        fill=COLOR_STAR_DIM,
                        outline=COLOR_STAR_DIM_BORDER,
                    )

            # 수집 현황 텍스트
            status_text = f"{collected}/{total}"
            if is_complete:
                status_text = f"✨ {status_text} 완성"
            s_bbox = draw.textbbox((0, 0), status_text, font=self.font_star_name)
            s_w = s_bbox[2] - s_bbox[0]
            draw.text(
                (cx - s_w // 2, card_y + mini_h - int(28 * S)),
                status_text,
                fill=COLOR_TEXT_GOLD if is_complete else COLOR_TEXT_GRAY,
                font=self.font_star_name
            )

        # ── 하단 전체 진행률 ──
        overall_progress = collected_stars_all / total_stars_all if total_stars_all > 0 else 0

        bar_x = int(CANVAS_W * 0.15)
        bar_y = int(CANVAS_H * 0.88)
        bar_w = int(CANVAS_W * 0.7)
        bar_h = int(18 * S)

        draw.rounded_rectangle(
            [(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)],
            radius=bar_h // 2, fill=COLOR_PROGRESS_BG
        )
        if overall_progress > 0:
            fill_w = max(int(bar_w * overall_progress), bar_h)
            draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h)],
                radius=bar_h // 2, fill=COLOR_PROGRESS_FILL
            )

        # 전체 진행률 텍스트
        overall_text = f"전체: {collected_stars_all}/{total_stars_all} 별 수집 · 별자리 {completed_count}/{len(CONSTELLATION_ORDER)} 완성"
        o_bbox = draw.textbbox((0, 0), overall_text, font=self.font_info)
        o_w = o_bbox[2] - o_bbox[0]
        draw.text(
            (CANVAS_W // 2 - o_w // 2, bar_y - int(28 * S)),
            overall_text,
            fill=COLOR_TEXT_LIGHT,
            font=self.font_info
        )

        # 관측자
        user_text = f"관측자: {user_name}"
        u_bbox = draw.textbbox((0, 0), user_text, font=self.font_desc)
        u_w = u_bbox[2] - u_bbox[0]
        draw.text(
            (CANVAS_W // 2 - u_w // 2, int(CANVAS_H * 0.95)),
            user_text,
            fill=COLOR_TEXT_GRAY,
            font=self.font_desc
        )

        # 다운스케일
        output = canvas.resize((OUTPUT_W, OUTPUT_H), Image.LANCZOS)
        buffer = io.BytesIO()
        output.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer
