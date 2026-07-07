import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import requests

from scraper.zendesk_scraper import (
    slugify,
    calculate_hash,
    html_to_markdown,
    save_article,
    fetch_all_articles,
    run_scrape
)

def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("This_is_a_test-123!!!") == "this-is-a-test-123"
    assert slugify("   Multiple    Spaces   ") == "multiple-spaces"
    assert slugify("???") == ""

def test_calculate_hash():
    content = "Hello, world!"
    expected_hash = "6cd3556deb0da54bca060b4c39479839"  # MD5 của "Hello, world!"
    assert calculate_hash(content) == expected_hash

def test_html_to_markdown():
    html = """
    <nav>Navigation</nav>
    <div class="breadcrumb-container">Breadcrumbs here</div>
    <h1>Article Title</h1>
    <p>This is a paragraph with a <a href="/relative/path">relative link</a>.</p>
    <pre><code>print("hello")</code></pre>
    <script>console.log("bad script");</script>
    <style>body { color: red; }</style>
    <button>Click me</button>
    """
    md = html_to_markdown(html)
    
    # Kiểm tra loại bỏ các thẻ bị cấm
    assert "Navigation" not in md
    assert "Breadcrumbs" not in md
    assert "bad script" not in md
    assert "body {" not in md
    assert "Click me" not in md
    
    # Kiểm tra việc chuyển đổi định dạng
    assert "# Article Title" in md or "Article Title" in md
    assert "[relative link](/relative/path)" in md
    assert "```" in md
    assert 'print("hello")' in md

def test_save_article():
    with tempfile.TemporaryDirectory() as tmp_dir:
        article = {
            "id": 12345,
            "title": "My Awesome Article!",
            "html_url": "https://help.example.com/hc/articles/12345",
            "updated_at": "2026-07-07T12:00:00Z"
        }
        markdown_body = "This is the body content."
        
        file_path = save_article(article, markdown_body, tmp_dir)
        
        assert os.path.exists(file_path)
        assert os.path.basename(file_path) == "my-awesome-article.md"
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        assert 'title: "My Awesome Article!"' in content
        assert 'article_url: "https://help.example.com/hc/articles/12345"' in content
        assert 'updated_at: "2026-07-07T12:00:00Z"' in content
        assert 'zendesk_id: 12345' in content
        assert "This is the body content." in content

@patch("scraper.zendesk_scraper.requests.get")
def test_fetch_all_articles_success(mock_get):
    # Mô phỏng phân trang: gồm 2 trang giả lập
    # Trang 1
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {
        "articles": [
            {"id": i, "title": f"Art {i}", "body": f"<p>Body {i}</p>", "html_url": f"http://{i}", "updated_at": "2026", "section_id": 1}
            for i in range(1, 3)
        ],
        "next_page": "http://example.com/page2"
    }
    # Trang 2
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {
        "articles": [
            {"id": i, "title": f"Art {i}", "body": f"<p>Body {i}</p>", "html_url": f"http://{i}", "updated_at": "2026", "section_id": 1}
            for i in range(3, 5)
        ],
        "next_page": None
    }
    
    mock_get.side_effect = [mock_resp1, mock_resp2]
    
    articles = fetch_all_articles("http://example.com")
    assert len(articles) == 4
    assert articles[0]["id"] == 1
    assert articles[3]["id"] == 4

@patch("scraper.zendesk_scraper.requests.get")
def test_fetch_all_articles_retry_and_fail(mock_get):
    mock_get.side_effect = requests.RequestException("Connection error")
    
    # Thay thế time.sleep để tránh phải chờ đợi lâu khi chạy unit test
    with patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError, match="Không thể tải URL"):
            fetch_all_articles("http://example.com")
            
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

@patch("scraper.zendesk_scraper.fetch_all_articles")
def test_run_scrape_validation_error(mock_fetch):
    # Giả lập chỉ lấy về được 29 bài (ít hơn mức tối thiểu 30 bài yêu cầu)
    mock_fetch.return_value = [{"id": i, "title": f"Art {i}", "html_body": "", "html_url": "", "updated_at": "", "section_id": 1} for i in range(29)]
    
    with pytest.raises(ValueError, match="Kiểm tra tính hợp lệ thất bại"):
        run_scrape("http://example.com", "dummy_dir")

@patch("scraper.zendesk_scraper.fetch_all_articles")
def test_run_scrape_success(mock_fetch):
    # Giả lập lấy về được 35 bài viết (đáp ứng điều kiện tối thiểu 30 bài)
    mock_fetch.return_value = [
        {
            "id": i,
            "title": f"Article Number {i}",
            "html_body": f"<p>Content for article {i}</p>",
            "html_url": f"https://help.example.com/hc/articles/{i}",
            "updated_at": f"2026-07-07T12:00:{i:02d}Z",
            "section_id": 999
        }
        for i in range(1, 36)
    ]
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        meta_list = run_scrape("http://example.com", tmp_dir)
        
        assert len(meta_list) == 35
        assert len(os.listdir(tmp_dir)) == 35
        
        # Kiểm tra định dạng dữ liệu metadata trả về
        first_item = meta_list[0]
        assert "id" in first_item
        assert "slug" in first_item
        assert "file_path" in first_item
        assert "updated_at" in first_item
        assert "content_hash" in first_item
        
        assert first_item["id"] == 1
        assert first_item["slug"] == "article-number-1"
        assert os.path.exists(first_item["file_path"])
