from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import Settings, get_settings
from app.core.exceptions import NotConfiguredError, UpstreamError

PURPOSE_LABELS = {
    "verify_email": "verify your BidKaro email address",
    "login": "finish signing in to BidKaro",
}


class EmailService:
    """Gmail SMTP delivery for one-time codes.

    The app password is read from the environment only and is never logged,
    returned by an endpoint, or included in an email.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.smtp_username.strip() and self.settings.smtp_app_password.strip())

    def send_otp(self, *, to: str, code: str, purpose: str, expires_minutes: int) -> None:
        if not self.configured:
            raise NotConfiguredError(
                "Email sign-in is not configured. Set SMTP_USERNAME and SMTP_APP_PASSWORD "
                "on the server (use a Google App Password, not the Gmail password)."
            )

        action = PURPOSE_LABELS.get(purpose, "continue to BidKaro")
        message = EmailMessage()
        message["Subject"] = f"BidKaro verification code: {code}"
        message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_username}>"
        message["To"] = to
        message.set_content(
            "\n".join(
                [
                    f"Use this code to {action}:",
                    "",
                    code,
                    "",
                    f"The code expires in {expires_minutes} minutes. It can be used once.",
                    "If you did not request this, you can ignore this email.",
                    "",
                    "BidKaro",
                ]
            )
        )

        try:
            with smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=max(self.settings.smtp_timeout_seconds, 5),
            ) as smtp:
                smtp.login(self.settings.smtp_username, self.settings.smtp_app_password)
                smtp.send_message(message)
        except NotConfiguredError:
            raise
        except Exception as exc:
            raise UpstreamError(
                "We could not send the verification email. Check the SMTP settings and try again."
            ) from exc
