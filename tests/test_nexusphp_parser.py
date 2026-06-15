from musicpilot.adapters.indexers.config import parser_config_from_mapping
from musicpilot.adapters.indexers.nexusphp import NexusPHPCrawler, NexusPHPSiteConfig

PARSER = parser_config_from_mapping(
    {
        "list_selector": (
            "table.torrents tr:has(a[href*='details.php']):has(a[href*='download.php'])"
        ),
        "fields": {
            "title": {
                "selector": "a[href*='details.php']",
                "filters": ["collapse_space"],
            },
            "subtitle": {
                "selector": (
                    "td:nth-of-type(2) .subtitle, "
                    "td:nth-of-type(2) .embedded, "
                    "td:nth-of-type(2) > span, "
                    "td:nth-of-type(2)"
                ),
                "attribute": "text",
                "filters": ["collapse_space"],
            },
            "details": {
                "selector": "a[href*='details.php']",
                "attribute": "href",
            },
            "download": {
                "selector": "a[href*='download.php']",
                "attribute": "href",
            },
            "size": {
                "selector": "td",
                "attribute": "text+attrs",
                "regex": r"(\d+(?:\.\d+)?\s*(?:[KMGT]i?B|[KMGT]B))",
            },
            "published_at": {
                "selector": "time, td, span, font",
                "attribute": "text+attrs",
                "filters": ["date"],
            },
            "promotion": {
                "selector": "img, font, span, td",
                "attribute": "text+attrs",
                "filters": ["promotion"],
            },
            "seeders": {"selector": ":scope > td:nth-last-of-type(4)"},
            "leechers": {"selector": ":scope > td:nth-last-of-type(3)"},
        },
    }
)


def test_nexusphp_parser_uses_direct_tail_columns_and_clean_subtitle() -> None:
    html = """
    <table class="torrents">
      <tr>
        <td class="cat">Music</td>
        <td>
          <table class="torrentname">
            <tr>
              <td>
                <img src="pic/trans.gif" alt="hot" title="hot" />
                <a href="details.php?id=1">Jay Chou - Jay 2001 - FLAC</a>
                <span class="subtitle">[ hot ] Jay Chou / album / CD / Lossless</span>
              </td>
            </tr>
          </table>
        </td>
        <td>266.67 MB</td>
        <td><time title="2026-06-12 10:30:00">06-12 10:30</time></td>
        <td>155</td>
        <td>21</td>
        <td>8</td>
        <td><a href="download.php?id=1">download</a></td>
      </tr>
      <tr>
        <td colspan="8">
          <a href="details.php?id=1">Jay Chou - Jay 2001 - FLAC</a>
          <a href="download.php?id=1">download</a>
        </td>
      </tr>
    </table>
    """
    crawler = NexusPHPCrawler(
        NexusPHPSiteConfig(name="OpenCD", base_url="https://open.cd/", parser=PARSER)
    )

    results = crawler._parse_results(html, 10)

    assert len(results) == 1
    assert results[0].title == "Jay Chou - Jay 2001 - FLAC"
    assert results[0].download_url == "https://open.cd/download.php?id=1"
    assert results[0].details_url == "https://open.cd/details.php?id=1"
    assert results[0].size_bytes == 279623761
    assert results[0].published_at == "2026-06-12 10:30:00"
    assert results[0].promotion == "热门"
    assert results[0].seeders == 155
    assert results[0].leechers == 21
    assert results[0].subtitle == "[ hot ] Jay Chou / album / CD / Lossless"
    assert "pic/trans.gif" not in (results[0].subtitle or "")
