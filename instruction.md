Here is the updated `instruction.md` file. It incorporates the new **Tiered XP System**, specific **Command** requirements, and strict **Integration** rules with your existing voice/chat modules.

***

# Instruction: Implement "Kyungji" Rank Card System with Tiered XP

## 1. Project Overview
We are implementing a custom Rank Card system for a Discord bot. The system visualizes user levels based on a unique "Kyungji" (Boundaries) concept and calculates levels using a specific **Tiered Growth System**.

The card must be designed using `easy_pil` (or `Pillow`) with a **Korean-style, Compact, and Density-filled** layout.

## 2. Directory Structure & Location
*   **Target Directory:** `src/rankcard/`
*   **Existing Context:**
    *   Voice Data Logic: `src/voice/` (Do not modify, just import/read)
    *   Chat Data Logic: `src/chatting/` (Do not modify, just import/read)
    *   Monggyeong (Main Level) Logic: `src/level/`
    *   Assets: `assets/fonts/`

**Required File Structure:**
```text
src/rankcard/
├── __init__.py
├── RankCardGenerator.py  # Image drawing logic (Visuals)
├── RankCardService.py    # Data aggregation & Level Calculation Logic
├── XPFormulas.py         # The new specific math for Voice/Chat levels
└── RankCardCog.py        # Discord Commands (*rank, /rank)
```

## 3. Data Integration & XP Logic (Crucial)

### A. Data Retrieval
*   **Do not** create new databases or tables for raw scores.
*   **Voice Score:** Import/Use the existing logic from `src/voice/` to retrieve the user's total voice time or score.
*   **Chat Score:** Import/Use the existing logic from `src/chatting/` to retrieve the user's total chat count or score.
*   **Main Level (Monggyeong):** Use `src/level/LevelDataManager` to retrieve the "Kyungji" (Role) and Total "Dagong" (EXP).

### B. Tiered XP System (New Logic)
You must implement a calculator (in `XPFormulas.py`) that converts **Total Raw Score** into **Level** and **Progress %** using the following rules.

**Concept:** Difficulty increases sharply every 10 levels (Tiers).
*   **Tier Calculation:** `current_level // 10`
*   **Tier Multiplier:** `1 + (tier * 0.5)`

**Formulas (XP required for NEXT level):**

1.  **Voice Level:**
    *   Base: `(Level * 139) + 70`
    *   **Final:** `((Level * 139) + 70) * (1 + (Level // 10) * 0.5)`
2.  **Chat Level:**
    *   Base: `(Level * 69.5) + 35`
    *   **Final:** `((Level * 69.5) + 35) * (1 + (Level // 10) * 0.5)`

**Implementation Snippet:**
Use this exact logic structure to determine requirements:
```python
import math

class LevelManager:
    # Constants
    VOICE_GROWTH = 139
    VOICE_BASE = 70
    CHAT_GROWTH = 69.5
    CHAT_BASE = 35

    @staticmethod
    def get_tier_multiplier(level):
        """Multiplier increases by 0.5 every 10 levels"""
        tier = level // 10
        return 1 + (tier * 0.5)

    @classmethod
    def get_next_voice_xp(cls, level):
        standard_xp = (level * cls.VOICE_GROWTH) + cls.VOICE_BASE
        return int(standard_xp * cls.get_tier_multiplier(level))

    @classmethod
    def get_next_chat_xp(cls, level):
        standard_xp = (level * cls.CHAT_GROWTH) + cls.CHAT_BASE
        return int(standard_xp * cls.get_tier_multiplier(level))
```
*Note: Since you will have the **Total XP** from the DB, you need to write a loop or an algorithm that subtracts required XP cumulatively to find the current Level and the remaining XP for the progress bar.*

## 4. Design Specifications (Visuals)

### A. General Settings
*   **Canvas:** `860px` x `280px`, Rounded Corners (`24px`).
*   **Theme:** Dark (`#0f0f13`) with specific gradients per role.
*   **Fonts:**
    *   Bold: `assets/fonts/Pretendard-Bold.ttf`
    *   Medium: `assets/fonts/Pretendard-Medium.ttf`
*   **Language:** **Korean Only**. Do not use English labels (e.g., use '다공' instead of 'EXP').

### B. "Kyungji" Themes (Roles)
Background gradient must change based on the user's role.

| Role Key | Korean Name | Color (Hex) | Concept |
| :--- | :--- | :--- | :--- |
| `hub` | **허브** | `#4ade80` | Green / Sprout |
| `dado` | **다도** | `#a3e635` | Lime / Tea |
| `daho` | **다호** | `#f472b6` | Pink / Flower |
| `dakyung` | **다경** | `#fbbf24` | Gold / Star |
| `dahyang` | **다향** | `#818cf8` | Purple / Universe |

### C. Layout Details
1.  **Background:**
    *   Dark base (`#0f0f13`).
    *   **Decoration:** Place a large, semi-transparent (opacity ~10%) icon or shape representing the role on the right side. (For prototype, use a large text character of the Role Name or a simple shape if icons are missing).
2.  **Avatar (Left):**
    *   Size: `140x140px`, Circular.
    *   Badge: Pill-shaped, located under the avatar, displaying the **Role Name** (e.g., **🌸 다호**).
3.  **Info (Right):**
    *   **Name:** Large, White.
    *   **Total Dagong:** `3,500 다공` (Use the Main Level XP).
    *   **Main Progress Bar:** Shows progress to the *Next Kyungji* (Role).
        *   Text: `다음 경지 : [Next Role Name]` | `[Percent]%`
4.  **Sub-Stats (Bottom):**
    *   **Chat Level:** Box layout. Label `채팅 레벨`, Value `Lv. [Calc]`. Progress bar based on the tiered formula.
    *   **Voice Level:** Box layout. Label `음성 레벨`, Value `Lv. [Calc]`. Progress bar based on the tiered formula.

## 5. Commands & Coding Standards

### A. Commands
The functionality must be accessible via:
1.  Prefix Command: `*rank`
2.  Prefix Command: `*랭크`
3.  Slash Command: `/rank`

### B. Requirements
1.  **Logging:** Analyze existing files in `src/` and replicate the logging format/system exactly.
2.  **Comments:** Provide clear comments explaining the logic (especially the tiered XP calculation).
3.  **Error Handling:**
    *   Handle cases where a user has no data in Voice or Chat modules (treat as 0 XP).
    *   Handle missing font files gracefully (fallback or error log).
4.  **Separation of Concerns:**
    *   `RankCardGenerator` should **only** draw images.
    *   `RankCardService` should **only** handle data logic (fetching from other modules + calculating levels).
    *   `RankCardCog` should handle Discord interactions.

***
*End of Instruction*