import json
import shutil
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from app.generation import generate_response
from app.models import Conversation, Message
from app.search import SearchResult


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
            self.assertTrue(job["image_url"].endswith((".svg", ".png")))
            self.assertTrue(job["filename"].startswith("imageforge/"))
            self.assertTrue(
                job["provider"].startswith("placeholder")
                or job["provider"].startswith("huggingface")
            )
            expected_path = TEST_MEDIA_ROOT / Path(job["filename"])
            self.assertTrue(expected_path.exists())
            self.assertIn("gpt-oss-20b", job["provider"])
            self.assertIn("caption", job)
            self.assertTrue(job["caption"])
            self.assertIn("director_prompt", job)


class SearchToolTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="scout", password="trail123")
        self.client.force_login(self.user)

    def test_tool_web_search_uses_external_results(self) -> None:
        with mock.patch(
            "app.views.perform_web_search",
            return_value=[
                SearchResult(
                    title="DuckDuckGo",
                    excerpt="Search engine",
                    url="https://duckduckgo.com",
                    source="DuckDuckGo",
                )
            ],
        ):
            response = self.client.post(
                reverse("tool_web_search"),
                data=json.dumps({"query": "duckduckgo"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"], "duckduckgo+gpt-oss-20b")
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["url"], "https://duckduckgo.com")

    def test_tool_web_search_includes_summary(self) -> None:
        with mock.patch("app.views.perform_web_search", return_value=[]) as patched_search:
            response = self.client.post(
                reverse("tool_web_search"),
                data=json.dumps({"query": "no results"}),
                content_type="application/json",
            )

        self.assertTrue(patched_search.called)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("gpt-oss-20b", payload["provider"])
