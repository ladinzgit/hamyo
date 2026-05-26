"""
운세 기능 설정/사용 기록 JSON 저장 모듈.

- 저장 위치: config/fortune.json
- 저장 정보: 길드별 운세 사용 채널, 유저별 일일 사용 기록/운세 히스토리
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FORTUNE_CONFIG_PATH = Path("config/fortune.json")

DEFAULT_GUILD_CONFIG = {
    "channel_id": None,
    "users": [],  # [{"user_id": int, "last_used_date": str|None, "fortune_history": [{"date": str, "text": str}, ...]}]
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
            pass
    return {}


def _save_config(config: Dict):
    """fortune.json을 저장합니다."""
    FORTUNE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FORTUNE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _normalize_user(user: Dict) -> Optional[Dict]:
    """유저 레코드 기본 구조를 보정합니다."""
    if not isinstance(user, dict):
        return None

    try:
        user_id = int(user.get("user_id", 0))
    except (ValueError, TypeError):
        return None

    last_used_date = user.get("last_used_date")
    if last_used_date is not None and not isinstance(last_used_date, str):
        last_used_date = None

    cleaned_history = []
    for h in user.get("fortune_history", []):
        if not isinstance(h, dict):
            continue
        date_str = h.get("date")
        text = h.get("text")
        if isinstance(date_str, str) and isinstance(text, str):
            cleaned_history.append({"date": date_str, "text": text})

    cleaned_history.sort(key=lambda x: x["date"])

    return {
        "user_id": user_id,
        "last_used_date": last_used_date,
        "fortune_history": cleaned_history,
    }


def _ensure_guild_config(config: Dict, guild_id: int) -> Tuple[Dict, str]:
    """길드별 기본 구조를 확보하고 key를 반환합니다."""
    key = str(guild_id)

    if key not in config or not isinstance(config[key], dict):
        config[key] = deepcopy(DEFAULT_GUILD_CONFIG)
    else:
        guild_conf = config[key]

        if "channel_id" not in guild_conf:
            guild_conf["channel_id"] = None

        # 구버전 데이터(targets) 마이그레이션
        users = guild_conf.get("users")
        if not isinstance(users, list):
            users = []

        legacy_targets = guild_conf.get("targets", [])
        if isinstance(legacy_targets, list):
            existing_ids = {int(u.get("user_id", 0)) for u in users if isinstance(u, dict)}
            for t in legacy_targets:
                if not isinstance(t, dict):
                    continue
                try:
                    user_id = int(t.get("user_id", 0))
                except (ValueError, TypeError):
                    continue
                if user_id in existing_ids:
                    continue
                users.append({
                    "user_id": user_id,
                    "last_used_date": t.get("last_used_date"),
                    "fortune_history": t.get("fortune_history", []),
                })
                existing_ids.add(user_id)

        normalized_users = []
        seen = set()
        for user in users:
            normalized = _normalize_user(user)
            if not normalized:
                continue
            uid = normalized["user_id"]
            if uid in seen:
                continue
            seen.add(uid)
            normalized_users.append(normalized)

        guild_conf["users"] = normalized_users

        # 더 이상 사용하지 않는 키는 정리
        guild_conf.pop("targets", None)
        guild_conf.pop("role_id", None)
        guild_conf.pop("send_time", None)
        guild_conf.pop("last_ping_date", None)
        guild_conf.pop("buttons", None)

        config[key] = guild_conf

    return config, key


def get_guild_config(guild_id: int) -> Dict:
    """길드별 운세 설정을 반환합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    _save_config(config)
    return config.get(key, deepcopy(DEFAULT_GUILD_CONFIG))


