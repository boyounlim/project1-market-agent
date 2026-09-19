# 📋 데이터 수집 계획서 (Source Collection Plan)

**프로젝트**: `project1-market-agent` (NovaFactory AI 시장/경쟁사/정책 인텔리전스)  
**작성일시**: 2026-09-19  
**수집 목표**: 로그인 없이 접근 가능한 공개 채널을 통해 최소 200건 이상의 시장·경쟁사·정책·기술 데이터 수집

---

## 1. 기업 프로필 및 수집 목적 분석

`config/company_profile.yaml` 기반 수집 타깃:
- **대상 기업**: NovaFactory AI (제조업 AI 비전 품질검사 SaaS)
- **주요 경쟁사**: `VisionForge`, `InspectAI`, `FactoryMind`, `QualiBot`
- **핵심 관심 키워드**: `AI`, `스마트팩토리`, `품질검사`, `자동화`, `클라우드`, `제조 AX`
- **지원사업 키워드**: `창업지원`, `AI 바우처`, `스마트공장`, `R&D`, `사업화 자금`

---

## 2. 수집 대상 정보 유형 (3종 이상 충족)

1. **시장 및 경쟁사 동향 (Market & Competitor Intelligence)**
   - 스마트팩토리 AI 시장 규모, 비전 품질검사 경쟁사 동향, 제조 기업의 DX/AX 도입 사례
2. **정책 및 정부지원사업 (Policy & Government Funding)**
   - 중소벤처기업부/과기정통부 AI 바우처, 스마트공장 보급·확산 사업, R&D 지원 공고
3. **기술 및 산업 동향 (Technology & Industry Trends)**
   - 머신비전, 컴퓨터 비전 AI 알고리즘, 에지 AI, 공정 자동화 최신 기술 동향

---

## 3. 선정된 공개 Source 후보 목록

| 번호 | Source 명칭 | 정보 유형 | 수집 방식 | 대상 URL / 엔드포인트 | 접근성 검증 | 예상 수집량 |
|:---:|:---|:---|:---:|:---|:---:|:---:|
| **1** | **Google News RSS (키워드 기반)** | 시장/경쟁사/기술 | RSS | `https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko` | ✅ 성공 (No Login) | 300~500건 |
| **2** | **AI Times RSS** | 기술/산업동향 | RSS | `https://www.aitimes.com/rss/allArticle.xml` | ✅ 성공 (No Login) | 50건 |
| **3** | **연합뉴스 산업 RSS** | 시장/산업동향 | RSS | `https://www.yna.co.kr/rss/industry.xml` | ✅ 성공 (No Login) | 100~120건 |
| **4** | **Bloter / GeekNews RSS** | IT/테크 트렌드 | RSS | `https://www.bloter.net/rss/allArticle.xml`<br>`https://news.hada.io/rss/news` | ✅ 성공 (No Login) | 50~100건 |
| **5** | **기업마당 (BizInfo) 지원사업** | 정책/정부지원 | requests + BS4 | `https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do` | ✅ 성공 (Status 200) | 15~30건 |
| **6** | *(Fallback) 로컬 CSV* | 종합 (백업) | CSV Reader | `data/fallback/fallback_market_news.csv` | ✅ 상시 가능 | 800건 |

---

## 4. 단계별 수집 전략 (Collection Strategy)

```
[1단계: RSS 피드 파싱]
  - Google News (스마트팩토리, 제조 AI, AI 바우처, 품질검사, 경쟁사명)
  - AI Times, 연합뉴스 산업, Bloter
  → 가장 빠르고 안정적이며 API 키/로그인 불필요 (feedparser 활용)

[2단계: requests + BeautifulSoup 정적 스크래핑]
  - 기업마당(BizInfo) 및 정부 공고 목록 페이지
  → 정책/지원사업 실시간 공고 추출

[3단계: 공개 API (선택적 확장)]
  - 공공데이터포털 중기부 사업공고 API 등 활용 가능

[4단계: Playwright 동적 크롤링 (필요 시에만)]
  - 무거운 브라우저 자동화는 차단/비용/속도 고려하여 SPA 렌더링이 필수적인 경우에만 최소화

[5단계: Fallback 데이터 결합]
  - 네트워크 단절이나 수집 건수 부족(< 200건) 발생 시 `fallback_market_news.csv` 자동 병합
```

---

## 5. 200건 확보 가능성 및 품질 평가

- **실시간 수집 예상 건수**:
  - Google News RSS 5개 주요 쿼리: 약 500건
  - 기술/산업 전문 RSS (AI Times, 연합뉴스, Bloter): 약 200건
  - 기업마당 지원사업 공고: 약 15~20건
  - **총 실시간 가용 데이터: 약 700건 이상**
- **품질 및 안정성 평가**:
  - 100% 비로그인 공개 소스로 구성되어 접근 차단 리스크가 낮음
  - 중복 기사 제거(URL, 제목 기준) 및 결측치 필터링을 거치더라도 **최소 200건 목표를 여유 있게 초과 달성(400건 이상 유효 데이터 확보 예상)** 가능
  - 최악의 오프라인/네트워크 장애 환경에서도 800건의 합성 fallback 데이터셋이 완벽하게 준비되어 있음
