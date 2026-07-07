"""
Module hỗ trợ đồng bộ và tải (upload) tài liệu lên Google Gemini File Search Store
sử dụng thư viện google-genai chính thức (phiên bản >= 0.1.0).
"""
import os
import re
import sys
import glob
import json
import time
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Thêm thư mục gốc của dự án vào sys.path để chạy trực tiếp không bị lỗi import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.zendesk_scraper import slugify

# Cấu hình logging
logger = logging.getLogger("file_search_uploader")

# Hằng số SYSTEM_PROMPT đúng y nguyên văn bản yêu cầu không sửa đổi
SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.

- Tone: helpful, factual, concise.
- Only answer using the uploaded docs.
- Max 5 bullet points; else link to the doc.
- Cite up to 3 "Article URL:" lines per reply."""

def clean_env_var(value: str) -> str:
    """
    Dọn dẹp các ký tự chú thích và khoảng trắng từ file .env.
    """
    if not value:
        return ""
    return value.split("#")[0].strip()

def parse_article_file(file_path: str) -> dict:
    """
    Đọc và tách front-matter metadata cùng body của file markdown.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    parts = re.split(r'^---\s*$', content, flags=re.MULTILINE)
    body = ""
    metadata = {}
    if len(parts) >= 3:
        fm_text = parts[1]
        body = "\n".join(parts[2:]).strip()
        for line in fm_text.strip().split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                metadata[key] = val
    else:
        body = content
        
    return {
        "metadata": metadata,
        "body": body
    }

def get_or_create_store(client: genai.Client, display_name: str) -> str:
    """
    Lấy File Search Store ID từ biến môi trường hoặc tạo mới nếu chưa tồn tại.
    
    Args:
        client: Đối tượng Google GenAI client.
        display_name: Tên hiển thị của Store nếu tạo mới.
        
    Returns:
        Resource name của Store (dạng "fileSearchStores/xxxx").
    """
    store_name = clean_env_var(os.getenv("FILE_SEARCH_STORE_NAME"))
    if store_name:
        try:
            logger.info(f"Sử dụng lại File Search Store từ .env: {store_name}")
            store = client.file_search_stores.get(name=store_name)
            return store.name
        except Exception as e:
            logger.warning(f"Không thể lấy Store {store_name}, tiến hành tạo mới: {e}")
            
    logger.info(f"Tạo mới File Search Store với tên: {display_name}")
    store = client.file_search_stores.create(
        config={'display_name': display_name}
    )
    print(f"\n[VUI LÒNG LƯU VÀO .env] FILE_SEARCH_STORE_NAME={store.name}\n")
    return store.name

def upload_files(client: genai.Client, store_name: str, file_paths: list[str]) -> dict:
    """
    Tải danh sách các file markdown lên Gemini File Search Store và gán siêu dữ liệu.
    
    Args:
        client: Đối tượng Google GenAI client.
        store_name: Resource name của Store đích.
        file_paths: Danh sách đường dẫn file cần upload.
        
    Returns:
        Dict thống kê kết quả: {"num_files": n, "succeeded": [...], "failed": [...]}
    """
    succeeded = []
    failed = []
    
    logger.info(f"Bắt đầu upload {len(file_paths)} tài liệu lên File Search Store: {store_name}...")
    
    for path in file_paths:
        try:
            parsed = parse_article_file(path)
            title = parsed["metadata"].get("title", "no-title")
            article_url = parsed["metadata"].get("article_url", "")
            zendesk_id = parsed["metadata"].get("zendesk_id", "")
            updated_at = parsed["metadata"].get("updated_at", "")
            
            slug = slugify(title)
            if not slug:
                slug = f"doc-{zendesk_id}"
                
            logger.info(f"Đang upload file: {path} (Slug: {slug})...")
            
            # Gọi API upload lên store
            operation = client.file_search_stores.upload_to_file_search_store(
                file=path,
                file_search_store_name=store_name,
                config={
                    'display_name': slug,
                    'custom_metadata': [
                        {'key': 'article_url', 'string_value': article_url},
                        {'key': 'zendesk_id', 'string_value': str(zendesk_id)},
                        {'key': 'updated_at', 'string_value': updated_at},
                    ]
                }
            )
            
            # Chờ Long-running operation hoàn tất
            while not operation.done:
                time.sleep(2)
                operation = client.operations.get(operation)
                
            if operation.error:
                error_msg = getattr(operation.error, "message", str(operation.error))
                logger.error(f"Lỗi indexing file {path}: {error_msg}")
                failed.append({"file_path": path, "error": error_msg})
            else:
                doc_name = getattr(operation.response, "document_name", "Unknown")
                logger.info(f"Upload thành công file {path} -> Document Resource: {doc_name}")
                succeeded.append({
                    "file_path": path,
                    "document_name": doc_name,
                    "zendesk_id": zendesk_id
                })
                
        except Exception as e:
            logger.error(f"Thất bại trong quá trình upload file {path}: {e}")
            failed.append({"file_path": path, "error": str(e)})
            
    return {
        "num_files": len(file_paths),
        "succeeded": succeeded,
        "failed": failed
    }

