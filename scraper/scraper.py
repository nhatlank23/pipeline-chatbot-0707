"""
Module for scraping articles from Zendesk (or other sources) and converting them to Markdown.
"""

def scrape_articles(base_url: str) -> list[dict]:
    """
    Scrapes articles from the source Zendesk base URL.
    
    Args:
        base_url: The API/Web base URL of the Zendesk help center.
        
    Returns:
        A list of dictionaries containing article data (id, title, content, html_url, etc.).
    """
    # TODO: Implement API/Web scraping logic using requests/beautifulsoup4
    return []

def convert_to_markdown(html_content: str) -> str:
    """
    Converts HTML content of an article into Markdown format.
    
    Args:
        html_content: The HTML string to convert.
        
    Returns:
        Markdown formatted string.
    """
    # TODO: Implement HTML to Markdown conversion (e.g., using markdownify or custom parser)
    return ""

def save_article_as_markdown(article_id: str, title: str, markdown_content: str, output_dir: str) -> str:
    """
    Saves the markdown content to a file in the data directory.
    
    Args:
        article_id: Unique identifier for the article.
        title: The title of the article (used for filename or metadata).
        markdown_content: The converted markdown text.
        output_dir: Target directory path to save the .md file.
        
    Returns:
        The absolute path to the saved file.
    """
    # TODO: Save to output_dir/article_id.md
    return ""

def run_scraper(base_url: str, output_dir: str) -> list[dict]:
    """
    Main entry point for the scraper module. Scrapes all articles, converts them to markdown,
    and saves them to the output directory.
    
    Args:
        base_url: Zendesk base URL.
        output_dir: Directory to store the Markdown files.
        
    Returns:
        List of processed article metadata (id, file_path, hash, etc.).
    """
    # TODO: Orchestrate scraping, conversion, and saving
    return []
