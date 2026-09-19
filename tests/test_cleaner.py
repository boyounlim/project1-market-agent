import os
import pandas as pd
import pytest
from src.cleaner import DataCleaner, clean_text_content, normalize_date_string


def test_clean_text_content():
    raw_html = "<p>스마트팩토리 &amp; AI 검사 &quot;솔루션&quot;</p>\n\n  "
    cleaned = clean_text_content(raw_html)
    assert cleaned == '스마트팩토리 & AI 검사 "솔루션"'


def test_normalize_date_string():
    assert normalize_date_string("2026-09-19 14:00:00") == "2026-09-19"
    assert normalize_date_string("2026.09.19") == "2026-09-19"
    assert normalize_date_string("2026년 9월 19일") == "2026-09-19"


def test_cleaned_dataset_validity():
    csv_path = "data/processed/cleaned_market_news.csv"
    assert os.path.exists(csv_path), "Cleaned dataset does not exist"
    
    df = pd.read_csv(csv_path)
    assert len(df) > 0, "Cleaned dataset should not be empty"
    
    # Verification rules
    assert df["title"].isna().sum() == 0, "No null titles allowed"
    assert (df["title"].str.strip() == "").sum() == 0, "No empty titles allowed"
    assert df["source_url"].duplicated().sum() == 0, "No duplicate source URLs allowed"
    assert df["article_id"].duplicated().sum() == 0, "No duplicate article IDs allowed"
