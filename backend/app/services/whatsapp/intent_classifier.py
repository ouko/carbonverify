"""Intent classification for WhatsApp messages using Kimi API and heuristics."""

import re
from typing import Any, Dict, List, Optional

from app.services.kimi_api import get_kimi_client
from app.core.logging import get_logger

logger = get_logger(__name__)

# Intent keyword mappings for fast heuristic classification
INTENT_KEYWORDS = {
    "survey_response": ["survey", "utafiti", "questions", "maswali"],
    "photo_upload": ["photo", "picha", "image", "camera"],
    "start_survey": ["start", "anza", "begin"],
    "status_check": ["status", "hali", "progress", "maendeleo"],
    "help_request": ["help", "saida", "msaada", "support", "assistance"],
    "complaint": ["problem", "shida", "issue", "wrong", "error", "mbaya"],
    "question": ["how", "what", "why", "je", "nini", "vipi", "kwa nini"],
    "cancel": ["cancel", "achana", "stop", "acha", "quit"],
    "yes": ["yes", "ndio", "yeah", "sure", "ok"],
    "no": ["no", "hapana", "nope"],
}

ENTITY_PATTERNS = {
    "stove_id": [
        r"(?:stove|device)\s*id[:\s]*([A-Z0-9\-]{3,20})",
        r"(?:jiko|kifaa)\s*id[:\s]*([A-Z0-9\-]{3,20})",
        r"#?([A-Z]{2,4}\-?\d{3,8})",
    ],
    "household_id": [
        r"(?:household|hh)\s*id[:\s]*([A-Z0-9\-]{3,20})",
        r"(?:kaya)\s*id[:\s]*([A-Z0-9\-]{3,20})",
    ],
    "village_name": [
        r"(?:village|location)[:\s]*([A-Za-z\s]{3,30})",
        r"(?:kijiji|eneo)[:\s]*([A-Za-z\s]{3,30})",
    ],
    "usage_hours": [
        r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|h)\b",
        r"(\d+(?:\.\d+)?)\s*(?:masaa|saa)\b",
    ],
    "fuel_type": [
        r"\b(wood|charcoal|gas|lpg|electricity|kerosene|biogas|dung)\b",
        r"\b(kuni|mkaa|gesi|umeme|mafuta|kinyesi)\b",
    ],
    "phone_number": [
        r"(\+?\d{1,3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3,4})",
    ],
}


class IntentClassifier:
    """Classifies WhatsApp message intents and extracts entities."""

    def __init__(self):
        self.kimi = get_kimi_client()

    def classify(self, message: str, language: str = "en") -> Dict[str, Any]:
        """Classify intent using heuristics (fast) with optional Kimi fallback."""
        message_lower = message.lower().strip()

        # 1. Check for exact command matches
        if message_lower in ("start", "anza"):
            return {"intent": "start_survey", "confidence": 1.0, "entities": {}}
        if message_lower in ("help", "saida", "msaada"):
            return {"intent": "help_request", "confidence": 1.0, "entities": {}}
        if message_lower in ("status", "hali"):
            return {"intent": "status_check", "confidence": 1.0, "entities": {}}
        if message_lower in ("cancel", "achana", "stop", "acha"):
            return {"intent": "cancel", "confidence": 1.0, "entities": {}}
        if message_lower in ("photos", "picha"):
            return {"intent": "photo_upload", "confidence": 1.0, "entities": {}}

        # 2. Heuristic keyword scoring
        scores = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                scores[intent] = score

        if scores:
            best_intent = max(scores, key=scores.get)
            best_score = scores[best_intent]
            confidence = min(1.0, best_score * 0.3 + 0.4)
        else:
            best_intent = "unknown"
            confidence = 0.3

        # 3. Entity extraction
        entities = self.extract_entities(message)

        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "entities": entities,
            "method": "heuristic",
        }

    async def classify_with_kimi(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Use Kimi API for advanced intent classification."""
        system_prompt = (
            "You are a WhatsApp bot intent classifier for a carbon credit MRV platform. "
            "Classify the user's message into exactly one of these intents: "
            "survey_response, photo_upload, start_survey, status_check, help_request, "
            "complaint, question, cancel, yes, no, unknown. "
            "Also extract any entities: stove_id, household_id, village_name, usage_hours, fuel_type. "
            "Respond ONLY with valid JSON in this exact format:\n"
            '{"intent": "...", "confidence": 0.95, "entities": {"stove_id": "..."}}'
        )
        user_prompt = f"Message: {message}"
        if context:
            user_prompt += f"\nContext: {context}"

        try:
            result = await self.kimi.chat_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], temperature=0.1, max_tokens=256)

            content = result.get("content", "")
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                import json
                parsed = json.loads(json_match.group())
                return {
                    "intent": parsed.get("intent", "unknown"),
                    "confidence": parsed.get("confidence", 0.5),
                    "entities": parsed.get("entities", {}),
                    "method": "kimi",
                }
        except Exception as exc:
            logger.error("kimi_intent_classification_error", error=str(exc))

        # Fallback to heuristic
        return self.classify(message)

    def extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from message using regex patterns."""
        entities = {}
        for entity_type, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    entities[entity_type] = value
                    break
        return entities

    def validate_numeric_response(self, message: str, min_val: float, max_val: float) -> Dict[str, Any]:
        """Validate a numeric response."""
        cleaned = message.replace(",", "").strip()
        try:
            value = float(cleaned)
            if min_val <= value <= max_val:
                return {"valid": True, "value": value, "errors": []}
            return {
                "valid": False,
                "value": value,
                "errors": [f"Value must be between {min_val} and {max_val}"],
            }
        except ValueError:
            return {"valid": False, "value": None, "errors": ["Please enter a valid number"]}

    def validate_choice_response(self, message: str, options: List[str]) -> Dict[str, Any]:
        """Validate a choice response."""
        message_lower = message.lower().strip()
        for option in options:
            if option.lower() in message_lower or message_lower in option.lower():
                return {"valid": True, "value": option, "errors": []}
        return {
            "valid": False,
            "value": None,
            "errors": [f"Please choose from: {', '.join(options)}"],
        }


# Global singleton
intent_classifier = IntentClassifier()
