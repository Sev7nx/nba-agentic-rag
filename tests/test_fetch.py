from app.tools.fetch import fetch_page, is_link_alive


def test_fetch_page_truncates(monkeypatch):
    monkeypatch.setattr("app.tools.fetch._extract", lambda url: "x" * 10000)
    assert (
        len(
            fetch_page(
                "https://example.com",
                max_chars=100,
                url_checker=lambda url: True,
            )
        )
        == 100
    )


def test_fetch_page_returns_empty_on_error(monkeypatch):
    def boom(url):
        raise RuntimeError("timeout")

    monkeypatch.setattr("app.tools.fetch._extract", boom)
    assert fetch_page("https://example.com", url_checker=lambda url: True) == ""


def test_is_link_alive_false_on_timeout(monkeypatch):
    import httpx

    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "head", boom)
    assert (
        is_link_alive("https://example.com", url_checker=lambda url: True)
        is False
    )


def test_fetch_page_rejects_private_urls(monkeypatch):
    monkeypatch.setattr("app.tools.fetch._extract", lambda url: "secret")
    assert fetch_page("http://127.0.0.1/secret") == ""
    assert fetch_page("http://169.254.169.254/latest/meta-data") == ""
    assert fetch_page("file:///etc/passwd") == ""


def test_is_link_alive_rejects_private(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 200

    monkeypatch.setattr(httpx, "head", lambda *args, **kwargs: FakeResponse())
    assert is_link_alive("http://127.0.0.1/") is False


def test_fetch_page_tool_returns_search_result(monkeypatch):
    from app.tools.fetch import fetch_page_tool

    monkeypatch.setattr(
        "app.tools.fetch.fetch_page",
        lambda url, max_chars=4000: "正文" * 200,
    )
    results = fetch_page_tool("https://example.com/a")
    assert len(results) == 1
    assert results[0].result_type == "doc"
    assert results[0].url == "https://example.com/a"
    assert len(results[0].snippet) <= 300


def test_fetch_page_tool_rejects_non_url():
    from app.tools.fetch import fetch_page_tool

    assert fetch_page_tool("库里最经典的比赛") == []