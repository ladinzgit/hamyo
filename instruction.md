Great. Since the performance (execution time) issue is resolved and you have provided the working code structure, this **new `instruction.md`** will focus entirely on **polishing the Visuals (UI/UX)** to match your design requirements (Flower pattern, Glassmorphism, Density).

It instructs the Coding Agent to **keep the logic** of `RankCardService` and `RankCardCog` (since they work) but **rewrite `RankCardGenerator`** to fix the design issues.

***

# Instruction: Refine Visuals for "Kyungji" Rank Card

## 1. Project Status & Goal
*   **Current Status:** The backend logic (Data fetching, XP calculation, Command handling) is **working correctly and fast**.
*   **Goal:** The current image output is visually broken (text on background, opaque boxes). We need to **rewrite `RankCardGenerator.py`** to match the "Compact & Glassmorphism" design with a procedural flower background.

## 2. Directory Structure
*   **Work Directory:** `src/rankcard/`
*   **Files:**
    *   `RankCardGenerator.py` **(TARGET FOR REWRITE)**
    *   `RankCardService.py` (Keep existing logic)
    *   `RankCardCog.py` (Keep existing logic)
    *   `XPFormulas.py` (Keep existing logic)

## 3. Visual Design Specifications (RankCardGenerator.py)

You must rewrite `RankCardGenerator.py` to implement the following specific design details.

### A. Canvas & Theme
*   **Size:** `860px` (W) x `280px` (H).
*   **Background Color:** `#0f0f13` (Dark).
*   **Corners:** Rounded (`24px`).
*   **Fonts:**
    *   Bold: `assets/fonts/Pretendard-Bold.ttf`
    *   Medium: `assets/fonts/Pretendard-Medium.ttf`

### B. Background Decoration (The Flower)
*   **Requirement:** Remove the existing `_draw_deco_character` (Text). Replace it with a **Procedural Flower Pattern**.
*   **Logic:** Draw 5 overlapping circles arranged in a circle to mimic a flower shape.
*   **Style:**
    *   **Color:** Role Theme Color.
    *   **Opacity:** Very Low (**10%** / Alpha ~25). It must be subtle.
    *   **Position:** Right side of the card, partially cut off, serving as a wallpaper.
*   **Snippet for Generator:**
    ```python
    def _draw_flower_pattern(self, canvas, draw, color):
        # Center coordinates for the flower (Right side)
        cx, cy = 720, 100
        radius = 120 
        # 5 petals
        offsets = [
            (0, -1), (0.95, -0.31), (0.59, 0.81), (-0.59, 0.81), (-0.95, -0.31)
        ]
        # Use a separate layer for transparency
        overlay = Image.new('RGBA', canvas.size, (0,0,0,0))
        d = ImageDraw.Draw(overlay)
        
        petal_color = color + (25,) # Low Alpha (approx 10%)
        
        for dx, dy in offsets:
            x = cx + dx * (radius * 0.6)
            y = cy + dy * (radius * 0.6)
            # Draw petal (circle)
            d.ellipse(
                [(x - radius, y - radius), (x + radius, y + radius)],
                fill=petal_color
            )
        
        # Composite
        canvas.paste(Image.alpha_composite(canvas, overlay), (0,0))
    ```

### C. Sub-Stat Boxes (Glassmorphism)
*   **Requirement:** The current boxes are too dark/opaque. They need to look like **Glass**.
*   **Style:**
    *   **Fill:** White with extremely low opacity (`255, 255, 255, 15`). **Do not use Gray/Black.**
    *   **Stroke (Border):** White with low opacity (`255, 255, 255, 40`), 1px width.
    *   **Text Colors inside box:**
        *   Labels: Light Gray (`#dddddd`).
        *   Values (Lv): Pure White (`#ffffff`).
    *   **Progress Bar inside box:**
        *   Track (Background): Black with low opacity (`0, 0, 0, 80`).
        *   Fill: Specific Role/Stat Color.

### D. Layout Adjustments
1.  **Avatar:** Keep the circular crop and badge logic. Ensure `Image.LANCZOS` is used for high-quality resizing.
2.  **Badge:** Ensure the text is centered and the pill shape has the Role Color.
3.  **Main Progress Bar:**
    *   Label: `다음 경지 : [Next Role]` (Left) | `[XX.X]%` (Right).
    *   Track: Dark Gray (`#282832`).
    *   Fill: Gradient or Solid Role Color.

## 4. Logic & Data Preservation

### A. `RankCardService.py`
*   **Keep the provided code.** It correctly fetches data and calculates the Tiered XP.
*   **Reminder:** It uses `TieredLevelManager` from `XPFormulas.py`.

### B. `XPFormulas.py`
*   **Keep the provided code.**
*   **Formula Check:**
    *   `Multiplier = 1 + (Level // 10) * 0.5`
    *   Voice: `((Lv * 139) + 70) * Multiplier`
    *   Chat: `((Lv * 69.5) + 35) * Multiplier`

### C. `RankCardCog.py`
*   **Keep the provided code.**
*   It handles the `discord.File` sending and error logging correctly.

## 5. Implementation Steps for Coding Agent

1.  **Analyze** the provided `RankCardGenerator.py` code.
2.  **Modify** `RankCardGenerator.py`:
    *   Remove `ROLE_DECO_CHAR` mapping and `_draw_deco_character`.
    *   Add `_draw_flower_pattern` method.
    *   Update `_draw_sub_stat_box` to use the **Glassmorphism** colors (White transparent fill) instead of the current dark fill.
    *   Update `_draw_background_gradient` to be subtle.
3.  **Verify** that `RankCardService` and `XPFormulas` are imported correctly.
4.  **Final Check:** Ensure no English labels exist on the card canvas (Use '다공', '레벨', '경지').

***
*End of Instruction*