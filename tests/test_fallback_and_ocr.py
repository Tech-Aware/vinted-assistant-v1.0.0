import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock, TestCase

from config.settings import Settings
from domain.models import VintedListing
from domain.templates import ALL_PROFILES, AnalysisProfileName
from infrastructure.gemini_client import GeminiListingClient


class FakeOCR:
    def extract_text(self, image_paths):
        return SimpleNamespace(full_text="OCR TEXTE", per_image_text={})


class FakeGemini(GeminiListingClient):
    def __init__(self):
        super().__init__(Settings(gemini_api_key="dummy-key", gemini_model="gemini-3-pro-preview"), ocr_provider=FakeOCR())
        self.last_image_paths = []

    def _call_api(self, image_paths, profile, ui_data=None, ocr_text=None, structured_schema=None):
        # capture paths envoyées à Gemini (pour vérifier l'exclusion OCR)
        self.last_image_paths = list(image_paths)
        payload = {
            "title": "Titre test",
            "description": "Description test",
            "brand": "Test",
            "style": None,
            "pattern": None,
            "neckline": None,
            "season": None,
            "defects": None,
            "features": {
                "brand": "Test",
            },
        }
        return json.dumps(payload)


class DummyLabel:
    def __init__(self):
        self.last_kwargs = {}

    def configure(self, **kwargs):
        self.last_kwargs.update(kwargs)


class DummyText:
    def delete(self, *_args, **_kwargs):
        pass

    def insert(self, *_args, **_kwargs):
        pass


class UIHandlerTest(TestCase):
    def test_handle_generation_success_sets_warning_on_fallback(self):
        from presentation.ui_app import VintedAIApp

        app = object.__new__(VintedAIApp)
        app.generate_btn = None
        app.current_listing = None
        app.palette = {"accent_gradient_start": "#00ff00"}
        app.status_label = DummyLabel()
        app.title_text = DummyText()
        app.description_text = DummyText()
        app.description_header_label = DummyLabel()
        app._prompt_composition_if_needed = lambda listing: None
        app._update_result_fields = lambda listing: None
        app._needs_manual_sku = lambda listing: False

        listing = VintedListing(
            title="Fallback",
            description="desc",
            fallback_reason="JSON invalide",
        )

        with mock.patch("presentation.ui_app.messagebox.showwarning") as warn_box:
            VintedAIApp._handle_generation_success(app, listing)
            self.assertIn("fallback", app.status_label.last_kwargs.get("text", "").lower())
            warn_box.assert_called()


class GeminiClientTest(TestCase):
    def test_build_fallback_listing_sets_reason_and_logs(self):
        client = FakeGemini()
        listing = client._build_fallback_listing("erreur json", raw_text="{}")
        self.assertEqual("erreur json", listing.fallback_reason)
        self.assertTrue(listing.title)
        self.assertTrue(listing.description)

    def test_ocr_images_not_sent_to_gemini(self):
        profile = ALL_PROFILES[AnalysisProfileName.JEAN_LEVIS]
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "img1.jpg"
            p2 = Path(tmpdir) / "img2.jpg"
            p1.write_bytes(b"data1")
            p2.write_bytes(b"data2")

            client = FakeGemini()
            listing = client.generate_listing(
                [p1, p2],
                profile,
                ui_data={"ocr_image_paths": [str(p1)]},
            )

            sent_paths = {Path(p) for p in client.last_image_paths}
            self.assertNotIn(p1, sent_paths, "L'image OCR ne doit pas être envoyée à Gemini.")
            self.assertIn(p2, sent_paths, "Les autres images doivent être envoyées.")
            self.assertTrue(listing.title)
            self.assertTrue(listing.description)
