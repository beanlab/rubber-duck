import os
from urllib.request import urlopen, Request

def fetch_github_file(url: str) -> str:
    token = os.getenv("GH_TOKEN", None)
    # Convert "blob" URLs to raw
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    headers = {"User-Agent": "fetch-github-file", "Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with urlopen(Request(url, headers=headers), timeout=20) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")
