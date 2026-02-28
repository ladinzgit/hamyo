
import discord
from typing import List, Set
from .DataManager import DataManager

async def get_expanded_tracked_channels(
    bot: discord.Client,
    data_manager: DataManager,
    source: str = "voice"
) -> List[int]:
    """
    tracked_channels 테이블에 등록된 값(카테고리/채널 혼재)을
    실제 집계에 쓰일 '음성/스테이지 채널 ID' 목록으로 확장해 반환.
    - 카테고리 → 하위 voice + stage 채널 포함
    - 삭제된 채널 → deleted_channels 테이블에서 카테고리 매핑으로 보강
    - 삭제된 카테고리 → 해당 카테고리에 속한 삭제된 채널도 포함
    """
    tracked_ids = await data_manager.get_tracked_channels(source)
    expanded_ids: Set[int] = set()

    category_ids: Set[int] = set()
    deleted_category_ids: Set[int] = set()  # 삭제된 카테고리 ID 저장
    
    # 1) 등록 목록을 분류
    for cid in tracked_ids:
        ch = bot.get_channel(cid)
        if ch is None:
            # fetch_channel은 레이트 제한도 있고 실패 가능성 있으니, 먼저 get_channel로 시도
            try:
                ch = await bot.fetch_channel(cid)
            except Exception:
                ch = None

        if isinstance(ch, discord.CategoryChannel):
            category_ids.add(cid)
        elif isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            expanded_ids.add(cid)
        else:
            # 삭제되었거나 접근 불가 → 삭제된 카테고리로 간주하여 deleted_channels에서 조회
            deleted_category_ids.add(cid)

    # 2) 카테고리 하위의 활성 채널(보이스 + 스테이지) 추가
    for cat_id in category_ids:
        cat = bot.get_channel(cat_id) or await bot.fetch_channel(cat_id)
        if isinstance(cat, discord.CategoryChannel):
            for vc in getattr(cat, "voice_channels", []):
                expanded_ids.add(vc.id)
            # ✅ Stage 채널도 포함
            for sc in getattr(cat, "stage_channels", []):
                expanded_ids.add(sc.id)

    # 3) 삭제된 채널(카테고리 매핑 보유분) 추가 - 활성 카테고리 + 삭제된 카테고리 모두 포함
    all_category_ids = category_ids | deleted_category_ids
    if all_category_ids:
        deleted_ids = await data_manager.get_deleted_channels_by_categories(list(all_category_ids))
        expanded_ids.update(int(i) for i in deleted_ids)

    return list(expanded_ids)

async def get_herb_expanded_tracked_channels(
    bot: discord.Client,
    data_manager: DataManager,
    source: str = "herb"
) -> List[int]:
    """
    tracked_channels 테이블에 등록된 값(카테고리/채널 혼재)을
    실제 집계에 쓰일 '음성/스테이지 채널 ID' 목록으로 확장해 반환.
    - 카테고리 → 하위 voice + stage 채널 포함
    - 삭제된 채널 → deleted_channels 테이블에서 카테고리 매핑으로 보강
    - 삭제된 카테고리 → 해당 카테고리에 속한 삭제된 채널도 포함
    """
    tracked_ids = await data_manager.get_tracked_channels(source)
    expanded_ids: Set[int] = set()

    category_ids: Set[int] = set()
    deleted_category_ids: Set[int] = set()  # 삭제된 카테고리 ID 저장
    
    # 1) 등록 목록을 분류
    for cid in tracked_ids:
        ch = bot.get_channel(cid)
        if ch is None:
            # fetch_channel은 레이트 제한도 있고 실패 가능성 있으니, 먼저 get_channel로 시도
            try:
                ch = await bot.fetch_channel(cid)
            except Exception:
                ch = None

        if isinstance(ch, discord.CategoryChannel):
            category_ids.add(cid)
        elif isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            expanded_ids.add(cid)
        else:
            # 삭제되었거나 접근 불가 → 삭제된 카테고리로 간주하여 deleted_channels에서 조회
            deleted_category_ids.add(cid)

    # 2) 카테고리 하위의 활성 채널(보이스 + 스테이지) 추가
    for cat_id in category_ids:
        cat = bot.get_channel(cat_id) or await bot.fetch_channel(cat_id)
        if isinstance(cat, discord.CategoryChannel):
            for vc in getattr(cat, "voice_channels", []):
                expanded_ids.add(vc.id)
            # ✅ Stage 채널도 포함
            for sc in getattr(cat, "stage_channels", []):
                expanded_ids.add(sc.id)

    # 3) 삭제된 채널(카테고리 매핑 보유분) 추가 - 활성 카테고리 + 삭제된 카테고리 모두 포함
    all_category_ids = category_ids | deleted_category_ids
    if all_category_ids:
        deleted_ids = await data_manager.get_deleted_channels_by_categories(list(all_category_ids))
        expanded_ids.update(int(i) for i in deleted_ids)

    return list(expanded_ids)

