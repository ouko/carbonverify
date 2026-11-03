from celery import Celery
from celery.signals import worker_process_shutdown, worker_shutdown

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "carbonverify",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.jobs", "app.tasks.report_jobs", "app.tasks.lead_jobs", "app.tasks.pre_audit_jobs", "app.tasks.compliance_jobs", "app.tasks.lifecycle_jobs", "app.tasks.escalation_jobs", "app.tasks.knowledge_jobs", "app.tasks.learning_jobs", "app.tasks.validation_jobs", "app.validation_engine.tasks"],
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
        "app.tasks.lifecycle_jobs.*": {"queue": "default"},
        "app.tasks.escalation_jobs.*": {"queue": "default"},
        # Phase 5: knowledge base + learning loop jobs
        "app.tasks.knowledge_jobs.*": {"queue": "default"},
        "app.tasks.learning_jobs.*": {"queue": "default"},
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
        "fetch-all-pending-documents": {
            "task": "app.tasks.pre_audit_jobs.fetch_all_pending_documents",
            "schedule": 86400.0,  # daily
        },
        "run-pre-audit-pipeline": {
            "task": "app.tasks.pre_audit_jobs.run_pre_audit_pipeline",
            "schedule": 86400.0,  # daily
        },
        "re-audit-changed-projects": {
            "task": "app.tasks.pre_audit_jobs.re_audit_changed_projects",
            "schedule": 86400.0,  # daily
        },
        "lifecycle-scan": {
            "task": "app.tasks.lifecycle_jobs.lifecycle_scan",
            "schedule": 300.0,  # every 5 minutes
        },
        "human-review-sla-sweep": {
            "task": "app.tasks.lifecycle_jobs.human_review_sla_sweep",
            "schedule": 3600.0,  # hourly
        },
        "dispatch-p0-escalations": {
            "task": "app.tasks.escalation_jobs.dispatch_p0_escalations",
            "schedule": 60.0,  # every minute
        },
        "send-p1-escalations": {
            "task": "app.tasks.escalation_jobs.send_p1_escalations",
            "schedule": 1800.0,  # every 30 minutes
        },
        "daily-escalation-digest": {
            "task": "app.tasks.escalation_jobs.daily_escalation_digest",
            "schedule": 86400.0,  # daily
        },
        # Shared remediation engine sweep (self-healing): re-run stale failures.
        "remediation-sweep": {
            "task": "app.tasks.lifecycle_jobs.remediation_sweep",
            "schedule": 900.0,  # every 15 minutes
        },
        # Phase 5: methodology knowledge base refresh check (stub-safe;
        # documents are ingested via API/admin upload only, never scraped).
        "check-methodology-updates": {
            "task": "app.tasks.knowledge_jobs.check_methodology_updates",
            "schedule": 86400.0,  # daily
        },
        # Phase 5: weekly agent retraining report (learning loop).
        "generate-weekly-learning-report": {
            "task": "app.tasks.learning_jobs.generate_weekly_learning_report",
            "schedule": 604800.0,  # weekly
        },
        # Phase 4: continuous synthetic validation + health snapshot (every 15 min).
        "run-synthetic-validation": {
            "task": "app.tasks.validation_jobs.run_synthetic_validation",
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
    from app.core.logging import get_logger
    from app.services.lead_intelligence.playwright_utils import close_persistent_browser

    logger = get_logger(__name__)
    logger.info("celery_worker_shutdown", signal=signal, sender=str(sender))
    close_persistent_browser()
