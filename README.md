<div align="center">

<br>

# � hamyo

### `하묘` — 몽경수행 디스코드 봇

<br>

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.5+-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![License](https://img.shields.io/badge/License-MIT-F5A623?style=for-the-badge)](LICENSE)

<br>

> _차향이 스며든 꿈의 세계 — 서버 활동을 촉진하고 커뮤니티에 재미를 더하는 다기능 봇_

<br>

</div>

---

## 📋 목차

- [개요](#-개요)
- [기능](#-기능)
- [프로젝트 구조](#-프로젝트-구조)
- [시작하기](#-시작하기)
- [명령어 레퍼런스](#-명령어-레퍼런스)
- [기여하기](#-기여하기)
- [라이센스](#-라이센스)

---

## 🌸 개요

**hamyo**(하묘)는 디스코드 서버 커뮤니티를 위한 올인원 다기능 봇입니다.  
레벨 시스템, 경제, 음성 활동 측정, 운세, 생일 관리, 채팅 실적, 허브 키우기 등  
다양한 모듈이 유기적으로 연결되어 **몽경수행**이라는 독자적인 성장 체계를 구축합니다.

<br>

## ✨ 기능

<table>
<tr>
<td width="50%" valign="top">

### 📈 몽경수행 — 레벨 & 퀘스트
서버 활동을 통해 **다공(경험치)**을 쌓고,  
`허브` → `다도` → `다호` → `다경` → `다향`으로  
**경지를 승급**하며 성장하세요.

- 일일 / 주간 / 일회성 **퀘스트 시스템**
- 누적 / 월간 / 주간 / 일간 **순위 시스템**
- 자동 역할 부여 및 칭호 관리

</td>
<td width="50%" valign="top">

### 💰 온 — 경제 시스템
서버 전용 화폐 **'온'**을 거래하고  
활동 인증을 통해 보상을 획득하세요.

- 출석 체크 & 인증 보상
- 관리자 지급 / 회수 시스템
- 보유량 확인 및 관리 명령어

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎤 보이스 — 음성 활동 추적
음성 채널 참여 시간을 **실시간으로 기록**하고  
기간별 통계와 순위를 제공합니다.

- 일간 / 주간 / 월간 / 누적 통계
- 서버 전체 & 역할별 순위
- 음성 기반 퀘스트 자동 완료

</td>
<td width="50%" valign="top">

### � 운세 — 일일 운세 시스템
매일 새로운 **오늘의 운세**를 확인하고  
운세 이용권을 관리하세요.

- 버튼 기반 이용권 배포
- 관리자 설정 명령어
- 자동 일일 초기화 스케줄러

</td>
</tr>
<tr>
<td width="50%" valign="top">

### � 생일 — 생일 알림 & 관리
서버 멤버의 생일을 등록하고  
**자동 축하 메시지**를 보내세요.

- 생일 등록 / 수정 / 삭제
- 자동 알림 & 인터페이스
- 달력 기반 생일 조회

</td>
<td width="50%" valign="top">

### � 채팅 — 채팅 실적 관리
텍스트 채널 활동량을 **자동으로 집계**하고  
기간별 채팅 순위를 확인하세요.

- 채팅량 자동 카운팅
- 역할 필터링 순위 시스템
- 기간별 실적 통계

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🌿 허브 — 허브 키우기
가상의 **허브를 키우며** 서버 활동에  
새로운 재미를 더하세요.

- 허브 관리 명령어
- 성장 시스템 & 보드
- 이벤트 연동

</td>
<td width="50%" valign="top">

### 🛠️ 관리 — 서버 관리 도구
서버 운영에 필요한 **관리자 전용 도구**를  
제공합니다.

- 본부계 변경 (계정 데이터 병합)
- 대량 DM 발송
- 봇 재시작 / 임베드 관리

</td>
</tr>
</table>

<br>

---

## 🏗️ 프로젝트 구조

```
hamyo/
├── main.py                    # 봇 엔트리포인트
├── pyproject.toml             # Poetry 의존성 및 프로젝트 설정
│
├── config/                    # JSON 기반 설정 파일
│   ├── config.json            # 전역 봇 설정
│   ├── level_config.json      # 레벨 시스템 설정
│   ├── chatting_config.json   # 채팅 실적 설정
│   ├── birthday_config.json   # 생일 관리 설정
│   ├── embed_config.json      # 임베드 & 역할 버튼 설정
│   ├── fortune.json           # 운세 시스템 설정
│   ├── herbconfig.json        # 허브 시스템 설정
│   ├── tree_config.json       # 비몽트리 이벤트 설정
│   └── logger_config.json     # 로깅 채널 설정
│
├── data/                      # SQLite 데이터베이스
│   ├── level_system.db        # 레벨 & 퀘스트 데이터
│   ├── balance.db             # 경제(온) 데이터
│   ├── voice_logs.db          # 음성 활동 로그
│   ├── attendance.db          # 출석 데이터
│   ├── birthday.db            # 생일 데이터
│   ├── herb.db                # 허브 시스템 데이터
│   └── tree.db                # 비몽트리 이벤트 데이터
│
└── src/
    ├── core/                  # 공통 데이터 매니저 & 유틸리티
    │   ├── DataManager.py
    │   ├── LevelDataManager.py
    │   ├── balance_data_manager.py
    │   ├── birthday_db.py
    │   ├── fortune_db.py
    │   ├── voice_utils.py
    │   └── admin_utils.py
    │
    ├── level/                 # 몽경수행 (레벨/퀘스트)
    │   ├── LevelSystem.py
    │   ├── LevelChecker.py
    │   ├── LevelCommand.py
    │   ├── LevelConfig.py
    │   └── PrefixChanger.py
    │
    ├── economy/               # 경제 시스템
    │   ├── Economy.py
    │   ├── OnAdminSettings.py
    │   └── attendance.py
    │
    ├── voice/                 # 음성 활동
    │   ├── VoiceTracker.py
    │   ├── VoiceCommands.py
    │   └── VoiceConfig.py
    │
    ├── fortune/               # 운세 시스템
    │   ├── FortuneCommand.py
    │   ├── FortuneConfig.py
    │   └── FortuneTimer.py
    │
    ├── birthday/              # 생일 관리
    │   ├── Birthday.py
    │   └── BirthdayInterface.py
    │
    ├── chatting/              # 채팅 실적
    │   ├── ChattingCommands.py
    │   ├── ChattingConfig.py
    │   └── ChattingRanking.py
    │
    ├── herb/                  # 허브 키우기
    │   ├── HerbCommand.py
    │   └── HerbConfig.py
    │
    ├── embed/                 # 임베드 & 역할 버튼
    │   ├── EmbedCommon.py
    │   ├── EmbedUtils.py
    │   └── RoleEmbed.py
    │
    ├── admin/                 # 서버 관리 도구
    │   ├── AccountSwapper.py
    │   ├── BulkDM.py
    │   └── Restart.py
    │
    └── utils/                 # 유틸리티 (우선 로드)
        ├── Scheduler.py
        ├── Logger.py
        ├── Counter.py
        └── Response.py
```

<br>

---

## 🚀 시작하기

### 필요 사항

| 항목 | 버전 |
|------|------|
| Python | `3.13+` |
| Poetry | `latest` |

### 1. 저장소 클론

```bash
git clone https://github.com/ladinzgit/hamyo.git
cd hamyo
```

### 2. Poetry 설치 (선택)

```bash
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# macOS / Linux
curl -sSL https://install.python-poetry.org | python3 -
```

### 3. 의존성 설치

```bash
poetry install
```

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 키를 입력하세요.

```env
DISCORD_BOT_TOKEN=your_bot_token_here
APPLICATION_ID=your_application_id_here
```

### 5. 봇 실행

```bash
# Poetry 가상환경에서 직접 실행
poetry run python main.py

# 또는 가상환경 활성화 후 실행
poetry shell
python main.py
```

<br>

---

## 🎮 명령어 레퍼런스

> `*` 접두사 명령어와 `/` 슬래시 명령어를 모두 지원합니다.

<details>
<summary><b>� 몽경수행 (레벨 시스템)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*내정보 [@유저]` | 몽경수행 현황 (다공, 경지, 퀘스트 진행도) 확인 |
| `*출석` | 출석 체크 및 일일 퀘스트 완료 |
| `*순위 [기간]` | 다공 순위 확인 (`일간` / `주간` / `월간` / `누적`) |

</details>

<details>
<summary><b>💰 온 (경제 시스템)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*온 확인 [@유저]` | '온' 보유량 확인 |
| `*온 지급 @유저 금액 [횟수]` | 🔒 유저에게 '온' 지급 |
| `*온 회수 @유저 금액` | 🔒 유저 '온' 회수 |
| `*온 인증 @유저 조건 [횟수]` | 🔒 조건 달성 인증 및 보상 지급 |

> � = 관리자 전용 명령어

</details>

<details>
<summary><b>🎤 보이스 (음성 활동)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/보이스 확인 [유저] [기간] [기준일]` | 음성 활동 시간 확인 |
| `/보이스 순위 [기간] [페이지]` | 서버 전체 음성 순위 |
| `/보이스 역할순위 [역할] [기간] [페이지]` | 역할별 음성 순위 |

</details>

<details>
<summary><b>💬 채팅 (채팅 실적)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/채팅 확인 [유저] [기간]` | 채팅 실적 확인 |
| `/채팅 순위 [기간] [역할]` | 채팅 순위 확인 |

</details>

<details>
<summary><b>🔮 운세</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*운세` | 오늘의 운세 확인 |
| `*운세설정 버튼생성 [기간]` | 🔒 운세 이용권 배포 버튼 생성 |

</details>

<details>
<summary><b>🎂 생일</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*생일 등록 [MM-DD]` | 생일 등록 |
| `*생일 확인 [@유저]` | 생일 정보 확인 |

</details>

<br>

---

## 🛠️ 기술 스택

<div align="center">

| 카테고리 | 기술 |
|----------|------|
| **런타임** | Python 3.13+ |
| **봇 프레임워크** | discord.py 2.5+ |
| **데이터베이스** | SQLite (aiosqlite, SQLAlchemy) |
| **AI** | OpenAI API, tiktoken |
| **한국어 처리** | jamo |
| **패키지 관리** | Poetry |

</div>

<br>

---

## 🤝 기여하기

프로젝트에 기여를 환영합니다!

```
1. Fork → 2. Branch → 3. Commit → 4. Push → 5. Pull Request
```

```bash
git checkout -b feature/amazing-feature
git commit -m "feat: add amazing feature"
git push origin feature/amazing-feature
```

<br>

---

## 📄 라이센스

이 프로젝트는 [MIT License](LICENSE) 하에 배포됩니다.

---

## 📞 문의

<div align="center">

| 채널 | 링크 |
|------|------|
| **Discord** | `ladinz` |
| **Issues** | [GitHub Issues](https://github.com/ladinzgit/hamyo/issues) |

<br>

---

<br>

_🌙 꿈과 현실 사이에서 만나는 특별한 경험_

**hamyo**와 함께 몽경수행의 여정을 시작하세요.

<br>

</div>
