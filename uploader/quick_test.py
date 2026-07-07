"""
Script chạy kiểm tra nhanh (quick test) RAG Chatbot bằng Google Gemini API.
Hỗ trợ cả 2 chế độ:
1. Chế độ Cloud RAG (Khuyên dùng): Sử dụng Gemini File Search Store nếu cấu hình FILE_SEARCH_STORE_NAME trong .env.
2. Chế độ Local RAG (Fallback): Quét tài liệu cục bộ và đưa vào ngữ cảnh (context) nếu chưa cấu hình Store.
   Sử dụng thuật toán TF-IDF cục bộ để tìm kiếm và xếp hạng tài liệu chính xác nhất.
"""
import os
import sys
import glob
import re
import logging
import math
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Thêm thư mục gốc của dự án vào sys.path để chạy trực tiếp không bị lỗi import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uploader.file_search_uploader import ask_optibot, clean_env_var

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quick_test_gemini")

# Đường dẫn tài liệu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
ARTICLES_DIR = os.path.join(DATA_DIR, "articles")

def safe_print(text: str):
    """
    Hàm print an toàn chống lỗi UnicodeEncodeError trên terminal Windows.
    """
    try:
        encoding = sys.stdout.encoding or 'utf-8'
        print(text.encode(encoding, errors='replace').decode(encoding))
    except Exception:
        print(text.encode('ascii', errors='replace').decode('ascii'))

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

def retrieve_relevant_articles(file_paths: list[str], query: str, top_k: int = 10) -> list[str]:
    """
    Thuật toán xếp hạng tài liệu cục bộ dựa trên cơ chế TF-IDF rút gọn.
    Từ khóa xuất hiện ở ít tài liệu (như 'youtube') sẽ có trọng số cao hơn các từ khóa phổ biến (như 'how', 'add').
    """
    # Trích xuất các từ khóa dài từ 3 ký tự trở lên từ câu hỏi
    keywords = set(re.findall(r'\b\w{3,}\b', query.lower()))
    logger.info(f"Từ khóa tìm kiếm được trích xuất: {list(keywords)}")
    
    # 1. Tính Document Frequency (DF) cho từng từ khóa để đánh giá độ hiếm (đặc trưng)
    keyword_dfs = {}
    total_docs = len(file_paths)
    for kw in keywords:
        df = 0
        for path in file_paths:
            filename = os.path.basename(path).lower()
            if kw in filename:
                df += 1
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if kw in f.read().lower():
                        df += 1
            except Exception:
                pass
        keyword_dfs[kw] = df
        
    # 2. Xếp hạng chấm điểm từng bài viết theo trọng số nghịch đảo (IDF) của từ khóa
    scored_files = []
    for path in file_paths:
        filename = os.path.basename(path).lower()
        score = 0
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().lower()
        except Exception:
            content = ""
            
        for kw in keywords:
            df = keyword_dfs.get(kw, total_docs)
            
            # Tính trọng số nghịch đảo (IDF-like weight). Từ càng hiếm, weight càng cao.
            # Tránh chia cho 0 bằng cách dùng tối thiểu df = 1
            df = max(1, df)
            weight = 100.0 / df  # Ví dụ: youtube (df=2) -> weight=50; how (df=150) -> weight=0.66
            
            # Cộng điểm lớn nếu từ khóa xuất hiện trong tên file (tiêu đề bài viết)
            if kw in filename:
                score += weight * 100
                
            # Cộng điểm nếu từ khóa xuất hiện trong nội dung
            score += content.count(kw) * weight * 10
            
        if score > 0:
            scored_files.append((score, path))
            
    # Sắp xếp các bài viết theo điểm số giảm dần
    scored_files.sort(key=lambda x: x[0], reverse=True)
    
    # Lấy top_k bài viết tốt nhất
    selected_paths = [path for _, path in scored_files[:top_k]]
    
    # In ra danh sách file tìm thấy để debug
    logger.info("Danh sách 5 tài liệu hàng đầu tìm được:")
    for score, path in scored_files[:5]:
        logger.info(f"- Điểm: {score:.1f} | File: {os.path.basename(path)}")
        
    # Fallback: Nếu không tìm thấy bài nào trùng từ khóa, lấy mặc định top_k bài đầu tiên
    if not selected_paths:
        logger.warning("Không tìm thấy bài viết nào khớp từ khóa. Sử dụng fallback 10 bài đầu tiên.")
        selected_paths = file_paths[:top_k]
        
    return selected_paths