# --- Special Category Rules ---
# Key: Category ID (int), Value: List of allowed Channel IDs (int)
SPECIAL_CATEGORY_RULES = {
    1452268260010496162: [1396829224744259691]
}

async def get_filtered_tracked_channels(
    bot: discord.Client,
    data_manager: DataManager,
    source: str = "voice"
) -> List[int]:
    """
    기본적으로 get_expanded_tracked_channels와 동일하게 작동하되,
    SPECIAL_CATEGORY_RULES에 정의된 카테고리에 대해서는
    지정된 채널 ID만 필터링하여 반환합니다.
    """
    tracked_ids = await data_manager.get_tracked_channels(source)
    expanded_ids: Set[int] = set()

    category_ids: Set[int] = set()
    deleted_category_ids: Set[int] = set()
    
    # 1) 등록 목록 분류
    for cid in tracked_ids:
        ch = bot.get_channel(cid)
        if ch is None:
            try:
                ch = await bot.fetch_channel(cid)
            except Exception:
                ch = None

        if isinstance(ch, discord.CategoryChannel):
            category_ids.add(cid)
        elif isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            # 개별 채널 등록의 경우:
            # 만약 이 채널이 특수 카테고리에 속해있다면 규칙을 확인해야 할 수도 있지만,
            # 현재 요구사항은 "카테고리 ID가 X인 경우 Y채널만 포함"이므로
            # 카테고리 단위로 트래킹 등록된 경우를 주로 제어합니다.
            # 개별 등록된 채널은 사용자가 의도한 것이므로 그냥 추가합니다.
            # (필요 시 수정 가능)
            expanded_ids.add(cid)
        else:
            deleted_category_ids.add(cid)

    # 2) 활성 카테고리 처리
    for cat_id in category_ids:
        # 특수 규칙 적용 대상인지 확인
        allowed_channels = SPECIAL_CATEGORY_RULES.get(cat_id)
        
        cat = bot.get_channel(cat_id) or await bot.fetch_channel(cat_id)
        
        if isinstance(cat, discord.CategoryChannel):
            children = getattr(cat, "voice_channels", []) + getattr(cat, "stage_channels", [])
            for ch in children:
                # 규칙이 있는 카테고리라면, 허용 목록에 있는 경우만 추가
                if allowed_channels is not None:
                    if ch.id in allowed_channels:
                        expanded_ids.add(ch.id)
                else:
                    # 규칙 없으면 모두 추가
                    expanded_ids.add(ch.id)

    # 3) 삭제된 채널 처리
    tracked_special_cats = set(SPECIAL_CATEGORY_RULES.keys())
    target_special_cats = deleted_category_ids & tracked_special_cats
    target_normal_cats = deleted_category_ids - tracked_special_cats
    
    # 3-1) 일반 삭제 카테고리
    if target_normal_cats:
        deleted_ids = await data_manager.get_deleted_channels_by_categories(list(target_normal_cats))
        expanded_ids.update(deleted_ids)
        
    # 3-2) 특수 삭제 카테고리
    if target_special_cats:
         candidates = await data_manager.get_deleted_channels_by_categories(list(target_special_cats))
         
         allowed_all_special = set()
         for cat_id in target_special_cats:
             allowed = SPECIAL_CATEGORY_RULES.get(cat_id, [])
             allowed_all_special.update(allowed)
             
         for ch_id in candidates:
             if ch_id in allowed_all_special:
                 expanded_ids.add(ch_id)

    # 4) 특정 카테고리에 속한 채널은 집계에서 완전 제외 (예: 책방선율)
    EXCLUDED_CATEGORIES = {1474014243052585126}
    final_expanded = set()
    for ch_id in expanded_ids:
        ch = bot.get_channel(ch_id)
        if ch and getattr(ch, "category_id", None) in EXCLUDED_CATEGORIES:
            continue
        final_expanded.add(ch_id)

    return list(final_expanded)
