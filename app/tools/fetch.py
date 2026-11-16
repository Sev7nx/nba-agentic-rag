import re

import httpx


def _extract(url: str) -> str:
    response = httpx.get(url, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", response.text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(url: str, max_chars: int = 4000) -> str:
    try:
        return _extract(url)[:max_chars]
    except Exception:
        return ""


def is_link_alive(url: str, timeout: float = 3.0) -> bool:
    try:
        response = httpx.head(url, timeout=timeout, follow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False