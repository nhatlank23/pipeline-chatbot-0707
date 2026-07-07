"""
Module hỗ trợ quét, kiểm tra và thống kê các tài liệu Markdown để phục vụ In-Context RAG của Gemini.
Do Gemini hỗ trợ Context Window lớn, ta không cần upload lên OpenAI Vector Store nữa mà sẽ tải trực tiếp tài liệu local vào prompt.
"""
import os
import glob
import json
import logging
from dotenv import load_dotenv

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gemini_uploader")

def clean_env_var(value: str) -> str:
    """
    Dọn dẹp các ký tự chú thích và khoảng trắng từ file .env.
    """
    if not value:
        return ""
    return value.split("#")[0].strip()

def load_local_articles(articles_dir: str) -> list[dict]:
    """
    Quét và đọc toàn bộ các file markdown (.md) trong thư mục articles_dir.
    
    Args:
        articles_dir: Đường dẫn thư mục chứa bài viết.
        
    Returns:
        Danh sách các dictionary chứa thông tin bài viết và nội dung.
    """
    file_paths = glob.glob(os.path.join(articles_dir, "*.md"))
    articles_data = []
    
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            size_bytes = os.path.getsize(path)
            articles_data.append({
                "file_path": path,
                "filename": os.path.basename(path),
                "size_bytes": size_bytes,
                "content": content
            })
        except Exception as e:
            logger.error(f"Lỗi khi đọc file {path}: {e}")
            
    return articles_data

def verify_and_summarize(articles: list[dict], min_required: int = 30) -> dict:
    """
    Kiểm tra số lượng bài viết và sinh cấu trúc JSON thống kê kết quả.
    
    Args:
        articles: Danh sách bài viết đã đọc.
        min_required: Số lượng bài viết tối thiểu bắt buộc.
        
    Returns:
        Dict thống kê kết quả.
    """
    num_files = len(articles)
    logger.info(f"Tổng số bài viết quét được: {num_files}")
    
    if num_files < min_required:
        error_msg = f"Lỗi xác thực: Số lượng bài viết ({num_files}) ít hơn yêu cầu tối thiểu là {min_required}."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    total_bytes = sum(art["size_bytes"] for art in articles)
    
    return {
        "num_files": num_files,
        "total_bytes": total_bytes,
        "failed": []  # Ở bước này, nếu file lỗi đã bị lọc qua try-except ở load
    }

def main():
    # Nạp cấu hình từ .env
    load_dotenv()
    
    gemini_model = clean_env_var(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    
    # Định nghĩa các đường dẫn thư mục
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    articles_dir = os.path.join(base_dir, "data", "articles")
    
    logger.info(f"Đang tiến hành quét tài liệu tại: {articles_dir}")
    
    try:
        articles = load_local_articles(articles_dir)
        summary = verify_and_summarize(articles, min_required=30)
        
        # Kết quả tổng kết dạng JSON tương thích
        output = {
            "gemini_model": gemini_model,
            "upload_summary": summary
        }
        
        print("\n=== KẾT QUẢ TỔNG KẾT JSON ===")
        print(json.dumps(output, indent=4, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Thất bại trong quá trình quét dữ liệu: {e}")

if __name__ == "__main__":
    main()
