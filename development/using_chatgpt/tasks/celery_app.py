from celery import Celery

from core.config import settings

celery_app = Celery(
    "luck_game",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task
def send_email_job(to_address: str, subject: str, body: str) -> dict:
    return {"queued": True, "to": to_address, "subject": subject}


@celery_app.task
def generate_report_job(report_name: str) -> dict:
    return {"queued": True, "report": report_name}

