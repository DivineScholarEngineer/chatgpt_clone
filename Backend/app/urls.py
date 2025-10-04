from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("conversations", views.list_conversations, name="list_conversations"),
    path("conversations/<int:conversation_id>", views.get_conversation, name="get_conversation"),
    path("chat", views.create_completion, name="create_completion"),
    path("upload", views.upload_file, name="upload_file"),
    path("attachments/<int:attachment_id>", views.delete_attachment, name="delete_attachment"),
]
