"""
Package scraper dùng để cào các bài viết và chuyển đổi sang định dạng Markdown.
"""
from .zendesk_scraper import run_scrape as run_scraper

__all__ = ["run_scraper"]
