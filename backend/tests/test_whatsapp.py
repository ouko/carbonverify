"""Tests for CarbonVerify WhatsApp Business API bot."""

import uuid
import pytest

from app.services.whatsapp.message_templates import (
    get_template,
    get_photo_prompt,
    get_survey_questions,
    detect_language,
)
from app.services.whatsapp.intent_classifier import intent_classifier
from app.services.whatsapp.photo_validator import photo_validator


class TestMessageTemplates:
    def test_welcome_english(self):
        msg = get_template("welcome", "en")
        assert "CarbonVerify" in msg
        assert "survey" in msg.lower()

    def test_welcome_swahili(self):
        msg = get_template("welcome", "sw")
        assert "Habari" in msg or "CarbonVerify" in msg

    def test_survey_progress(self):
        msg = get_template("survey_progress", "en", current=3, total=10)
        assert "3" in msg
        assert "10" in msg

    def test_invalid_key_returns_empty(self):
        msg = get_template("nonexistent", "en")
        assert msg == ""

    def test_photo_prompt_english(self):
        prompt = get_photo_prompt(0, "en")
        assert prompt is not None
        assert "stove" in prompt.lower()

    def test_photo_prompt_swahili(self):
        prompt = get_photo_prompt(0, "sw")
        assert prompt is not None
        assert "jiko" in prompt.lower()

    def test_survey_questions_tpddtec(self):
        questions = get_survey_questions("TPDDTEC_v4", "en")
        assert len(questions) > 0
        assert any(q["id"] == "fuel_type" for q in questions)

    def test_survey_questions_fallback(self):
        questions = get_survey_questions("UNKNOWN", "en")
        assert len(questions) > 0  # Falls back to TPDDTEC_v4


class TestLanguageDetection:
    def test_detect_swahili(self):
        assert detect_language("Habari, nataka kuanza utafiti") == "sw"
        assert detect_language("Asante sana") == "sw"
        assert detect_language("Tafadhali saidia") == "sw"

    def test_detect_english(self):
        assert detect_language("Hello, I want to start a survey") == "en"
        assert detect_language("Thank you very much") == "en"

    def test_mixed_defaults_english(self):
        assert detect_language("Hello") == "en"


class TestIntentClassifier:
    def test_classify_start_survey(self):
        result = intent_classifier.classify("start", "en")
        assert result["intent"] == "start_survey"

    def test_classify_help(self):
        result = intent_classifier.classify("help", "en")
        assert result["intent"] == "help_request"

    def test_classify_status(self):
        result = intent_classifier.classify("status", "en")
        assert result["intent"] == "status_check"

    def test_classify_photos(self):
        result = intent_classifier.classify("photos", "en")
        assert result["intent"] == "photo_upload"

    def test_classify_cancel(self):
        result = intent_classifier.classify("cancel", "en")
        assert result["intent"] == "cancel"

    def test_classify_swahili_anza(self):
        result = intent_classifier.classify("anza", "sw")
        assert result["intent"] == "start_survey"

    def test_classify_swahili_saida(self):
        result = intent_classifier.classify("saida", "sw")
        assert result["intent"] == "help_request"

    def test_classify_unknown(self):
        result = intent_classifier.classify("xyzabc123", "en")
        assert result["intent"] == "unknown"
        assert result["confidence"] < 0.5

    def test_extract_entities_stove_id(self):
        entities = intent_classifier.extract_entities("Stove ID: AB-1234")
        assert "stove_id" in entities
        assert entities["stove_id"] == "AB-1234"

    def test_extract_entities_village(self):
        entities = intent_classifier.extract_entities("Village: Kibera")
        assert "village_name" in entities

    def test_validate_numeric_valid(self):
        result = intent_classifier.validate_numeric_response("5.5", 1, 10)
        assert result["valid"] is True
        assert result["value"] == 5.5

    def test_validate_numeric_too_high(self):
        result = intent_classifier.validate_numeric_response("15", 1, 10)
        assert result["valid"] is False

    def test_validate_numeric_invalid(self):
        result = intent_classifier.validate_numeric_response("abc", 1, 10)
        assert result["valid"] is False

    def test_validate_choice_valid(self):
        result = intent_classifier.validate_choice_response("wood", ["wood", "charcoal", "gas"])
        assert result["valid"] is True
        assert result["value"] == "wood"

    def test_validate_choice_invalid(self):
        result = intent_classifier.validate_choice_response("nuclear", ["wood", "charcoal", "gas"])
        assert result["valid"] is False


class TestPhotoValidator:
    def test_validate_too_small_file(self):
        tiny_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = photo_validator.validate(tiny_image)
        assert result["size_valid"] is False
        assert result["valid"] is False

    def test_validate_missing_gps(self):
        # Create a minimal valid image without GPS
        from PIL import Image
        import io
        img = Image.new("RGB", (800, 600), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        result = photo_validator.validate(image_bytes)
        assert result["format_valid"] is True
        assert result["quality_valid"] is True
        assert result["gps_present"] is False
        assert result["valid"] is False
        assert any("GPS" in e for e in result["errors"])

    def test_boundary_check_with_bbox(self):
        boundary = {
            "min_latitude": -2.0,
            "max_latitude": 2.0,
            "min_longitude": 34.0,
            "max_longitude": 42.0,
        }
        inside = photo_validator._check_boundary(0.0, 36.0, boundary)
        outside = photo_validator._check_boundary(10.0, 50.0, boundary)
        assert inside is True
        assert outside is False

    def test_boundary_check_with_center_radius(self):
        boundary = {
            "center_latitude": -1.2921,
            "center_longitude": 36.8219,
            "radius_km": 50,
        }
        inside = photo_validator._check_boundary(-1.3, 36.8, boundary)
        far = photo_validator._check_boundary(-5.0, 40.0, boundary)
        assert inside is True
        assert far is False
