import aiohttp
from io import BytesIO
from typing import Optional
from .protocols import Attachment

async def download_file(attachment: Attachment) -> Optional[BytesIO]:
    """
    Download a file from a Discord attachment URL.
    
    Args:
        attachment: The Attachment object containing the file URL
        
    Returns:
        BytesIO object containing the file content, or None if download failed
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment['url']) as response:
                if response.status == 200:
                    content = await response.read()
                    return BytesIO(content)
                return None
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

async def process_attachments(attachments: list[Attachment]) -> list[tuple[str, BytesIO]]:
    """
    Process a list of attachments and download their contents.
    
    Args:
        attachments: List of Attachment objects
        
    Returns:
        List of tuples containing (filename, BytesIO) for each successfully downloaded file
    """
    processed_files = []
    for attachment in attachments:
        file_content = await download_file(attachment)
        if file_content:
            processed_files.append((attachment['filename'], file_content))
    return processed_files 