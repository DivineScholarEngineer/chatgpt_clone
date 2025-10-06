from __future__ import annotations

import json
import logging
import os
import secrets
from collections import Counter
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .emailing import send_admin_request_email, send_password_reset_email
from .generation import generate_response, remote_text
from .images import generate_images
from .models import (
    AdminRequest,
    Attachment,
    Conversation,
    Message,
    PasswordResetRequest,
)
from .search import perform_web_search

User = get_user_model()


logger = logging.getLogger(__name__)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        return value.isoformat()
    return (
        value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")
    )


def _serialize_attachment(attachment: Attachment) -> Dict[str, Any]:
    return {
        "id": attachment.id,
        "message_id": attachment.message_id,
        "filename": attachment.filename,
        "original_name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "created_at": _isoformat(attachment.created_at),
    }


def _serialize_message(message: Message) -> Dict[str, Any]:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "created_at": _isoformat(message.created_at),
        "attachments": [_serialize_attachment(a) for a in message.attachments.all()],
    }


def _serialize_conversation(conversation: Conversation, viewer: User | None) -> Dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": _isoformat(conversation.created_at),
        "archived": conversation.archived,
        "archived_at": _isoformat(conversation.archived_at),
        "private_until": _isoformat(conversation.private_until),
        "owner": conversation.owner.username if conversation.owner else None,
        "messages": [_serialize_message(m) for m in conversation.messages.all()],
        "can_manage": bool(
            viewer
            and (
                viewer.is_staff
                or (conversation.owner_id and conversation.owner_id == viewer.id)
            )
        ),
    }


def _serialize_user(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "date_joined": _isoformat(user.date_joined),
    }


def _user_can_access_conversation(user: User | None, conversation: Conversation) -> bool:
    if user is None:
        return False
    if user.is_staff:
        return True
    return conversation.owner_id == user.id


def _conversation_queryset(user: User | None) -> Iterable[Conversation]:
    qs = Conversation.objects.prefetch_related("messages__attachments", "messages")
    if user is None:
        return qs.none()
    if user.is_staff:
        return qs
    return qs.filter(owner=user)


def _predict_persona(messages: Iterable[Message]) -> Dict[str, Any]:
    """Generate lightweight insights about a user's interests."""
    text_blob = " ".join(message.content.lower() for message in messages if message.role == "user")
    words = [word for word in text_blob.split() if len(word) > 4]
    common = Counter(words).most_common(5)
    topics = [word for word, _ in common]
    tone = "thoughtful" if any(word in text_blob for word in ["think", "consider", "reflect"]) else "curious"
    return {
        "top_topics": topics,
        "tone": tone,
        "message_count": len(list(messages)),
    }


def _build_dashboard_snapshot(user: User) -> Dict[str, Any]:
    qs = _conversation_queryset(user)
    total = qs.count()
    archived = qs.filter(archived=True).count()
    recent = (
        qs.filter(archived=False)
        .order_by("-created_at")
        .values("id", "title", "created_at")[:5]
    )
    predictions = _predict_persona(Message.objects.filter(conversation__in=qs))
    return {
        "total_conversations": total,
        "archived_conversations": archived,
        "recent_conversations": [
            {
                "id": item["id"],
                "title": item["title"],
                "created_at": _isoformat(item["created_at"]),
            }
            for item in recent
        ],
        "persona": predictions,
    }


def _summarize_search_results(query: str, results: List[Any]) -> str:
    if not results:
        return "I couldn't reach live results just now. Try refining your search in a moment."

    bullet_points = []
    for index, item in enumerate(results[:5], start=1):
        title = getattr(item, "title", "Untitled result")
        excerpt = getattr(item, "excerpt", "")
        url = getattr(item, "url", "")
        bullet_points.append(f"{index}. {title} — {excerpt} ({url})")

    prompt = (
        "You are GPT-OSS-20B acting as the Web Pulse analyst. Summarise the "
        "most important insights for the user in two short paragraphs and "
        "close with an actionable tip. Use natural language, not bullet "
        "points. Base your answer only on these findings:\n"
        + "\n".join(bullet_points)
        + f"\n\nFocus on responding to this query: {query}."
    )

    completion = remote_text(prompt, max_new_tokens=260, temperature=0.35, top_p=0.9)
    if completion:
        return completion.strip()

    fallback_lines = [
        f"- {getattr(item, 'title', 'Result')} ({getattr(item, 'url', '')})"
        for item in results[:3]
    ]
    return "Here's what I found:\n" + "\n".join(fallback_lines)


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")


