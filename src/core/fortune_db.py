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
    "send_time": [],         # ["HH:MM", ...] (KST)
    "role_id": None,         # int role id
    "channel_id": None,      # int channel id (운세 안내 채널)
    "last_ping_date": {},    # {"HH:MM": "YYYY-MM-DD"}
    "targets": [],           # [{"user_id": int, "count": int, "last_used_date": str|None, "fortune_history": [{"date": str, "text": str}, ...]}, ...]
    "buttons": {}            # {message_id: {"expiration_days": int, "used_users": [user_id, ...]}}
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
                    if "fortune_history" not in t or not isinstance(t.get("fortune_history"), list):
                        t["fortune_history"] = []
                    else:
                        cleaned_history = []
                        for h in t["fortune_history"]:
                            if isinstance(h, dict):
                                date_str = h.get("date")
                                text = h.get("text")
                                if isinstance(date_str, str) and isinstance(text, str):
                                    cleaned_history.append({"date": date_str, "text": text})
                        t["fortune_history"] = cleaned_history
                    normalized.append(t)
            config[key]["targets"] = normalized
        # send_time 호환성 유지 및 리스트화
        if "send_time" not in config[key]:
            config[key]["send_time"] = []
        elif isinstance(config[key]["send_time"], str):
            config[key]["send_time"] = [config[key]["send_time"]]
        elif config[key]["send_time"] is None:
            config[key]["send_time"] = []

        if "role_id" not in config[key]:
            config[key]["role_id"] = None
        if "channel_id" not in config[key]:
            config[key]["channel_id"] = None

        # last_ping_date 호환성 유지 및 딕셔너리화
        if "last_ping_date" not in config[key] or not isinstance(config[key]["last_ping_date"], dict):
            config[key]["last_ping_date"] = {}

        if "buttons" not in config[key]:
            config[key]["buttons"] = {}
    return config, key


def get_guild_config(guild_id: int) -> Dict:
    """길드별 운세 설정을 반환합니다."""
    config = _load_config()
    _, key = _ensure_guild_config(config, guild_id)
    return config.get(key, deepcopy(DEFAULT_GUILD_CONFIG))


def add_send_time(guild_id: int, send_time: str) -> bool:
    """운세 전송 시간을 추가합니다. 이미 존재하면 False 반환."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    if send_time in config[key]["send_time"]:
        return False
    config[key]["send_time"].append(send_time)
    config[key]["send_time"].sort()  # 시간순 정렬
    _save_config(config)
    return True


def remove_send_time(guild_id: int, send_time: str) -> bool:
    """운세 전송 시간을 제거합니다. 존재하지 않으면 False 반환."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    if send_time not in config[key]["send_time"]:
        return False
    config[key]["send_time"].remove(send_time)
    _save_config(config)
    return True


def get_send_times(guild_id: int) -> List[str]:
    """길드의 운세 전송 시간 목록을 반환합니다."""
    config = get_guild_config(guild_id)
    return config.get("send_time", [])


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


def set_last_ping_date(guild_id: int, time_str: str, date_str: Optional[str]) -> Dict:
    """해당 길드의 특정 시간 마지막 안내 전송 날짜를 저장합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    if date_str is None:
        config[key]["last_ping_date"].pop(time_str, None)
    else:
        config[key]["last_ping_date"][time_str] = date_str
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
                "last_used_date": t.get("last_used_date"),
                "fortune_history": t.get("fortune_history", [])
            })
    return targets


def get_target(guild_id: int, user_id: int) -> Optional[Dict]:
    """특정 유저의 운세 사용 정보를 조회합니다."""
    for target in list_targets(guild_id):
        if int(target.get("user_id", 0)) == int(user_id):
            if "last_used_date" not in target:
                target["last_used_date"] = None
            if "fortune_history" not in target or not isinstance(target.get("fortune_history"), list):
                target["fortune_history"] = []
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
    history = existing.get("fortune_history", []) if existing else []

    # 기존 대상 제거
    targets = [t for t in targets if int(t.get("user_id", 0)) != int(user_id)]

    if count >= 1:
        new_target = {
            "user_id": int(user_id),
            "count": int(count),
            "last_used_date": last_used,
            "fortune_history": history,
        }
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


def add_fortune_history(guild_id: int, user_id: int, date_str: str, fortune_text: str, keep_days: int = 7) -> bool:
    """
    대상 유저의 운세 생성 기록을 추가합니다.
    같은 날짜 기록이 있으면 최신 텍스트로 교체하며, 최근 keep_days만 유지합니다.
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    targets = config[key].get("targets", [])
    updated = False

    for t in targets:
        if int(t.get("user_id", 0)) == int(user_id):
            history = t.get("fortune_history", [])
            history = [
                h for h in history
                if not (isinstance(h, dict) and h.get("date") == date_str)
            ]

            # 저장 용량 급증 방지를 위해 텍스트 길이 제한
            trimmed_text = str(fortune_text).strip()[:3500]
            history.append({"date": date_str, "text": trimmed_text})

            # 날짜 문자열 기준 최근 keep_days개 유지 (YYYY-MM-DD 정렬 가능)
            history = sorted(
                [h for h in history if isinstance(h, dict) and isinstance(h.get("date"), str)],
                key=lambda x: x["date"],
            )
            t["fortune_history"] = history[-max(1, int(keep_days)):]
            updated = True
            break

    if updated:
        _save_config(config)
    return updated


