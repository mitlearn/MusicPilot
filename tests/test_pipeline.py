from musicpilot.core.event_bus import EventBus
from musicpilot.core.events import SearchEvent, SearchResult
from musicpilot.core.pipeline import MusicPipeline


class FakeIndexer:
    name = "fake"

    async def search(self, query: str, *, limit: int = 20) -> tuple[SearchResult, ...]:
        assert query == "bjork"
        return (
            SearchResult("Low seed", "https://example.test/a", self.name, seeders=1),
            SearchResult("High seed", "https://example.test/b", self.name, seeders=9),
            SearchResult("Duplicate", "https://example.test/a", self.name, seeders=3),
        )


async def test_pipeline_deduplicates_and_ranks_search_results() -> None:
    pipeline = MusicPipeline(event_bus=EventBus(), indexers=[FakeIndexer()])

    results = await pipeline.search(SearchEvent("bjork"))

    assert [result.title for result in results] == ["High seed", "Duplicate"]
