from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class Attachment(BaseModel):
    id: int
    message_id: Optional[int]
    filename: str
    original_name: str
    mime_type: str
    created_at: datetime

    class Config:
        orm_mode = True


class Message(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    attachments: List['Attachment'] = []

    class Config:
        orm_mode = True


class Conversation(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: List['Message'] = []

    class Config:
        orm_mode = True


class MessageCreate(BaseModel):
    conversation_id: Optional[int]
    message: str
    attachment_ids: List[int] = []


class CompletionResponse(BaseModel):
    conversation: Conversation
    reply: Message


Attachment.update_forward_refs()
Message.update_forward_refs()
