# Anchor Backend — Agent Rules

Scope: this directory only (`backend/`). The FastAPI API + workers for the Anchor platform.

## Stack
- Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · Alembic
- PostgreSQL 16 · Redis · Celery · MinIO (S3) · Fernet (encrypted FCM creds)
- Tests: pytest + httpx (async). Lint: Ruff + mypy.

## Run / verify
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # local Postgres/Redis or docker compose
alembic upgrade head                 # apply ALL migrations (0001..latest)
python -m app.db.seed                # demo org/project/user
uvicorn app.main:app --reload        # http://localhost:8000  (docs: /docs)
pytest -q                            # run tests before every change
```
Docker alternative: `docker compose up` (postgres, redis, minio, mailpit, api, worker, beat).

## Layout
```
app/
  main.py            # app factory; mounts /admin/* and /v1/* routers
  core/              # config, db, security, deps (RBAC), audit, sdk_auth, sdk_device, rate_limit
  models/            # SQLAlchemy models (GUID TypeDecorator for cross-db UUID)
  schemas/           # Pydantic v2 schemas
  api/admin/         # dashboard API (cookie/JWT auth, RBAC)
  api/v1/            # SDK API (X-Anchor-Key handshake -> session JWT)
  services/          # config_evaluator, crash_grouper, experiment_assigner, fcm_sender
  workers/           # celery_app + tasks (push_delivery, email)
alembic/versions/    # 0001_phase0 .. 0006_phase5
scripts/             # send_test_push.py, backup.sh, restore.sh
```

## Two APIs — do not confuse them
- `/admin/*` — dashboard. Auth via httpOnly cookie OR `Authorization: Bearer`. RBAC: owner>admin>editor>viewer. Audit-log every mutation via `write_audit`.
- `/v1/*` — SDK. `POST /v1/handshake` (X-Anchor-Key) issues a 1h session JWT; all other `/v1` calls use `Authorization: Bearer <session jwt>`.

## SDK contract rules (critical)
- The Flutter SDK is the source of truth. SDK `/v1` calls send **no `install_id`** — resolve the device with `get_or_create_session_device(db, session)` (see `app/core/sdk_device.py`). Never add a required `install_id` query/body to `/v1` endpoints.
- Handshake `session` object MUST include `jwt`, `token`, `expires_at`, `project_id`, `mode_id`, `version_id`, `platform` (the SDK's `AnchorSession.fromHandshakeResponse` reads these). Build it via `_build_session` in `handshake.py`.
- Match JSON response keys exactly to the SDK model `fromMap()` expectations.
- Error format: `{"detail": "message", "code": "ERROR_CODE"}`.

## Conventions
- SQLAlchemy 2.0 async + `mapped_column`. Schema changes ONLY via Alembic (enums use `op.execute("CREATE TYPE ...")` + `create_type=False`).
- Pin dependencies exactly (no `^`/`~`).
- All list endpoints: cursor-based pagination.
- JWT: access 15m, refresh 7d (httpOnly). Roles enforced via `require_role` dependency.

## Push (FCM)
- Real delivery: `app/services/fcm_sender.py` (FCM HTTP v1, OAuth2 via `google-auth`). Needs a Firebase **service-account JSON** at `FCM_SERVICE_ACCOUNT_FILE` — the app's `google-services.json` is client config only.
- Send test: `FCM_SERVICE_ACCOUNT_FILE=... python -m scripts.send_test_push "Title" "Body"`.
- Never commit service-account keys.

## Don't
- Don't hardcode secrets (use `.env` / env vars). Don't run destructive DB ops without confirmation. Don't break `/v1` SDK compatibility.
