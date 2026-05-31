import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.email.send_invitation_email")
def send_invitation_email(email: str, token: str, org_name: str) -> dict[str, str]:
    subject = f"You've been invited to join {org_name} on Anchor"
    body = (
        f"You've been invited to join {org_name} on Anchor.\n\n"
        f"Accept your invitation using this token:\n{token}\n\n"
        f"This invitation expires in 7 days."
    )

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [email], msg.as_string())

    return {"status": "sent", "to": email}
