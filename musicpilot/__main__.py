from __future__ import annotations

import uvicorn

from musicpilot.infra.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "musicpilot.infra.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
