"""
Market Intelligence Crawler Module
Collects market, competitor, policy, and technology news/announcements
based on config/company_profile.yaml.
"""

import os
import re
import sys
import uuid
import logging
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

import yaml
import requests
import feedparser
import pandas as pd
from bs4 import BeautifulSoup


# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "crawler.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MarketCrawler")


def clean_html(raw_html: str) -> str:
    """Removes HTML tags and cleans up whitespace."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_published_date(entry: Any) -> str:
    """Extracts and standardizes published date from feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        return str(entry.published)[:10]
    return datetime.now().strftime("%Y-%m-%d")


class MarketCrawler:
    def __init__(self, config_path: str = "config/company_profile.yaml"):
        self.config_path = config_path
        self.profile = self._load_profile()
        self.failed_sources = []
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }

    def _load_profile(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}, using defaults.")
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _match_keywords(self, text: str) -> List[str]:
        matched = []
        all_keywords = (
            self.profile.get("interest_keywords", []) +
            self.profile.get("funding_keywords", [])
        )
        for kw in all_keywords:
            if kw.lower() in text.lower():
                matched.append(kw)
        return matched

    def _match_company(self, text: str) -> Optional[str]:
        competitors = self.profile.get("competitors", [])
        for comp in competitors:
            if comp.lower() in text.lower():
                return comp
        if self.profile.get("company_name", "").lower() in text.lower():
            return self.profile.get("company_name")
        return None

    def fetch_google_news_rss(self, query: str, category: str) -> List[Dict[str, Any]]:
        """Fetches news items from Google News RSS by keyword."""
        items = []
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                raise Exception(f"Feed error: {feed.bozo_exception}")
            for entry in feed.entries:
                title = clean_html(getattr(entry, "title", ""))
                summary = clean_html(getattr(entry, "summary", ""))
                link = getattr(entry, "link", "")
                source_name = getattr(entry, "source", {}).get("title", "Google News")
                date_str = parse_published_date(entry)

                combined_text = f"{title} {summary}"
                matched_kws = self._match_keywords(combined_text)
                matched_comp = self._match_company(combined_text)

                items.append({
                    "article_id": f"LIVE-{uuid.uuid4().hex[:8].upper()}",
                    "category": category,
                    "title": title,
                    "date": date_str,
                    "content": summary,
                    "summary": summary[:200] if summary else title,
                    "source_url": link,
                    "source_name": source_name,
                    "company_tag": matched_comp,
                    "keywords": "|".join(matched_kws) if matched_kws else query,
                    "collected_at": datetime.now().isoformat(),
                    "has_null": False,
                    "is_duplicate_seed": False,
                    "data_origin": "live"
                })
            logger.info(f"[Google News RSS] Query: '{query}' -> Fetched {len(items)} items.")
        except Exception as e:
            logger.error(f"[Google News RSS] Failed for query '{query}': {e}")
            self.failed_sources.append(f"Google News RSS ({query}): {e}")
        return items

    def fetch_generic_rss(self, url: str, source_name: str, category: str) -> List[Dict[str, Any]]:
        """Fetches news items from a generic RSS feed."""
        items = []
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                raise Exception(f"Feed error: {feed.bozo_exception}")
            for entry in feed.entries:
                title = clean_html(getattr(entry, "title", ""))
                summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                link = getattr(entry, "link", "")
                date_str = parse_published_date(entry)

                combined_text = f"{title} {summary}"
                matched_kws = self._match_keywords(combined_text)
                matched_comp = self._match_company(combined_text)

                items.append({
                    "article_id": f"LIVE-{uuid.uuid4().hex[:8].upper()}",
                    "category": category,
                    "title": title,
                    "date": date_str,
                    "content": summary,
                    "summary": summary[:200] if summary else title,
                    "source_url": link,
                    "source_name": source_name,
                    "company_tag": matched_comp,
                    "keywords": "|".join(matched_kws) if matched_kws else "IT/Tech",
                    "collected_at": datetime.now().isoformat(),
                    "has_null": False,
                    "is_duplicate_seed": False,
                    "data_origin": "live"
                })
            logger.info(f"[{source_name}] Fetched {len(items)} items from {url}")
        except Exception as e:
            logger.error(f"[{source_name}] Failed to fetch from {url}: {e}")
            self.failed_sources.append(f"{source_name} ({url}): {e}")
        return items

    def fetch_bizinfo_announcements(self) -> List[Dict[str, Any]]:
        """Scrapes public government support project announcements from BizInfo."""
        items = []
        url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                raise Exception(f"HTTP status {resp.status_code}")
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select(".table_type01 tbody tr, table tbody tr")
            for row in rows:
                link_elem = row.select_one("a")
                if not link_elem:
                    continue
                title = link_elem.get_text(strip=True)
                if not title or "공지" in title:
                    continue
                href = link_elem.get("href", "")
                if href and not href.startswith("http"):
                    href = urllib.parse.urljoin("https://www.bizinfo.go.kr", href)

                date_tds = row.select("td")
                date_str = datetime.now().strftime("%Y-%m-%d")
                for td in date_tds:
                    txt = td.get_text(strip=True)
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", txt):
                        date_str = txt
                        break

                combined_text = title
                matched_kws = self._match_keywords(combined_text)

                items.append({
                    "article_id": f"LIVE-{uuid.uuid4().hex[:8].upper()}",
                    "category": "policy",
                    "title": title,
                    "date": date_str,
                    "content": f"[정부/지자체 지원사업 공고] {title}",
                    "summary": title,
                    "source_url": href,
                    "source_name": "기업마당(BizInfo)",
                    "company_tag": None,
                    "keywords": "|".join(matched_kws) if matched_kws else "정부지원사업",
                    "collected_at": datetime.now().isoformat(),
                    "has_null": False,
                    "is_duplicate_seed": False,
                    "data_origin": "live"
                })
            logger.info(f"[BizInfo] Scraped {len(items)} policy announcements.")
        except Exception as e:
            logger.error(f"[BizInfo] Scraping failed: {e}")
            self.failed_sources.append(f"BizInfo ({url}): {e}")
        return items

    def run(self, output_path: str = "data/raw/crawled_market_news.csv", target_min_count: int = 200) -> pd.DataFrame:
        """Executes full collection pipeline and saves to CSV."""
        logger.info("=========================================")
        logger.info("Starting Market Intelligence Collection Pipeline")
        logger.info("=========================================")

        all_items: List[Dict[str, Any]] = []

        # 1. Competitor News (Google News RSS)
        competitors = self.profile.get("competitors", ["VisionForge", "InspectAI", "FactoryMind", "QualiBot"])
        comp_query = " OR ".join(competitors)
        all_items.extend(self.fetch_google_news_rss(comp_query, category="competitor"))

        # 2. Market & Technology Keywords (Google News RSS)
        market_keywords = ["스마트팩토리 AI", "제조 AI 품질검사", "비전 AI 불량탐지", "스마트공장 제조 AX"]
        for kw in market_keywords:
            all_items.extend(self.fetch_google_news_rss(kw, category="market"))

        # 3. Policy & Funding Keywords (Google News RSS)
        policy_keywords = ["AI 바우처 지원사업", "스마트공장 보급 확산", "제조업 R&D 지원사업"]
        for kw in policy_keywords:
            all_items.extend(self.fetch_google_news_rss(kw, category="policy"))

        # 4. Tech RSS Feeds
        all_items.extend(self.fetch_generic_rss("https://www.aitimes.com/rss/allArticle.xml", "AI Times", category="tech"))
        all_items.extend(self.fetch_generic_rss("https://www.yna.co.kr/rss/industry.xml", "연합뉴스 산업", category="market"))
        all_items.extend(self.fetch_generic_rss("https://www.bloter.net/rss/allArticle.xml", "블로터(Bloter)", category="tech"))
        all_items.extend(self.fetch_generic_rss("https://news.hada.io/rss/news", "GeekNews", category="tech"))

        # 5. Public Policy Scraper (BizInfo)
        all_items.extend(self.fetch_bizinfo_announcements())

        # Deduplicate live items by title
        live_df = pd.DataFrame(all_items)
        if not live_df.empty:
            live_df = live_df.drop_duplicates(subset=["title"]).reset_index(drop=True)
            live_count = len(live_df)
        else:
            live_count = 0
            live_df = pd.DataFrame()

        logger.info(f"Total unique LIVE items collected: {live_count}")

        fallback_count = 0
        final_df = live_df

        # Check if live items meet minimum threshold
        if live_count < target_min_count:
            logger.warning(
                f"Live collected count ({live_count}) is below target ({target_min_count}). "
                f"Merging fallback dataset..."
            )
            fallback_path = "data/fallback/fallback_market_news.csv"
            if os.path.exists(fallback_path):
                fallback_df = pd.read_csv(fallback_path)
                fallback_df["data_origin"] = "synthetic_fallback"
                
                needed = target_min_count - live_count
                # Append needed or all fallback data
                fallback_subset = fallback_df.iloc[:max(needed, len(fallback_df))]
                fallback_count = len(fallback_subset)

                final_df = pd.concat([live_df, fallback_subset], ignore_index=True)
                logger.info(f"Merged {fallback_count} rows from fallback data.")
            else:
                logger.error(f"Fallback data file not found at {fallback_path}")

        # Ensure output directory exists and save CSV
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"Successfully saved {len(final_df)} items to {output_path}")

        # Summary Log
        logger.info("=========================================")
        logger.info("Collection Pipeline Summary:")
        logger.info(f" - Live Collected: {live_count}")
        logger.info(f" - Fallback Merged: {fallback_count}")
        logger.info(f" - Total Final Count: {len(final_df)}")
        logger.info(f" - Failed Sources ({len(self.failed_sources)}): {self.failed_sources}")
        logger.info("=========================================")

        return final_df


if __name__ == "__main__":
    crawler = MarketCrawler()
    df_result = crawler.run()
