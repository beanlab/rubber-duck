import os
import chromadb

def main():
    try:
        # Connect to Chroma database using environment variables
        host = os.getenv("CHROMA_HOST")
        port = os.getenv("CHROMA_PORT")

        if not host:
            raise ValueError("CHROMA_HOST environment variable is not set")
        if not port:
            raise ValueError("CHROMA_PORT environment variable is not set")

        print(f"Connecting to Chroma database at {host}:{port}")
        client = chromadb.HttpClient(host=host, port=int(port))

        # List all collections (returns list of dicts with collection metadata)
        collections = client.list_collections()
        print(f"Found {len(collections)} collections")

        if not collections:
            print("No collections to delete.")
            return 0

        print("\nCollections found:")
        for i, collection_info in enumerate(collections, 1):
            collection_name = collection_info.name
            try:
                collection = client.get_collection(collection_name)
                count = collection.count()
                print(f"  {i}. {collection_name} ({count} documents)")

                if count > 0:
                    # get returns dict with keys: ids, metadatas, documents
                    result = collection.get(limit=5)
                    if result['ids']:
                        print(f"     Sample documents: {', '.join(result['ids'][:3])}")
                        if len(result['ids']) > 3:
                            print(f"     ... and {count - 3} more")
                else:
                    print(f"     (empty collection)")
            except Exception as e:
                print(f"  {i}. {collection_name} (error reading: {str(e)})")

        confirm = input(f"Are you sure you want to delete all {len(collections)} collections? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return 0

        # Delete each collection by name
        for collection_info in collections:
            collection_name = collection_info.name
            client.delete_collection(collection_name)
            print(f"Deleted collection: {collection_name}")

        print("All collections deleted successfully!")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
