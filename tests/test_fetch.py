from app.tools.fetch import fetch_page, is_link_alive


def test_fetch_page_truncates(monkeypatch):
    monkeypatch.setattr("app.tools.fetch._extract", lambda url: "x" * 10000)
    assert len(fetch_page("https://example.com", max_chars=100)) == 100


def test_fetch_page_returns_empty_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("timeout")

    monkeypatch.setattr("app.tools.fetch._extract", boom)
    assert fetch_page("https://example.com") == ""


def test_is_link_alive_false_on_timeout(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "head", boom)
    assert is_link_alive("https://example.com") is False