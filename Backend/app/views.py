from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .generation import generate_response
from .models import Attachment, Conversation, Message


def _isoformat(value: datetime) -> str:
    if timezone.is_naive(value):
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _serialize_conversation(conversation: Conversation) -> Dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": _isoformat(conversation.created_at),
        "messages": [_serialize_message(m) for m in conversation.messages.all()],
    }


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "index.html")


@require_GET
def list_conversations(request: HttpRequest) -> JsonResponse:
    conversations = (
        Conversation.objects.all()
        .prefetch_related("messages__attachments")
        .order_by("-created_at")
    )
    data = [_serialize_conversation(conversation) for conversation in conversations]
    return JsonResponse(data, safe=False)


@require_GET
def get_conversation(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = (
        Conversation.objects.prefetch_related("messages__attachments")
        .filter(pk=conversation_id)
        .first()
    )
    if conversation is None:
        return JsonResponse({"detail": "Conversation not found"}, status=404)
    return JsonResponse(_serialize_conversation(conversation))


@csrf_exempt
@require_POST
@transaction.atomic
def create_completion(request: HttpRequest) -> JsonResponse:
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
    else:
        title = (message_text or "New chat")[:80] or "New chat"
        conversation = Conversation.objects.create(title=title)

    user_message = Message.objects.create(
        conversation=conversation,
        role="user",
        content=message_text,
    )

    if attachment_ids:
        attachments = Attachment.objects.filter(id__in=attachment_ids)
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
        "conversation": _serialize_conversation(conversation),
        "reply": _serialize_message(assistant_message),
    }
    return JsonResponse(response_data)


@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request: HttpRequest) -> JsonResponse:
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"detail": "No file uploaded"}, status=400)

    conversation_id = request.POST.get("conversation_id")
    if conversation_id:
        get_object_or_404(Conversation, pk=conversation_id)

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
    attachment = get_object_or_404(Attachment, pk=attachment_id)
    file_path = Path(settings.BASE_DIR) / attachment.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    attachment.delete()
    return HttpResponse(status=204)
