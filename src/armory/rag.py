import chromadb
from typing import List, Dict, Any, Callable, Awaitable
import hashlib

from agents import RunContextWrapper

from ..armory.tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger


class MultiClassRAGDatabase:
    def __init__(self,
                 chroma_host: str,
                 chroma_port: int,
                 autocorrect: Callable[[list[str], str], Awaitable[str]],
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 enable_chunking: bool = True):

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._enable_chunking = enable_chunking
        self._autocorrect = autocorrect
        self._client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        self._collections = {}

    def _get_collection_name(self, channel_id: str) -> str:
        return f"channel_{channel_id}"

    def get_or_create_collection(self, channel_id: str):
        if channel_id not in self._collections:
            collection_name = self._get_collection_name(channel_id)
            self._collections[channel_id] = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"description": f"Documents for channel {channel_id}", "channel_id": channel_id}
            )
        return self._collections[channel_id]

    def _chunk_text(self, text: str) -> List[str]:
        if not self._enable_chunking:
            return [text]

        if len(text) <= self._chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self._chunk_size

            if end < len(text):
                sentence_break = text.rfind('.', start, end)
                if sentence_break > start + self._chunk_size - 100:
                    end = sentence_break + 1
                else:
                    word_break = text.rfind(' ', start, end)
                    if word_break > start:
                        end = word_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = max(start + 1, end - self._chunk_overlap)

        return chunks

    def add_document(self, channel_id: str, category: str, document_name: str, content: str) -> List[str]:
        collection = self.get_or_create_collection(channel_id)
        chunks = self._chunk_text(content)
        chunk_ids = []
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        for i, chunk in enumerate(chunks):
            chunk_id = f"{channel_id}_{category}_{document_name}_{content_hash}_chunk_{i}"
            metadata = {
                "channel_id": channel_id,
                "category": category,
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

        print(f"Added document to channel {channel_id}: {document_name} ({len(chunks)} chunks)")
        return chunk_ids

    @register_tool
    def get_categories(self, ctx: RunContextWrapper[DuckContext]) -> List[str]:

        """
        Get all document categories that a student can get information about for a specific channel

        Returns:
            List[str]: A sorted list of unique categories available in the channel.

        """

        channel_id = str(ctx.context.parent_channel_id)
        try:
            collection = self.get_or_create_collection(channel_id)
            all_data = collection.get()
            if not all_data['metadatas']:
                return []

            categories = list(set(meta.get('category', '') for meta in all_data['metadatas']))
            return sorted([c for c in categories if c])
        except Exception as e:
            print(f"Error getting categories for channel {channel_id}: {e}")
            return []

    @register_tool
    async def search_by_category(self,
                           ctx: RunContextWrapper[DuckContext],
                           category: str,
                           query: str,
                           n_results: int = 4) -> List[Dict[str, Any]]:
        """
        Search for relevant document chunks within a specific category in a channel.

        Args:
            category (str): The category to filter documents by (e.g., "Lectures", "Homework").
            query (str): The search query string provided by the user.
            n_results (int, optional): The maximum number of results to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: A list of results containing content, similarity scores, and metadata.
        """
        channel_id = str(ctx.context.parent_channel_id)
        duck_logger.debug("Using Tool: Searching in channel %s, category: %s with query: %s",
                          channel_id, category, query)

        try:
            collection = self.get_or_create_collection(channel_id)
            available_categories = self.get_categories(ctx)
            if category not in available_categories:
                category = await self._autocorrect(available_categories, category)

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"category": {"$eq": category}}
            )
            return self._format_results(results, channel_id)
        except Exception as e:
            duck_logger.error("Error searching category in channel %s: %s", channel_id, e)
            return []

    @register_tool
    def search_channel(self, ctx: RunContextWrapper[DuckContext], query: str, n_results: int = 4) -> List[Dict[str, Any]]:
        """
        Search for relevant document chunks across an entire channel's collection.

        Args:
            query (str): The search query string provided by the user.
            n_results (int, optional): The maximum number of results to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: A list of results containing content, similarity scores, and metadata.
        """
        channel_id = str(ctx.context.parent_channel_id)
        duck_logger.debug("Using Tool: Searching channel %s with query: %s", channel_id, query)

        try:
            collection = self.get_or_create_collection(channel_id)
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results, channel_id)
        except Exception as e:
            duck_logger.error("Error searching channel %s: %s", channel_id, e)
            return []

    def _format_results(self, results, channel_id: str) -> List[Dict[str, Any]]:
        if not results['documents'] or not results['documents'][0]:
            return []

        formatted_results = []
        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        distances = results['distances'][0] if results['distances'] else []

        for i, doc in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            metadata['channel_id'] = channel_id
            result = {
                "content": doc,
                "similarity_score": 1 - distances[i] if i < len(distances) else 1.0,
                "metadata": metadata
            }
            formatted_results.append(result)

        return formatted_results


    def delete_document(self, channel_id: str, category: str, document_name: str) -> bool:
        """Delete a specific document from a channel"""
        try:
            collection = self.get_or_create_collection(channel_id)
            results = collection.get(
                where={
                    "$and": [
                        {"category": {"$eq": category}},
                        {"document_name": {"$eq": document_name}}
                    ]
                }
            )
            if results['ids']:
                collection.delete(ids=results['ids'])
                print(f"Deleted document: channel {channel_id}/{category}/{document_name}")
                return True
            else:
                print(f"Document not found: channel {channel_id}/{category}/{document_name}")
                return False
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False

    def delete_channel(self, channel_id: str) -> bool:
        """Delete an entire channel's collection"""
        try:
            collection_name = self._get_collection_name(channel_id)
            self._client.delete_collection(name=collection_name)
            if channel_id in self._collections:
                del self._collections[channel_id]
            print(f"Deleted channel: {channel_id}")
            return True
        except Exception as e:
            print(f"Error deleting channel {channel_id}: {e}")
            return False
