"""
Entrypoint chính để chạy toàn bộ pipeline đồng bộ nội dung (RAG chatbot) sử dụng Gemini.
Được tối ưu để chạy trong môi trường Docker kết hợp với GitHub Actions:
1. Nạp các biến môi trường từ .env.
2. Đọc file trạng thái cũ (data/state.json) từ máy cục bộ (hoặc workspace).
3. Chạy scraper.zendesk_scraper.run_scrape() để tải toàn bộ bài viết mới nhất từ Zendesk và tính toán mã băm (content_hash).
4. So sánh trạng thái cũ với kết quả cào mới để phân loại thay đổi (added, updated, skipped, deleted).
5. Xóa các bài viết thuộc danh mục 'deleted' và 'updated' (phiên bản cũ) khỏi Gemini File Search Store trước để tránh trùng lặp nội dung.
6. Upload các bài viết thuộc danh mục 'added' và 'updated' (phiên bản mới) lên Gemini File Search Store.
7. Cập nhật trạng thái mới vào file data/state.json.
8. Ghi log tổng kết ra màn hình và lưu file log cục bộ tại logs/run_<timestamp>.log để GitHub Actions commit ngược lại repo.
9. Quản lý mã thoát (exit code 0 nếu thành công, 1 nếu gặp lỗi nghiêm trọng).
"""
import os
import sys
import time
import json
import logging
import argparse
from dotenv import load_dotenv
from google import genai

# Thêm thư mục gốc vào sys.path để chạy trực tiếp không bị lỗi import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.zendesk_scraper import run_scrape
from uploader.file_search_uploader import get_or_create_store, upload_files, clean_env_var

# Định nghĩa các thư mục mặc định
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTICLES_DIR = os.path.join(DATA_DIR, "articles")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOCAL_STATE_PATH = os.path.join(DATA_DIR, "state.json")

# Đảm bảo các thư mục tồn tại
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Khởi tạo logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main_pipeline")

def setup_log_file(timestamp: str) -> str:
    """
    Tạo file log cục bộ cho phiên chạy hiện tại.
    """
    log_filename = f"run_{timestamp}.log"
    log_filepath = os.path.join(LOGS_DIR, log_filename)
    
    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(file_handler)
    
    return log_filepath

def load_state() -> dict:
    """
    Đọc trạng thái đồng bộ từ file state.json cục bộ.
    Nếu file chưa tồn tại, khởi tạo một trạng thái trống.
    """
    if os.path.exists(LOCAL_STATE_PATH):
        try:
            with open(LOCAL_STATE_PATH, "r", encoding="utf-8") as f:
                logger.info(f"Đã tải thành công trạng thái cũ từ: {LOCAL_STATE_PATH}")
                return json.load(f)
        except Exception as e:
            logger.warning(f"Lỗi khi đọc file state.json cũ, sẽ khởi tạo mới: {e}")
    else:
        logger.info("Chưa có file state.json cũ. Khởi tạo trạng thái mới.")
    return {"articles": {}}

