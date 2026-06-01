"""Async email service with AWS SES primary and SMTP fallback."""

import asyncio
from typing import Optional

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    """Send transactional emails via SES or SMTP."""

    def __init__(self):
        self.provider = settings.EMAIL_PROVIDER.lower()
        self.from_email = settings.AWS_SES_FROM_EMAIL or settings.SMTP_FROM or "noreply@carbonverify.io"

    async def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        """Send an email to a single recipient."""
        if self.provider == "ses":
            await self._send_via_ses(to, subject, body_text, body_html)
        else:
            await self._send_via_smtp(to, subject, body_text, body_html)

    async def _send_via_ses(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:  # pragma: no cover
            logger.error("boto3_not_installed", provider="ses")
            raise RuntimeError("boto3 is required for SES email")

        client = boto3.client("ses", region_name=settings.AWS_REGION)
        destination = {"ToAddresses": [to]}
        message = {
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body_text}},
        }
        if body_html:
            message["Body"]["Html"] = {"Data": body_html}

        try:
            client.send_email(
                Source=self.from_email,
                Destination=destination,
                Message=message,
            )
            logger.info("email_sent_ses", to=to, subject=subject)
        except ClientError as e:
            logger.error("ses_send_failed", to=to, error=str(e))
            raise

    async def _send_via_smtp(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        def _send():
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(self.from_email, [to], msg.as_string())
            server.quit()

        try:
            await asyncio.to_thread(_send)
            logger.info("email_sent_smtp", to=to, subject=subject)
        except Exception as e:
            logger.error("smtp_send_failed", to=to, error=str(e))
            raise


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
