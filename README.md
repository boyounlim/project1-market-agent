# Project 1: Market Intelligence Agent (project1-market-agent)

제조업 AI 비전 품질검사 기업 **NovaFactory AI**를 위한 시장 동향 및 경쟁사 모니터링 자동화 에이전트입니다.

## 📁 프로젝트 구조

```text
day1_ex1/
├── .github/
│   └── workflows/          # GitHub Actions 자동화 워크플로우
├── config/
│   └── company_profile.yaml # 기업 프로필, 경쟁사, 관심/지원사업 키워드 설정
├── data/
│   ├── fallback/
│   │   └── fallback_market_news.csv  # 수집 실패 시 사용할 800행 fallback 데이터
│   ├── raw/                # 수집된 원본 데이터
│   └── processed/          # 정제 및 가공된 데이터
├── docs/                   # GitHub Pages 정적 리포트 및 문서 산출물
├── logs/                   # 실행 로그
├── src/                    # 에이전트 소스 코드
├── .env.example            # 환경변수 예시 파일
├── .gitignore              # Git 추적 제외 목록
├── requirements.txt        # Python 의존성 목록
└── README.md               # 프로젝트 안내 문서
```

## 🏢 기업 프로필 요약

- **기업명**: `NovaFactory AI`
- **사업 분야**: 제조업 AI 비전 품질검사
- **주요 제품**:
  - 비전 기반 불량 탐지 SaaS
  - 제조 품질 리포트 자동화
- **타깃 시장**:
  - 중소·중견 제조기업
  - 스마트팩토리 구축 기업
- **주요 경쟁사**: `VisionForge`, `InspectAI`, `FactoryMind`, `QualiBot` (4개사)
- **관심 키워드**: `AI`, `스마트팩토리`, `품질검사`, `자동화`, `클라우드`, `제조 AX` (6개)
- **지원사업/자금 키워드**: `창업지원`, `AI 바우처`, `스마트공장`, `R&D`, `사업화 자금` (5개)

## 🚀 빠른 시작

```powershell
# 의존성 설치
pip install -r requirements.txt
```
