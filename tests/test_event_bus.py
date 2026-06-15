from musicpilot.core.event_bus import EventBus
from musicpilot.core.events import SearchEvent


async def test_event_bus_round_trip() -> None:
    bus = EventBus()
    event = SearchEvent("radiohead")

    await bus.publish(event)

    assert bus.qsize() == 1
    assert await bus.next() == event