def save_state(state: dict):
    """
    Lưu trạng thái đồng bộ mới vào file state.json cục bộ.
    """
    try:
        with open(LOCAL_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        logger.info(f"Đã lưu trạng thái mới vào: {LOCAL_STATE_PATH}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file state.json: {e}")
        raise e

def main():
    # Nạp các biến môi trường
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Zendesk to Gemini RAG sync pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Run sync pipeline in dry-run mode.")
    parser.add_argument("--chat", "-c", action="store_true", help="Start interactive CLI chatbot interface.")
    args = parser.parse_args()
    
    if args.chat:
        from cli_chat import run_chat_loop
        run_chat_loop()
        sys.exit(0)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    local_log_path = setup_log_file(timestamp)
    
    dry_run = args.dry_run
    if dry_run:
        logger.info("===============================================")
        logger.info("CHẠY TRONG CHẾ ĐỘ THỬ NGHIỆM (DRY RUN)")
        logger.info("===============================================")
        
    gemini_api_key = clean_env_var(os.getenv("GEMINI_API_KEY"))
    zendesk_base_url = clean_env_var(os.getenv("ZENDESK_BASE_URL"))
    
    if not all([gemini_api_key, zendesk_base_url]):
        logger.error("Lỗi: Thiếu các cấu hình bắt buộc trong file .env (GEMINI_API_KEY, ZENDESK_BASE_URL).")
        sys.exit(1)
        
    try:
        # 1. Khởi tạo Gemini Client
        client = genai.Client(api_key=gemini_api_key)
        
        # 2. Tải trạng thái cục bộ cũ
        previous_state = load_state()
        old_articles = previous_state.get("articles", {})
        
        # 3. Cào toàn bộ bài viết mới nhất từ Zendesk
        logger.info("Bắt đầu chạy scraper quét các bài viết mới từ Zendesk...")
        scraped_articles = run_scrape(zendesk_base_url, ARTICLES_DIR)
        
        # 4. Phân loại thay đổi (Compare Delta)
        new_articles_by_slug = {item["slug"]: item for item in scraped_articles}
        
        added = []
        updated = []
        skipped = []
        deleted = []
        
        # Phân loại added, updated, skipped
        for slug, new_item in new_articles_by_slug.items():
            if slug not in old_articles:
                added.append(new_item)
            else:
                old_item = old_articles[slug]
                if old_item.get("hash") != new_item["content_hash"]:
                    updated.append(new_item)
                else:
                    skipped.append(new_item)
                    
        # Phân loại deleted
        for slug, old_item in old_articles.items():
            if slug not in new_articles_by_slug:
                deleted.append({
                    "slug": slug,
                    "document_name": old_item.get("document_name"),
                    "zendesk_id": old_item.get("zendesk_id")
                })
                
        logger.info(f"Phân loại delta: added={len(added)}, updated={len(updated)}, skipped={len(skipped)}, deleted={len(deleted)}")
        
        # Lấy hoặc tạo File Search Store
        store_display_name = "OptiBot Knowledge Base"
        if not dry_run:
            store_name = get_or_create_store(client, store_display_name)
        else:
            store_name = "dry-run-store-name"
            
        # 5. Xử lý xóa (deleted + updated cũ) khỏi Store
        # Xóa các file bị deleted
        for item in deleted:
            slug = item["slug"]
            doc_name = item["document_name"]
            if doc_name and doc_name != "Unknown":
                logger.info(f"Đang xóa bài viết gỡ bỏ khỏi Store: {slug} (Document Name: {doc_name})")
                if not dry_run:
                    try:
                        client.file_search_stores.documents.delete(name=doc_name)
                        logger.info(f"Đã xóa thành công document {doc_name} khỏi Store.")
                    except Exception as e:
                        logger.error(f"Lỗi khi xóa document {doc_name}: {e}")
                else:
                    logger.info(f"[Dry Run] Sẽ xóa document: {doc_name} của bài viết {slug}")
            if slug in previous_state["articles"]:
                del previous_state["articles"][slug]
                
        # Xóa phiên bản cũ của các file bị updated
        for item in updated:
            slug = item["slug"]
            old_item = old_articles.get(slug, {})
            doc_name = old_item.get("document_name")
            if doc_name and doc_name != "Unknown":
                logger.info(f"Đang xóa phiên bản cũ bài viết {slug} khỏi Store (Document Name: {doc_name})")
                if not dry_run:
                    try:
                        client.file_search_stores.documents.delete(name=doc_name)
                        logger.info(f"Đã xóa thành công phiên bản cũ {doc_name} khỏi Store.")
                    except Exception as e:
                        logger.error(f"Lỗi khi xóa document cũ {doc_name}: {e}")
                else:
                    logger.info(f"[Dry Run] Sẽ xóa document cũ: {doc_name} của bài viết {slug}")
                    
        # 6. Upload các bài viết mới hoặc được cập nhật lên Store (added + updated)
        files_to_upload = added + updated
        if files_to_upload:
            paths_to_upload = [item["file_path"] for item in files_to_upload]
            if not dry_run:
                upload_res = upload_files(client, store_name, paths_to_upload)
                
                # Cập nhật các file upload thành công vào state
                for succ in upload_res.get("succeeded", []):
                    matched_item = None
                    for item in files_to_upload:
                        if item["file_path"] == succ["file_path"]:
                            matched_item = item
                            break
                    if matched_item:
                        previous_state["articles"][matched_item["slug"]] = {
                            "hash": matched_item["content_hash"],
                            "updated_at": matched_item["updated_at"],
                            "document_name": succ["document_name"],
                            "zendesk_id": matched_item["id"]
                        }
            else:
                for item in files_to_upload:
                    logger.info(f"[Dry Run] Sẽ upload file mới/cập nhật: {item['file_path']}")
                    previous_state["articles"][item["slug"]] = {
                        "hash": item["content_hash"],
                        "updated_at": item["updated_at"],
                        "document_name": f"dry-run-doc-{item['id']}",
                        "zendesk_id": item["id"]
                    }
                    
        # 7. Ghi trạng thái state.json cục bộ
        save_state(previous_state)
        
        # 8. Log tổng kết
        summary_log = f"[main] added={len(added)} updated={len(updated)} skipped={len(skipped)} deleted={len(deleted)} total_articles={len(scraped_articles)}"
        logger.info(summary_log)
        logger.info("Đồng bộ pipeline hoàn tất thành công.")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng xảy ra trong quá trình chạy pipeline: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
