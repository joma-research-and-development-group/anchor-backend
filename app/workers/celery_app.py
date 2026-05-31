from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "anchor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.workers.tasks.email.*": {"queue": "email"},
    },
)

celery_app.autodiscover_tasks(["app.workers.tasks"])
