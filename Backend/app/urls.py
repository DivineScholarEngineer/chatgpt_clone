from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("auth/session", views.session_info, name="session_info"),
    path("auth/register", views.register, name="register"),
    path("auth/login", views.login, name="login"),
    path("auth/logout", views.logout, name="logout"),
    path("auth/password/forgot", views.password_forgot, name="password_forgot"),
    path("auth/password/reset", views.password_reset, name="password_reset"),
    path("account/profile", views.account_profile, name="account_profile"),
    path("auth/become-admin", views.request_admin, name="request_admin"),
    path("conversations", views.list_conversations, name="list_conversations"),
    path("conversations/<int:conversation_id>", views.get_conversation, name="get_conversation"),
    path("conversations/<int:conversation_id>/update", views.update_conversation, name="update_conversation"),
    path("conversations/<int:conversation_id>/delete", views.delete_conversation, name="delete_conversation"),
    path(
        "conversations/<int:conversation_id>/messages/<int:message_id>",
        views.message_detail,
        name="message_detail",
    ),
    path("chat", views.create_completion, name="create_completion"),
    path("upload", views.upload_file, name="upload_file"),
    path("attachments/<int:attachment_id>", views.delete_attachment, name="delete_attachment"),
    path("admin/overview", views.admin_overview, name="admin_overview"),
    path("admin/requests", views.list_admin_requests, name="list_admin_requests"),
    path("admin/requests/approve/<str:token>", views.approve_admin, name="approve_admin"),
    path("tools/search", views.tool_web_search, name="tool_web_search"),
    path("tools/images", views.tool_generate_images, name="tool_generate_images"),
]
