def is_s3(path: str) -> bool:
    return path.startswith('s3://')


def get_s3_desc(path: str) -> str:
    pass


def get_local_desc(path: str) -> str:
    pass


def get_s3_bytes(path: str) -> bytes:
    pass


def get_local_bytes(path: str) -> bytes:
    pass


def get_dataset_info(path: str) -> tuple[str, bytes]:
    d: str = get_s3_desc(path) if is_s3(path) else get_local_desc(path)
    b: bytes = get_s3_bytes(path) if is_s3(path) else get_local_bytes(path)
    return d, b
