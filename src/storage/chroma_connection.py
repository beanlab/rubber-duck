import chromadb

from src.utils.config_types import ChromaConfig


def create_chroma_client(
    chroma_ip: str = "localhost",
    chroma_port: int = 8000,
):
    return chromadb.HttpClient(
        host=chroma_ip,
        port=chroma_port,
    )

def create_chroma_session(config: ChromaConfig):
    return create_chroma_client(config['host'], int(config['port']))
