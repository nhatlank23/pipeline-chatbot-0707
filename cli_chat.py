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

# Ẩn log của các thư viện để terminal sạch sẽ
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

def local_rag_query(client, question: str, gemini_model: str) -> dict:
    """
    Xử lý câu hỏi bằng RAG cục bộ.
    """
    all_file_paths = glob.glob(os.path.join(ARTICLES_DIR, "*.md"))
    if not all_file_paths:
        return {
            "answer": "Không tìm thấy tài liệu hỗ trợ cục bộ. Hãy chạy đồng bộ dữ liệu trước.",
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
    
    citations = []
    for path in selected_file_paths:
        parsed = parse_article_file(path)
        url = parsed["metadata"].get("article_url")
        if url and url not in citations:
            citations.append(url)
            if len(citations) >= 3:
                break
                
    return {
        "answer": response.text,
        "citations": citations
    }

def run_chat_loop():
    """
    Khởi động vòng lặp chat tương tác trong console.
    """
    load_dotenv()
    
    gemini_api_key = clean_env_var(os.getenv("GEMINI_API_KEY"))
    gemini_model = clean_env_var(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    store_name = clean_env_var(os.getenv("FILE_SEARCH_STORE_NAME"))
    
    if not gemini_api_key:
        safe_print("Lỗi: Thiếu GEMINI_API_KEY trong file .env.")
        sys.exit(1)
        
    client = genai.Client(api_key=gemini_api_key)
    
    # Giao diện chào mừng tối giản và thẩm mỹ
    safe_print("\n" + "═" * 50)
    safe_print(" 🤖  OPTIBOT - HỖ TRỢ TRỰC TUYẾN OPTISIGNS.COM")
    safe_print("═" * 50)
    
    if store_name:
        safe_print(" [Trạng thái: Kết nối Cloud RAG Mode]")
    else:
        safe_print(" [Trạng thái: Kết nối Local RAG Mode (Offline)]")
    safe_print(" (Gõ 'exit' hoặc 'quit' để dừng trò chuyện)\n" + "─" * 50)
    
    while True:
        try:
            # Nhập tin nhắn từ người dùng
            sys.stdout.write("\n👤 Bạn: ")
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                safe_print("\n🤖 OptiBot: Cảm ơn bạn đã sử dụng dịch vụ. Tạm biệt!")
                safe_print("═" * 50 + "\n")
                break
                
            # Trạng thái đang xử lý động
            sys.stdout.write("🤖 OptiBot đang nhập câu trả lời...")
            sys.stdout.flush()
            
            # Gọi API lấy câu trả lời
            if store_name:
                result = ask_optibot(client, store_name, user_input)
            else:
                result = local_rag_query(client, user_input, gemini_model)
                
            # Xóa chữ "OptiBot đang nhập..."
            sys.stdout.write("\r" + " " * 40 + "\r")
            sys.stdout.flush()
            
            # In câu trả lời
            safe_print("🤖 OptiBot:")
            safe_print(result["answer"])
            
            # In nguồn trích dẫn
            if result["citations"]:
                safe_print("\n📄 [Tài liệu tham chiếu]:")
                for url in result["citations"][:3]:
                    safe_print(f"  • {url}")
            safe_print("─" * 50)
            
        except KeyboardInterrupt:
            safe_print("\n🤖 OptiBot: Hẹn gặp lại bạn lần sau!")
            safe_print("═" * 50 + "\n")
            break
        except Exception as e:
            # Xóa trạng thái đang nhập nếu lỗi
            sys.stdout.write("\r" + " " * 40 + "\r")
            sys.stdout.flush()
            safe_print(f"❌ [Lỗi]: {e}")

def main():
    run_chat_loop()

if __name__ == "__main__":
    main()
