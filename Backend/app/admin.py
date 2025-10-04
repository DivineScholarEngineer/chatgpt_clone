from django.contrib import admin

from .models import AdminRequest, Attachment, Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "archived", "created_at")
    list_filter = ("archived", "created_at")
    search_fields = ("title", "owner__username")
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


@admin.register(AdminRequest)
class AdminRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at", "responded_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-created_at",)
