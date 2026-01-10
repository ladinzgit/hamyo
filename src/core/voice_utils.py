# voice_utils.py
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