def main():
    # Nạp các biến môi trường
    load_dotenv()
    
    gemini_api_key = clean_env_var(os.getenv("GEMINI_API_KEY"))
    gemini_model = clean_env_var(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    store_name = clean_env_var(os.getenv("FILE_SEARCH_STORE_NAME"))
    
    if not gemini_api_key:
        logger.error("Thiếu biến môi trường GEMINI_API_KEY. Vui lòng kiểm tra lại file .env")
        return

    client = genai.Client(api_key=gemini_api_key)
    question = "How do I add a YouTube video?"
    
    # KỊCH BẢN 1: Sử dụng File Search Store trên đám mây (Cloud RAG)
    if store_name:
        logger.info(f"Khởi động RAG Chatbot bằng Gemini File Search Store: {store_name}")
        try:
            result = ask_optibot(client, store_name, question)
            
            safe_print("\n" + "=" * 50)
            safe_print("DELIVERABLE: SCREENSHOT TEST RUN (GEMINI CLOUD RAG)")
            safe_print("=" * 50)
            safe_print("\n[CÂU HỎI]:")
            safe_print(question)
            safe_print("\n[CÂU TRẢ LỜI CỦA GEMINI OPTIBOT]:")
            safe_print(result["answer"])
            
            if result["citations"]:
                safe_print("\n[NGUỒN TRÍCH DẪN (CITATIONS)]:")
                for url in result["citations"]:
                    safe_print(f"- {url}")
            safe_print("=" * 50 + "\n")
            
        except Exception as e:
            logger.error(f"Thất bại khi thực hiện Cloud RAG: {e}")
            
    # KỊCH BẢN 2: Sử dụng ngữ cảnh cục bộ (Local RAG Fallback)
    else:
        logger.info("Chưa cấu hình FILE_SEARCH_STORE_NAME. Chuyển sang chế độ Local RAG (Context Injection)...")
        all_file_paths = glob.glob(os.path.join(ARTICLES_DIR, "*.md"))
        if not all_file_paths:
            logger.error(f"Không tìm thấy tài liệu markdown nào tại {ARTICLES_DIR}.")
            return
            
        # Lọc bằng thuật toán TF-IDF cải tiến
        selected_file_paths = retrieve_relevant_articles(all_file_paths, question, top_k=10)
        
        context_parts = ["Dưới đây là các tài liệu trợ giúp chính thức làm cơ sở tri thức tham khảo:\n"]
        for path in selected_file_paths:
            parsed = parse_article_file(path)
            title = parsed["metadata"].get("title", "Không có tiêu đề")
            url = parsed["metadata"].get("article_url", "Không có URL")
            body = parsed["body"]
            
            doc_text = (
                f"Tài liệu: {title}\n"
                f"Article URL: {url}\n"
                f"Nội dung:\n{body}\n"
                f"----------------------------------------\n"
            )
            context_parts.append(doc_text)
            
        reference_context = "\n".join(context_parts)
        
        # System instructions đúng nguyên văn yêu cầu
        system_instruction = (
            "You are OptiBot, the customer-support bot for OptiSigns.com.\n\n"
            "• Tone: helpful, factual, concise.\n"
            "• Only answer using the uploaded docs.\n"
            "• Max 5 bullet points; else link to the doc.\n"
            "• Cite up to 3 \"Article URL:\" lines per reply."
        )
        
        prompt_contents = f"{reference_context}\nCâu hỏi từ người dùng: {question}"
        
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            
            safe_print("\n" + "=" * 50)
            safe_print("DELIVERABLE: SCREENSHOT TEST RUN (GEMINI LOCAL RAG)")
            safe_print("=" * 50)
            safe_print("\n[CÂU HỎI]:")
            safe_print(question)
            safe_print("\n[CÂU TRẢ LỜI CỦA GEMINI OPTIBOT]:")
            safe_print(response.text)
            safe_print("=" * 50 + "\n")
            
        except Exception as e:
            logger.error(f"Thất bại khi thực hiện Local RAG: {e}")

if __name__ == "__main__":
    main()