@require_GET
def session_info(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})
    return JsonResponse({
        "authenticated": True,
        "user": _serialize_user(request.user),
        "dashboard": _build_dashboard_snapshot(request.user),
    })


@csrf_exempt
@require_POST
def register(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return JsonResponse({"detail": "Username and password are required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse(
            {
                "detail": "Username already taken. Try signing in or use the password reset option if you need a new login.",
            },
            status=409,
        )

    if email and User.objects.filter(email__iexact=email).exists():
        return JsonResponse(
            {
                "detail": "Email already registered. Use the password reset flow if you can't remember the password.",
            },
            status=409,
        )

    user = User.objects.create_user(username=username, email=email, password=password)

    authenticated_user = authenticate(
        request, username=user.get_username(), password=password
    )
    if authenticated_user is None:
        backend_list = list(
            getattr(
                settings,
                "AUTHENTICATION_BACKENDS",
                ["django.contrib.auth.backends.ModelBackend"],
            )
        )
        preferred_backend = next(
            (
                backend
                for backend in backend_list
                if backend == "django.contrib.auth.backends.ModelBackend"
            ),
            backend_list[0],
        )
        auth_login(request, user, backend=preferred_backend)
        active_user = user
    else:
        auth_login(request, authenticated_user)
        active_user = authenticated_user

    return JsonResponse({"user": _serialize_user(active_user)})


@csrf_exempt
@require_POST
def login(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    identifier = (payload.get("username") or payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not identifier or not password:
        return JsonResponse({"detail": "Username and password are required"}, status=400)

    user = authenticate(request, username=identifier, password=password)

    if user is None and "@" in identifier:
        matched_user = User.objects.filter(email__iexact=identifier).first()
        if matched_user is not None:
            user = authenticate(
                request, username=matched_user.get_username(), password=password
            )

    if user is None:
        return JsonResponse(
            {
                "detail": "Invalid credentials. Reset your password if you've forgotten it.",
            },
            status=401,
        )

    auth_login(request, user)
    return JsonResponse({"user": _serialize_user(user)})


@csrf_exempt
@require_POST
def logout(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        auth_logout(request)
    return JsonResponse({"success": True})


@csrf_exempt
@require_POST
def password_forgot(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    identifier = (payload.get("identifier") or "").strip()
    if not identifier:
        return JsonResponse({"detail": "Provide a username or email"}, status=400)

    user = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()

    if user is not None:
        PasswordResetRequest.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        reset_request = PasswordResetRequest.create_for_user(user)
        result = send_password_reset_email(reset_request)
        if not result.sent:
            logger.warning("Failed to dispatch password reset email: %s", result.reason)

    return JsonResponse(
        {
            "detail": "If the account exists, a reset code has been emailed. Check your inbox for further instructions.",
        }
    )


@csrf_exempt
@require_POST
def password_reset(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or new_password

    if not token:
        return JsonResponse({"detail": "Reset code is required"}, status=400)

    if len(new_password) < 8:
        return JsonResponse(
            {"detail": "New password must be at least 8 characters"}, status=400
        )

    if new_password != confirm_password:
        return JsonResponse({"detail": "Passwords do not match"}, status=400)

    try:
        reset_request = PasswordResetRequest.objects.select_related("user").get(token=token)
    except PasswordResetRequest.DoesNotExist:
        return JsonResponse({"detail": "Invalid or expired reset code"}, status=404)

    if not reset_request.is_active:
        return JsonResponse({"detail": "Invalid or expired reset code"}, status=400)

    user = reset_request.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    reset_request.mark_used()
    PasswordResetRequest.objects.filter(user=user).exclude(pk=reset_request.pk).update(
        used_at=timezone.now()
    )

    return JsonResponse({"detail": "Password updated. You can sign in with the new password now."})


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def account_profile(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    if request.method == "GET":
        return JsonResponse({"user": _serialize_user(request.user)})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    user = request.user
    messages: List[str] = []

    if "username" in payload:
        new_username = (payload.get("username") or "").strip()
        if not new_username:
            return JsonResponse({"detail": "Username cannot be empty"}, status=400)
        if (
            new_username != user.username
            and User.objects.filter(username=new_username).exclude(pk=user.pk).exists()
        ):
            return JsonResponse({"detail": "Username already taken"}, status=409)
        if new_username != user.username:
            user.username = new_username
            messages.append("Username updated")

    if "email" in payload:
        new_email = (payload.get("email") or "").strip()
        if new_email and (
            User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists()
        ):
            return JsonResponse({"detail": "Email already registered"}, status=409)
        if new_email != user.email:
            user.email = new_email
            messages.append("Email updated")

    new_password = payload.get("new_password")
    if new_password:
        current_password = payload.get("current_password") or ""
        confirm_password = payload.get("confirm_password") or new_password

        if len(new_password) < 8:
            return JsonResponse(
                {"detail": "New password must be at least 8 characters"}, status=400
            )
        if not user.check_password(current_password):
            return JsonResponse({"detail": "Current password is incorrect"}, status=403)
        if new_password != confirm_password:
            return JsonResponse({"detail": "Passwords do not match"}, status=400)

        user.set_password(new_password)
        messages.append("Password updated")
        update_session_auth_hash(request, user)
    elif any(
        key in payload for key in ("current_password", "confirm_password")
    ):
        return JsonResponse(
            {"detail": "Provide a new_password to change your password"}, status=400
        )

    if messages:
        user.save()

    return JsonResponse({"user": _serialize_user(user), "detail": "; ".join(messages) or None})


@require_GET
def list_conversations(request: HttpRequest) -> JsonResponse:
    user = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"items": []})

    include_archived = request.GET.get("archived", "false").lower() == "true"
    scope = request.GET.get("scope", "mine")

    queryset = _conversation_queryset(user)
    if include_archived:
        queryset = queryset.filter(archived=True)
    else:
        queryset = queryset.filter(archived=False)

    if not user.is_staff or scope != "all":
        queryset = queryset.filter(Q(owner=user) | Q(owner__isnull=True))

    conversations = list(queryset.order_by("-created_at"))
    data = [_serialize_conversation(conversation, user) for conversation in conversations]
    return JsonResponse({"items": data, "archived": include_archived})


@require_GET
def get_conversation(request: HttpRequest, conversation_id: int) -> JsonResponse:
    user = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    conversation = (
        Conversation.objects.prefetch_related("messages__attachments")
        .filter(pk=conversation_id)
        .first()
    )
    if conversation is None:
        return JsonResponse({"detail": "Conversation not found"}, status=404)
    if not _user_can_access_conversation(user, conversation):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(_serialize_conversation(conversation, user))


@csrf_exempt
@require_http_methods(["PATCH"])
@transaction.atomic
def update_conversation(request: HttpRequest, conversation_id: int) -> JsonResponse:
    user = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not _user_can_access_conversation(user, conversation):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    updated_fields: List[str] = []

    if "title" in payload:
        new_title = (payload.get("title") or "New chat").strip() or "New chat"
        conversation.title = new_title[:200]
        updated_fields.append("title")

    if "archived" in payload:
        archived_value = bool(payload.get("archived"))
        conversation.archived = archived_value
        conversation.archived_at = timezone.now() if archived_value else None
        updated_fields.extend(["archived", "archived_at"])

    if "private_until" in payload:
        raw_value = payload.get("private_until")
        if raw_value:
            parsed = parse_datetime(str(raw_value))
            if parsed is None:
                return JsonResponse({"detail": "Invalid datetime format"}, status=400)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            conversation.private_until = parsed
        else:
            conversation.private_until = None
        updated_fields.append("private_until")

    if updated_fields:
        conversation.save(update_fields=updated_fields)

    conversation = Conversation.objects.prefetch_related("messages__attachments").get(pk=conversation.pk)
    return JsonResponse(_serialize_conversation(conversation, user))


@csrf_exempt
@require_http_methods(["DELETE"])
@transaction.atomic
def delete_conversation(request: HttpRequest, conversation_id: int) -> HttpResponse:
    user = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not _user_can_access_conversation(user, conversation):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    conversation.delete()
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@transaction.atomic
def message_detail(
    request: HttpRequest, conversation_id: int, message_id: int
) -> HttpResponse:
    user = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not _user_can_access_conversation(user, conversation):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    message = get_object_or_404(Message, pk=message_id, conversation=conversation)

    if request.method == "DELETE":
        if message.role == "assistant" and not user.is_staff:
            return JsonResponse({"detail": "Only admins can delete assistant replies"}, status=403)
        message.delete()
        return HttpResponse(status=204)

    if message.role != "user" and not user.is_staff:
        return JsonResponse({"detail": "Only user messages can be edited"}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    new_content = (payload.get("content") or "").strip()
    if not new_content:
        return JsonResponse({"detail": "Content cannot be empty"}, status=400)

    message.content = new_content
    message.save(update_fields=["content"])
    return JsonResponse(_serialize_message(message))


@csrf_exempt
@require_POST
@transaction.atomic
def create_completion(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    conversation_id = payload.get("conversation_id")
    message_text = (payload.get("message") or "").strip()
    attachment_ids = payload.get("attachment_ids") or []

    if not message_text and not attachment_ids:
        return JsonResponse({"detail": "Message content or attachments required"}, status=400)

    conversation: Conversation
    if conversation_id:
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not _user_can_access_conversation(request.user, conversation):
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if conversation.archived:
            conversation.archived = False
            conversation.archived_at = None
            conversation.save(update_fields=["archived", "archived_at"])
    else:
        title = (message_text or "New chat")[:80] or "New chat"
        conversation = Conversation.objects.create(owner=request.user, title=title)

    user_message = Message.objects.create(
        conversation=conversation,
        role="user",
        content=message_text,
    )

    if attachment_ids:
        attachments = Attachment.objects.filter(id__in=attachment_ids, message__isnull=True)
        attachments.update(message=user_message)

    history = list(
        conversation.messages.select_related("conversation").order_by("created_at", "id")
    )
    reply_content = generate_response(history)

    assistant_message = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=reply_content,
    )

    conversation = (
        Conversation.objects.prefetch_related("messages__attachments")
        .get(pk=conversation.pk)
    )

    response_data = {
        "conversation": _serialize_conversation(conversation, request.user),
        "reply": _serialize_message(assistant_message),
    }
    return JsonResponse(response_data)


@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"detail": "No file uploaded"}, status=400)

    conversation_id = request.POST.get("conversation_id")
    if conversation_id:
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if not _user_can_access_conversation(request.user, conversation):
            return JsonResponse({"detail": "Forbidden"}, status=403)

    safe_name = f"{Path(uploaded_file.name).stem}_{os.urandom(6).hex()}{Path(uploaded_file.name).suffix}"
    relative_path = Path("uploads") / safe_name
    absolute_path = Path(settings.BASE_DIR) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    with absolute_path.open("wb") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    attachment = Attachment.objects.create(
        filename=str(relative_path).replace("\\", "/"),
        original_name=uploaded_file.name,
        mime_type=uploaded_file.content_type or "application/octet-stream",
    )

    return JsonResponse(_serialize_attachment(attachment))


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_attachment(request: HttpRequest, attachment_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    attachment = get_object_or_404(Attachment, pk=attachment_id)
    if attachment.message and not _user_can_access_conversation(request.user, attachment.message.conversation):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    file_path = Path(settings.BASE_DIR) / attachment.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    attachment.delete()
    return HttpResponse(status=204)


@csrf_exempt
@require_POST
def request_admin(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    if request.user.is_staff:
        return JsonResponse({"detail": "You are already an admin"}, status=400)

    existing = request.user.admin_requests.filter(status=AdminRequest.STATUS_PENDING).first()
    if existing:
        return JsonResponse({"detail": "You already have a pending request"}, status=409)

    token = secrets.token_urlsafe(32)
    admin_request = AdminRequest.objects.create(user=request.user, token=token)
    email_result = send_admin_request_email(admin_request)
    detail = "Request submitted"
    if email_result.sent:
        detail += " · email delivered"
    elif email_result.reason:
        detail += f" · email pending: {email_result.reason}"
    return JsonResponse({"detail": detail, "token": token})


@require_GET
def approve_admin(request: HttpRequest, token: str) -> HttpResponse:
    admin_request = get_object_or_404(AdminRequest, token=token)
    decision = request.GET.get("decision", "approve").lower()

    if admin_request.status != AdminRequest.STATUS_PENDING:
        return HttpResponse("This request has already been processed.")

    if decision == "approve":
        admin_request.status = AdminRequest.STATUS_APPROVED
        admin_request.responded_at = timezone.now()
        admin_request.save(update_fields=["status", "responded_at"])
        user = admin_request.user
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        return HttpResponse("The account has been promoted to admin.")

    admin_request.status = AdminRequest.STATUS_REJECTED
    admin_request.responded_at = timezone.now()
    admin_request.save(update_fields=["status", "responded_at"])
    return HttpResponse("The admin request was rejected.")


@require_GET
def admin_overview(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    user_count = User.objects.count()
    conversation_count = Conversation.objects.count()
    message_count = Message.objects.count()
    attachment_count = Attachment.objects.count()
    pending_requests = AdminRequest.objects.filter(status=AdminRequest.STATUS_PENDING).count()

    top_users = (
        User.objects.annotate(conversation_total=Count("conversations"))
        .order_by("-conversation_total")
        .values("username", "conversation_total")[:5]
    )

    return JsonResponse(
        {
            "metrics": {
                "users": user_count,
                "conversations": conversation_count,
                "messages": message_count,
                "attachments": attachment_count,
                "pending_admin_requests": pending_requests,
            },
            "top_users": list(top_users),
        }
    )


@require_GET
def list_admin_requests(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    requests_qs = AdminRequest.objects.select_related("user")
    data = [
        {
            "id": item.id,
            "user": _serialize_user(item.user),
            "status": item.status,
            "token": item.token,
            "created_at": _isoformat(item.created_at),
            "responded_at": _isoformat(item.responded_at),
        }
        for item in requests_qs
    ]
    return JsonResponse({"items": data})


@csrf_exempt
@require_POST
def tool_web_search(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    query = (payload.get("query") or "").strip()
    if not query:
        return JsonResponse({"detail": "Search query required"}, status=400)

    results = perform_web_search(query)
    summary = _summarize_search_results(query, results)

    if not results:
        return JsonResponse(
            {
                "query": query,
                "results": [],
                "summary": summary,
                "provider": "duckduckgo+gpt-oss-20b",
                "detail": "No live results available right now",
            }
        )

    return JsonResponse(
        {
            "query": query,
            "results": [
                {
                    "title": item.title,
                    "excerpt": item.excerpt,
                    "url": item.url,
                    "source": item.source,
                }
                for item in results
            ],
            "summary": summary,
            "provider": "duckduckgo+gpt-oss-20b",
        }
    )


@csrf_exempt
@require_POST
def tool_generate_images(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

    prompt = (payload.get("prompt") or "").strip()
    count = int(payload.get("count") or 1)
    count = max(1, min(count, 8))

    if not prompt:
        return JsonResponse({"detail": "Prompt is required"}, status=400)

    generated = generate_images(prompt, count)
    jobs = []
    for item in generated:
        provider_label = f"{item.provider}+gpt-oss-20b"
        jobs.append(
            {
                "id": item.identifier,
                "prompt": item.prompt,
                "status": "completed",
                "image_url": item.url,
                "filename": item.relative_path,
                "palette": item.palette,
                "created_at": item.created_at.isoformat(),
                "mime_type": item.mime_type,
                "provider": provider_label,
                "caption": item.caption,
                "director_prompt": item.director_prompt,
            }
        )

    return JsonResponse({"prompt": prompt, "jobs": jobs})
