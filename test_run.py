import logging
from scraper.zendesk_scraper import run_scrape

# Cấu hình logging để hiển thị thông tin
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Dùng help center của chính Zendesk để test
TEST_BASE_URL = "https://support.zendesk.com"
OUTPUT_DIR = "data/articles"

if __name__ == "__main__":
    print(f"Bắt đầu chạy thử tải bài viết từ: {TEST_BASE_URL}")
    print(f"Thư mục lưu bài viết: {OUTPUT_DIR}\n")
    try:
        metadata = run_scrape(TEST_BASE_URL, OUTPUT_DIR)
        print("\n=== KẾT QUẢ TẢI XUỐNG ===")
        print(f"Đã tải thành công: {len(metadata)} bài viết.")
        print("3 bài viết đầu tiên:")
        for meta in metadata[:3]:
            print(f"- ID: {meta['id']} | Slug: {meta['slug']} | File: {meta['file_path']}")
    except Exception as e:
        print(f"\n[Lỗi] Có lỗi xảy ra: {e}")
