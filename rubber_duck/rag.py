import chromadb
from openai import AsyncOpenAI


class Rag:

    def __init__(self, openai_api_key: str, chroma_db_path: str, collection_name: str, document_path: str):
        self._client = AsyncOpenAI(api_key=openai_api_key)
        self._chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self._collection = self._chroma_client.get_or_create_collection(name=collection_name)
        self._document_path = document_path

    def _extract_text(self):
        """Extract text from a text file."""
        with open(self._document_path, "r") as file:
            text = file.read()
        return text

    async def _get_embeddings(self, text_chunks):
        """Generate embeddings for multiple text chunks in batch mode."""
        response = await self._client.embeddings.create(input=text_chunks, model="text-embedding-3-small")
        return [res.embedding for res in response.data]

    async def store_embeddings(self, chunk_size=120):
        """Extract text, split into chunks, and store embeddings in ChromaDB."""
        text = self._extract_text()
        words = text.split()
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), int(0.8 * chunk_size))]

        # Check for existing embeddings to avoid duplication
        existing_ids = set(self._collection.get()["ids"]) if self._collection.count() > 0 else set()
        new_chunks = [(f"chunk_{i}", chunk) for i, chunk in enumerate(chunks) if f"chunk_{i}" not in existing_ids]

        if not new_chunks:
            return

        chunk_ids, chunk_texts = zip(*new_chunks)
        embeddings = await self._get_embeddings(chunk_texts)

        # Store embeddings in ChromaDB
        self._collection.add(
            ids=list(chunk_ids),
            embeddings=embeddings,
            metadatas=[{"text": chunk} for chunk in chunk_texts]
        )

    async def search_relevant_docs(self, query, top_k=5):
        """Finds the most relevant document chunks from ChromaDB using similarity search."""
        query_embedding = (await self._get_embeddings([query]))[0]  # Get single query embedding
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        if results["ids"] and results["metadatas"]:
            matches = [results["metadatas"][0][i]["text"] for i in range(len(results["ids"][0]))]
            return ' '.join(matches)
        return None