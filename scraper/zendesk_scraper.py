"""
Module hỗ trợ cào (scrape) các bài viết từ Zendesk Help Center API, chuyển đổi sang định dạng Markdown,
và lưu trữ kèm theo siêu dữ liệu (metadata front-matter).
"""
import os
import re
import time
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
import markdownify

logger = logging.getLogger("scraper")

def slugify(title: str) -> str:
    """
    Chuyển đổi chuỗi tiêu đề thành một slug thân thiện với URL (chữ thường).
    Thay thế khoảng trắng và dấu gạch dưới bằng dấu gạch ngang, loại bỏ các ký tự đặc biệt.
    """
    s = title.lower()
    # Thay thế khoảng trắng và dấu gạch dưới thành dấu gạch ngang
    s = re.sub(r'[\s_]+', '-', s)
    # Loại bỏ các ký tự không phải chữ cái, chữ số hoặc dấu gạch ngang
    s = re.sub(r'[^\w\-]', '', s)
    # Loại bỏ các dấu gạch ngang liên tiếp
    s = re.sub(r'-+', '-', s)
    # Cắt bỏ các dấu gạch ngang ở đầu và cuối chuỗi
    return s.strip('-')

def calculate_hash(content: str) -> str:
    """
    Tính toán mã hash MD5 của một chuỗi nội dung đầu vào.
    """
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def fetch_with_retry(url: str, max_retries: int = 3, backoff: float = 2.0) -> dict:
    """
    Tải dữ liệu từ URL với cơ chế thử lại (retry) và thời gian chờ (backoff) tăng dần/cố định.
    Sẽ raise RuntimeError nếu tất cả các lần thử đều thất bại.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Đang tải: {url} (Lần thử {attempt}/{max_retries})")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Lần thử {attempt} thất bại: HTTP status {response.status_code} cho URL {url}")
        except requests.RequestException as e:
            logger.warning(f"Lần thử {attempt} thất bại: Lỗi mạng {e} cho URL {url}")
        
        if attempt < max_retries:
            time.sleep(backoff)
            
    raise RuntimeError(f"Không thể tải URL {url} sau {max_retries} lần thử")

def fetch_all_articles(base_url: str) -> list[dict]:
    """
    Gọi Zendesk Help Center API để lấy tất cả bài viết.
    Tự động xử lý phân trang thông qua trường 'next_page'.
    
    Returns:
        Một danh sách các dict chứa các thông tin: id, title, html_body, html_url, updated_at, section_id.
    """
    url = f"{base_url.rstrip('/')}/api/v2/help_center/articles.json?page[size]=100"
    articles = []
    
    while url:
        data = fetch_with_retry(url)
        page_articles = data.get("articles", [])
        for art in page_articles:
            articles.append({
                "id": art.get("id"),
                "title": art.get("title", ""),
                "html_body": art.get("body") or "",
                "html_url": art.get("html_url", ""),
                "updated_at": art.get("updated_at", ""),
                "section_id": art.get("section_id")
            })
        url = data.get("next_page") or data.get("links", {}).get("next")
        
    return articles

def html_to_markdown(html: str) -> str:
    """
    Chuyển đổi nội dung HTML body sang Markdown sử dụng thư viện markdownify,
    sau khi đã dọn dẹp các thẻ không cần thiết bằng BeautifulSoup.
    """
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Loại bỏ các thẻ script, style, nav, và button
    for tag in soup(["script", "style", "nav", "button"]):
        tag.decompose()
        
    # Loại bỏ các thẻ có class chứa từ khóa "breadcrumb"
    for tag in soup.find_all(class_=True):
        classes = tag.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        if any("breadcrumb" in c for c in classes):
            tag.decompose()
            
    cleaned_html = str(soup)
    
    # Chuyển đổi HTML đã dọn dẹp sang Markdown, đảm bảo định dạng heading dạng ATX (# heading)
    md = markdownify.markdownify(cleaned_html, heading_style="ATX")
    return md.strip()

def save_article(article: dict, markdown_body: str, out_dir: str) -> str:
    """
    Lưu nội dung Markdown vào một file trong thư mục out_dir kèm theo front-matter.
    Tên file được tự động slug hóa từ tiêu đề bài viết.
    
    Returns:
        Đường dẫn tuyệt đối/tương đối của file đã lưu.
    """
    title = article.get("title", "")
    slug = slugify(title)
    if not slug:
        slug = f"article-{article.get('id')}"
        
    filename = f"{slug}.md"
    file_path = os.path.join(out_dir, filename)
    
    # Chuẩn bị metadata front-matter
    escaped_title = title.replace('"', '\\"')
    front_matter = (
        "---\n"
        f'title: "{escaped_title}"\n'
        f'article_url: "{article.get("html_url", "")}"\n'
        f'updated_at: "{article.get("updated_at", "")}"\n'
        f'zendesk_id: {article.get("id")}\n'
        "---\n\n"
    )
    
    os.makedirs(out_dir, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(front_matter + markdown_body)
        
    return file_path

def run_scrape(base_url: str, out_dir: str) -> list[dict]:
    """
    Thực hiện cào toàn bộ bài viết từ base_url, convert sang Markdown và lưu vào out_dir.
    Sẽ dừng chương trình và raise ValueError nếu tổng số bài viết cào được nhỏ hơn 30.
    
    Returns:
        Danh sách thông tin metadata của các bài viết để phục vụ so khớp delta ở bước sau:
        [{"id": 123, "slug": "title-slug", "file_path": "...", "updated_at": "...", "content_hash": "..."}]
    """
    logger.info(f"Bắt đầu cào dữ liệu từ URL: {base_url}")
    articles = fetch_all_articles(base_url)
    total_count = len(articles)
    logger.info(f"Tổng số bài viết lấy về được: {total_count}")
    
    if total_count < 30:
        error_msg = f"Kiểm tra tính hợp lệ thất bại: Lấy được {total_count} bài viết, nhưng yêu cầu tối thiểu là 30."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    metadata_list = []
    
    for art in articles:
        md_content = html_to_markdown(art["html_body"])
        file_path = save_article(art, md_content, out_dir)
        content_hash = calculate_hash(md_content)
        
        slug = slugify(art["title"])
        if not slug:
            slug = f"article-{art['id']}"
            
        metadata_list.append({
            "id": art["id"],
            "slug": slug,
            "file_path": file_path,
            "updated_at": art["updated_at"],
            "content_hash": content_hash
        })
        
    return metadata_list
