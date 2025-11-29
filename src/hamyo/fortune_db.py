"""
운세 기능에 필요한 설정을 JSON 파일로 관리하는 모듈입니다.

- 저장 위치: config/fortune.json
- 저장 정보: 길드별 운세 전송 시간, 운세 역할 ID, 운세 사용 대상(user_id/count)
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FORTUNE_CONFIG_PATH = Path("config/fortune.json")

# 길드 설정 기본값
DEFAULT_GUILD_CONFIG = {
    "send_time": None,       # "HH:MM" (KST)
    "role_id": None,         # int role id
    "channel_id": None,      # int channel id (운세 안내 채널)
    "last_ping_date": None,  # "YYYY-MM-DD" 로직
    "targets": []            # [{"user_id": int, "count": int, "last_used_date": str|None}, ...]
}


def _load_config() -> Dict:
    """fortune.json을 읽어 기본 구조를 보장합니다."""
    FORTUNE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if FORTUNE_CONFIG_PATH.exists():
        try:
            with open(FORTUNE_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except json.JSONDecodeError:
            # 손상된 파일은 덮어쓰기 전에 빈 구조로 반환
            pass
    return {}


def _save_config(config: Dict):
    """fortune.json을 저장합니다."""
    FORTUNE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FORTUNE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _ensure_guild_config(config: Dict, guild_id: int) -> Tuple[Dict, str]:
    """길드별 기본 구조를 확보하고 key를 반환합니다."""
    key = str(guild_id)
    if key not in config:
        config[key] = deepcopy(DEFAULT_GUILD_CONFIG)
    else:
        # targets 필드를 항상 리스트로 유지
        if "targets" not in config[key] or not isinstance(config[key].get("targets"), list):
            config[key]["targets"] = []
        else:
            # 기존 데이터에 last_used_date가 없으면 None으로 채운다
            normalized = []
            for t in config[key]["targets"]:
                if isinstance(t, dict):
                    if "last_used_date" not in t:
                        t["last_used_date"] = None
                    normalized.append(t)
            config[key]["targets"] = normalized
        if "send_time" not in config[key]:
            config[key]["send_time"] = None
        if "role_id" not in config[key]:
            config[key]["role_id"] = None
        if "channel_id" not in config[key]:
            config[key]["channel_id"] = None
        if "last_ping_date" not in config[key]:
            config[key]["last_ping_date"] = None
    return config, key


def get_guild_config(guild_id: int) -> Dict:
    """길드별 운세 설정을 반환합니다."""
    config = _load_config()
    _, key = _ensure_guild_config(config, guild_id)
    return config.get(key, deepcopy(DEFAULT_GUILD_CONFIG))


def set_send_time(guild_id: int, send_time: Optional[str]) -> Dict:
    """
    운세 전송 시간을 저장합니다.
    Args:
        send_time: "HH:MM" 형식(KST) 혹은 None(미설정)
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    config[key]["send_time"] = send_time
    _save_config(config)
    return config[key]


def set_role_id(guild_id: int, role_id: Optional[int]) -> Dict:
    """운세 역할 ID를 저장하거나 해제합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    config[key]["role_id"] = role_id
    _save_config(config)
    return config[key]


def set_channel_id(guild_id: int, channel_id: Optional[int]) -> Dict:
    """운세 안내 채널 ID를 저장하거나 해제합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    config[key]["channel_id"] = channel_id
    _save_config(config)
    return config[key]


