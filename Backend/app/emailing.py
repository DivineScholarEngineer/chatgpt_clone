from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage

from .models import AdminRequest, PasswordResetRequest


@dataclass
class EmailResult:
    sent: bool
    reason: str | None = None


def send_admin_request_email(admin_request: AdminRequest) -> EmailResult:
    """Send an email to the configured approver when a new admin request is created."""
    approver = getattr(settings, "ADMIN_APPROVER_EMAIL", None)
    if not approver:
        return EmailResult(False, "No approver email configured")

    approval_base = getattr(settings, "ADMIN_APPROVAL_BASE_URL", "")
    if approval_base:
        approval_link = f"{approval_base.rstrip('/')}/{admin_request.token}"
    else:
        approval_link = f"/admin/requests/approve/{admin_request.token}"

    subject = "New admin access request"
    body = (
        "A user has requested admin access to your GPT-OSS control center.\n\n"
        f"User: {admin_request.user.username}\n"
        f"Email: {admin_request.user.email or 'N/A'}\n"
        f"Approve: {approval_link}?decision=approve\n"
        f"Reject: {approval_link}?decision=reject\n"
    )

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", approver),
        to=[approver],
    )

    try:
        message.send(fail_silently=False)
        return EmailResult(True)
    except Exception as exc:  # pragma: no cover - depends on SMTP availability
        return EmailResult(False, str(exc))


def send_password_reset_email(reset_request: PasswordResetRequest) -> EmailResult:
    """Dispatch a password reset token to the account's email address."""

    user = reset_request.user
    if not user.email:
        return EmailResult(False, "User has no email address on file")

    subject = "Reset your DIV GPT Studio password"
    body = (
        "You requested a password reset for your DIV GPT Studio account.\n\n"
        f"Username: {user.username}\n"
        f"Reset code: {reset_request.token}\n\n"
        "Enter this code in the app to set a new password within the next two hours. "
        "If you did not make this request you can safely ignore this email."
    )

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER,
        to=[user.email],
    )

    try:
        message.send(fail_silently=False)
        return EmailResult(True)
    except Exception as exc:  # pragma: no cover - depends on SMTP availability
        return EmailResult(False, str(exc))