def get_recent_fortune_texts(guild_id: int, user_id: int, days: int = 7) -> List[str]:
    """대상 유저의 최근 운세 본문 텍스트를 오래된 순으로 반환합니다."""
    target = get_target(guild_id, user_id)
    if not target:
        return []

    history = target.get("fortune_history", [])
    if not isinstance(history, list):
        return []

    records = [
        h for h in history
        if isinstance(h, dict) and isinstance(h.get("date"), str) and isinstance(h.get("text"), str)
    ]
    records.sort(key=lambda x: x["date"])
    recent = records[-max(1, int(days)):]
    return [h["text"] for h in recent]


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


def swap_user_fortune_data(old_user_id: int, new_user_id: int) -> bool:
    """
    운세 데이터에서 old_user_id의 정보를 new_user_id로 통합합니다.
    new_user_id가 이미 대상이라면 count를 합치고, 아니라면 old_user_id를 new_user_id로 바꿉니다.
    """
    try:
        config = _load_config()
        changed = False
        
        for key, guild_conf in config.items():
            targets = guild_conf.get("targets", [])
            new_targets = []
            
            # 1. Main(new_id)과 Sub(old_id) 찾기
            main_target = None
            sub_target = None
            
            for t in targets:
                uid = int(t.get("user_id", 0))
                if uid == int(new_user_id):
                    main_target = t
                elif uid == int(old_user_id):
                    sub_target = t
            
            # 둘 다 없으면 패스
            if not main_target and not sub_target:
                continue

            # 2. 로직 적용
            # Main이 있으면: Main.count += Sub.count (Sub는 제거)
            # Main이 없으면: Sub.id -> Main.id (Sub 유지 -> 변경)
            
            # 일단 기존 리스트에서 둘 다 제외한 리스트를 만듦
            others = [t for t in targets if int(t.get("user_id", 0)) not in (int(new_user_id), int(old_user_id))]
            
            if main_target:
                # 합치기
                if sub_target:
                    main_target["count"] = int(main_target.get("count", 0)) + int(sub_target.get("count", 0))
                    # last_used_date는? Main 우선 (이미 썼으면 쓴 걸로)
                others.append(main_target)
                changed = True
            elif sub_target:
                # Sub 이름을 Main으로 변경
                sub_target["user_id"] = int(new_user_id)
                others.append(sub_target)
                changed = True
                
            guild_conf["targets"] = others
            config[key] = guild_conf
        
        if changed:
            _save_config(config)
            return True
        return False
        
    except Exception as e:
        print(f"Error swapping fortune data: {e}")
        return False


def create_fortune_button(guild_id: int, message_id: int, expiration_days: int):
    """
    운세 보상 버튼을 생성하여 저장합니다.
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    
    config[key]["buttons"][str(message_id)] = {
        "expiration_days": int(expiration_days),
        "used_users": []
    }
    _save_config(config)


def get_button_info(guild_id: int, message_id: int) -> Optional[Dict]:
    """
    버튼 정보를 가져옵니다.
    """
    config = get_guild_config(guild_id)
    buttons = config.get("buttons", {})
    return buttons.get(str(message_id))


def record_button_click(guild_id: int, message_id: int, user_id: int) -> bool:
    """
    유저가 버튼을 클릭했음을 기록합니다.
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    
    buttons = config[key].get("buttons", {})
    btn_data = buttons.get(str(message_id))
    
    if not btn_data:
        return False
        
    used_users = btn_data.get("used_users", [])
    if int(user_id) in used_users:
        return False  # 이미 누름
        
    used_users.append(int(user_id))
    btn_data["used_users"] = used_users
    config[key]["buttons"][str(message_id)] = btn_data
    _save_config(config)
    return True


def is_button_clicked(guild_id: int, message_id: int, user_id: int) -> bool:
    """
    유저가 해당 버튼을 이미 눌렀는지 확인합니다.
    """
    info = get_button_info(guild_id, message_id)
    if not info:
        return False
    return int(user_id) in info.get("used_users", [])
