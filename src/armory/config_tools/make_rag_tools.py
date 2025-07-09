import hashlib
import io
from typing import Any

import PyPDF2
import aiohttp
import chromadb
import docx
from crawl4ai import CrawlerRunConfig, CacheMode, AsyncWebCrawler
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.armory.tools import register_tool
from src.utils.logger import duck_logger


class RAGManager:
    def __init__(self, tool_name: str, chroma_client: chromadb.HttpClient, collection_name: str,
                 chunk_size: int = 1000, chunk_overlap: int = 200,
                 enable_chunking: bool = False):

        self._tool_name = tool_name
        self._chroma_client = chroma_client
        self._collection_name = collection_name
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._enable_chunking = enable_chunking
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def _add_document_tool(self, document_name: str, content: str) -> dict[str, list[str]]:
        collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"description": "Shared documents collection"}
        )

        chunks = self._text_splitter.split_text(content) if self._enable_chunking else [content]
        chunk_ids = []
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_name}_{content_hash}_chunk_{i}"
            metadata = {
                "document_name": document_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "is_chunked": self._enable_chunking
            }

            collection.add(
                documents=[chunk],
                metadatas=[metadata],
                ids=[chunk_id]
            )

            chunk_ids.append(chunk_id)

        duck_logger.debug(f"Added document: {document_name} ({len(chunks)} chunks)")
        return {document_name: chunk_ids}

    def create_add_url_tool(self):
        async def add_url(url: str) -> dict[str, list[str]]:
            """
            Extracts text content from the provided URL if it is not a discord URL, and adds it to the RAG collection.
            Must be a valid URL that is not a Discord URL.

            Args:
                url (str): The URL from which to extract text content.

            Returns:
                str: The extracted text content.
            """
            content = ""
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
                content = result.markdown

            return self._add_document_tool(url, content)

        add_url.__name__ = self._tool_name + "_add_url"
        register_tool(add_url)
        return add_url

    def create_add_file_tool(self):
        async def add_file(url: str, file_type: str) -> dict[str, list[str]]:
            """
            Add a file to the RAG collection by fetching it from a Discord URL in the message history and extracting its text content.
            Must be a Discord File URL

            Args:
                url (str): The URL of the file to be added.
                file_type (str): The type of the file (e.g., "txt", "pdf", "docx").

            Returns:
                dict: A dictionary with the document name and list of chunk IDs.
            """
            content = ""
            file_type = file_type.lower()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise ValueError(f"Failed to fetch file. Status code: {response.status}")
                        file_bytes = await response.read()

                if file_type in ["txt", "md"]:
                    content = file_bytes.decode("utf-8")

                elif file_type == "pdf":
                    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    content = text.strip()

                elif file_type == "docx":
                    document = docx.Document(io.BytesIO(file_bytes))
                    content = "\n".join([para.text for para in document.paragraphs])

                return self._add_document_tool(url, content)

            except Exception as e:
                raise ValueError(f"Error reading file: {e}")

        add_file.__name__ = self._tool_name + "_add_file"
        register_tool(add_file)
        return add_file


    def create_add_text_tool(self):
        def add_text(document_name: str, content: str) -> dict[str, list[str]]:
            """
            Adds a set of text content from the user to the RAG collection.

            Args:
                document_name (str): The name of the document.
                content (str): The text content of the document.

            Returns:
                dict: A dictionary with the document name and list of chunk IDs.
            """
            return self._add_document_tool(document_name, content)

        add_text.__name__ = self._tool_name + "_add_text"
        register_tool(add_text)
        return add_text

    def _format_results(self, results) -> list[dict[str, Any]]:
        formatted_results = []

        if not results['documents'] or not results['documents'][0]:
            return formatted_results

        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)

        for i, doc in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            formatted_results.append({
                "text": doc.strip(),
                "document_name": metadata.get("source", f"doc_{i}"),
            })

        return formatted_results

    def create_search_documents_tool(self):
        def search_documents_tool(query: str, n_results: int = 4) -> list[dict[str, Any]]:
            """
            Search for relevant document chunks across the entire collection.

            Args:
                query (str): The search query string provided by the user.
                n_results (int, optional): The maximum number of results to return. Defaults to 4.

            Returns:
                List[Dict[str, Any]]: A list of results containing content, similarity scores, and metadata.
            """
            duck_logger.debug(f"Searching collection with query: {query}")

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )
                results = collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                duck_logger.debug(f"Search results: {results}")
                return self._format_results(results)
            except Exception as e:
                duck_logger.debug(f"Error searching collection: {e}")
                return []

        search_documents_tool.__name__ = self._tool_name + "_query"
        register_tool(search_documents_tool)
        return search_documents_tool

    def create_list_documents_tool(self):
        def list_documents_tool() -> str:
            """
            List all documents in the collection as a numbered list.

            Returns:
                str: A numbered list of all documents in the collection
            """
            duck_logger.debug("Listing all documents in collection")

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )

                # Get all documents in the collection
                results = collection.get()

                if not results['metadatas']:
                    return "No documents found in the collection."

                # Extract unique document names
                document_names = set()
                for metadata in results['metadatas']:
                    if metadata and 'document_name' in metadata:
                        document_names.add(metadata['document_name'])

                if not document_names:
                    return "No documents found in the collection."

                # Create numbered list
                document_list = []
                for i, doc_name in enumerate(sorted(document_names), 1):
                    document_list.append(f"{i}. {doc_name}")

                result = "Documents in collection:\n" + "\n".join(document_list)
                duck_logger.debug(f"Found {len(document_names)} documents")
                return result

            except Exception as e:
                error_msg = f"Error listing documents: {e}"
                duck_logger.debug(error_msg)
                return error_msg

        list_documents_tool.__name__ = self._tool_name + "_list"
        register_tool(list_documents_tool)
        return list_documents_tool

    def create_delete_document_tool(self):
        def delete_document_tool(document_name: str) -> str:
            """
            Delete a specific document and all its chunks from the collection.

            Args:
                document_name: The name of the document to delete

            Returns:
                str: Success or error message
            """
            duck_logger.debug("Deleting document: %s", document_name)

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )

                # Get all documents in the collection
                results = collection.get()

                if not results['metadatas'] or not results['ids']:
                    return f"No documents found in the collection."

                # Find all chunk IDs for the specified document
                chunk_ids_to_delete = []
                for i, metadata in enumerate(results['metadatas']):
                    if metadata and metadata.get('document_name') == document_name:
                        chunk_ids_to_delete.append(results['ids'][i])

                if not chunk_ids_to_delete:
                    return f"Document '{document_name}' not found in the collection."

                # Delete all chunks for this document
                collection.delete(ids=chunk_ids_to_delete)

                success_msg = f"Successfully deleted document '{document_name}' ({len(chunk_ids_to_delete)} chunks removed)"
                duck_logger.debug(success_msg)
                return success_msg

            except Exception as e:
                error_msg = f"Error deleting document '{document_name}': {e}"
                duck_logger.error(error_msg)
                return error_msg

        delete_document_tool.__name__ = self._tool_name + "_delete"
        register_tool(delete_document_tool)
        return delete_document_tool
