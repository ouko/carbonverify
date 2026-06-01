from celery import Celery
from celery.signals import worker_process_shutdown, worker_shutdown

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "carbonverify",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.jobs", "app.tasks.report_jobs", "app.tasks.lead_jobs", "app.tasks.compliance_jobs", "app.validation_engine.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_scheduler="app.tasks.beat_scheduler.LeaderElectionScheduler",
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Worker observability
    worker_send_task_events=True,
    worker_enable_remote_control=True,
    # Dead Letter Queue for failed tasks
    task_routes={
        "app.tasks.jobs.*": {"queue": "default"},
        "app.tasks.report_jobs.*": {"queue": "default"},
        "app.tasks.lead_jobs.*": {"queue": "default"},
        # Validation and compliance tasks route to dedicated queues with DLQ semantics
        "app.validation_engine.tasks.*": {"queue": "validation"},
        "app.tasks.compliance_jobs.*": {"queue": "compliance"},
    },
    task_default_exchange="default",
    task_default_queue="default",
    task_default_routing_key="default",
    # DLQ configuration: failed tasks after max retries are routed to dead-letter queues.
    # When using Redis as broker, declare companion queues (e.g., "validation.dlq",
    # "compliance.dlq") and route failed messages there via worker event hooks or
    # a custom Task class that overrides on_failure to re-publish to the DLQ.
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    # Beat schedule
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
        "scrape-registries": {
            "task": "app.tasks.lead_jobs.scrape_registries",
            "schedule": 86400.0,  # daily
        },
        "score-leads": {
            "task": "app.tasks.lead_jobs.score_leads",
            "schedule": 604800.0,  # weekly
        },
        "check-lead-deadlines": {
            "task": "app.tasks.lead_jobs.check_lead_deadlines",
            "schedule": 86400.0,  # daily
        },
        "cleanup-archived-validation-runs": {
            "task": "app.validation_engine.tasks.cleanup_archived_runs",
            "schedule": 86400.0,  # daily
        },
        "check-stalled-escalations": {
            "task": "app.validation_engine.tasks.check_stalled_escalations",
            "schedule": 900.0,  # every 15 minutes
        },
    },
)

# Dead Letter Queue configuration: failed tasks after max retries go to DLQ
celery_app.conf.task_queue_max_priority = 10
celery_app.conf.broker_transport_options = {
    "priority_steps": list(range(10)),
    "sep": ":",
    "queue_order_strategy": "priority",
}


@worker_process_shutdown.connect
@worker_shutdown.connect
def _on_worker_shutdown(signal=None, sender=None, **kwargs):
    """Graceful shutdown: close persistent Playwright browser and clean up resources."""
    from app.services.lead_intelligence.playwright_utils import close_persistent_browser
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("celery_worker_shutdown", signal=signal, sender=str(sender))
    close_persistent_browser()
