"""
Data Cleaning and Preprocessing Module for Market Intelligence Data.
Standardizes dates, cleans HTML noise, handles missing values, and eliminates duplicates.
"""

import os
import re
import sys
import html
import logging
from datetime import datetime
from typing import Optional, Tuple, Any

import pandas as pd
from bs4 import BeautifulSoup


# Logging setup
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cleaner.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DataCleaner")


def clean_text_content(text: Optional[str]) -> str:
    """Removes HTML tags, decodes HTML entities, and normalizes whitespaces."""
    if text is None or pd.isna(text):
        return ""
    text = str(text)
    
    # 1. Decode HTML entities (e.g., &quot; &amp; &lt;)
    text = html.unescape(text)
    
    # 2. Strip HTML tags
    if "<" in text and ">" in text:
        try:
            soup = BeautifulSoup(text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
        except Exception:
            text = re.sub(r"<[^>]+>", " ", text)

    # 3. Clean control characters and normalize whitespaces
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_date_string(date_val: Any, fallback_date: Optional[str] = None) -> str:
    """Parses and converts various date formats into YYYY-MM-DD."""
    if pd.isna(date_val) or not date_val:
        if fallback_date and not pd.isna(fallback_date):
            return str(fallback_date)[:10]
        return datetime.now().strftime("%Y-%m-%d")

    date_str = str(date_val).strip()
    
    # Standard YYYY-MM-DD
    match = re.search(r"(\d{4})[-/.년]\s*(\d{1,2})[-/.월]\s*(\d{1,2})", date_str)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    # Try pandas date parser
    try:
        parsed = pd.to_datetime(date_str, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Fallback
    if fallback_date and not pd.isna(fallback_date):
        return str(fallback_date)[:10]
    return datetime.now().strftime("%Y-%m-%d")


class DataCleaner:
    def __init__(self, raw_data_path: str = "data/raw/crawled_market_news.csv",
                 output_path: str = "data/processed/cleaned_market_news.csv"):
        self.raw_data_path = raw_data_path
        self.output_path = output_path

    def clean(self) -> Tuple[pd.DataFrame, dict]:
        logger.info("=========================================")
        logger.info(f"Starting Data Cleaning Pipeline on: {self.raw_data_path}")
        logger.info("=========================================")

        if not os.path.exists(self.raw_data_path):
            raise FileNotFoundError(f"Raw data file not found: {self.raw_data_path}")

        df_raw = pd.read_csv(self.raw_data_path)
        initial_count = len(df_raw)
        logger.info(f"Loaded raw dataset with {initial_count} records.")

        stats = {
            "initial_count": initial_count,
            "null_title_dropped": 0,
            "short_title_dropped": 0,
            "null_url_dropped": 0,
            "duplicate_exact_dropped": 0,
            "duplicate_url_dropped": 0,
            "duplicate_title_dropped": 0,
            "final_count": 0
        }

        # 1. Clean HTML & normalize text fields
        df = df_raw.copy()
        text_cols = ["title", "content", "summary", "source_name", "keywords"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_text_content)

        # 2. Filter missing / empty titles and URLs
        null_title_mask = df["title"].isna() | (df["title"] == "")
        stats["null_title_dropped"] = int(null_title_mask.sum())
        df = df[~null_title_mask]

        short_title_mask = df["title"].str.len() < 5
        stats["short_title_dropped"] = int(short_title_mask.sum())
        df = df[~short_title_mask]

        if "source_url" in df.columns:
            null_url_mask = df["source_url"].isna() | (df["source_url"] == "")
            stats["null_url_dropped"] = int(null_url_mask.sum())
            df = df[~null_url_mask]

        # 3. Normalize dates
        if "date" in df.columns:
            fallback_col = "collected_at" if "collected_at" in df.columns else None
            df["date"] = df.apply(
                lambda row: normalize_date_string(
                    row.get("date"),
                    row.get(fallback_col) if fallback_col else None
                ),
                axis=1
            )

        # 4. Fill empty summaries with title
        if "summary" in df.columns:
            df["summary"] = df.apply(
                lambda row: row["title"] if not row.get("summary") else row["summary"],
                axis=1
            )

        # 5. Deduplication
        # 5a. Exact duplicates
        before_exact = len(df)
        df = df.drop_duplicates()
        stats["duplicate_exact_dropped"] = before_exact - len(df)

        # 5b. Deduplicate by article_id (if present)
        if "article_id" in df.columns:
            df = df.drop_duplicates(subset=["article_id"])

        # 5c. Deduplicate by source_url
        if "source_url" in df.columns:
            before_url = len(df)
            df = df.drop_duplicates(subset=["source_url"])
            stats["duplicate_url_dropped"] = before_url - len(df)

        # 5d. Deduplicate by normalized title
        if "title" in df.columns:
            before_title = len(df)
            # Create a normalized lowercased title key for deduplication
            df["_norm_title"] = df["title"].str.lower().str.replace(r"\s+", "", regex=True)
            df = df.drop_duplicates(subset=["_norm_title"])
            df = df.drop(columns=["_norm_title"])
            stats["duplicate_title_dropped"] = before_title - len(df)

        # 6. Reset index and finalize
        df = df.reset_index(drop=True)
        stats["final_count"] = len(df)

        # Save to processed directory
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        df.to_csv(self.output_path, index=False, encoding="utf-8-sig")
        logger.info(f"Saved cleaned dataset ({len(df)} rows) to: {self.output_path}")

        logger.info("=========================================")
        logger.info("Cleaning Pipeline Summary:")
        logger.info(f" - Raw Initial Count: {stats['initial_count']}")
        logger.info(f" - Null/Empty Title Dropped: {stats['null_title_dropped']}")
        logger.info(f" - Short Title (<5 chars) Dropped: {stats['short_title_dropped']}")
        logger.info(f" - Null URL Dropped: {stats['null_url_dropped']}")
        logger.info(f" - Exact Duplicate Dropped: {stats['duplicate_exact_dropped']}")
        logger.info(f" - Duplicate URL Dropped: {stats['duplicate_url_dropped']}")
        logger.info(f" - Duplicate Title Dropped: {stats['duplicate_title_dropped']}")
        logger.info(f" - Final Cleaned Count: {stats['final_count']}")
        logger.info("=========================================")

        return df, stats


if __name__ == "__main__":
    cleaner = DataCleaner()
    df_clean, stats_summary = cleaner.clean()
