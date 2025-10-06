from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Conversation(models.Model):
    owner = models.ForeignKey(
        User,
        related_name="conversations",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    private_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Conversation #{self.pk}: {self.title}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=20)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.role} message #{self.pk}"


class Attachment(models.Model):
    message = models.ForeignKey(
        Message,
        related_name="attachments",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    filename = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.original_name


class AdminRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="admin_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Admin request for {self.user} ({self.status})"


class PasswordResetRequest(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_resets"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Password reset for {self.user} ({self.token[:6]}…)"

    @classmethod
    def create_for_user(cls, user: User) -> "PasswordResetRequest":
        """Create a fresh reset token with a short-lived expiry."""

        token = secrets.token_urlsafe(48).replace("-", "").replace("_", "")[:64]
        expires_at = timezone.now() + timedelta(hours=2)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_active(self) -> bool:
        return self.used_at is None and not self.is_expired

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
