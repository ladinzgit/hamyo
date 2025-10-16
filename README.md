<div align="center">

# 🌸 hamyo (하묘)
### *몽경수행* - 꿈과 현실 사이의 디스코드 다기능 봇

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.5+-5865F2.svg?style=flat-square&logo=discord)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57.svg?style=flat-square&logo=sqlite)](https://www.sqlite.org/)

*차향이 스며든 꿈의 세계로 떠나는 여행 ☕*

</div>

---

## ✨ 주요 기능

### 📈 **몽경수행: 레벨/퀘스트 시스템**
- **다공(경험치) 획득**: 서버 내 다양한 활동을 통해 성장합니다.
- **역할(경지) 승급**: `허브` → `다도` → `다호` → `다경` 순서로 더 높은 경지에 도달하세요.
- **퀘스트 시스템**: 일일/주간/일회성 수행 과제를 통해 다공을 획득할 수 있습니다.
  - **일일**: 출석, 다방일지 작성, 음성 활동(30분), 삐삐(특정 역할 멘션)
  - **주간**: 추천 인증, 주간 출석/일지 달성, 음성 활동(5/10/20시간), 상점 이용, 게시판 활동
  - **일회성**: 자기소개, 후기 작성 등 특별 과제
- **순위 시스템**: 누적/월간/주간/일간 다공 획득량 순위를 확인하며 다른 수행자들과 경쟁할 수 있습니다.

### 💰 **경제 시스템**
- **온(화폐) 관리**: 서버 전용 화폐 '온'을 획득하고 사용할 수 있습니다.
- **인증 보상**: 특정 활동(예: 서버 추천)을 인증받고 '온'을 보상으로 획득하세요.
- **관리 기능**: 관리자는 유저에게 '온'을 지급하거나 회수할 수 있습니다.

### 🔊 **음성 활동 측정 시스템**
- **실시간 추적**: 음성 채널 참여 시간을 자동으로 측정하고 기록합니다.
- **자동 보상**: 측정된 시간을 바탕으로 일일/주간 음성 활동 퀘스트가 자동으로 완료됩니다.
- **통계 제공**: 개인별/역할별 음성 활동 시간을 기간(일간/주간/월간/누적)에 따라 상세히 확인할 수 있습니다.
- **음성 랭킹**: 서버 전체 또는 특정 역할 내에서 가장 활발히 음성 채널에 참여한 유저 순위를 볼 수 있습니다.

---

## 🚀 시작하기

### 📋 필요 사항
- **Python 3.13+**
- **Poetry** (Python 패키지 및 의존성 관리자)

### 🔧 설치 방법

1. **Poetry 설치** (아직 설치하지 않은 경우)
   ```bash
   # Windows (PowerShell)
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
   
   # macOS/Linux
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **저장소 클론**
   ```bash
   git clone https://github.com/ladinzgit/hamyo.git
   cd hamyo
   ```

3. **의존성 설치**
   ```bash
   poetry install
   ```

4. **환경 설정**
   - 프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 추가하세요.
   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```

5. **봇 실행**
   - **참고**: 봇의 메인 실행 파일이 현재 프로젝트에 포함되어 있지 않습니다. `discord.py` 기본 코드를 참고하여 `src/hamyo/main.py`와 같은 파일을 직접 생성해야 합니다.
   ```python
   # src/hamyo/main.py 예시
   import discord
   import os
   from discord.ext import commands
   from dotenv import load_dotenv

   load_dotenv()
   TOKEN = os.getenv('DISCORD_TOKEN')

   intents = discord.Intents.default()
   intents.message_content = True
   intents.members = True

   bot = commands.Bot(command_prefix='*', intents=intents)

   @bot.event
   async def on_ready():
       print(f'{bot.user} has connected to Discord!')
       # Cogs 로드
       for filename in os.listdir('./src/hamyo/cogs'):
           if filename.endswith('.py'):
               await bot.load_extension(f'hamyo.cogs.{filename[:-3]}')

   bot.run(TOKEN)
   ```
   - 위와 같이 `main.py` 파일을 생성한 후, 아래 명령어로 봇을 실행할 수 있습니다.
   ```bash
   # Poetry 가상환경에서 실행
   poetry run python src/hamyo/main.py
   
   # 또는 가상환경 활성화 후 실행
   poetry shell
   python src/hamyo/main.py
   ```

---

## 🎮 주요 명령어

### 📊 **몽경수행 (레벨)**
- `*내정보 [@유저]` : 자신 또는 다른 유저의 몽경수행 현황(다공, 경지, 퀘스트 진행도)을 확인합니다.
- `*출석` : 출석 체크를 하고 일일 퀘스트를 완료합니다.
- `*순위 [기간]` : 다공 획득량 순위를 확인합니다. (기간: `일간`, `주간`, `월간`, `누적`)

### 💰 **온 (경제)**
- `*온 확인 [@유저]` : 자신 또는 다른 유저의 '온' 보유량을 확인합니다.
- `*온 지급 @유저 금액 [횟수]` : (관리자) 유저에게 '온'을 지급합니다.
- `*온 회수 @유저 금액` : (관리자) 유저의 '온'을 회수합니다.
- `*온 인증 @유저 조건 [횟수]` : (관리자) 조건 달성을 인증하고 보상을 지급합니다.

### 🔊 **보이스 활동**
- `/보이스 확인 [유저] [기간] [기준일]` : 자신 또는 다른 유저의 음성 활동 시간을 확인합니다.
- `/보이스 순위 [기간] [페이지]` : 서버 전체 음성 활동 순위를 확인합니다.
- `/보이스 역할순위 [역할] [기간] [페이지]` : 특정 역할 내 음성 활동 순위를 확인합니다.

---

## 🏗️ 프로젝트 구조

```
hamyo/
├── data/                     # SQLite 데이터베이스 파일 저장 위치
│   ├── balance.db
│   ├── level_system.db
│   └── voice_logs.db
├── src/hamyo/
│   ├── cogs/                 # 기능별 명령어 및 로직 (Cogs)
│   │   ├── Economy.py        # 경제 시스템
│   │   ├── LevelChecker.py   # 레벨 및 퀘스트 로직
│   │   ├── LevelCommand.py   # 레벨 관련 명령어
│   │   ├── VoiceTracker.py   # 음성 활동 추적 로직
│   │   └── VoiceCommands.py  # 음성 활동 관련 명령어
│   ├── balance_data_manager.py # 경제 DB 관리
│   ├── DataManager.py          # 음성 활동 DB 관리
│   └── LevelDataManager.py   # 레벨 시스템 DB 관리
├── pyproject.toml            # Poetry 의존성 및 프로젝트 설정
└── README.md
```

---

## 🤝 기여하기

1. 이 저장소를 포크(Fork)합니다.
2. 새로운 기능 브랜치를 만듭니다 (`git checkout -b feature/AmazingFeature`).
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`).
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`).
5. Pull Request를 열어주세요.

---

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

---

## 📞 문의

- **Discord**: ladinz
- **Issues**: [GitHub Issues](https://github.com/ladinzgit/hamyo/issues)

---

<div align="center">

### 🌙 *꿈과 현실 사이에서 만나는 특별한 경험*

**hamyo**와 함께 몽경수행의 여정을 시작해보세요 ✨

</div>