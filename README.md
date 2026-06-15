# MusicPilot

MusicPilot (MP) is a self-hosted automation hub for music discovery, download, metadata enrichment, library linking, and media-server refresh.

The project is designed around three constraints:

- **Async I/O first**: one Python process, pure async orchestration, low memory overhead, and high network/file-I/O concurrency.
- **Hexagonal architecture**: the core workflow depends on stable ports, while Telegram, Web UI, NexusPHP, qBittorrent, MusicBrainz, Navidrome, and future services live behind adapters.
- **Single artifact delivery**: the final deployment target is one Docker image containing the backend API and compiled Web UI.

`SPEC.md` is the source-of-truth architecture document for contributors and AI-assisted development. New modules should preserve its boundaries unless the spec is explicitly updated.

## Current Skeleton

```text
musicpilot/
  core/        domain events, event bus, pipeline orchestration
  ports/       adapter protocols
  adapters/    external service implementations
  infra/       config, database, API, app bootstrap
frontend/      Vue/Vite management UI scaffold
alembic/       database migration scaffold
tests/         focused core tests
```

## Implemented Modules

- Async event bus and core pipeline
- NexusPHP indexer loading from database sites and `config/sites.parser.yaml`
- qBittorrent download injection and completion webhook
- Download-completion media processor
- Audio file discovery and hardlink-based library import
- Metadata cascade with MusicBrainz provider
- Mutagen-based tag writer
- Navidrome/Subsonic library refresh notifier
- Optional Telegram bot search/notification adapter
- Subscription persistence and APScheduler lifecycle
- Management UI with login, streaming search, configuration cards, and connection tests
- FastAPI endpoints for health, search, downloads, media, indexers, subscriptions, and qBittorrent webhooks

## Development

Python 3.11+ is the target runtime.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn musicpilot.infra.api.app:create_app --factory --reload
```

Run tests:

```bash
pytest
```

With the included `Makefile`:

```bash
make install
make smoke
make dev
```

Verify the running backend:

```bash
curl --noproxy '*' http://127.0.0.1:8000/api/health
```

Run the frontend during development:

```bash
cd frontend
npm install
npm run dev
```

The temporary management login is:

```text
username: admin
password: musicpilot
```

These can later be overridden with `MP_ADMIN_USERNAME` and `MP_ADMIN_PASSWORD`.

## API Surface

- `GET /api/health`
- `POST /api/search`
- `POST /api/downloads`
- `POST /api/webhooks/qbittorrent/{torrent_hash}`
- `GET /api/indexers`
- `GET /api/media`
- `GET /api/subscriptions`
- `POST /api/subscriptions`

## Configuration

MusicPilot reads environment variables with the `MP_` prefix.

```bash
MP_DATABASE_URL=sqlite+aiosqlite:///./data/musicpilot.db
MP_LOG_LEVEL=INFO
MP_MUSIC_LIBRARY_PATH=/music
MP_DOWNLOAD_STAGING_PATH=/downloads
```

SQLite is the default database. The database layer enables WAL mode for SQLite and keeps model types portable for future PostgreSQL support.

## License

GPL-3.0. See `LICENSE`.
