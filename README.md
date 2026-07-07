# OptiBot RAG Chatbot & Scraper Pipeline

Hệ thống tự động cào dữ liệu (scraping) tài liệu hỗ trợ từ Zendesk Help Center, lưu trữ và đồng bộ hóa delta (chỉ đồng bộ thay đổi) lên Google Gemini File Search Store để phục vụ RAG Chatbot (OptiSigns support bot).

## Các liên kết theo dõi nhanh (Job Logs & Artifacts)
*   **[Thư mục chứa logs chạy hàng ngày (Job Logs)](https://github.com/nhatlank23/pipeline-chatbot-0707/tree/main/logs)**: Nơi lưu các file log `run_<timestamp>.log` được sinh ra tự động bởi GitHub Actions sau mỗi phiên chạy.
*   **[Trạng thái đồng bộ gần nhất (Last Run State)](https://github.com/nhatlank23/pipeline-chatbot-0707/blob/main/data/state.json)**: File lưu trữ trạng thái băm (hash), thời gian cập nhật và tên document trên Gemini để theo dõi delta.

---

## Tính năng chính
1. **Zendesk Scraper**: Tải toàn bộ bài viết hướng dẫn sử dụng, làm sạch mã HTML thừa và chuyển đổi sang Markdown chuẩn kèm Front-matter metadata.
2. **Delta Sync (Docker + GitHub Actions)**: Chạy container hóa hàng ngày (00:00 UTC) để so sánh mã băm MD5 phát hiện bài viết mới/cập nhật/đã xóa. Chỉ đẩy phần thay đổi lên Gemini và cập nhật trạng thái ngược về Git repository.
3. **Gemini RAG Engine**: Sử dụng thư viện `google-genai` chính thức, hỗ trợ cả Cloud RAG (Gemini File Search) và Local RAG (TF-IDF offline) với khả năng tìm kiếm ngữ cảnh chính xác cao.
4. **Interactive CLI Chat**: Giao diện chat trực tiếp với OptiBot thông qua dòng lệnh.

---

## Cấu hình môi trường (.env)
Tạo file `.env` tại thư mục gốc dựa theo mẫu:
```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
ZENDESK_BASE_URL=https://support.optisigns.com
FILE_SEARCH_STORE_NAME=fileSearchStores/your-store-id-here
```

---

## Hướng dẫn chạy cục bộ (Local)

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Chạy Pipeline đồng bộ dữ liệu (Dry Run trước)
```bash
# Chạy chế độ giả lập kiểm tra delta
python main.py --dry-run

# Chạy đồng bộ thực tế (yêu cầu GEMINI_API_KEY)
python main.py
```

### 3. Trò chuyện thử nghiệm với Chatbot (CLI)
```bash
python cli_chat.py
```
*(Nếu muốn chạy thử nghiệm chế độ Local RAG offline, hãy thêm dấu `#` vào đầu dòng `FILE_SEARCH_STORE_NAME` trong file `.env`)*

---

## Kiểm thử tự động (Unit Test)
Chạy bộ test kiểm thử scraper:
```bash
python -m pytest
```
