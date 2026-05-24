from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "carbonverify",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.jobs", "app.tasks.report_jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-flagged-data-sources": {
            "task": "app.tasks.jobs.check_flagged_data_sources",
            "schedule": 300.0,  # every 5 minutes
        },
        "generate-overdue-reports": {
            "task": "app.tasks.jobs.generate_overdue_reports",
            "schedule": 3600.0,  # every hour
        },
        "poll-registry-statuses": {
            "task": "app.tasks.report_jobs.poll_registry_statuses",
            "schedule": 86400.0,  # daily
        },
        "send-registry-follow-ups": {
            "task": "app.tasks.report_jobs.send_registry_follow_ups",
            "schedule": 86400.0,  # daily
        },
    },
)
