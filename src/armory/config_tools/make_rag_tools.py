import hashlib
from typing import Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb

from src.armory.tools import register_tool
from src.utils.logger import duck_logger




def _format_results(results) -> list[dict[str, Any]]:
    """Format ChromaDB results into a more readable format."""
    formatted_results = []

    if not results['documents'] or not results['documents'][0]:
        return formatted_results

    documents = results['documents'][0]
    metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)
    distances = results['distances'][0] if results['distances'] else [0.0] * len(documents)
    ids = results['ids'][0] if results['ids'] else [f"doc_{i}" for i in range(len(documents))]

    for i, doc in enumerate(documents):
        formatted_results.append({
            'content': doc,
            'metadata': metadatas[i] if i < len(metadatas) else {},
            'similarity_score': 1.0 - distances[i] if i < len(distances) else 0.0,  # Convert distance to similarity
            'id': ids[i] if i < len(ids) else f"doc_{i}"
        })

    return formatted_results


def make_add_document_tool(tool_name: str, chroma_client: chromadb.HttpClient, collection_name: str,
                           chunk_size: int = 1000, chunk_overlap: int = 200,
                           enable_chunking: bool = False):

    def add_document(document_name: str, content: str) -> list[str]:
        """
        Add any text, url, or file document to the collection, chunking it if necessary.
        Args:
            document_name (str): The name of the document being added.
            content (str): The content of the document to be added.
        Returns:
            List[str]: A list of chunk IDs for the added document.
        """
        collection = chroma_client.get_or_create_collection(name=collection_name, metadata={"description": "Shared documents collection"})
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.split_text(content) if enable_chunking else [content]
        chunk_ids = []
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_name}_{content_hash}_chunk_{i}"
            metadata = {
                "document_name": document_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "is_chunked": enable_chunking
            }

            collection.add(
                documents=[chunk],
                metadatas=[metadata],
                ids=[chunk_id]
            )

            chunk_ids.append(chunk_id)

        duck_logger.debug("Added document: %s (%s chunks)", document_name, len(chunks))
        return chunk_ids

    add_document.__name__ = tool_name
    register_tool(add_document)
    return add_document


def make_search_documents_tool(tool_name: str, chroma_client: chromadb.HttpClient, collection_name: str):

    def search_documents(query: str, n_results: int = 4) -> list[dict[str, Any]]:  # Fixed: removed self parameter
        """
        Search for relevant document chunks across the entire collection.

        Args:
            query (str): The search query string provided by the user.
            n_results (int, optional): The maximum number of results to return. Defaults to 4.

        Returns:
            List[Dict[str, Any]]: A list of results containing content, similarity scores, and metadata.
        """
        duck_logger.debug("Using Tool: Searching collection with query: %s", query)

        try:
            collection = chroma_client.get_or_create_collection(name=collection_name, metadata={"description": "Shared documents collection"})
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            duck_logger.error("Search results: %s", results)
            return _format_results(results)
        except Exception as e:
            duck_logger.error("Error searching collection: %s", e)
            return []

    search_documents.__name__ = tool_name
    register_tool(search_documents)
    return search_documents