import hashlib
import io
from typing import Any
from datetime import datetime, date

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

    def _is_date_in_range(self, date_str: str, start_date: str = None, end_date: str = None) -> bool:
        """
        Check if a date string is within the specified range.

        Args:
            date_str (str): ISO date string to check
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format

        Returns:
            bool: True if date is in range, False otherwise
        """
        if date_str == 'unknown':
            return False


        check_date = datetime.fromisoformat(date_str).date()

        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            if check_date < start:
                return False

        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            if check_date > end:
                return False

        return True


    def _add_document_tool(self, document_name: str, content: str, category: str = "other") -> dict[str, list[str]]:
        collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"description": "Shared documents collection"}
        )

        chunks = self._text_splitter.split_text(content) if self._enable_chunking else [content]
        chunk_ids = []
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        date_added = datetime.now().strftime("%Y-%m-%d")

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_name}_{content_hash}_chunk_{i}"
            metadata = {
                "document_name": document_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "is_chunked": self._enable_chunking,
                "date_added": date_added,
                "category": category.lower()
            }

            collection.add(
                documents=[chunk],
                metadatas=[metadata],
                ids=[chunk_id]
            )

            chunk_ids.append(chunk_id)

        duck_logger.debug(f"Added document: {document_name} ({len(chunks)} chunks) - Category: {category}")
        return {document_name: chunk_ids}

    def create_add_url_tool(self):
        async def add_url(url: str, category: str = "other") -> dict[str, list[str]]:
            """
            Extracts text content from the provided URL if it is not a discord URL, and adds it to the RAG collection.
            Must be a valid URL that is not a Discord URL.

            Args:
                url (str): The URL from which to extract text content.
                category (str, optional): The category for the document. Defaults to "other".

            Returns:
                dict: A dictionary with the document name and list of chunk IDs.
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

            return self._add_document_tool(url, content, category)

        add_url.__name__ = self._tool_name + "_add_url"
        register_tool(add_url)
        return add_url

    def create_add_file_tool(self):
        async def add_file(url: str, file_name: str, file_type: str, category: str = "other") -> dict[str, list[str]]:
            """
            Add a file to the RAG collection by fetching it from a Discord URL in the message history and extracting its text content.
            Must be a Discord File URL

            Args:
                url (str): The URL of the file to be added.
                file_name: str: The name of the file to be added.
                file_type (str): The type of the file (e.g., "txt", "pdf", "docx").
                category (str, optional): The category for the document. Defaults to "other".

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

                return self._add_document_tool(file_name, content, category)

            except Exception as e:
                raise ValueError(f"Error reading file: {e}")

        add_file.__name__ = self._tool_name + "_add_file"
        register_tool(add_file)
        return add_file

    def create_add_text_tool(self):
        def add_text(document_name: str, content: str, category: str = "other") -> dict[str, list[str]]:
            """
            Adds a set of text content from the user to the RAG collection.

            Args:
                document_name (str): The name of the document.
                content (str): The text content of the document.
                category (str, optional): The category for the document. Defaults to "other".

            Returns:
                dict: A dictionary with the document name and list of chunk IDs.
            """
            return self._add_document_tool(document_name, content, category)

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
                "category": metadata.get("category", "other"),
                "date_added": metadata.get("date_added", "unknown")
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
        def list_documents_tool(category: str = None, start_date: str = None, end_date: str = None) -> str:
            """
            List all documents in the collection as a numbered list, optionally filtered by category or date range.

            Args:
                category (str, optional): Filter documents by category. If None, all categories are included.
                start_date (str, optional): Filter documents from this date onwards (YYYY-MM-DD format).
                end_date (str, optional): Filter documents up to this date (YYYY-MM-DD format).

            Returns:
                str: A numbered list of all documents in the collection with their metadata
            """
            duck_logger.debug(f"Listing documents - Category: {category}, Start: {start_date}, End: {end_date}")

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )

                # Get all documents in the collection
                results = collection.get()

                if not results['metadatas']:
                    return "No documents found in the collection."

                # Extract unique documents with their metadata
                documents = {}
                for metadata in results['metadatas']:
                    if metadata and 'document_name' in metadata:
                        doc_name = metadata['document_name']
                        doc_category = metadata.get('category', 'other')
                        doc_date = metadata.get('date_added', 'unknown')

                        # Apply filters
                        if category and doc_category != category.lower():
                            continue
                        if (start_date or end_date) and not self._is_date_in_range(doc_date, start_date, end_date):
                            continue

                        documents[doc_name] = {
                            'category': doc_category,
                            'date_added': doc_date
                        }

                if not documents:
                    filter_msg = ""
                    if category:
                        filter_msg += f" in category '{category}'"
                    if start_date and end_date:
                        filter_msg += f" between '{start_date}' and '{end_date}'"
                    elif start_date:
                        filter_msg += f" from '{start_date}' onwards"
                    elif end_date:
                        filter_msg += f" up to '{end_date}'"
                    return f"No documents found{filter_msg}."

                # Create numbered list with metadata
                document_list = []
                for i, (doc_name, metadata) in enumerate(sorted(documents.items()), 1):
                    date_display = metadata['date_added'][:10] if metadata['date_added'] != 'unknown' else 'unknown'
                    document_list.append(f"{i}. {doc_name} (Category: {metadata['category']}, Date: {date_display})")

                result = "Documents in collection:\n" + "\n".join(document_list)
                duck_logger.debug(f"Found {len(documents)} documents")
                return result

            except Exception as e:
                error_msg = f"Error listing documents: {e}"
                duck_logger.debug(error_msg)
                return error_msg

        list_documents_tool.__name__ = self._tool_name + "_list"
        register_tool(list_documents_tool)
        return list_documents_tool

    def create_delete_document_tool(self):
        def delete_document_tool(document_name: str = None, category: str = None, start_date: str = None,
                                 end_date: str = None) -> str:
            """
            Delete documents from the collection. Can delete by specific name, category, or date range.

            Args:
                document_name (str, optional): The name of the specific document to delete
                category (str, optional): Delete all documents in this category
                start_date (str, optional): Delete documents from this date onwards (YYYY-MM-DD format)
                end_date (str, optional): Delete documents up to this date (YYYY-MM-DD format)

            Returns:
                str: Success or error message
            """
            if not any([document_name, category, start_date, end_date]):
                return "Must specify either document_name, category, or date range (start_date/end_date) to delete documents."

            duck_logger.debug(
                f"Deleting documents - Name: {document_name}, Category: {category}, Start: {start_date}, End: {end_date}")

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )

                # Get all documents in the collection
                results = collection.get()

                if not results['metadatas'] or not results['ids']:
                    return f"No documents found in the collection."

                # Find all chunk IDs to delete based on criteria
                chunk_ids_to_delete = []
                documents_to_delete = set()

                for i, metadata in enumerate(results['metadatas']):
                    if not metadata:
                        continue

                    should_delete = False

                    # Check specific document name
                    if document_name and metadata.get('document_name') == document_name:
                        should_delete = True

                    # Check category
                    if category and metadata.get('category') == category.lower():
                        should_delete = True

                    # Check date range
                    if (start_date or end_date) and self._is_date_in_range(metadata.get('date_added', ''), start_date,
                                                                           end_date):
                        should_delete = True

                    if should_delete:
                        chunk_ids_to_delete.append(results['ids'][i])
                        documents_to_delete.add(metadata.get('document_name'))

                if not chunk_ids_to_delete:
                    criteria = []
                    if document_name:
                        criteria.append(f"name '{document_name}'")
                    if category:
                        criteria.append(f"category '{category}'")
                    if start_date and end_date:
                        criteria.append(f"date range '{start_date}' to '{end_date}'")
                    elif start_date:
                        criteria.append(f"date from '{start_date}' onwards")
                    elif end_date:
                        criteria.append(f"date up to '{end_date}'")
                    return f"No documents found matching criteria: {', '.join(criteria)}."

                # Delete all matching chunks
                collection.delete(ids=chunk_ids_to_delete)

                success_msg = f"Successfully deleted {len(documents_to_delete)} documents ({len(chunk_ids_to_delete)} chunks removed)"
                if document_name:
                    success_msg = f"Successfully deleted document '{document_name}' ({len(chunk_ids_to_delete)} chunks removed)"
                elif category:
                    success_msg = f"Successfully deleted {len(documents_to_delete)} documents from category '{category}' ({len(chunk_ids_to_delete)} chunks removed)"
                elif start_date and end_date:
                    success_msg = f"Successfully deleted {len(documents_to_delete)} documents from date range '{start_date}' to '{end_date}' ({len(chunk_ids_to_delete)} chunks removed)"
                elif start_date:
                    success_msg = f"Successfully deleted {len(documents_to_delete)} documents from '{start_date}' onwards ({len(chunk_ids_to_delete)} chunks removed)"
                elif end_date:
                    success_msg = f"Successfully deleted {len(documents_to_delete)} documents up to '{end_date}' ({len(chunk_ids_to_delete)} chunks removed)"

                duck_logger.debug(success_msg)
                return success_msg

            except Exception as e:
                error_msg = f"Error deleting documents: {e}"
                duck_logger.error(error_msg)
                return error_msg

        delete_document_tool.__name__ = self._tool_name + "_delete"
        register_tool(delete_document_tool)
        return delete_document_tool

    def create_list_categories_tool(self):
        def list_categories_tool() -> str:
            """
            List all unique categories in the collection.

            Returns:
                str: A list of all categories with document counts
            """
            duck_logger.debug("Listing all categories in collection")

            try:
                collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"description": "Shared documents collection"}
                )

                # Get all documents in the collection
                results = collection.get()

                if not results['metadatas']:
                    return "No documents found in the collection."

                # Count documents by category
                category_counts = {}
                for metadata in results['metadatas']:
                    if metadata and 'category' in metadata:
                        category = metadata['category']
                        if category not in category_counts:
                            category_counts[category] = set()
                        category_counts[category].add(metadata.get('document_name'))

                if not category_counts:
                    return "No categories found in the collection."

                # Create category list with counts
                category_list = []
                for category, documents in sorted(category_counts.items()):
                    category_list.append(f"• {category}: {len(documents)} documents")

                result = "Categories in collection:\n" + "\n".join(category_list)
                duck_logger.debug(f"Found {len(category_counts)} categories")
                return result

            except Exception as e:
                error_msg = f"Error listing categories: {e}"
                duck_logger.debug(error_msg)
                return error_msg

        list_categories_tool.__name__ = self._tool_name + "_list_cat"
        register_tool(list_categories_tool)
        return list_categories_tool



    def get_all_tools(self):
        return [
            self.create_add_url_tool(),
            self.create_add_file_tool(),
            self.create_add_text_tool(),
            self.create_search_documents_tool(),
            self.create_list_documents_tool(),
            self.create_delete_document_tool(),
            self.create_list_categories_tool()
        ]