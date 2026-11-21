import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import Tuple, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    """Returns True if either SMTP or Resend API is configured with real credentials."""
    if settings.RESEND_API_KEY and len(settings.RESEND_API_KEY.strip()) > 5:
        return True
    if settings.SMTP_HOST and len(settings.SMTP_HOST.strip()) > 3 and settings.SMTP_HOST not in ("localhost", "127.0.0.1"):
        if settings.SMTP_USER and len(settings.SMTP_USER.strip()) > 0:
            return True
    return False


def send_password_reset_email(to_email: str, full_name: str, token: str) -> Tuple[bool, Optional[str]]:
    """
    Sends a password reset link and token to the user.
    Returns (True, None) if sent, or (False, reason) if not sent / not configured.
    """
    subject = "Reset your Decidr password"
    frontend_origin = "https://decidr-pi.vercel.app" if settings.ENVIRONMENT == "production" else "http://localhost:3000"
    reset_url = f"{frontend_origin}/forgot-password?token={token}&email={to_email}"

    text_body = f"""Hello {full_name},

A password reset request was received for your Decidr account.

Click the following link to choose a new password:
{reset_url}

Your direct password reset token: {token}

This link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.

If you did not request a password reset, please ignore this email.

— The Decidr Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 40px 20px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px;">
    <h2 style="color: #38bdf8; margin-top: 0;">Reset your Decidr password</h2>
    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Hello {full_name},</p>
    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">A request was received to reset your password. Click the button below to choose a new password:</p>
    <div style="margin: 30px 0; text-align: center;">
      <a href="{reset_url}" style="background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">Reset Password</a>
    </div>
    <p style="color: #94a3b8; font-size: 13px;">Or enter your reset token directly: <code style="background-color: #0f172a; padding: 4px 8px; border-radius: 4px; color: #38bdf8;">{token}</code></p>
    <p style="color: #64748b; font-size: 12px; border-top: 1px solid #334155; padding-top: 16px; margin-top: 24px;">This link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours. If you did not request this reset, you can safely ignore this email.</p>
  </div>
</body>
</html>
"""

    return _dispatch_email(to_email, subject, text_body, html_body)


def _dispatch_email(to_email: str, subject: str, text_body: str, html_body: str) -> Tuple[bool, Optional[str]]:
    """Dispatches email via Resend or SMTP, or logs clear guidance if neither is configured."""
    # 1. Try Resend if configured
    if settings.RESEND_API_KEY and len(settings.RESEND_API_KEY.strip()) > 5:
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.SMTP_FROM,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                return True, None
            else:
                err_msg = f"Resend API error: {resp.status_code} - {resp.text}"
                logger.error(err_msg)
                return False, err_msg
        except Exception as e:
            err_msg = f"Failed to send via Resend: {str(e)}"
            logger.error(err_msg)
            return False, err_msg

    # 2. Try SMTP if configured
    if settings.SMTP_HOST and len(settings.SMTP_HOST.strip()) > 3:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email

            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
                server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
            return True, None
        except Exception as e:
            err_msg = f"Failed to send via SMTP: {str(e)}"
            logger.error(err_msg)
            return False, err_msg

    # 3. Not configured: log clearly and do NOT claim email was sent
    reason = (
        "Email delivery provider is not configured. "
        "Set SMTP_HOST or RESEND_API_KEY in .env to enable live email delivery."
    )
    logger.info(f"[EMAIL_SERVICE] {reason} (To: {to_email}, Subject: {subject})")
    return False, reason
