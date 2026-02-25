"""Email notification service — sends job-complete emails to users.

Strategy (DEC-007):
    Primary channel is Google SMTP (smtp.gmail.com:587 with STARTTLS).
    The sender account is configured via SMTP_FROM_EMAIL + SMTP_APP_PASSWORD
    environment variables (a Gmail App Password — not the account password).

    If SMTP credentials are not configured, the service degrades gracefully:
    it logs the notification at WARNING level and returns without raising.
    This allows the backend to run without email configured (e.g. in dev).

Configuration (add to .env):
    SMTP_FROM_EMAIL=youraccount@gmail.com
    SMTP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # 16-char Gmail App Password

The user's Google email comes from the OAuth User model (user.email).
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)

# Module-level singleton
_email_service: "EmailService | None" = None


class EmailService:
    """Sends transactional emails via SMTP (Gmail STARTTLS).

    Falls back to a no-op log when SMTP credentials are absent so the
    backend boots cleanly in environments without email configured.
    """

    def __init__(
        self,
        from_email: str = "",
        app_password: str = "",
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        frontend_url: str = "http://localhost:3000",
    ) -> None:
        self._from_email = from_email
        self._app_password = app_password
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._frontend_url = frontend_url
        self._configured = bool(from_email and app_password)

        if not self._configured:
            logger.info(
                "Email service: SMTP credentials not configured — "
                "notifications will be logged only"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_job_completed(
        self,
        to_email: str,
        user_name: str,
        job_id: str,
        product_id: str,
        image_count: int,
    ) -> bool:
        """Send a job-completed notification email.

        Args:
            to_email: Recipient email address (from User.email).
            user_name: Recipient display name.
            job_id: Job UUID string for building the dashboard URL.
            product_id: Product identifier for the email subject.
            image_count: Number of images generated.

        Returns:
            True if the email was sent, False if not configured or on error.
        """
        subject = f"Your Etsy listing for {product_id} is ready"
        dashboard_url = f"{self._frontend_url}/dashboard?job={job_id}"

        html_body = _render_job_completed_html(
            user_name=user_name,
            product_id=product_id,
            image_count=image_count,
            dashboard_url=dashboard_url,
        )
        text_body = _render_job_completed_text(
            user_name=user_name,
            product_id=product_id,
            image_count=image_count,
            dashboard_url=dashboard_url,
        )

        return await self._send(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_job_failed(
        self,
        to_email: str,
        user_name: str,
        job_id: str,
        product_id: str,
        error_message: str,
    ) -> bool:
        """Send a job-failed notification email.

        Args:
            to_email: Recipient email address.
            user_name: Recipient display name.
            job_id: Job UUID string.
            product_id: Product identifier.
            error_message: Human-readable error summary.

        Returns:
            True if sent, False if not configured or on error.
        """
        subject = f"Generation failed for {product_id}"
        dashboard_url = f"{self._frontend_url}/dashboard?job={job_id}"

        html_body = _render_job_failed_html(
            user_name=user_name,
            product_id=product_id,
            error_message=error_message,
            dashboard_url=dashboard_url,
        )
        text_body = _render_job_failed_text(
            user_name=user_name,
            product_id=product_id,
            error_message=error_message,
            dashboard_url=dashboard_url,
        )

        return await self._send(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    # ------------------------------------------------------------------
    # Internal send helper
    # ------------------------------------------------------------------

    async def _send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """Build and send a MIME multipart email via aiosmtplib.

        Returns True on success, False on failure (never raises).
        """
        if not self._configured:
            logger.warning(
                "EMAIL (no SMTP configured) → %s | Subject: %s", to_email, subject
            )
            return False

        try:
            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from_email
            msg["To"] = to_email

            # Plain-text first, HTML second (preferred by clients)
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._from_email,
                password=self._app_password,
                start_tls=True,
            )

            logger.info("Email sent → %s | Subject: %s", to_email, subject)
            return True

        except Exception as exc:
            logger.error(
                "Failed to send email to %s: %s", to_email, exc, exc_info=True
            )
            return False


# ---------------------------------------------------------------------------
# Email template renderers
# ---------------------------------------------------------------------------


def _render_job_completed_html(
    user_name: str,
    product_id: str,
    image_count: int,
    dashboard_url: str,
) -> str:
    """Render the HTML body for a job-completed email."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: auto; padding: 24px;">
  <h2 style="color: #2d6a4f;">Your Etsy listing is ready! ✨</h2>
  <p>Hi {user_name},</p>
  <p>
    Great news — your AI-generated product photos and listing for
    <strong>{product_id}</strong> are ready.
    {image_count} image{'' if image_count == 1 else 's'} were generated successfully.
  </p>
  <p style="margin: 32px 0;">
    <a href="{dashboard_url}"
       style="background:#2d6a4f; color:white; padding:12px 24px;
              border-radius:6px; text-decoration:none; font-weight:bold;">
      View Results →
    </a>
  </p>
  <p style="color: #666; font-size: 0.9em;">
    You can also find all your jobs in the
    <a href="{dashboard_url.split('?')[0]}">Dashboard</a>.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="color:#999; font-size:0.8em;">Etsy Listing Agent</p>
</body>
</html>"""


def _render_job_completed_text(
    user_name: str,
    product_id: str,
    image_count: int,
    dashboard_url: str,
) -> str:
    """Render the plain-text body for a job-completed email."""
    images_phrase = f"{image_count} image{'s' if image_count != 1 else ''}"
    return (
        f"Hi {user_name},\n\n"
        f"Your AI-generated product photos and listing for {product_id} are ready!\n"
        f"{images_phrase} were generated successfully.\n\n"
        f"View your results: {dashboard_url}\n\n"
        "-- Etsy Listing Agent"
    )


def _render_job_failed_html(
    user_name: str,
    product_id: str,
    error_message: str,
    dashboard_url: str,
) -> str:
    """Render the HTML body for a job-failed email."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: auto; padding: 24px;">
  <h2 style="color: #c0392b;">Generation failed for {product_id}</h2>
  <p>Hi {user_name},</p>
  <p>
    Unfortunately the image generation for <strong>{product_id}</strong> encountered an error.
  </p>
  <p style="background:#fff3f3; border-left: 4px solid #c0392b;
            padding: 12px 16px; font-family: monospace; font-size: 0.9em;">
    {error_message[:500]}
  </p>
  <p>
    You can retry the generation from your
    <a href="{dashboard_url}">Dashboard</a>.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="color:#999; font-size:0.8em;">Etsy Listing Agent</p>
</body>
</html>"""


def _render_job_failed_text(
    user_name: str,
    product_id: str,
    error_message: str,
    dashboard_url: str,
) -> str:
    """Render the plain-text body for a job-failed email."""
    return (
        f"Hi {user_name},\n\n"
        f"Image generation for {product_id} failed.\n\n"
        f"Error: {error_message[:500]}\n\n"
        f"You can retry from your dashboard: {dashboard_url}\n\n"
        "-- Etsy Listing Agent"
    )


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_email_service() -> EmailService:
    """Return the module-level EmailService singleton.

    Reads SMTP configuration from the app settings on first call.
    """
    global _email_service
    if _email_service is None:
        from app.config import settings

        _email_service = EmailService(
            from_email=getattr(settings, "smtp_from_email", ""),
            app_password=getattr(settings, "smtp_app_password", ""),
            frontend_url=settings.frontend_url,
        )
    return _email_service
