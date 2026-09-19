"""
Market Intelligence Recommender Module.
Calculates relevance scores based on company profile and generates
customized recommendations using Gemini LLM (with seamless rule-based fallback).
"""

import os
import re
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

import yaml
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "recommender.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Recommender")


class MarketRecommender:
    def __init__(self,
                 config_path: str = "config/company_profile.yaml",
                 input_data_path: str = "data/processed/cleaned_market_news.csv",
                 output_data_path: str = "data/processed/recommended_market_news.csv"):
        self.config_path = config_path
        self.input_data_path = input_data_path
        self.output_data_path = output_data_path
        self.profile = self._load_profile()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.llm_used = False

    def _load_profile(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}")
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def calculate_rule_score(self, row: pd.Series) -> Tuple[float, List[str], Optional[str], str]:
        """
        Calculates rule-based relevance score (0-100), matched keywords,
        competitor tag, and a default rationale.
        """
        title = str(row.get("title", ""))
        content = str(row.get("content", ""))
        summary = str(row.get("summary", ""))
        combined_text = f"{title} {content} {summary}".lower()

        score = 30.0  # Base score
        matched_kws = []
        competitor_found = None

        # 1. Competitor Match (+30 points)
        for comp in self.profile.get("competitors", []):
            if comp.lower() in combined_text:
                score += 30.0
                competitor_found = comp
                matched_kws.append(f"경쟁사:{comp}")
                break

        # 2. Interest Keywords (+10 points each, max 30)
        interest_kws = self.profile.get("interest_keywords", [])
        kw_hits = 0
        for kw in interest_kws:
            if kw.lower() in combined_text:
                kw_hits += 1
                matched_kws.append(kw)
                if kw.lower() in title.lower():
                    score += 6.0  # Bonus for keyword in title
        score += min(kw_hits * 10.0, 30.0)

        # 3. Funding / Policy Keywords (+15 points each, max 30)
        funding_kws = self.profile.get("funding_keywords", [])
        funding_hits = 0
        for fkw in funding_kws:
            if fkw.lower() in combined_text:
                funding_hits += 1
                matched_kws.append(fkw)
                if fkw.lower() in title.lower():
                    score += 8.0
        score += min(funding_hits * 15.0, 30.0)

        # 4. Domain & Product alignment bonus (+10 points)
        domain_terms = ["비전", "검사", "불량", "품질", "스마트팩토리", "제조", "saas", "vision"]
        domain_hits = sum(1 for term in domain_terms if term in combined_text)
        score += min(domain_hits * 4.0, 15.0)

        # 5. Category weight
        cat = str(row.get("category", "")).lower()
        if cat == "competitor":
            score += 10.0
        elif cat == "policy":
            score += 5.0

        # Cap score at 100
        score = min(max(round(score, 1), 10.0), 100.0)

        # Build fallback rule-based reason
        reason_parts = []
        if competitor_found:
            reason_parts.append(f"주요 경쟁사({competitor_found}) 관련 시장 동향 모니터링 필요")
        if funding_hits > 0:
            reason_parts.append(f"정부 지원사업 및 자금 연계 키워드({', '.join(funding_kws[:2])}) 부합")
        if domain_hits > 0:
            reason_parts.append(f"제조 AI 비전 검사 핵심 사업 영역과의 높은 연관성 보유")
        if not reason_parts:
            reason_parts.append("제조업 AI 및 스마트공장 산업 트렌드 참고 자료")

        default_reason = " | ".join(reason_parts)
        return score, list(set(matched_kws)), competitor_found, default_reason

    def evaluate_with_gemini(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluates batch of articles with Gemini LLM to refine score and reason."""
        if not self.gemini_api_key:
            return items

        company_name = self.profile.get("company_name", "NovaFactory AI")
        business_area = self.profile.get("business_area", "제조업 AI 비전 품질검사")
        products = ", ".join(self.profile.get("products", []))
        target_market = ", ".join(self.profile.get("target_market", []))
        competitors = ", ".join(self.profile.get("competitors", []))

        # We will process in batches of 10
        batch_size = 10
        enriched_items = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            prompt = f"""
당신은 '{company_name}'의 수석 시장 인텔리전스 전략 분석가입니다.
우리 기업 프로필:
- 사업분야: {business_area}
- 주요제품: {products}
- 타깃시장: {target_market}
- 주요경쟁사: {competitors}

아래 {len(batch)}개의 시장/정책/기술 뉴스에 대해 우리 기업 관점에서 분석해주세요.
각 기사마다:
1. adjusted_score: 50~100 사이의 관련성/중요도 점수 (정수)
2. reason: 우리 기업({company_name}) 입장에서 왜 이 기사를 주목해야 하는지 1~2문장의 전문적이고 통찰력 있는 한국어 추천 이유

기사 목록:
"""
            for idx, item in enumerate(batch):
                prompt += f"\n[기사 {idx+1}] ID: {item['article_id']}\n제목: {item['title']}\n카테고리: {item['category']}\n요약: {item.get('summary', item['title'])}\n"

            prompt += """
응답은 반드시 아래 형식의 유효한 JSON 배열로만 반환해주세요:
[
  {"article_id": "...", "adjusted_score": 95, "reason": "..."},
  ...
]
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.gemini_api_key}"
            try:
                resp = requests.post(
                    url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=25
                )
                if resp.status_code == 200:
                    resp_json = resp.json()
                    res_text = resp_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # Clean json markdown tags if present
                    res_text = re.sub(r"^```json\s*", "", res_text)
                    res_text = re.sub(r"\s*```$", "", res_text)
                    parsed_evals = json.loads(res_text)
                    
                    eval_map = {e["article_id"]: e for e in parsed_evals if "article_id" in e}
                    for item in batch:
                        if item["article_id"] in eval_map:
                            e = eval_map[item["article_id"]]
                            item["score"] = float(e.get("adjusted_score", item["score"]))
                            item["recommendation_reason"] = e.get("reason", item["recommendation_reason"])
                    self.llm_used = True
                    logger.info(f"Successfully evaluated batch {i//batch_size + 1} with Gemini LLM.")
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}, using rule-based fallback.")
            except Exception as e:
                logger.warning(f"Gemini evaluation error on batch {i//batch_size + 1}: {e}, using rule-based.")

            enriched_items.extend(batch)

        return enriched_items

    def recommend(self, top_k: int = 30) -> pd.DataFrame:
        logger.info("=========================================")
        logger.info(f"Starting Recommendation Pipeline (Target TOP {top_k})")
        logger.info("=========================================")

        if not os.path.exists(self.input_data_path):
            raise FileNotFoundError(f"Cleaned data file not found: {self.input_data_path}")

        df = pd.read_csv(self.input_data_path)
        logger.info(f"Loaded {len(df)} cleaned records.")

        # Step 1: Compute Rule Scores for all items
        scored_records = []
        for _, row in df.iterrows():
            score, matched_kws, comp_found, reason = self.calculate_rule_score(row)
            rec = row.to_dict()
            rec["score"] = score
            rec["matched_keywords"] = "|".join(matched_kws) if matched_kws else ""
            rec["competitor_mentioned"] = comp_found if comp_found else ""
            rec["recommendation_reason"] = reason
            scored_records.append(rec)

        # Sort by initial score descending
        scored_records.sort(key=lambda x: x["score"], reverse=True)

        # Step 2: Select top candidates for LLM enrichment (e.g. top 40 candidates)
        candidates_for_llm = scored_records[:max(top_k + 10, 40)]
        remaining = scored_records[max(top_k + 10, 40):]

        if self.gemini_api_key:
            logger.info(f"GEMINI_API_KEY detected. Running LLM enhancement on top {len(candidates_for_llm)} items...")
            enriched_candidates = self.evaluate_with_gemini(candidates_for_llm)
        else:
            logger.info("No GEMINI_API_KEY found. Proceeding with rule-based scoring.")
            enriched_candidates = candidates_for_llm

        all_final = enriched_candidates + remaining
        # Re-sort by final score descending
        all_final.sort(key=lambda x: x["score"], reverse=True)

        # Select Top K
        top_records = all_final[:top_k]
        for idx, rec in enumerate(top_records):
            rec["rank"] = idx + 1

        top_df = pd.DataFrame(top_records)

        # Ensure output directory exists and save
        os.makedirs(os.path.dirname(self.output_data_path), exist_ok=True)
        
        # Ensure column ordering
        cols_order = [
            "rank", "article_id", "category", "title", "score",
            "recommendation_reason", "date", "source_name", "source_url",
            "matched_keywords", "competitor_mentioned", "summary", "data_origin"
        ]
        available_cols = [c for c in cols_order if c in top_df.columns]
        top_df = top_df[available_cols]

        top_df.to_csv(self.output_data_path, index=False, encoding="utf-8-sig")
        logger.info(f"Saved TOP {len(top_df)} recommendations to: {self.output_data_path}")
        logger.info(f"LLM Enhancement Status: {'ENABLED (Gemini)' if self.llm_used else 'RULE-BASED'}")
        logger.info("=========================================")

        return top_df


if __name__ == "__main__":
    recommender = MarketRecommender()
    top_df = recommender.recommend(top_k=30)