def set_last_ping_date(guild_id: int, date_str: Optional[str]) -> Dict:
    """해당 길드의 마지막 안내 전송 날짜(YYYY-MM-DD)를 저장합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    config[key]["last_ping_date"] = date_str
    _save_config(config)
    return config[key]


def list_targets(guild_id: int) -> List[Dict]:
    """길드의 모든 운세 사용 대상을 반환합니다."""
    config = get_guild_config(guild_id)
    targets = []
    for t in config.get("targets", []):
        if isinstance(t, dict):
            targets.append({
                "user_id": int(t.get("user_id", 0)),
                "count": int(t.get("count", 0)),
                "last_used_date": t.get("last_used_date")
            })
    return targets


def get_target(guild_id: int, user_id: int) -> Optional[Dict]:
    """특정 유저의 운세 사용 정보를 조회합니다."""
    for target in list_targets(guild_id):
        if int(target.get("user_id", 0)) == int(user_id):
            if "last_used_date" not in target:
                target["last_used_date"] = None
            return target
    return None


def upsert_target(guild_id: int, user_id: int, count: int) -> Optional[Dict]:
    """
    운세 사용 대상을 추가/수정합니다.
    count가 1 미만이면 대상에서 제거합니다.
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    targets = config[key].get("targets", [])
    existing = get_target(guild_id, user_id)
    last_used = existing.get("last_used_date") if existing else None

    # 기존 대상 제거
    targets = [t for t in targets if int(t.get("user_id", 0)) != int(user_id)]

    if count >= 1:
        new_target = {"user_id": int(user_id), "count": int(count), "last_used_date": last_used}
        targets.append(new_target)
        config[key]["targets"] = targets
        _save_config(config)
        return new_target

    # count < 1 이면 삭제로 간주
    config[key]["targets"] = targets
    _save_config(config)
    return None


def remove_target(guild_id: int, user_id: int) -> bool:
    """운세 사용 대상을 삭제합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    before = len(config[key].get("targets", []))
    config[key]["targets"] = [
        t for t in config[key].get("targets", [])
        if int(t.get("user_id", 0)) != int(user_id)
    ]
    after = len(config[key]["targets"])
    _save_config(config)
    return after < before


def mark_target_used(guild_id: int, user_id: int, date_str: str) -> Optional[Dict]:
    """대상의 마지막 사용 날짜를 기록합니다. (YYYY-MM-DD)"""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    targets = config[key].get("targets", [])
    for t in targets:
        if int(t.get("user_id", 0)) == int(user_id):
            t["last_used_date"] = date_str
            break
    _save_config(config)
    return get_target(guild_id, user_id)


def reset_last_used(guild_id: int, user_id: Optional[int] = None) -> int:
    """
    하루 1회 제한을 초기화합니다.
    Args:
        guild_id: 길드 ID
        user_id: 특정 유저 ID (None이면 길드 내 모든 대상 초기화)
    Returns:
        변경된 대상 수
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    targets = config[key].get("targets", [])
    updated = 0

    for t in targets:
        if user_id is None or int(t.get("user_id", 0)) == int(user_id):
            if "last_used_date" in t and t["last_used_date"] is not None:
                t["last_used_date"] = None
                updated += 1
    config[key]["targets"] = targets
    _save_config(config)
    return updated


def decrement_all_targets() -> Dict[str, List[Dict]]:
    """
    모든 길드의 운세 사용 대상 count를 하루씩 차감합니다.
    count가 0 이하가 되면 제거합니다.
    Returns:
        {"updated": [...], "removed": [...]} 변경 목록
    """
    config = _load_config()
    updated = []
    removed = []

    for key, guild_conf in config.items():
        targets = guild_conf.get("targets", [])
        new_targets = []

        for target in targets:
            user_id = int(target.get("user_id", 0))
            try:
                old_count = int(target.get("count", 0))
            except (ValueError, TypeError):
                old_count = 0
            last_used_date = target.get("last_used_date")
            new_count = old_count - 1

            if new_count > 0:
                new_targets.append({"user_id": user_id, "count": new_count, "last_used_date": last_used_date})
                updated.append({
                    "guild_id": int(key),
                    "user_id": user_id,
                    "count": new_count,
                    "previous_count": old_count
                })
            else:
                removed.append({
                    "guild_id": int(key),
                    "user_id": user_id,
                    "previous_count": old_count
                })

        guild_conf["targets"] = new_targets
        config[key] = guild_conf

    _save_config(config)
    return {"updated": updated, "removed": removed}
