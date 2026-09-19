"""
Static Site Builder Module for GitHub Pages.
Generates docs/index.html and docs/report.json from processed recommendation data.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

import yaml
import pandas as pd

# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "build_site.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
logger = logging.getLogger("SiteBuilder")


class SiteBuilder:
    def __init__(self,
                 config_path: str = "config/company_profile.yaml",
                 cleaned_path: str = "data/processed/cleaned_market_news.csv",
                 rec_path: str = "data/processed/recommended_market_news.csv",
                 docs_dir: str = "docs"):
        self.config_path = config_path
        self.cleaned_path = cleaned_path
        self.rec_path = rec_path
        self.docs_dir = docs_dir

    def _load_profile(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def build(self) -> None:
        os.makedirs(self.docs_dir, exist_ok=True)
        profile = self._load_profile()
        company_name = profile.get("company_name", "NovaFactory AI")
        business_area = profile.get("business_area", "제조업 AI 비전 품질검사")

        df_cleaned = pd.read_csv(self.cleaned_path) if os.path.exists(self.cleaned_path) else pd.DataFrame()
        df_rec = pd.read_csv(self.rec_path) if os.path.exists(self.rec_path) else pd.DataFrame()

        total_cleaned = len(df_cleaned)
        total_rec = len(df_rec)

        # Category statistics
        cat_counts = df_cleaned["category"].value_counts().to_dict() if not df_cleaned.empty else {}
        total_cats = sum(cat_counts.values()) or 1
        cat_stats = {
            cat: {
                "count": count,
                "percentage": round((count / total_cats) * 100, 1)
            }
            for cat, count in cat_counts.items()
        }

        # Top 10 and Top 30 items
        rec_records = df_rec.to_dict(orient="records") if not df_rec.empty else []
        top_10 = rec_records[:10]

        # 1. Generate docs/report.json
        report_data = {
            "metadata": {
                "company_name": company_name,
                "business_area": business_area,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_cleaned_count": total_cleaned,
                "recommended_count": total_rec,
                "engine": "Nova Market Agent v1.0 (Gemini LLM Enhanced)"
            },
            "category_stats": cat_stats,
            "top_10_recommendations": top_10,
            "all_recommendations": rec_records
        }

        report_json_path = os.path.join(self.docs_dir, "report.json")
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Generated JSON report: {report_json_path}")

        # 2. Generate docs/index.html
        html_content = self._render_html(report_data, top_10, rec_records, profile)
        index_html_path = os.path.join(self.docs_dir, "index.html")
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Generated HTML Dashboard: {index_html_path}")
        print(f"[OK] Dashboard generated successfully at: {index_html_path}")

    def _render_html(self, report_data: dict, top_10: list, all_rec: list, profile: dict) -> str:
        meta = report_data["metadata"]
        cat_stats = report_data["category_stats"]
        
        # Helper badges
        def category_badge(cat: str) -> str:
            c = str(cat).lower()
            if "policy" in c:
                return '<span class="badge badge-policy">🏛️ 정책/지원사업</span>'
            elif "market" in c:
                return '<span class="badge badge-market">📈 시장 동향</span>'
            elif "competitor" in c:
                return '<span class="badge badge-competitor">🎯 경쟁사 동향</span>'
            return '<span class="badge badge-tech">💡 기술/AI</span>'

        # Render Top 10 Cards
        top_10_cards_html = ""
        for item in top_10:
            rank = item.get("rank", 1)
            title = item.get("title", "")
            score = float(item.get("score", 0))
            reason = item.get("recommendation_reason", "")
            date = item.get("date", "")
            source_name = item.get("source_name", "출처 미상")
            source_url = item.get("source_url", "#")
            cat_badge = category_badge(item.get("category", ""))
            keywords = str(item.get("matched_keywords", "")).replace("|", ", ")

            top_10_cards_html += f"""
            <div class="card item-card mb-3 shadow-sm border-0">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="d-flex align-items-center gap-2">
                            <span class="rank-badge">#{rank}</span>
                            {cat_badge}
                            <span class="text-muted small"><i class="bi bi-building"></i> {source_name}</span>
                            <span class="text-muted small"><i class="bi bi-calendar"></i> {date}</span>
                        </div>
                        <div class="score-badge">
                            <span class="score-label">적합도</span>
                            <span class="score-val">{score:.0f}</span>
                        </div>
                    </div>
                    
                    <h5 class="card-title fw-bold my-2">
                        <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="news-link">
                            {title} <i class="bi bi-box-arrow-up-right small"></i>
                        </a>
                    </h5>
                    
                    <div class="reason-box mt-3 p-3 rounded">
                        <div class="fw-semibold text-primary mb-1"><i class="bi bi-lightbulb-fill"></i> 기업 맞춤 추천 이유</div>
                        <div class="reason-text text-dark">{reason}</div>
                    </div>

                    <div class="mt-3 d-flex justify-content-between align-items-center">
                        <div class="keyword-tags small text-muted">
                            <i class="bi bi-tags"></i> 매칭 키워드: <span class="badge bg-light text-secondary border">{keywords if keywords else '제조 AI 일반'}</span>
                        </div>
                        <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary rounded-pill px-3">
                            원문 바로가기 →
                        </a>
                    </div>
                </div>
            </div>
            """

        # Render Table Rows for Top 30
        table_rows_html = ""
        for item in all_rec:
            rank = item.get("rank", "-")
            title = item.get("title", "")
            score = float(item.get("score", 0))
            date = item.get("date", "")
            source_name = item.get("source_name", "")
            source_url = item.get("source_url", "#")
            cat_badge = category_badge(item.get("category", ""))
            reason = item.get("recommendation_reason", "")

            table_rows_html += f"""
            <tr>
                <td class="fw-bold text-center">#{rank}</td>
                <td>{cat_badge}</td>
                <td>
                    <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="text-decoration-none fw-semibold text-dark">
                        {title}
                    </a>
                    <div class="text-muted small mt-1">{reason}</div>
                </td>
                <td class="text-center"><span class="badge bg-primary-subtle text-primary fw-bold px-2 py-1">{score:.0f}점</span></td>
                <td class="small text-muted">{source_name}</td>
                <td class="small text-muted text-nowrap">{date}</td>
                <td class="text-center">
                    <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-light border py-0 px-2">
                        보기
                    </a>
                </td>
            </tr>
            """

        # Render Categories stats cards
        market_cnt = cat_stats.get("market", {}).get("count", 0)
        policy_cnt = cat_stats.get("policy", {}).get("count", 0)
        tech_cnt = cat_stats.get("tech", {}).get("count", 0)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta['company_name']} - 시장 & 경쟁사 인텔리전스 대시보드</title>
    <!-- Bootstrap 5 CSS & Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
        }}
        .navbar-brand {{
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .hero-banner {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: #fff;
            padding: 2.5rem 0;
            border-bottom: 1px solid #334155;
        }}
        .kpi-card {{
            background: #ffffff;
            border-radius: 12px;
            padding: 1.25rem;
            border: 1px solid #e2e8f0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
        }}
        .rank-badge {{
            background: #0f172a;
            color: #ffffff;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.85rem;
        }}
        .badge-policy {{
            background-color: #ecfdf5;
            color: #065f46;
            border: 1px solid #a7f3d0;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 6px;
        }}
        .badge-market {{
            background-color: #eff6ff;
            color: #1e40af;
            border: 1px solid #bfdbfe;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 6px;
        }}
        .badge-competitor {{
            background-color: #fdf2f8;
            color: #9d174d;
            border: 1px solid #fbcfe8;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 6px;
        }}
        .badge-tech {{
            background-color: #f5f3ff;
            color: #5b21b6;
            border: 1px solid #ddd6fe;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 6px;
        }}
        .item-card {{
            border-radius: 14px;
            transition: all 0.2s ease-in-out;
            background: #ffffff;
            border: 1px solid #e2e8f0 !important;
        }}
        .item-card:hover {{
            border-color: #3b82f6 !important;
            box-shadow: 0 12px 24px -8px rgba(59, 130, 246, 0.15) !important;
        }}
        .news-link {{
            color: #0f172a;
            text-decoration: none;
            transition: color 0.15s;
        }}
        .news-link:hover {{
            color: #2563eb;
            text-decoration: underline;
        }}
        .reason-box {{
            background-color: #f1f5f9;
            border-left: 4px solid #2563eb;
        }}
        .score-badge {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}
        .score-val {{
            font-size: 1.35rem;
            font-weight: 800;
            color: #2563eb;
            line-height: 1;
        }}
        .score-label {{
            font-size: 0.7rem;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .nav-pills .nav-link.active {{
            background-color: #2563eb;
        }}
    </style>
</head>
<body>

    <!-- Header / Navbar -->
    <nav class="navbar navbar-dark bg-dark">
        <div class="container d-flex justify-content-between align-items-center">
            <span class="navbar-brand d-flex align-items-center gap-2">
                <i class="bi bi-robot text-primary"></i> {meta['company_name']} <span class="badge bg-primary-subtle text-primary fw-normal small">Market Agent</span>
            </span>
            <div class="text-secondary small">
                <i class="bi bi-clock-history"></i> 최종 갱신: {meta['generated_at']}
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <header class="hero-banner">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-lg-8">
                    <span class="badge bg-info-subtle text-info border border-info-subtle mb-2">실시간 시장 인텔리전스</span>
                    <h2 class="fw-bold mb-2">{meta['company_name']} 비즈니스 모니터링 대시보드</h2>
                    <p class="text-slate-300 mb-0 opacity-75">
                        분야: <strong>{meta['business_area']}</strong> | 경쟁사 및 정부 지원사업, AI 비전 품질검사 시장 동향을 자동 수집·분석합니다.
                    </p>
                </div>
                <div class="col-lg-4 text-lg-end mt-3 mt-lg-0">
                    <span class="badge bg-success py-2 px-3 fs-6">
                        <i class="bi bi-check-circle-fill"></i> {meta['engine']}
                    </span>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container my-4">

        <!-- KPI Metrics Row -->
        <div class="row g-3 mb-4">
            <div class="col-md-3 col-6">
                <div class="kpi-card text-center">
                    <div class="text-muted small fw-semibold">수집 & 정제 건수</div>
                    <div class="fs-3 fw-bold text-dark mt-1">{meta['total_cleaned_count']}건</div>
                    <div class="text-success small mt-1"><i class="bi bi-check2-all"></i> 정상 수집 완료</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="kpi-card text-center">
                    <div class="text-muted small fw-semibold">전략 추천 기사</div>
                    <div class="fs-3 fw-bold text-primary mt-1">{meta['recommended_count']}건</div>
                    <div class="text-primary small mt-1"><i class="bi bi-star-fill"></i> TOP 30 랭킹</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="kpi-card text-center">
                    <div class="text-muted small fw-semibold">시장·경쟁사 동향</div>
                    <div class="fs-3 fw-bold text-dark mt-1">{market_cnt}건</div>
                    <div class="text-muted small mt-1">Market & Competitor</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="kpi-card text-center">
                    <div class="text-muted small fw-semibold">정책 & 정부지원</div>
                    <div class="fs-3 fw-bold text-success mt-1">{policy_cnt}건</div>
                    <div class="text-success small mt-1">Policy & Grants</div>
                </div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-pills mb-4 justify-content-center" id="dashboardTab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active px-4 fw-semibold" id="top10-tab" data-bs-toggle="pill" data-bs-target="#top10-content" type="button" role="tab">
                    🔥 핵심 추천 TOP 10
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link px-4 fw-semibold" id="table-tab" data-bs-toggle="pill" data-bs-target="#table-content" type="button" role="tab">
                    📋 전체 추천 목록 (TOP 30)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link px-4 fw-semibold" id="stats-tab" data-bs-toggle="pill" data-bs-target="#stats-content" type="button" role="tab">
                    📊 카테고리 & 분석 정보
                </button>
            </li>
        </ul>

        <!-- Tab Contents -->
        <div class="tab-content" id="dashboardTabContent">

            <!-- TAB 1: TOP 10 CARDS -->
            <div class="tab-pane fade show active" id="top10-content" role="tabpanel">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4 class="fw-bold m-0"><i class="bi bi-trophy-fill text-warning"></i> 오늘의 핵심 브리핑 TOP 10</h4>
                    <span class="text-muted small">점수 및 기업 연관도 기준 선별</span>
                </div>
                {top_10_cards_html}
            </div>

            <!-- TAB 2: TOP 30 TABLE -->
            <div class="tab-pane fade" id="table-content" role="tabpanel">
                <div class="card border-0 shadow-sm rounded-4">
                    <div class="card-body p-4">
                        <h4 class="fw-bold mb-3"><i class="bi bi-table"></i> 맞춤 추천 목록 전체 (상위 30건)</h4>
                        <div class="table-responsive">
                            <table class="table table-hover align-middle">
                                <thead class="table-light">
                                    <tr>
                                        <th class="text-center" style="width: 60px;">순위</th>
                                        <th style="width: 130px;">분류</th>
                                        <th>기사 제목 및 추천 이유</th>
                                        <th class="text-center" style="width: 90px;">점수</th>
                                        <th style="width: 120px;">출처</th>
                                        <th style="width: 100px;">날짜</th>
                                        <th class="text-center" style="width: 70px;">원문</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {table_rows_html}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: STATS & PROFILE -->
            <div class="tab-pane fade" id="stats-content" role="tabpanel">
                <div class="row g-4">
                    <div class="col-md-6">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4">
                            <h5 class="fw-bold mb-3"><i class="bi bi-pie-chart-fill text-primary"></i> 카테고리별 수집 분포</h5>
                            <div class="list-group list-group-flush">
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div><i class="bi bi-graph-up text-primary me-2"></i> 시장 동향 (Market)</div>
                                    <span class="badge bg-primary rounded-pill">{market_cnt}건 ({cat_stats.get('market', {}).get('percentage', 0)}%)</span>
                                </div>
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div><i class="bi bi-bank text-success me-2"></i> 정책 및 지원사업 (Policy)</div>
                                    <span class="badge bg-success rounded-pill">{policy_cnt}건 ({cat_stats.get('policy', {}).get('percentage', 0)}%)</span>
                                </div>
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div><i class="bi bi-cpu text-purple me-2"></i> 기술 및 AI 동향 (Tech)</div>
                                    <span class="badge bg-secondary rounded-pill">{tech_cnt}건 ({cat_stats.get('tech', {}).get('percentage', 0)}%)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4">
                            <h5 class="fw-bold mb-3"><i class="bi bi-person-badge-fill text-info"></i> 분석 타깃 프로필</h5>
                            <ul class="list-unstyled mb-0">
                                <li class="mb-2"><strong>기업명:</strong> {profile.get('company_name', '-')}</li>
                                <li class="mb-2"><strong>사업 영역:</strong> {profile.get('business_area', '-')}</li>
                                <li class="mb-2"><strong>모니터링 경쟁사:</strong> {', '.join(profile.get('competitors', []))}</li>
                                <li class="mb-2"><strong>핵심 관심 키워드:</strong> {', '.join(profile.get('interest_keywords', []))}</li>
                                <li class="mb-0"><strong>지원사업 키워드:</strong> {', '.join(profile.get('funding_keywords', []))}</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

        </div>

    </main>

    <!-- Footer -->
    <footer class="bg-white border-top py-4 mt-5">
        <div class="container text-center text-muted small">
            <p class="mb-1">Market Agent by <strong>{meta['company_name']}</strong> &bull; Automated with Antigravity & GitHub Pages</p>
            <p class="mb-0">Data source: Public RSS & Official Announcements &bull; Evaluated with Google Gemini AI</p>
        </div>
    </footer>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
        return html


if __name__ == "__main__":
    builder = SiteBuilder()
    builder.build()
