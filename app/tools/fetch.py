import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from app.tools.base import SearchResult


def _site_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _extract(url: str) -> str:
    response = httpx.get(url, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", response.text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(url: str, max_chars: int = 4000, url_checker=None) -> str:
    checker = url_checker or _is_safe_url
    if not checker(url):
        return ""
    try:
        return _extract(url)[:max_chars]
    except Exception:
        return ""


def is_link_alive(url: str, timeout: float = 3.0, url_checker=None) -> bool:
    checker = url_checker or _is_safe_url
    if not checker(url):
        return False
    try:
        response = httpx.head(url, timeout=timeout, follow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False


def fetch_page_tool(query: str) -> list[SearchResult]:
    url = query.strip()
    if not url.startswith(("http://", "https://")):
        return []
    text = fetch_page(url)
    if not text:
        return []
    return [
        SearchResult(
            title=url,
            url=url,
            site=_site_from_url(url),
            snippet=text[:300],
            result_type="doc",
        )
    ]