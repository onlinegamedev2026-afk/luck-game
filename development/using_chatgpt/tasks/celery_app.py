from celery import Celery
import smtplib
from email.message import EmailMessage

from core.config import settings

celery_app = Celery(
    "luck_game",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task
def send_email_job(to_address: str, subject: str, body: str) -> dict:
    if not to_address:
        return {"sent": False, "error": "Missing recipient email address."}
    if not settings.smtp_host:
        return {"sent": False, "error": "SMTP_HOST is not configured.", "to": to_address}
    message = EmailMessage()
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return {"sent": True, "to": to_address, "subject": subject}
    except Exception as exc:
        return {"sent": False, "error": str(exc), "to": to_address, "subject": subject}


@celery_app.task
def generate_report_job(report_name: str) -> dict:
    return {"queued": True, "report": report_name}
