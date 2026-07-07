# OptiBot: Zendesk to Gemini RAG Pipeline & Chatbot

Dự án triển khai một pipeline tự động cào bài viết (scraping) từ Zendesk Help Center sang Markdown, đồng bộ phần thay đổi (delta) lên Google Gemini File Search Store để phục vụ RAG Chatbot trả lời thông tin hỗ trợ kỹ thuật kèm liên kết trích dẫn nguồn. Hệ thống tự động kích hoạt chạy hàng ngày bằng GitHub Actions + Docker hoàn toàn miễn phí.

---

## 1. Cài đặt cục bộ (Setup)
1. **Clone mã nguồn & Tạo venv**:
   ```bash
   git clone <repo_url> && cd pipeline-chatbot-0707
   python -m venv venv
   # Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate
   ```
2. **Cài đặt thư viện**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Cấu hình môi trường**: Sao chép file `.env.sample` thành `.env` và điền:
   *   `GEMINI_API_KEY`: API Key lấy từ Google AI Studio.
   *   `ZENDESK_BASE_URL`: Đặt địa chỉ cổng hỗ trợ (ví dụ: `https://support.optisigns.com`).
   *   `FILE_SEARCH_STORE_NAME`: ID của Store trên Gemini (hệ thống tự tạo mới nếu để trống).

---

## 2. Cách chạy cục bộ (How to run locally)
*   **Chạy Scraper riêng lẻ**: `python test_run.py`
*   **Chạy Uploader riêng lẻ** (Đẩy toàn bộ file lên Store): `python uploader/file_search_uploader.py`
*   **Chạy Pipeline đồng bộ đầy đủ** (So khớp delta và cập nhật trạng thái):
    *   *Giả lập kiểm tra (Dry run)*: `python main.py --dry-run`
    *   *Đồng bộ thực tế*: `python main.py`
*   **Khởi động CLI Chatbot tương tác**: `python main.py --chat` hoặc `python main.py -c`

---

## 3. Cơ chế thiết kế & Tối ưu chi phí ($0 Cost)
*   **Gemini File Search Tool**: Sử dụng tính năng quản lý tài liệu tích hợp của Gemini (tự động chunking và tạo embedding). Giúp tối giản hóa hệ thống, loại bỏ sự phụ thuộc vào các Vector Database bên thứ ba.
*   **Lưu trữ State miễn phí**: File trạng thái `data/state.json` được tự động commit và đẩy ngược lại GitHub bởi Actions Bot sau mỗi phiên chạy. Nhờ đó, loại bỏ được chi phí lưu trữ Cloud (như S3/Spaces), giữ toàn bộ chi phí ở mức **$0**.

---

## 4. Tự động hóa qua GitHub Actions
*   **Chu kỳ**: Tự động chạy thông qua Docker Container lúc `00:00 UTC` hàng ngày.
*   **Xem lịch sử chạy (Job logs)**: [Xem trực tiếp tại tab Actions trên GitHub](https://github.com/nhatlank23/pipeline-chatbot-0707/actions) hoặc xem các file log trong thư mục [logs/](https://github.com/nhatlank23/pipeline-chatbot-0707/tree/main/logs).

---

## 5. Minh họa câu trả lời (Citations Screenshot)

[SCREENSHOT HERE]

---

## 6. Hạn chế & Cải tiến tương lai
*   **Hạn chế**: Tốc độ tải lên API miễn phí bị giới hạn băng thông nên lần chạy đầu tiên (nạp 405 tài liệu) sẽ tốn khoảng 10 - 15 phút.
*   **Cải tiến**: Tích hợp luồng upload song song (Concurrency) kết hợp kỹ thuật hàng đợi (Queue) để tối ưu hóa thời gian tải tài liệu.
