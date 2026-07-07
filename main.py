"""
Entrypoint chính để chạy toàn bộ pipeline đồng bộ nội dung của RAG chatbot.

Pipeline này thực hiện các bước sau:
1. Nạp các biến môi trường (environment variables).
2. Cào bài viết từ Zendesk và chuyển đổi sang định dạng Markdown.
3. Phát hiện thay đổi (detect delta) bằng cách so sánh hash của file với trạng thái cũ trong state.json.
4. Tải lên (upload) các bài viết mới/sửa đổi lên OpenAI Vector Store, và xóa các bài viết đã bị gỡ bỏ.
5. Lưu trạng thái cập nhật mới nhất vào file state.json.
"""
import os
import json
import hashlib
from dotenv import load_dotenv

from scraper import run_scraper
from uploader import run_uploader

# Định nghĩa các đường dẫn thư mục
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTICLES_DIR = os.path.join(DATA_DIR, "articles")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

def load_state() -> dict:
    """
    Tải thông tin trạng thái đồng bộ trước đó từ file state.json.
    
    Returns:
        Một dict chứa mã hash lịch sử của bài viết và OpenAI file ID.
        Định dạng:
        {
            "articles": {
                "article_id": {
                    "hash": "...",
                    "file_path": "...",
                    "openai_file_id": "..."
                }
            }
        }
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"articles": {}}

def save_state(state: dict):
    """
    Lưu trạng thái đồng bộ hiện tại vào file state.json.
    
    Args:
        state: Dict đại diện cho trạng thái đồng bộ cần lưu.
    """
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def calculate_hash(content: str) -> str:
    """
    Tính toán mã MD5 hash của một chuỗi nội dung văn bản.
    
    Args:
        content: Nội dung văn bản cần tính hash.
        
    Returns:
        Mã hex digest của MD5 dưới dạng chuỗi.
    """
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def detect_delta(current_articles: list[dict], previous_state: dict) -> tuple[list[dict], list[str]]:
    """
    So sánh các bài viết mới cào với trạng thái lưu trữ trước đó để phát hiện:
    - Bài viết mới (hoặc bài viết bị thay đổi nội dung dựa trên mã hash).
    - Bài viết bị xóa (không còn xuất hiện trong kết quả cào mới nhất).
    
    Args:
        current_articles: Danh sách thông tin bài viết vừa cào.
        previous_state: Dict trạng thái cũ đã được tải lên từ state.json.
        
    Returns:
        Một tuple gồm (danh sách bài viết cần đồng bộ, danh sách openai_file_id cần xóa).
    """
    # TODO: Triển khai logic phát hiện delta (thay đổi)
    # 1. Xác định bài viết nào là mới hoặc đã bị thay đổi mã hash.
    # 2. Xác định bài viết ID nào có trong previous_state nhưng không còn ở current_articles để xóa đi.
    return [], []

def main():
    # Nạp các biến môi trường từ file .env
    load_dotenv()
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    vector_store_id = os.getenv("VECTOR_STORE_ID")
    zendesk_base_url = os.getenv("ZENDESK_BASE_URL")
    
    if not all([openai_api_key, vector_store_id, zendesk_base_url]):
        print("Lỗi: Thiếu các biến môi trường bắt buộc. Vui lòng kiểm tra lại file .env của bạn.")
        return

    print("Bắt đầu đồng bộ pipeline...")
    
    # TODO: Phối hợp toàn bộ các bước trong pipeline:
    # 1. Cào bài viết và chuyển đổi sang markdown
    # scraped_articles = run_scraper(zendesk_base_url, ARTICLES_DIR)
    
    # 2. Đọc trạng thái cũ
    # previous_state = load_state()
    
    # 3. Phát hiện delta
    # articles_to_sync, files_to_delete = detect_delta(scraped_articles, previous_state)
    
    # 4. Upload/Delete vector thông qua OpenAI API
    # run_uploader(articles_to_sync, files_to_delete, vector_store_id, openai_api_key)
    
    # 5. Lưu trạng thái đồng bộ mới
    # save_state(updated_state)
    
    print("Hoàn thành đồng bộ pipeline.")

if __name__ == "__main__":
    main()
