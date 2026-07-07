import logging
from scraper.zendesk_scraper import run_scrape

# Configure logging with basic ASCII format
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TEST_BASE_URL = "https://support.optisigns.com"
OUTPUT_DIR = "data/articles"

if __name__ == "__main__":
    print(f"Starting test run for Zendesk Scraper: {TEST_BASE_URL}")
    print(f"Output directory: {OUTPUT_DIR}\n")
    try:
        metadata = run_scrape(TEST_BASE_URL, OUTPUT_DIR)
        print("\n=== DOWNLOAD SUCCESS ===")
        print(f"Total downloaded articles: {len(metadata)}")
        print("First 3 articles:")
        for meta in metadata[:3]:
            print(f"- ID: {meta['id']} | Slug: {meta['slug']} | File: {meta['file_path']}")
    except Exception as e:
        print(f"\n[Error] An error occurred: {e}")
