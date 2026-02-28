# src/level/LevelConstants.py

# 역할 승급 기준 (다공 -> 쪽)
ROLE_THRESHOLDS = {
    'yeobaek': 0,
    'goyo': 400,
    'seoyu': 1800,
    'seorim': 6000,
    'seohyang': 12000
}

# 역할 순서
ROLE_ORDER = ['yeobaek', 'goyo', 'seoyu', 'seorim', 'seohyang']

# 역할 한글 표시명
ROLE_DISPLAY = {
    'yeobaek': '여백',
    'goyo': '고요',
    'seoyu': '서유',
    'seorim': '서림',
    'seohyang': '서향'
}

# 역할별 디스코드 역할 ID
ROLE_IDS = {
    'yeobaek': 1396829213172174890,
    'goyo': 1396829213172174888,
    'seoyu': 1398926065111662703,
    'seorim': 1396829213172174891,
    'seohyang': 1396829213172174892
}

# 역할별 기호/이모지
ROLE_EMOJI = {
    'yeobaek': '🌱',
    'goyo': '🍃',
    'seoyu': '🌸',
    'seorim': '🌟',
    'seohyang': '💫'
}

def get_role_info():
    """LevelConfig.py 등에서 사용되는 통합 딕셔너리를 반환"""
    return {
        key: {
            'name': ROLE_DISPLAY[key],
            'threshold': ROLE_THRESHOLDS[key],
            'emoji': ROLE_EMOJI[key],
            'id': ROLE_IDS[key]
        }
        for key in ROLE_ORDER
    }
