<div align="center">

<br>

# 🐰 hamyo

### `하묘` — 비몽책방의 다기능 디스코드 봇

<br>

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.5+-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![License](https://img.shields.io/badge/License-MIT-F5A623?style=for-the-badge)](LICENSE)

<br>

> _책내음이 스며든 꿈의 세계 — 서버 활동을 촉진하고 커뮤니티에 재미를 더하는 다기능 봇_

<br>

</div>

---

## 📋 목차

- [개요](#-개요)
- [기능](#-기능)
- [프로젝트 구조](#-프로젝트-구조)
- [시작하기](#-시작하기)
- [명령어 레퍼런스](#-명령어-레퍼런스)
- [기술 스택](#-기술-스택)
- [기여하기](#-기여하기)
- [라이센스](#-라이센스)

---

## 🌸 개요

**hamyo**(하묘)는 디스코드 서버 **비몽책방** 커뮤니티를 위한 올인원 다기능 봇입니다.  
레벨 시스템, 경제, 음성 활동 측정, 랭크 카드, 운세, 생일 관리, 채팅 실적, 여백 키우기 등  
다양한 모듈이 유기적으로 연결되어 **백지동화**라는 독자적인 성장 체계를 구축합니다.

경험치 단위 **'쪽'**을 모으며  
`여백` → `고요` → `서유` → `서림` → `서향`으로 **경지를 승급**하고,  
AI 기반 퀘스트와 비주얼 랭크 카드로 활동을 시각화하세요.

<br>

## ✨ 기능

<table>
<tr>
<td width="50%" valign="top">

### 📈 백지동화 — 레벨 & 퀘스트
서버 활동을 통해 **쪽(경험치)**을 쌓고,  
`여백` → `고요` → `서유` → `서림` → `서향`으로  
**경지를 승급**하며 성장하세요.

- 일일 / 주간 / 일회성 **퀘스트 시스템**
- 누적 / 월간 / 주간 / 일간 **순위 시스템**
- 자동 역할 부여 및 칭호 관리
- **하묘가 건네는 첫 문장** — AI 기반 일일 포럼 질문
- **흩날리는 이야기 조각** — 선착순 보상 이벤트

</td>
<td width="50%" valign="top">

### 🎴 랭크 카드 — 시각화된 성장
Pillow로 생성된 **비주얼 랭크 카드** 이미지로  
나의 성장 현황을 한눈에 확인하세요.

- 경지, 쪽(경험치), 진행률 시각화
- 음성 레벨 & 채팅 레벨 별도 표시
- 아바타 & 닉네임 반영 카드 이미지 생성
- `*랭크` / `/rank` 명령어 지원

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 💰 온 — 경제 시스템
서버 전용 화폐 **'온'**을 거래하고  
활동 인증을 통해 보상을 획득하세요.

- 출석 체크 & 인증 보상
- 유저 간 **송금** (수수료 구간 설정 가능)
- 관리자 지급 / 회수 / **채널 대량 지급**
- 일일 송금·수취 횟수 제한 설정

</td>
<td width="50%" valign="top">

### 🎤 보이스 — 음성 활동 추적
음성 채널 참여 시간을 **실시간으로 기록**하고  
기간별 통계와 순위를 제공합니다.

- 일간 / 주간 / 월간 / 누적 통계
- 서버 전체 & 역할별 순위
- 카테고리별 세부 통계 뷰
- 음성 기반 퀘스트 자동 완료

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 💬 채팅 — 채팅 실적 관리
텍스트 채널 활동량을 **자동으로 집계**하고  
기간별 채팅 순위를 확인하세요.

- 한글 기반 채팅량 자동 카운팅 (10글자 이상)
- 점수 시스템 (기본 2점, 30자 이상 3점)
- 쿨타임 기반 스팸 방지 (60초)
- 역할 필터링 & 무시 역할 설정

</td>
<td width="50%" valign="top">

### 🔮 운세 — AI 일일 운세 시스템
OpenAI API로 **맞춤형 오늘의 운세**를 확인하고  
운세 이용권을 관리하세요.

- 생일 기반 개인화 운세 생성
- 버튼 기반 이용권 배포
- 관리자 설정 명령어
- 자동 일일 초기화 스케줄러

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎂 생일 — 생일 알림 & 관리
서버 멤버의 생일을 등록하고  
**자동 축하 메시지**를 보내세요.

- 모달 기반 생일 등록 / 수정 / 삭제
- 자동 알림 & 달력 인터페이스
- 매일 자정 자동 업데이트
- 버튼 기반 셀프서비스 UI

</td>
<td width="50%" valign="top">

### 🌿 여백 — 여백 키우기
별도 음성 채널 추적으로 **여백을 키우며**  
서버 활동에 새로운 재미를 더하세요.

- 독립 채널 등록 & 추적
- 일간 / 주간 / 월간 / 누적 통계
- 서버 전체 & 역할별 순위

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🏷️ 임베드 & 역할 — 커스텀 UI
서버에 **커스텀 임베드와 역할 버튼**을  
손쉽게 구성하세요.

- 슬래시 명령어 기반 임베드 생성 / 편집
- 입장 안내 임베드 (제목·설명·이미지·푸터)
- 역할 자동 부여 버튼 시스템
- 채널·역할 동적 바인딩

</td>
<td width="50%" valign="top">

### 🛠️ 관리 — 서버 관리 도구
서버 운영에 필요한 **관리자 전용 도구**를  
제공합니다.

- 본부계 변경 (계정 데이터 병합)
- 대량 DM 발송 (진행률 표시)
- 전체 DB 초기화 (2단계 확인)
- 봇 재시작 / 종료 / 상태 확인
- 멤버 수 카운터 채널

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
├── assets/                    # 정적 리소스
│   ├── fonts/                 # 랭크 카드용 폰트 (나눔명조 등)
│   └── images/                # 랭크 카드용 이미지
│
├── config/                    # JSON 기반 설정 파일
│   ├── config.json            # 전역 봇 설정
│   ├── level_config.json      # 레벨 시스템 설정
│   ├── chatting_config.json   # 채팅 실적 설정
│   ├── birthday_config.json   # 생일 관리 설정
│   ├── embed_config.json      # 임베드 & 역할 버튼 설정
│   ├── fortune.json           # 운세 시스템 설정
│   ├── blankconfig.json       # 여백 시스템 설정
│   ├── prefix_config.json     # 칭호 규칙 설정
│   ├── rankcard_config.json   # 랭크 카드 설정
│   ├── tree_config.json       # 비몽트리 이벤트 설정
│   └── logger_config.json     # 로깅 채널 설정
│
├── data/                      # SQLite 데이터베이스
│   ├── level_system.db        # 레벨 & 퀘스트 데이터
│   ├── level_archive.db       # 레벨 아카이브 (경험치 이전용)
│   ├── balance.db             # 경제(온) 데이터
│   ├── voice_logs.db          # 음성 활동 로그
│   ├── attendance.db          # 출석 데이터
│   ├── birthday.db            # 생일 데이터
│   ├── blank.db               # 여백 시스템 데이터
│   ├── chatting.db            # 채팅 실적 데이터
│   ├── tree.db                # 비몽트리 이벤트 데이터
│   └── count_channels.json    # 카운터 채널 설정
│
└── src/
    ├── core/                  # 공통 데이터 매니저 & 유틸리티
    │   ├── DataManager.py           # 음성/여백 DB 매니저
    │   ├── LevelDataManager.py      # 레벨/퀘스트 DB 매니저
    │   ├── ChattingDataManager.py   # 채팅 실적 DB 매니저
    │   ├── balance_data_manager.py  # 경제(온) DB 매니저
    │   ├── birthday_db.py           # 생일 DB 유틸
    │   ├── fortune_db.py            # 운세 DB 유틸
    │   ├── voice_utils.py           # 음성 채널 유틸
    │   ├── admin_utils.py           # 관리자 권한 유틸
    │   └── __init__.py
    │
    ├── level/                 # 백지동화 (레벨/퀘스트)
    │   ├── LevelSystem.py           # 역할 승급 & 이벤트 처리
    │   ├── LevelChecker.py          # 퀘스트 완료 감지 & 경험치 지급
    │   ├── LevelCommand.py          # *내정보, *순위 명령어
    │   ├── LevelConfig.py           # 관리자 경험치/퀘스트 설정
    │   ├── LevelConstants.py        # 역할·퀘스트·채널 상수 통합 관리
    │   ├── DailyFirstSentence.py    # 하묘가 건네는 첫 문장 (OpenAI)
    │   ├── ScatteredStoryPiece.py   # 흩날리는 이야기 조각 (선착순)
    │   ├── LevelExpTransfer.py      # 기존 다공 → 쪽 경험치 이전
    │   └── PrefixChanger.py         # 역할 기반 칭호 자동 변경
    │
    ├── rankcard/              # 랭크 카드 시스템
    │   ├── RankCardCog.py           # *랭크, /rank 명령어
    │   ├── RankCardGenerator.py     # Pillow 이미지 생성
    │   ├── RankCardService.py       # 데이터 수집 & 가공
    │   ├── XPFormulas.py            # 음성/채팅 레벨 계산 공식
    │   └── __init__.py
    │
    ├── economy/               # 경제 시스템
    │   ├── Economy.py               # *온 명령어 (확인/지급/회수/송금/대량지급)
    │   ├── OnAdminSettings.py       # 관리자 설정 (인증/수수료/채널/제한)
    │   └── attendance.py            # 출석 체크 & 순위
    │
    ├── voice/                 # 음성 활동
    │   ├── VoiceTracker.py          # 실시간 음성 추적 & 퀘스트 연동
    │   ├── VoiceCommands.py         # /보이스 확인·순위·역할순위
    │   └── VoiceConfig.py           # 관리자 채널 등록/제거/초기화
    │
    ├── chatting/              # 채팅 실적
    │   ├── ChattingTracker.py       # 실시간 채팅 추적 (on_message)
    │   ├── ChattingCommands.py      # /채팅 확인 슬래시 명령어
    │   ├── ChattingRanking.py       # /채팅 순위 슬래시 명령어
    │   └── ChattingConfig.py        # 관리자 채널/역할/DB동기화
    │
    ├── fortune/               # 운세 시스템
    │   ├── FortuneCommand.py        # *운세 명령어 (OpenAI)
    │   ├── FortuneConfig.py         # 관리자 설정 & 이용권 버튼
    │   └── FortuneTimer.py          # 운세 자동 초기화 타이머
    │
    ├── birthday/              # 생일 관리
    │   ├── Birthday.py              # 생일 등록/확인/삭제 (모달 & 버튼)
    │   └── BirthdayInterface.py     # 생일 달력 임베드 자동 갱신
    │
    ├── blank/                 # 여백 키우기
    │   ├── BlankCommand.py          # /여백 확인·순위·역할순위
    │   └── BlankConfig.py           # 관리자 채널 등록/제거/초기화
    │
    ├── embed/                 # 임베드 & 역할 버튼
    │   ├── EmbedCommon.py           # /임베드 생성·출력·삭제·색상
    │   ├── EmbedUtils.py            # 임베드 데이터 관리 유틸
    │   ├── EntranceEmbed.py         # 입장 안내 임베드 편집 UI
    │   └── RoleEmbed.py             # 역할 자동 부여 버튼
    │
    ├── admin/                 # 서버 관리 도구
    │   ├── AccountSwapper.py        # 본부계 변경 (데이터 병합)
    │   ├── BulkDM.py                # DM 일괄 전송
    │   ├── DatabaseResetter.py      # 전체 DB 초기화
    │   └── Restart.py               # 봇 재시작/종료/상태 확인
    │
    └── utils/                 # 유틸리티 (우선 로드)
        ├── Scheduler.py             # 중앙 작업 스케줄러
        ├── Logger.py                # 로그 채널 전송
        ├── Counter.py               # 멤버 수 카운터 채널
        └── Response.py              # 환영 메시지 & 봇 주인 명령어
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
OPENAI_API_KEY=your_openai_api_key_here
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
<summary><b>📈 백지동화 (레벨 시스템)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*내정보 [@유저]` | 백지동화 현황 (쪽, 경지, 퀘스트 진행도) 확인 |
| `*출석` | 출석 체크 및 일일 퀘스트 완료 |
| `*순위 [기간]` | 쪽 순위 확인 (`일간` / `주간` / `월간` / `누적`) |

**🔒 관리자 명령어**

| 명령어 | 설명 |
|--------|------|
| `*쪽 지급 @유저 수량 [사유]` | 경험치(쪽) 지급 |
| `*쪽 회수 @유저 수량 [사유]` | 경험치(쪽) 회수 |
| `*쪽 초기화 @유저` | 특정 유저 경험치 초기화 |
| `*쪽 전체초기화` | 전체 유저 경험치 초기화 |
| `*퀘스트 완료 @유저 퀘스트명 [사유]` | 퀘스트 강제 완료 |
| `*퀘스트 인증 @유저 [채팅레벨] [보이스레벨]` | 보이스/채팅 랭크 인증 |
| `*퀘스트 초기화 @유저` | 퀘스트 데이터 초기화 |
| `*퀘스트 목록` | 모든 퀘스트 목록 조회 |
| `*퀘스트 정보 퀘스트명` | 퀘스트 상세 정보 조회 |

</details>

<details>
<summary><b>🎴 랭크 카드</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*랭크 [@유저]` | 랭크 카드 이미지 확인 (접두사) |
| `/rank [유저]` | 랭크 카드 이미지 확인 (슬래시) |

**🔒 관리자 명령어**

| 명령어 | 설명 |
|--------|------|
| `*랭크설정 채널추가 [#채널]` | 랭크 명령어 허용 채널 추가 |
| `*랭크설정 채널제거 [#채널]` | 랭크 명령어 허용 채널 제거 |
| `*랭크설정 채널목록` | 허용 채널 목록 확인 |

</details>

<details>
<summary><b>💰 온 (경제 시스템)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*온 확인 [@유저]` | '온' 보유량 확인 |
| `*온 송금 @유저 금액` | 다른 유저에게 '온' 송금 |
| `*온 수수료` | 송금 수수료 구조 확인 |

**🔒 관리자 / 인증 역할 명령어**

| 명령어 | 설명 |
|--------|------|
| `*온 지급 @유저 금액 [횟수]` | 유저에게 '온' 지급 |
| `*온 회수 @유저 금액` | 유저 '온' 회수 |
| `*온 인증 @유저 조건 [횟수]` | 조건 달성 인증 및 보상 지급 |
| `*온 채널지급 금액 [#채널]` | 채널 내 활동 유저 대량 지급 |

**🔒 관리자 설정 명령어** (`*온설정`)

| 명령어 | 설명 |
|--------|------|
| `*온설정 인증추가 조건 보상` | 인증 조건 추가 |
| `*온설정 인증제거 조건` | 인증 조건 제거 |
| `*온설정 역할추가 @역할` | 인증/지급/회수 역할 추가 |
| `*온설정 화폐단위 이모지` | 화폐 단위 변경 |
| `*온설정 채널추가 [#채널]` | 허용 채널 추가 |
| `*온설정 수수료 설정 최소금액 수수료` | 수수료 구간 설정 |
| `*온설정 제한 송금횟수 숫자` | 일일 송금 제한 설정 |
| `*온설정 제한 수취횟수 숫자` | 일일 수취 제한 설정 |

</details>

<details>
<summary><b>🎤 보이스 (음성 활동)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/보이스 확인 [유저] [기간] [기준일]` | 음성 활동 시간 확인 |
| `/보이스 순위 [기간] [페이지] [기준일]` | 서버 전체 음성 순위 |
| `/보이스 역할순위 역할 [기간] [페이지] [기준일]` | 역할별 음성 순위 |

</details>

<details>
<summary><b>💬 채팅 (채팅 실적)</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/채팅 확인 [유저] [기간] [기준일]` | 채팅 실적 확인 |
| `/채팅 순위 [역할] [기간] [페이지] [기준일]` | 채팅 순위 확인 |

**🔒 관리자 명령어** (`*채팅설정`)

| 명령어 | 설명 |
|--------|------|
| `*채팅설정 채널등록 #채널` | 추적 채널/카테고리 등록 |
| `*채팅설정 채널제거 #채널` | 추적 채널/카테고리 제거 |
| `*채팅설정 채널초기화` | 모든 추적 채널 초기화 |
| `*채팅설정 무시추가 @역할` | 무시 역할 추가 |
| `*채팅설정 무시제거 @역할` | 무시 역할 제거 |
| `*채팅설정 DB동기화` | DB 재구축 (히스토리 기반) |

</details>

<details>
<summary><b>🔮 운세</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*운세` | 오늘의 운세 확인 (OpenAI 생성) |

**🔒 관리자 명령어** (`*운세설정`)

| 명령어 | 설명 |
|--------|------|
| `*운세설정` | 운세 설정 현황 확인 |
| `*운세설정 역할설정 @역할` | 안내 역할 설정 |
| `*운세설정 채널설정 #채널` | 안내 채널 설정 |
| `*운세설정 시간추가 HH:MM` | 전송 시간 추가 |
| `*운세설정 시간제거 HH:MM` | 전송 시간 제거 |
| `*운세설정 대상추가 @유저 횟수` | 사용 대상 추가 |
| `*운세설정 대상제거 @유저` | 사용 대상 제거 |
| `*운세설정 초기화 [@유저]` | 일일 제한 초기화 |
| `*운세설정 버튼생성 일수` | 이용권 배포 버튼 생성 |

</details>

<details>
<summary><b>🎂 생일</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*생일` | 생일 관련 도움말 |

**🔒 관리자 명령어**

| 명령어 | 설명 |
|--------|------|
| `*생일 버튼` | 생일 등록/확인/삭제 버튼 전송 |
| `*생일 확인 @유저` | 유저 생일 확인 |
| `*생일 삭제 @유저` | 유저 생일 삭제 |
| `*생일 관리자변경 @유저 월 일 [연도]` | 생일 강제 변경 |
| `*생일 횟수초기화 @유저` | 수정 횟수 초기화 |
| `*생일 목록` | 전체 생일 목록 조회 |
| `*생일표시 채널등록 [#채널]` | 생일 달력 채널 등록 |
| `*생일표시 갱신` | 강제 생일 메시지 갱신 |

</details>

<details>
<summary><b>🌿 여백 키우기</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/여백 확인 [유저] [기간] [기준일]` | 여백 음성 시간 확인 |
| `/여백 순위 [기간] [페이지] [기준일]` | 여백 전체 순위 |
| `/여백 역할순위 역할 [기간] [페이지] [기준일]` | 역할별 여백 순위 |

</details>

<details>
<summary><b>🏷️ 임베드 & 역할</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/임베드 생성 종류 이름` | 임베드 생성 (`안내` / `역할`) |
| `/임베드 출력 이름` | 저장된 임베드 채널에 출력 |
| `/임베드 목록` | 임베드 목록 확인 |
| `/임베드 삭제 이름` | 임베드 삭제 |
| `/임베드 색상 이름 R G B` | 임베드 색상 변경 |
| `/임베드 수정 이름` | 임베드 편집 UI |
| `/역할 추가 이름 @역할 설명 이모지` | 역할 버튼 추가 |
| `/역할 제거 이름 역할내용` | 역할 버튼 제거 |
| `/역할 수정 이름 역할내용 [설명] [이모지]` | 역할 버튼 수정 |

</details>

<details>
<summary><b>🛠️ 관리 도구</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `*본부계변경 @본계정 @부계정` | 🔒 계정 데이터 병합 |
| `*DM일괄전송` | 🔒 서버 전체 DM 발송 |
| `*전체DB초기화` | 🔒 모든 DB 데이터 초기화 (2단계 확인) |
| `*재시작` | 👑 봇 재시작 (봇 주인 전용) |
| `*종료` | 👑 봇 종료 (봇 주인 전용) |
| `*상태` | 👑 봇 상태 확인 (봇 주인 전용) |
| `*로그채널설정 [#채널]` | 👑 로그 채널 설정 |

> 🔒 = 관리자 전용, 👑 = 봇 주인 전용

</details>

<details>
<summary><b>🔧 유틸리티 & 기타</b></summary>
<br>

| 명령어 | 설명 |
|--------|------|
| `/카운터 생성 [역할] [접두어] [봇포함] [카테고리] [추가역할]` | 멤버 수 카운터 채널 생성 |
| `/카운터 삭제 채널` | 카운터 채널 삭제 |
| `/카운터 목록` | 카운터 채널 목록 |
| `*칭호규칙 추가 @역할 칭호` | 🔒 칭호 자동 변경 규칙 추가 |
| `*칭호규칙 예외추가 @역할` | 🔒 칭호 변경 예외 역할 추가 |
| `*칭호규칙 목록` | 🔒 칭호 규칙 목록 확인 |
| `*sync` | 👑 슬래시 명령어 동기화 |

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
| **이미지 생성** | Pillow (PIL) |
| **한국어 처리** | jamo |
| **시간대** | pytz (Asia/Seoul) |
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

### 📖 비몽책방에 놀러오세요!

꿈과 현실 사이, 책내음이 가득한 **비몽책방**이 궁금하시다면 언제든 문을 두드려주세요.

[![Disboard](https://img.shields.io/badge/비몽책방-Disboard-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://disboard.org/ko/server/1474014230549237857)

---

<br>

_🌙 꿈과 현실 사이, 책내음이 나는 곳_

**hamyo**와 함께 백지동화의 여정을 시작하세요.

<br>

</div>
