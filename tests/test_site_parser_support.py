from pathlib import Path
from types import SimpleNamespace

from musicpilot.adapters.indexers.config import load_parser_catalog
from musicpilot.infra.api.app import _supported_parser_or_422


class ReloadableParserState:
    def __init__(self, parser_path: Path) -> None:
        self.settings = SimpleNamespace(indexer_parser_config=parser_path)
        self.parser_catalog = load_parser_catalog(parser_path)

    def reload_parser_catalog(self) -> None:
        self.parser_catalog = load_parser_catalog(self.settings.indexer_parser_config)


def test_supported_parser_check_reloads_parser_file(tmp_path: Path) -> None:
    parser_path = tmp_path / "sites.parser.yaml"
    parser_path.write_text("sites: []\n", encoding="utf-8")
    state = ReloadableParserState(parser_path)

    parser_path.write_text(
        """
sites:
  - name: OpenCD
    base_url: https://open.cd
    parser:
      list_selector: "tr"
      fields:
        title:
          selector: "a[href*='details.php']"
        download:
          selector: "a[href*='download.php']"
          attribute: href
""",
        encoding="utf-8",
    )

    parser = _supported_parser_or_422(state, "https://open.cd")

    assert parser.list_selector == "tr"
