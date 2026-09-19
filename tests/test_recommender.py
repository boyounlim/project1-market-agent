import os
import json
import pandas as pd
import pytest
from src.recommender import MarketRecommender
from src.build_site import SiteBuilder


def test_recommender_output():
    rec_csv = "data/processed/recommended_market_news.csv"
    assert os.path.exists(rec_csv), "Recommended CSV does not exist"
    
    df = pd.read_csv(rec_csv)
    assert len(df) == 30, f"Expected 30 recommendations, got {len(df)}"
    
    required_cols = ["rank", "article_id", "category", "title", "score", "recommendation_reason", "source_url"]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"
        
    assert df["recommendation_reason"].isna().sum() == 0, "No null recommendation reasons allowed"
    assert (df["recommendation_reason"].str.strip() == "").sum() == 0, "No empty recommendation reasons allowed"
    assert (df["score"] >= 0).all(), "Scores must be non-negative"


def test_site_builder_output():
    index_html = "docs/index.html"
    report_json = "docs/report.json"
    
    assert os.path.exists(index_html), "docs/index.html does not exist"
    assert os.path.exists(report_json), "docs/report.json does not exist"
    
    # Check JSON content
    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "metadata" in data
    assert "top_10_recommendations" in data
    assert len(data["top_10_recommendations"]) == 10
    
    # Check HTML content
    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "<!DOCTYPE html>" in html
    assert "NovaFactory AI" in html
    assert "TOP 10" in html
