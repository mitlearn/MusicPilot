import httpx

from musicpilot.adapters.downloaders.qbittorrent import QBittorrentAuthError, QBittorrentClient
from musicpilot.adapters.indexers.config import parser_config_from_mapping
from musicpilot.adapters.indexers.nexusphp import NexusPHPCrawler, NexusPHPSiteConfig

PARSER = parser_config_from_mapping(
    {
        "list_selector": "tr",
        "fields": {
            "title": {"selector": "a[href*='details.php']"},
            "download": {"selector": "a[href*='download.php']", "attribute": "href"},
        },
    }
)


async def test_qbittorrent_login_rejects_non_ok_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/auth/login"
        return httpx.Response(200, text="Fails.")

    client = httpx.AsyncClient(
        base_url="http://qbittorrent.local",
        transport=httpx.MockTransport(handler),
    )
    qbittorrent = QBittorrentClient(
        "http://qbittorrent.local",
        username="admin",
        password="wrong",
        client=client,
    )

    try:
        await qbittorrent.login()
    except QBittorrentAuthError:
        pass
    else:
        raise AssertionError("Expected invalid qBittorrent login to fail")
    finally:
        await client.aclose()


async def test_qbittorrent_test_connection_requires_authenticated_api() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/auth/login":
            return httpx.Response(200, text="Ok.")
        if request.url.path == "/api/v2/torrents/info":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="http://qbittorrent.local",
        transport=httpx.MockTransport(handler),
    )
    qbittorrent = QBittorrentClient(
        "http://qbittorrent.local",
        username="admin",
        password="secret",
        client=client,
    )

    await qbittorrent.test_connection()
    await client.aclose()


async def test_nexusphp_auth_test_rejects_login_page() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/torrents.php"
        return httpx.Response(
            200,
            html='<form action="takelogin.php"><input type="password" name="password"></form>',
        )

    client = httpx.AsyncClient(
        base_url="https://pt.local",
        transport=httpx.MockTransport(handler),
    )
    crawler = NexusPHPCrawler(
        NexusPHPSiteConfig(
            name="pt",
            base_url="https://pt.local/",
            parser=PARSER,
            cookie="uid=1; pass=bad",
        ),
        client=client,
    )

    result = await crawler.test_auth()

    assert result.ok is False
    assert "Cookie" in result.message
    await client.aclose()


async def test_nexusphp_auth_test_accepts_authenticated_marker() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/torrents.php"
        return httpx.Response(200, html='<a href="logout.php">logout</a>')

    client = httpx.AsyncClient(
        base_url="https://pt.local",
        transport=httpx.MockTransport(handler),
    )
    crawler = NexusPHPCrawler(
        NexusPHPSiteConfig(
            name="pt",
            base_url="https://pt.local/",
            parser=PARSER,
            cookie="uid=1; pass=good",
        ),
        client=client,
    )

    result = await crawler.test_auth()

    assert result.ok is True
    await client.aclose()
