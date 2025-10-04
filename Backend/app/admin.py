from django.contrib import admin

from .models import Attachment, Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at")
    search_fields = ("title",)
    ordering = ("-created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content",)
    ordering = ("created_at", "id")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "original_name", "mime_type", "created_at")
    search_fields = ("original_name", "mime_type")
    ordering = ("-created_at",)
