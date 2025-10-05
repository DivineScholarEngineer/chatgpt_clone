import json
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from app.generation import generate_response
from app.models import Conversation, Message


User = get_user_model()

TEST_MEDIA_ROOT = Path(settings.BASE_DIR) / "test-media"


class GenerationFallbackTests(TestCase):
    def test_generate_response_returns_fallback_when_model_unavailable(self) -> None:
        conversation = Conversation.objects.create(title="Diagnostics")
        message = Message.objects.create(
            conversation=conversation, role="user", content="Hello there general Kenobi"
        )

        reply = generate_response([message])

        self.assertIn("Hello there", reply)
        self.assertIn("Model temporarily unavailable", reply)
        self.assertNotIn("An error occurred", reply)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ImageForgeViewTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="artist", password="brushes123")
        self.client.force_login(self.user)

    def tearDown(self) -> None:
        if TEST_MEDIA_ROOT.exists():
            shutil.rmtree(TEST_MEDIA_ROOT)

    def test_generate_images_creates_svg_assets(self) -> None:
        payload = {"prompt": "sunset over the valley", "count": 2}
        response = self.client.post(
            reverse("tool_generate_images"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["jobs"]), 2)

        for job in data["jobs"]:
            self.assertEqual(job["status"], "completed")
            self.assertTrue(job["image_url"].endswith(".svg"))
            self.assertTrue(job["filename"].startswith("imageforge/"))
            expected_path = TEST_MEDIA_ROOT / Path(job["filename"])
            self.assertTrue(expected_path.exists())
