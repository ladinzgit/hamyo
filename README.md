<div align="center">

# 🌸 hamyo (하묘)
### *몽경수행* - 꿈과 현실 사이의 디스코드 다기능 봇

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2.svg?style=flat-square&logo=discord)](https://discordpy.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57.svg?style=flat-square&logo=sqlite)](https://www.sqlite.org/)

*차향이 스며든 꿈의 세계로 떠나는 여행 ☕*

</div>

---

## ✨ 주요 기능

### 📈 **몽경수행 레벨/퀘스트 시스템**
- ⭐ **다공(경험치) 획득**: 다양한 활동으로 성장
- 🎭 **역할 승급**: 허브 → 다도 → 다호 → 다경
- 📊 **퀘스트 시스템**: 일간/주간/일회성 수행 과제
- 📅 **출석 수행**: 매일 접속으로 다공 획득
- 📝 **다방일지**: 일기 작성으로 내면 성찰
- 🌱 **추천 인증**: 서버 홍보 참여 보상
- 📚 **게시판 참여**: 커뮤니티 활동 장려
- 📢 **삐삐 퀘스트**: 특정 역할 멘션 활동
- 🏆 **마일스톤 보상**: 출석/일지 연속 달성 시 추가 보상

### 💰 **경제 시스템**
- 💰 **화폐 관리**: 다양한 아이템 구매 및 관리
- 🎁 **인벤토리**: 수집한 아이템 보관소
- 🏪 **상점**: 유용한 아이템 구매
- 💎 **랭크 보상**: 레벨 달성 시 경제적 혜택
- 🎯 **퀘스트 보상**: 수행 완료 시 경제적 인센티브

### 🔊 **보이스 측정 시스템**
- 🎤 **실시간 추적**: 음성방 참여 시간 자동 측정
- ⏰ **30분 단위 보상**: 일일 퀘스트 자동 완료
- 📊 **주간 마일스톤**: 5/10/20시간 달성 보상
- 🏆 **음성 랭크**: 참여도에 따른 등급 시스템
- 📈 **통계 제공**: 개인별 음성방 활동 기록

---

## 🚀 시작하기

### 📋 필요 사항
- **Python 3.8+**
- **Poetry** (Python 패키지 관리자)

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
   ```bash
   # .env 파일 생성 또는 환경변수 설정
   # DISCORD_TOKEN=your_bot_token_here
   ```

5. **봇 실행**
   ```bash
   # Poetry 가상환경에서 실행
   poetry run python src/hamyo/main.py
   
   # 또는 가상환경 활성화 후 실행
   poetry shell
   python src/hamyo/main.py
   ```

---

## 🎮 주요 명령어

### 📊 몽경수행
```
*내정보     - 현재 다공 및 역할 확인
*출석       - 출석 체크 및 다공 획득
```

### 💰 경제
```
*온 확인    - 보유 화폐 확인
```

### 🔊 보이스 활동
```
자동 추적   - 음성방 참여 시 자동으로 시간 측정
자동 보상   - 30분 달성 시 퀘스트 자동 완료
```

---

## 🏗️ 프로젝트 구조

```
hamyo/
├── src/hamyo/
│   ├── cogs/
│   │   ├── LevelChecker.py     # 레벨 및 퀘스트 시스템
│   │   ├── Economy.py          # 경제 시스템
│   │   ├── StorageCog.py       # 인벤토리 관리
│   │   ├── SchedulerCog.py     # 스케줄러 (자정 처리)
│   │   └── VoiceTracker.py     # 음성방 활동 추적
│   ├── data/
│   │   └── level.db           # 레벨 및 경제 데이터베이스
│   ├── LevelDataManager.py    # 레벨 시스템 DB 매니저
│   └── main.py                # 봇 메인 파일
├── pyproject.toml             # Poetry 설정
├── requirements.txt           # 의존성 목록
└── README.md
```

---

## 🎨 특별한 특징

### 🌸 **몽환적 컨셉**
- 차와 꿈을 테마로 한 감성적인 경험
- 한국적 감성이 담긴 역할명과 용어 ("다공", "다도", "다호", "다경")

### 🔄 **자동화 시스템**
- 실시간 음성방 활동 자동 추적
- 퀘스트 완료 시 자동 알림 및 보상 지급
- 역할 승급 시 자동 축하 메시지

### 📱 **사용자 친화적**
- 직관적인 명령어 시스템
- 시각적으로 아름다운 임베드 메시지
- 상세한 진행 상황 안내

### 🎯 **다양한 참여 방식**
- 출석체크를 통한 꾸준한 참여 유도
- 일기 작성으로 개인 성찰 시간 제공
- 음성방 활동을 통한 실질적 소통 장려

---

## 🤝 기여하기

1. 이 저장소를 포크합니다
2. 새로운 기능 브랜치를 만듭니다 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`)
5. Pull Request를 열어주세요

---

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

---

## 📞 문의

프로젝트에 대한 질문이나 제안사항이 있으시면 언제든지 연락해주세요!

- **Discord**: ladinz
- **Issues**: [GitHub Issues](https://github.com/ladinzgit/hamyo/issues)

---

<div align="center">

### 🌙 *꿈과 현실 사이에서 만나는 특별한 경험*

**hamyo**와 함께 몽경수행의 여정을 시작해보세요 ✨

</div>
