"""
CLI Chatbot Interface cho OptiBot.
Cho phép tương tác trực tiếp với hỗ trợ viên ảo OptiSigns qua dòng lệnh (Terminal).
Tự động sử dụng Cloud RAG (nếu có FILE_SEARCH_STORE_NAME) hoặc Local RAG (TF-IDF fallback).
"""
import os
import sys
import glob
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Thêm thư mục gốc vào sys.path để chạy trực tiếp không bị lỗi import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uploader.quick_test import parse_article_file, retrieve_relevant_articles, safe_print
from uploader.file_search_uploader import ask_optibot, clean_env_var

# Định nghĩa các thư mục mặc định
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTICLES_DIR = os.path.join(DATA_DIR, "articles")

# Ẩn bớt log info của các thư viện khác để CLI gọn gàng
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cli_chat")

def local_rag_query(client, question: str, gemini_model: str) -> dict:
    """
    Xử lý câu hỏi bằng cơ chế RAG cục bộ (TF-IDF và Context Injection).
    """
    all_file_paths = glob.glob(os.path.join(ARTICLES_DIR, "*.md"))
    if not all_file_paths:
        return {
            "answer": "Lỗi: Không tìm thấy tài liệu markdown nào trong thư mục data/articles/. Vui lòng chạy scraper trước.",
            "citations": []
        }
        
    selected_file_paths = retrieve_relevant_articles(all_file_paths, question, top_k=8)
    
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
    
    system_instruction = (
        "You are OptiBot, the customer-support bot for OptiSigns.com.\n\n"
        "• Tone: helpful, factual, concise.\n"
        "• Only answer using the uploaded docs.\n"
        "• Max 5 bullet points; else link to the doc.\n"
        "• Cite up to 3 \"Article URL:\" lines per reply."
    )
    
    prompt_contents = f"{reference_context}\nCâu hỏi từ người dùng: {question}"
    
    response = client.models.generate_content(
        model=gemini_model,
        contents=prompt_contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    
    # Trích xuất link từ tài liệu được chọn để làm nguồn tham khảo hiển thị
    citations = []
    for path in selected_file_paths:
        parsed = parse_article_file(path)
        url = parsed["metadata"].get("article_url")
        if url and url not in citations:
            citations.append(url)
            if len(citations) >= 3: # Giới hạn hiển thị 3 nguồn trích dẫn
                break
                
    return {
        "answer": response.text,
        "citations": citations
    }

def main():
    load_dotenv()
    
    gemini_api_key = clean_env_var(os.getenv("GEMINI_API_KEY"))
    gemini_model = clean_env_var(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    store_name = clean_env_var(os.getenv("FILE_SEARCH_STORE_NAME"))
    
    if not gemini_api_key:
        safe_print("Lỗi: Thiếu GEMINI_API_KEY trong file .env. Vui lòng cấu hình trước khi chạy.")
        sys.exit(1)
        
    client = genai.Client(api_key=gemini_api_key)
    
    # In tiêu đề chào mừng
    safe_print("=" * 60)
    safe_print("            CHÀO MỪNG BẠN ĐẾN VỚI OPTIBOT CLI CHATBOT")
    safe_print("=" * 60)
    
    if store_name:
        safe_print(f"[*] Trạng thái: Đang kết nối chế độ Cloud RAG (Store: {store_name})")
    else:
        safe_print("[*] Trạng thái: Đang kết nối chế độ Local RAG (TF-IDF offline)")
        
    safe_print("[*] Nhập 'exit' hoặc 'quit' để kết thúc cuộc trò chuyện.\n")
    
    while True:
        try:
            # Nhập câu hỏi
            sys.stdout.write("Bạn: ")
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                safe_print("\nTạm biệt! Hẹn gặp lại bạn lần sau.")
                break
                
            # Đang xử lý
            sys.stdout.write("OptiBot đang trả lời...")
            sys.stdout.flush()
            
            # Xóa dòng "OptiBot đang trả lời..." trước khi in kết quả
            sys.stdout.write("\r" + " " * 30 + "\r")
            sys.stdout.flush()
            
            if store_name:
                # Chạy chế độ Cloud RAG
                result = ask_optibot(client, store_name, user_input)
            else:
                # Chạy chế độ Local RAG
                result = local_rag_query(client, user_input, gemini_model)
                
            # In câu trả lời
            safe_print("OptiBot:")
            safe_print(result["answer"])
            
            # In trích dẫn nguồn
            if result["citations"]:
                safe_print("\n[Nguồn tài liệu tham khảo]:")
                for url in result["citations"][:3]:
                    safe_print(f"- {url}")
            safe_print("-" * 60 + "\n")
            
        except KeyboardInterrupt:
            safe_print("\nTạm biệt! Hẹn gặp lại bạn lần sau.")
            break
        except Exception as e:
            safe_print(f"\n[Lỗi xảy ra]: {e}\n")

if __name__ == "__main__":
    main()
