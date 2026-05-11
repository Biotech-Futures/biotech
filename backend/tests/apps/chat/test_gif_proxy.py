from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

DUMMY_TENOR_RESPONSE = {
    "results": [
        {
            "id": "abc123",
            "media_formats": {
                "gif": {"url": "https://media.tenor.com/abc123/gif"},
                "tinygif": {"url": "https://media.tenor.com/abc123/tinygif"},
            },
        }
    ]
}

# Prevent any real Redis or cache calls during tests
@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    TENOR_API_KEY="test-key-hidden",
)
class GifProxyTests(TestCase):
    """
    Tests for the GIF proxy service:
      - GET /chat/gifs/search?q={query}&limit=20
      - GET /chat/gifs/trending?limit=20
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="gif_user@test.com", password="pw")
        self.client.force_authenticate(user=self.user)

    @patch("apps.chat.services.gif.requests.get")
    def test_gif_search_proxy_schema(self, mock_get):
        """Mock external Tenor HTTP call; assert response maps to internal DTO contract."""
        mock_response = MagicMock()
        mock_response.json.return_value = DUMMY_TENOR_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get("/chat/gifs/search/", {"q": "cats", "limit": 1})

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        item = data["data"][0]
        # Assert DTO contract shape
        self.assertIn("id", item)
        self.assertIn("url", item)
        self.assertIn("preview", item)
        # Assert correct values mapped from Tenor response
        self.assertEqual(item["id"], "abc123")
        self.assertEqual(item["url"], "https://media.tenor.com/abc123/gif")
        self.assertEqual(item["preview"], "https://media.tenor.com/abc123/tinygif")

    @patch("apps.chat.services.gif.requests.get")
    def test_gif_api_key_omitted(self, mock_get):
        """Assert Tenor API key is never present in any serialized response field."""
        mock_response = MagicMock()
        mock_response.json.return_value = DUMMY_TENOR_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Check both endpoints
        search_response = self.client.get("/chat/gifs/search/", {"q": "dogs"})
        trending_response = self.client.get("/chat/gifs/trending/")

        for response in [search_response, trending_response]:
            raw = response.content.decode()
            self.assertNotIn("test-key-hidden", raw)
            self.assertNotIn("TENOR_API_KEY", raw)