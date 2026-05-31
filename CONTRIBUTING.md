# Contributing to Anchor Backend

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<you>/anchor-backend.git`
3. Create a feature branch: `git checkout -b feature/your-feature`
4. Install dependencies: `pip install -e ".[dev]"`
5. Start services: `docker compose up -d postgres redis minio`

## Development Workflow

1. Make your changes
2. Run linting: `ruff check . && mypy app`
3. Run tests: `pytest -q`
4. Commit with conventional commits: `feat(scope): description`
5. Push and open a Pull Request

## Pull Request Requirements

- All tests must pass
- No ruff or mypy errors
- New features require tests
- Update documentation if adding/changing API endpoints
- One logical change per PR

## Code Style

- Python 3.12+ with type annotations
- FastAPI + Pydantic v2 patterns
- SQLAlchemy 2.0 async with `mapped_column`
- Alembic for all schema changes

## Running Tests

```bash
pytest -q              # quick run
pytest --cov=app       # with coverage
```

## Reporting Issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version)
