import os
import pandas as pd
import pytest
from src.crawler import MarketCrawler


def test_company_profile_loading():
    crawler = MarketCrawler("config/company_profile.yaml")
    assert crawler.profile.get("company_name") == "NovaFactory AI"
    assert len(crawler.profile.get("competitors", [])) >= 3
    assert len(crawler.profile.get("interest_keywords", [])) >= 5


def test_crawled_csv_validity():
    csv_path = "data/raw/crawled_market_news.csv"
    assert os.path.exists(csv_path), "Crawled CSV file does not exist"
    
    df = pd.read_csv(csv_path)
    assert len(df) >= 200, f"Expected at least 200 items, got {len(df)}"
    
    required_cols = ["title", "source_url", "source_name", "data_origin"]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"
        
    assert "live" in df["data_origin"].values or "synthetic_fallback" in df["data_origin"].values