def ask_optibot(client: genai.Client, store_name: str, question: str) -> dict:
    """
    Gửi câu hỏi tới Gemini sử dụng File Search Store để trả lời câu hỏi.
    
    Args:
        client: Đối tượng Google GenAI client.
        store_name: Resource name của Store.
        question: Câu hỏi của người dùng.
        
    Returns:
        Dict phản hồi dạng: {"answer": text, "citations": [...]}
    """
    model_name = clean_env_var(os.getenv("MODEL_NAME", "gemini-2.5-flash"))
    
    logger.info(f"Đang gửi câu hỏi lên Gemini ({model_name}) với RAG File Search...")
    
    response = client.models.generate_content(
        model=model_name,
        contents=question,
        config={
            'system_instruction': SYSTEM_PROMPT,
            'tools': [{'file_search': {'file_search_store_names': [store_name]}}]
        }
    )
    
    answer = response.text
    citations = []
    
    # Trích xuất nguồn trích dẫn từ grounding_metadata
    try:
        if response.candidates and response.candidates[0].grounding_metadata:
            meta = response.candidates[0].grounding_metadata
            chunks = meta.grounding_chunks or []
            for chunk in chunks:
                if chunk.retrieved_context:
                    ctx = chunk.retrieved_context
                    url = None
                    if ctx.custom_metadata:
                        for item in ctx.custom_metadata:
                            if item.key == 'article_url':
                                url = item.string_value
                                break
                    # Sử dụng custom_metadata url hoặc fallback về uri/title
                    citation_url = url or ctx.uri or ctx.title
                    if citation_url and citation_url not in citations:
                        citations.append(citation_url)
    except Exception as e:
        logger.warning(f"Lỗi khi trích xuất citations: {e}")
        
    return {
        "answer": answer,
        "citations": citations
    }

def main():
    # Cấu hình logging cho file chạy độc lập
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    # Nạp các biến môi trường
    load_dotenv()
    
    gemini_api_key = clean_env_var(os.getenv("GEMINI_API_KEY"))
    if not gemini_api_key:
        logger.error("Thiếu biến môi trường GEMINI_API_KEY. Vui lòng kiểm tra lại file .env")
        return
        
    client = genai.Client(api_key=gemini_api_key)
    
    # Đường dẫn thư mục chứa tài liệu Markdown
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    articles_dir = os.path.join(base_dir, "data", "articles")
    
    # Chỉ lấy các file bài viết thật (bỏ qua file gitkeep)
    file_paths = [p for p in glob.glob(os.path.join(articles_dir, "*.md")) if not p.endswith(".gitkeep")]
    
    if not file_paths:
        logger.warning(f"Không tìm thấy tài liệu markdown nào trong {articles_dir}")
        return
        
    logger.info(f"Tìm thấy {len(file_paths)} tài liệu markdown sẵn sàng upload.")
    
    # 1. Khởi tạo/Lấy Store
    store_display_name = "OptiBot Knowledge Base"
    store_name = get_or_create_store(client, store_display_name)
    
    # 2. Upload tài liệu
    upload_result = upload_files(client, store_name, file_paths)
    
    # 3. Trích xuất log tổng kết định dạng JSON
    summary = {
        "file_search_store_name": store_name,
        "upload_summary": upload_result
    }
    
    print("\n=== KẾT QUẢ TỔNG KẾT JSON ===")
    print(json.dumps(summary, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
