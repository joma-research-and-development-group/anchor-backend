# Anchor Backend

Self-hosted mobile app management platform — push notifications, remote config, versioning, analytics, A/B testing, and more.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  Dashboard  │────▶│   FastAPI    │────▶│ Postgres │
│  (Next.js)  │     │   Backend    │     └──────────┘
└─────────────┘     │              │     ┌──────────┐
                    │  /admin/*    │────▶│  Redis   │
┌─────────────┐     │  /v1/*       │     └──────────┘
│ Flutter SDK │────▶│  /health     │     ┌──────────┐
└─────────────┘     └──────┬───────┘     │  MinIO   │
                           │             └──────────┘
                    ┌──────▼───────┐
                    │Celery Workers│
                    └──────────────┘
```

## Quickstart

```bash
# 1. Clone and enter
git clone https://github.com/your-org/anchor-backend.git
cd anchor-backend

# 2. Copy env
cp .env.example .env

# 3. Start everything
docker compose up -d

# 4. API is at http://localhost:8000
# 5. Health check: http://localhost:8000/health
```

## Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres redis minio
alembic upgrade head
uvicorn app.main:app --reload
```

## API Overview

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health (db, redis, uptime) |

### Auth & Admin (`/admin/*`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/auth/register` | Register user |
| POST | `/admin/auth/login` | Login (returns JWT) |
| POST | `/admin/auth/refresh` | Refresh access token |
| GET | `/admin/me` | Current user |

### Organizations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/orgs` | Create organization |
| GET | `/admin/orgs` | List organizations |
| GET | `/admin/orgs/{slug}` | Get organization |
| PATCH | `/admin/orgs/{slug}` | Update organization |

### Projects, Versions, Config

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/orgs/{slug}/projects` | Create project |
| GET | `/admin/orgs/{slug}/projects` | List projects |
| POST | `/admin/orgs/{slug}/projects/{id}/versions` | Create version |
| POST | `/admin/orgs/{slug}/projects/{id}/api-keys` | Create API key |
| GET/PUT | `/admin/orgs/{slug}/projects/{id}/config` | Remote config |

### Push & Devices

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/orgs/{slug}/projects/{id}/push-credentials` | Set FCM creds |
| POST | `/admin/orgs/{slug}/projects/{id}/push-campaigns` | Create campaign |
| GET | `/admin/orgs/{slug}/projects/{id}/devices` | List devices |

### Analytics & Experiments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/orgs/{slug}/projects/{id}/analytics/events` | Event analytics |
| GET | `/admin/orgs/{slug}/projects/{id}/crashes` | Crash groups |
| POST | `/admin/orgs/{slug}/projects/{id}/experiments` | Create experiment |

### SDK Endpoints (`/v1/*`)

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/v1/handshake` | 60/min/IP | SDK initialization |
| POST | `/v1/events` | 100/min/key | Event ingestion |
| POST | `/v1/devices/register` | — | Register device |
| GET | `/v1/config` | — | Get remote config |
| GET | `/v1/announcements` | — | Get announcements |
| GET | `/v1/banners` | — | Get banners |
| POST | `/v1/crashes` | — | Report crash |
| POST | `/v1/experiments/assign` | — | Get experiment assignment |

## Security

- JWT authentication (short-lived access + httpOnly refresh)
- Role-based access control (owner, admin, editor, viewer)
- Rate limiting via Redis sliding window
- Security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
- Request ID tracking (X-Request-ID)

## Backup & Restore

```bash
# Backup (uploads to S3/MinIO, retains 7 days)
./scripts/backup.sh

# Restore latest backup
./scripts/restore.sh
```

## Testing

```bash
pytest -q           # run all tests
ruff check .        # lint
mypy app            # type check
```

## License

MIT — see [LICENSE](LICENSE).
