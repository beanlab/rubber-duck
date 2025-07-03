from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from ..armory.tools import register_tool
import re


class Extraction:

    @register_tool
    def get_urls_from_text(self, content: str) -> list[str]:
        """
        Extracts URLs from the provided text content.

        Args:
            content (str): The text content from which to extract URLs.

        Returns:
            list[str]: A list of extracted URLs.
        """
        url_pattern = r'(https?://[^\s]+)'
        urls = re.findall(url_pattern, content)
        return urls

    @register_tool
    async def extract_text_from_url(self, url: str) -> str:
        """
        Extracts text content from the provided URL.

        Args:
            url (str): The URL from which to extract text content.

        Returns:
            str: The extracted text content.
        """
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,
            check_robots_txt=True,
            word_count_threshold=10,
            only_text=True,
            wait_for="css:.dynamic-content",
            delay_before_return_html=1.0,
            exclude_external_links=True,
            exclude_social_media_links=True
        )
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url, run_config=run_config)
            return result.markdown
