import os
import chromadb


def main():
    """Wipe all collections from the Chroma database."""
    try:
        # Connect to Chroma database using environment variables
        host = os.getenv("CHROMA_DB_HOST_IP")
        port = os.getenv("CHROMA_DB_PORT")

        if not host:
            raise ValueError("CHROMA_DB_HOST_IP environment variable is not set")
        if not port:
            raise ValueError("CHROMA_DB_PORT environment variable is not set")

        print(f"Connecting to Chroma database at {host}:{port}")
        client = chromadb.HttpClient(host=host, port=int(port))

        # List and delete all collections
        collections = client.list_collections()
        print(f"Found {len(collections)} collections")

        if not collections:
            print("No collections to delete.")
            return

        print("\nCollections found:")
        for i, collection_name in enumerate(collections, 1):
            try:
                collection = client.get_collection(collection_name)
                count = collection.count()
                print(f"  {i}. {collection_name} ({count} documents)")

                # Show first few document IDs if they exist
                if count > 0:
                    result = collection.get(limit=5)  # Get first 5 documents
                    if result['ids']:
                        print(f"     Sample documents: {', '.join(result['ids'][:3])}")
                        if len(result['ids']) > 3:
                            print(f"     ... and {count - 3} more")
                else:
                    print(f"     (empty collection)")
            except Exception as e:
                print(f"  {i}. {collection_name} (error reading: {str(e)})")

        # Confirm deletion
        confirm = input(f"Are you sure you want to delete all {len(collections)} collections? (y/N): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return

        # Delete each collection
        for collection_name in collections:
            client.delete_collection(collection_name)
            print(f"Deleted collection: {collection_name}")

        print("All collections deleted successfully!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())