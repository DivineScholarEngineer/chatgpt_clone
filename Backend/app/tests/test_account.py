import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models import Conversation, Message


User = get_user_model()


class AccountProfileTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="member", email="member@example.com", password="strongpass"
        )
        self.client.force_login(self.user)

    def test_get_profile_returns_authenticated_user(self) -> None:
        response = self.client.get(reverse("account_profile"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], "member")

    def test_update_profile_changes_username_and_email(self) -> None:
        response = self.client.patch(
            reverse("account_profile"),
            data=json.dumps({"username": "renamed", "email": "renamed@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")
        self.assertEqual(self.user.email, "renamed@example.com")

    def test_password_update_requires_current_password(self) -> None:
        response = self.client.patch(
            reverse("account_profile"),
            data=json.dumps({
                "new_password": "newsecret",
                "current_password": "wrong",
                "confirm_password": "newsecret",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("strongpass"))


class MessageManagementTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="owner", password="ownerpass")
        self.client.force_login(self.user)
        self.conversation = Conversation.objects.create(owner=self.user, title="Chat")
        self.message = Message.objects.create(
            conversation=self.conversation, role="user", content="Original"
        )

    def test_edit_message_updates_content(self) -> None:
        response = self.client.patch(
            reverse(
                "message_detail",
                kwargs={"conversation_id": self.conversation.id, "message_id": self.message.id},
            ),
            data=json.dumps({"content": "Updated message"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, "Updated message")

    def test_delete_assistant_message_requires_admin(self) -> None:
        assistant = Message.objects.create(
            conversation=self.conversation, role="assistant", content="Hello"
        )
        response = self.client.delete(
            reverse(
                "message_detail",
                kwargs={"conversation_id": self.conversation.id, "message_id": assistant.id},
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Message.objects.filter(pk=assistant.pk).exists())
