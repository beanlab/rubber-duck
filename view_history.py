import argparse
from pathlib import Path

from quest import LocalFileSystemBlobStorage, PersistentHistory


def print_history(history: PersistentHistory):
    for item in history:
        print('------', history._get_key(item), '------')
        print(item)


def main(save_folder: Path, historian_id: str):
    storage = LocalFileSystemBlobStorage(save_folder)
    history = PersistentHistory(historian_id, storage)

    print_history(history)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('save_folder', type=Path)
    parser.add_argument('id', type=str)
    args = parser.parse_args()

    main(args.save_folder, args.id)
