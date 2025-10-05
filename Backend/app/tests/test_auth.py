from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


class AuthViewTests(TestCase):
    def test_register_creates_user_and_logs_in(self) -> None:
        payload = {"username": "alice", "email": "alice@example.com", "password": "secret123"}
        response = self.client.post(
            reverse("register"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("user", data)
        self.assertEqual(data["user"]["username"], "alice")
        self.assertTrue(User.objects.filter(username="alice").exists())

        created_user = User.objects.get(username="alice")
        self.assertNotEqual(created_user.password, payload["password"])
        self.assertTrue(created_user.check_password(payload["password"]))

        session_response = self.client.get(reverse("session_info"))
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.json().get("authenticated"))

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.RemoteUserBackend",
            "django.contrib.auth.backends.ModelBackend",
        ]
    )
    def test_register_handles_multiple_backends(self) -> None:
        payload = {
            "username": "dave",
            "email": "dave@example.com",
            "password": "multi-pass",
        }

        response = self.client.post(
            reverse("register"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "dave")

        session_response = self.client.get(reverse("session_info"))
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.json().get("authenticated"))

    def test_login_accepts_email_identifier(self) -> None:
        user = User.objects.create_user(
            username="bob", email="bob@example.com", password="password456"
        )

        payload = {"email": "bob@example.com", "password": "password456"}
        response = self.client.post(
            reverse("login"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], user.username)

    def test_login_invalid_credentials_returns_401(self) -> None:
        User.objects.create_user(username="carol", password="validpass")

        payload = {"username": "carol", "password": "wrongpass"}
        response = self.client.post(
            reverse("login"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid credentials")
