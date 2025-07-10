import io

import PyPDF2
import aiohttp
import docx
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from datetime import datetime

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
            exclude_internal_links=True,
            exclude_all_images=True,
            exclude_social_media_links=True
        )
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url, run_config=run_config)
            return result.markdown


    @register_tool
    async def extract_text_from_file(self, url: str, file_type: str) -> str:
        file_type = file_type.lower()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to fetch file. Status code: {response.status}")
                    file_bytes = await response.read()

            if file_type in ["txt", "md"]:
                return file_bytes.decode("utf-8")

            elif file_type == "pdf":
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text.strip()

            elif file_type == "docx":
                document = docx.Document(io.BytesIO(file_bytes))
                return "\n".join([para.text for para in document.paragraphs])

            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            raise ValueError(f"Error reading file: {e}")

        @register_tool
        def get_todays_date(self) -> str:
            """
            Returns today's date in YYYY-MM-DD format.

            Returns:
                str: Today's date.
            """
            return datetime.now().strftime("%Y-%m-%d")