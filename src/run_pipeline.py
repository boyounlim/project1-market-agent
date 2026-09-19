"""
End-to-End Market Intelligence Pipeline Runner.
Orchestrates crawler -> cleaner -> recommender -> build_site with robust error handling.
"""

import os
import sys
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, Any

import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.crawler import MarketCrawler
from src.cleaner import DataCleaner
from src.recommender import MarketRecommender
from src.build_site import SiteBuilder

# Logging setup
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")

# Setup pipeline logger
logger = logging.getLogger("PipelineRunner")
logger.setLevel(logging.INFO)
# Clear existing handlers if any to avoid duplicate logging
logger.handlers.clear()

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(stream_handler)


class PipelineRunner:
    def __init__(self,
                 config_path: str = "config/company_profile.yaml",
                 raw_path: str = "data/raw/crawled_market_news.csv",
                 cleaned_path: str = "data/processed/cleaned_market_news.csv",
                 rec_path: str = "data/processed/recommended_market_news.csv",
                 fallback_path: str = "data/fallback/fallback_market_news.csv",
                 docs_dir: str = "docs"):
        self.config_path = config_path
        self.raw_path = raw_path
        self.cleaned_path = cleaned_path
        self.rec_path = rec_path
        self.fallback_path = fallback_path
        self.docs_dir = docs_dir

        self.statuses: Dict[str, str] = {
            "CRAWLER": "NOT_STARTED",
            "CLEANER": "NOT_STARTED",
            "RECOMMENDER": "NOT_STARTED",
            "BUILD_SITE": "NOT_STARTED"
        }
        self.step_details: Dict[str, Any] = {}

    def run_stage_crawler(self) -> bool:
        """Stage 1: Collect market news via crawler with fallback defense."""
        logger.info(">>> [STAGE 1/4] Starting Crawler Stage...")
        start_t = time.time()
        try:
            crawler = MarketCrawler(config_path=self.config_path)
            df_raw = crawler.run(output_path=self.raw_path, target_min_count=200)

            count = len(df_raw) if df_raw is not None else 0
            duration = round(time.time() - start_t, 2)

            if count >= 200:
                if crawler.failed_sources:
                    self.statuses["CRAWLER"] = "WARNING"
                    logger.warning(f"[STAGE 1] CRAWLER completed with WARNING: {count} items collected, but some sources failed: {crawler.failed_sources}")
                else:
                    self.statuses["CRAWLER"] = "SUCCESS"
                    logger.info(f"[STAGE 1] CRAWLER completed with SUCCESS: {count} items in {duration}s")
            else:
                self.statuses["CRAWLER"] = "WARNING"
                logger.warning(f"[STAGE 1] CRAWLER collected {count} items (< 200 target).")

            self.step_details["crawler_count"] = count
            self.step_details["crawler_failed_sources"] = crawler.failed_sources
            return True

        except Exception as e:
            logger.error(f"[STAGE 1] CRAWLER exception: {e}\n{traceback.format_exc()}")
            # Attempt emergency fallback dataset load
            if os.path.exists(self.fallback_path):
                logger.warning(f"[STAGE 1] Activating emergency fallback from {self.fallback_path}...")
                try:
                    df_fb = pd.read_csv(self.fallback_path)
                    df_fb["data_origin"] = "synthetic_fallback"
                    os.makedirs(os.path.dirname(self.raw_path), exist_ok=True)
                    df_fb.to_csv(self.raw_path, index=False, encoding="utf-8-sig")
                    self.statuses["CRAWLER"] = "WARNING"
                    logger.info(f"[STAGE 1] Recovered using fallback data ({len(df_fb)} items).")
                    return True
                except Exception as fb_err:
                    logger.critical(f"[STAGE 1] Emergency fallback failed: {fb_err}")
            
            self.statuses["CRAWLER"] = "FAILED"
            return False

    def run_stage_cleaner(self) -> bool:
        """Stage 2: Clean and standardize collected data."""
        logger.info(">>> [STAGE 2/4] Starting Cleaner Stage...")
        start_t = time.time()
        try:
            cleaner = DataCleaner(raw_data_path=self.raw_path, output_path=self.cleaned_path)
            df_clean, stats = cleaner.clean()

            count = len(df_clean) if df_clean is not None else 0
            duration = round(time.time() - start_t, 2)

            if count > 0:
                self.statuses["CLEANER"] = "SUCCESS"
                logger.info(f"[STAGE 2] CLEANER completed with SUCCESS: {count} items cleaned in {duration}s")
            else:
                self.statuses["CLEANER"] = "WARNING"
                logger.warning("[STAGE 2] CLEANER produced 0 records.")

            self.step_details["cleaner_stats"] = stats
            return count > 0

        except Exception as e:
            logger.error(f"[STAGE 2] CLEANER FAILED: {e}\n{traceback.format_exc()}")
            self.statuses["CLEANER"] = "FAILED"
            return False

    def run_stage_recommender(self) -> bool:
        """Stage 3: Calculate relevance scores and LLM recommendations."""
        logger.info(">>> [STAGE 3/4] Starting Recommender Stage...")
        start_t = time.time()
        try:
            recommender = MarketRecommender(
                config_path=self.config_path,
                input_data_path=self.cleaned_path,
                output_data_path=self.rec_path
            )
            df_rec = recommender.recommend(top_k=30)
            count = len(df_rec) if df_rec is not None else 0
            duration = round(time.time() - start_t, 2)

            if count > 0:
                if recommender.llm_used:
                    self.statuses["RECOMMENDER"] = "SUCCESS"
                    logger.info(f"[STAGE 3] RECOMMENDER completed with SUCCESS (LLM Enabled): {count} items in {duration}s")
                else:
                    self.statuses["RECOMMENDER"] = "SUCCESS"
                    logger.info(f"[STAGE 3] RECOMMENDER completed with SUCCESS (Rule-based): {count} items in {duration}s")
            else:
                self.statuses["RECOMMENDER"] = "FAILED"
                logger.error("[STAGE 3] RECOMMENDER returned 0 items.")

            self.step_details["rec_count"] = count
            self.step_details["llm_used"] = recommender.llm_used
            return count > 0

        except Exception as e:
            logger.error(f"[STAGE 3] RECOMMENDER FAILED: {e}\n{traceback.format_exc()}")
            self.statuses["RECOMMENDER"] = "FAILED"
            return False

    def run_stage_build_site(self) -> bool:
        """Stage 4: Generate HTML dashboard and JSON report in docs/."""
        logger.info(">>> [STAGE 4/4] Starting Site Builder Stage...")
        start_t = time.time()
        try:
            builder = SiteBuilder(
                config_path=self.config_path,
                cleaned_path=self.cleaned_path,
                rec_path=self.rec_path,
                docs_dir=self.docs_dir
            )
            builder.build()
            duration = round(time.time() - start_t, 2)

            index_file = os.path.join(self.docs_dir, "index.html")
            report_file = os.path.join(self.docs_dir, "report.json")

            if os.path.exists(index_file) and os.path.exists(report_file):
                self.statuses["BUILD_SITE"] = "SUCCESS"
                logger.info(f"[STAGE 4] BUILD_SITE completed with SUCCESS: Dashboard ready at {index_file} ({duration}s)")
                return True
            else:
                self.statuses["BUILD_SITE"] = "FAILED"
                logger.error("[STAGE 4] Site artifacts were not generated.")
                return False

        except Exception as e:
            logger.error(f"[STAGE 4] BUILD_SITE FAILED: {e}\n{traceback.format_exc()}")
            self.statuses["BUILD_SITE"] = "FAILED"
            return False

    def run_all(self) -> bool:
        """Executes full pipeline sequentially."""
        total_start = time.time()
        logger.info("================================================================")
        logger.info(f"[START] INITIATING MARKET AGENT PIPELINE [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        logger.info("================================================================")

        # Execute stages
        s1 = self.run_stage_crawler()
        s2 = self.run_stage_cleaner() if s1 else False
        s3 = self.run_stage_recommender() if s2 else False
        s4 = self.run_stage_build_site() if s3 else False

        total_duration = round(time.time() - total_start, 2)

        # Print Execution Summary Table
        logger.info("================================================================")
        logger.info("[SUMMARY] PIPELINE EXECUTION SUMMARY")
        logger.info("================================================================")
        for stage, status in self.statuses.items():
            icon = "[OK]" if status == "SUCCESS" else ("[WARN]" if status == "WARNING" else "[FAIL]")
            logger.info(f" {icon} Stage: {stage:<12} Status: {status}")
        logger.info(f"[TIME] Total Execution Time: {total_duration}s")
        logger.info("================================================================")

        return all(status in ["SUCCESS", "WARNING"] for status in self.statuses.values())


if __name__ == "__main__":
    runner = PipelineRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