def set_channel_id(guild_id: int, channel_id: Optional[int]) -> Dict:
    """운세 사용 채널 ID를 저장하거나 해제합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)
    config[key]["channel_id"] = channel_id
    _save_config(config)
    return config[key]


def list_users(guild_id: int) -> List[Dict]:
    """길드의 운세 사용자 기록 목록을 반환합니다."""
    conf = get_guild_config(guild_id)
    users = conf.get("users", [])
    if not isinstance(users, list):
        return []
    result = []
    for u in users:
        normalized = _normalize_user(u)
        if normalized:
            result.append(normalized)
    return result


def get_user_record(guild_id: int, user_id: int) -> Optional[Dict]:
    """특정 유저의 운세 사용 기록을 조회합니다."""
    target_id = int(user_id)
    for user in list_users(guild_id):
        if int(user.get("user_id", 0)) == target_id:
            return user
    return None


def upsert_user_record(guild_id: int, user_id: int, last_used_date: Optional[str] = None) -> Dict:
    """유저 운세 사용 기록을 추가/갱신합니다."""
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    users = config[key].get("users", [])
    target_id = int(user_id)

    # 기존 데이터 유지 갱신
    for u in users:
        if int(u.get("user_id", 0)) == target_id:
            if last_used_date is not None:
                u["last_used_date"] = last_used_date
            if "fortune_history" not in u or not isinstance(u.get("fortune_history"), list):
                u["fortune_history"] = []
            _save_config(config)
            return _normalize_user(u)

    new_user = {
        "user_id": target_id,
        "last_used_date": last_used_date,
        "fortune_history": [],
    }
    users.append(new_user)
    config[key]["users"] = users
    _save_config(config)
    return _normalize_user(new_user)


def mark_user_used(guild_id: int, user_id: int, date_str: str) -> Dict:
    """유저의 마지막 운세 사용 날짜를 기록합니다."""
    return upsert_user_record(guild_id, user_id, last_used_date=date_str)


def add_fortune_history(guild_id: int, user_id: int, date_str: str, fortune_text: str, keep_days: int = 7) -> bool:
    """
    유저의 운세 생성 기록을 추가합니다.
    같은 날짜 기록이 있으면 최신 텍스트로 교체하며, 최근 keep_days만 유지합니다.
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    users = config[key].get("users", [])
    target_id = int(user_id)

    found = None
    for u in users:
        if int(u.get("user_id", 0)) == target_id:
            found = u
            break

    if not found:
        found = {
            "user_id": target_id,
            "last_used_date": None,
            "fortune_history": [],
        }
        users.append(found)

    history = found.get("fortune_history", [])
    if not isinstance(history, list):
        history = []

    history = [
        h for h in history
        if not (isinstance(h, dict) and h.get("date") == date_str)
    ]

    trimmed_text = str(fortune_text).strip()[:3500]
    history.append({"date": date_str, "text": trimmed_text})

    valid_records = [
        h for h in history
        if isinstance(h, dict) and isinstance(h.get("date"), str) and isinstance(h.get("text"), str)
    ]
    valid_records.sort(key=lambda x: x["date"])
    found["fortune_history"] = valid_records[-max(1, int(keep_days)):]

    config[key]["users"] = users
    _save_config(config)
    return True


def get_recent_fortune_texts(guild_id: int, user_id: int, days: int = 7) -> List[str]:
    """유저의 최근 운세 본문 텍스트를 오래된 순으로 반환합니다."""
    user = get_user_record(guild_id, user_id)
    if not user:
        return []

    history = user.get("fortune_history", [])
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
        user_id: 특정 유저 ID (None이면 길드 내 전체 사용자 초기화)
    Returns:
        변경된 사용자 수
    """
    config = _load_config()
    config, key = _ensure_guild_config(config, guild_id)

    users = config[key].get("users", [])
    updated = 0

    target_id = int(user_id) if user_id is not None else None

    for u in users:
        if target_id is not None and int(u.get("user_id", 0)) != target_id:
            continue
        if u.get("last_used_date") is not None:
            u["last_used_date"] = None
            updated += 1

    config[key]["users"] = users
    _save_config(config)
    return updated


def swap_user_fortune_data(old_user_id: int, new_user_id: int) -> bool:
    """
    운세 데이터에서 old_user_id 정보를 new_user_id로 통합합니다.
    """
    try:
        config = _load_config()
        changed = False

        for key, guild_conf in config.items():
            if not isinstance(guild_conf, dict):
                continue

            # 정규화 보장
            config, key = _ensure_guild_config(config, int(key))
            guild_conf = config.get(key, {})
            users = guild_conf.get("users", [])

            main_user = None
            sub_user = None
            for u in users:
                uid = int(u.get("user_id", 0))
                if uid == int(new_user_id):
                    main_user = u
                elif uid == int(old_user_id):
                    sub_user = u

            if not main_user and not sub_user:
                continue

            others = [
                u for u in users
                if int(u.get("user_id", 0)) not in (int(new_user_id), int(old_user_id))
            ]

            if main_user:
                if sub_user:
                    # last_used_date는 더 최신(문자열 비교) 값 우선
                    main_date = main_user.get("last_used_date")
                    sub_date = sub_user.get("last_used_date")
                    if isinstance(sub_date, str) and (not isinstance(main_date, str) or sub_date > main_date):
                        main_user["last_used_date"] = sub_date

                    main_history = main_user.get("fortune_history", [])
                    sub_history = sub_user.get("fortune_history", [])
                    merged = []
                    seen_dates = set()
                    for rec in sorted(main_history + sub_history, key=lambda x: x.get("date", "")):
                        if not isinstance(rec, dict):
                            continue
                        d = rec.get("date")
                        t = rec.get("text")
                        if not isinstance(d, str) or not isinstance(t, str):
                            continue
                        if d in seen_dates:
                            continue
                        seen_dates.add(d)
                        merged.append({"date": d, "text": t})
                    main_user["fortune_history"] = merged[-7:]

                others.append(main_user)
                changed = True
            elif sub_user:
                sub_user["user_id"] = int(new_user_id)
                others.append(sub_user)
                changed = True

            guild_conf["users"] = others
            config[key] = guild_conf

        if changed:
            _save_config(config)
            return True
        return False

    except Exception as e:
        print(f"Error swapping fortune data: {e}")
        return False
