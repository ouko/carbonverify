"""CarbonVerify WhatsApp Bot - main orchestrator for all conversation flows."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.whatsapp.message_templates import (
    get_template,
    get_photo_prompt,
    get_survey_questions,
    detect_language,
)
from app.services.whatsapp.state_machine import conversation_state
from app.services.whatsapp.intent_classifier import intent_classifier
from app.services.whatsapp.photo_validator import photo_validator
from app.services.whatsapp.meta_api import get_whatsapp_api
from app.services.kimi_api import get_kimi_client
from app.core.logging import get_logger

logger = get_logger(__name__)

# Flow configurations
SURVEY_FLOWS = ["survey", "utafiti", "anza", "start"]
PHOTO_FLOWS = ["photos", "picha", "photo"]
SUPPORT_FLOWS = ["support", "msaada", "saida", "help"]
STATUS_FLOWS = ["status", "hali"]
CANCEL_COMMANDS = ["cancel", "achana", "stop", "acha"]


class WhatsAppBot:
    """Main WhatsApp bot that routes messages to appropriate flow handlers."""

    def __init__(self):
        self.whatsapp_api = get_whatsapp_api()
        self.kimi = get_kimi_client()

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming WhatsApp message from Meta webhook."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        if value.get("messaging_product") != "whatsapp":
            return {"status": "ignored", "reason": "not_whatsapp"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "ignored", "reason": "no_messages"}

        message = messages[0]
        from_number = message.get("from", "")
        message_type = message.get("type", "text")

        # Rate limiting
        if conversation_state.is_rate_limited(from_number):
            await self._send_text(from_number, "Rate limit exceeded. Please try again later.")
            return {"status": "rate_limited"}

        # Get or create conversation state
        state = conversation_state.get_state(from_number)

        # Auto-detect language from message text
        if message_type == "text":
            text = message.get("text", {}).get("body", "")
            detected = detect_language(text)
            if state.get("language") == "en" and detected == "sw":
                state["language"] = "sw"
                conversation_state.set_state(from_number, state)
        else:
            text = ""

        logger.info(
            "whatsapp_message_received",
            phone=from_number,
            type=message_type,
            flow=state.get("flow"),
            language=state.get("language"),
        )

        # Route based on current flow or intent
        if state.get("flow") == "idle":
            return await self._handle_idle_flow(from_number, text, message_type, message, state)
        elif state.get("flow") == "survey":
            return await self._handle_survey_flow(from_number, text, message_type, message, state)
        elif state.get("flow") == "photo_collection":
            return await self._handle_photo_flow(from_number, text, message_type, message, state)
        elif state.get("flow") == "support":
            return await self._handle_support_flow(from_number, text, message_type, message, state)

        return {"status": "unknown_flow"}

    async def _handle_idle_flow(
        self, phone: str, text: str, msg_type: str, message: Dict, state: Dict
    ) -> Dict[str, Any]:
        """Handle messages when no active flow is running."""
        text_lower = text.lower().strip()
        lang = state.get("language", "en")

        # Check for flow-starting commands
        if any(cmd in text_lower for cmd in SURVEY_FLOWS):
            return await self._start_survey(phone, state)
        elif any(cmd in text_lower for cmd in PHOTO_FLOWS):
            return await self._start_photo_collection(phone, state)
        elif any(cmd in text_lower for cmd in SUPPORT_FLOWS):
            return await self._start_support(phone, state)
        elif any(cmd in text_lower for cmd in STATUS_FLOWS):
            return await self._send_status(phone, state)
        elif any(cmd in text_lower for cmd in CANCEL_COMMANDS):
            await self._send_text(phone, get_template("survey_cancelled", lang))
            return {"status": "cancelled"}

        # Intent classification for natural language
        classification = intent_classifier.classify(text, lang)
        intent = classification.get("intent", "unknown")

        if intent == "start_survey":
            return await self._start_survey(phone, state)
        elif intent == "photo_upload":
            return await self._start_photo_collection(phone, state)
        elif intent == "help_request":
            return await self._start_support(phone, state)
        elif intent == "status_check":
            return await self._send_status(phone, state)
        elif intent == "question":
            # Use Kimi to answer general questions
            answer = await self.kimi.answer_methodology_question(
                question=text,
                methodology="TPDDTEC_v4",
            )
            await self._send_text(phone, answer)
            return {"status": "question_answered"}

        # Default: send welcome message
        await self._send_text(phone, get_template("welcome", lang))
        return {"status": "welcome_sent", "intent": intent}

    async def _handle_survey_flow(
        self, phone: str, text: str, msg_type: str, message: Dict, state: Dict
    ) -> Dict[str, Any]:
        """Handle survey flow messages."""
        lang = state.get("language", "en")
        step = state.get("step", 0)
        project_id = state.get("project_id")  # noqa: F841
        methodology = state.get("context_data", {}).get("methodology", "TPDDTEC_v4")

        # Check for cancel
        if text.lower().strip() in CANCEL_COMMANDS:
            conversation_state.delete_state(phone)
            await self._send_text(phone, get_template("survey_cancelled", lang))
            return {"status": "survey_cancelled"}

        questions = get_survey_questions(methodology, lang)

        # If we're past all questions, complete the survey
        if step >= len(questions):
            return await self._complete_survey(phone, state)

        current_question = questions[step]
        q_type = current_question["type"]
        q_id = current_question["id"]

        # Validate response based on question type
        validation_result = {"valid": True, "value": text, "errors": []}

        if q_type == "number":
            validation_result = intent_classifier.validate_numeric_response(
                text,
                current_question["validation"]["min"],
                current_question["validation"]["max"],
            )
        elif q_type == "choice":
            validation_result = intent_classifier.validate_choice_response(
                text, current_question["options"]
            )
        elif q_type == "image":
            if msg_type == "image":
                validation_result = await self._process_image_message(phone, message, state)
            else:
                validation_result = {
                    "valid": False,
                    "value": None,
                    "errors": [get_template("invalid", lang)],
                }
        elif q_type == "text":
            if not text or len(text.strip()) < 1:
                validation_result = {"valid": False, "value": None, "errors": ["Please provide a valid response"]}

        if not validation_result["valid"]:
            error_msg = "\n".join(validation_result["errors"])
            await self._send_text(phone, f"⚠️ {error_msg}\n\n{current_question['text']}")
            return {"status": "validation_failed", "step": step}

        # Store valid response
        conversation_state.store_response(
            phone, q_id, validation_result["value"], valid=True
        )

        # Advance to next step
        new_state = conversation_state.advance_step(phone)
        new_step = new_state["step"]

        # Send next question or completion
        if new_step < len(questions):
            next_q = questions[new_step]
            progress = get_template("survey_progress", lang, current=new_step + 1, total=len(questions))
            msg = f"{progress}\n\n{next_q['text']}"
            if next_q["type"] == "choice":
                options = "\n".join(f"• {opt}" for opt in next_q["options"])
                msg += f"\n\nOptions:\n{options}"
            await self._send_text(phone, msg)
            return {"status": "question_asked", "step": new_step}
        else:
            return await self._complete_survey(phone, new_state)

    async def _handle_photo_flow(
        self, phone: str, text: str, msg_type: str, message: Dict, state: Dict
    ) -> Dict[str, Any]:
        """Handle photo collection flow messages."""
        lang = state.get("language", "en")
        step = state.get("step", 0)

        # Check for cancel
        if text.lower().strip() in CANCEL_COMMANDS:
            conversation_state.delete_state(phone)
            await self._send_text(phone, get_template("survey_cancelled", lang))
            return {"status": "photo_cancelled"}

        total_photos = 3  # Configurable

        if msg_type == "image":
            # Process and validate the image
            validation_result = await self._process_image_message(phone, message, state)

            if validation_result["valid"]:
                conversation_state.store_photo(phone, validation_result.get("metadata", {}))
                new_state = conversation_state.advance_step(phone)
                current_photo = len(new_state.get("photos", []))

                if current_photo < total_photos:
                    await self._send_text(
                        phone,
                        get_template("photo_received", lang, current=current_photo, total=total_photos)
                    )
                    prompt = get_photo_prompt(current_photo, lang)
                    if prompt:
                        await self._send_text(phone, prompt)
                    return {"status": "photo_prompt", "step": current_photo}
                else:
                    # All photos collected
                    conversation_state.delete_state(phone)
                    ref = f"PH-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{phone[-4:]}"
                    await self._send_text(
                        phone,
                        f"✅ {get_template('photo_welcome', lang, total_photos=total_photos).split(chr(10))[0]}\n\n"
                        f"All {total_photos} photos received! Reference: *{ref}*\n\n"
                        f"Thank you for your submission."
                    )
                    return {"status": "photos_complete", "reference": ref}
            else:
                # Validation failed - send specific error
                errors = validation_result.get("errors", [])
                if any("GPS" in e for e in errors):
                    await self._send_text(phone, get_template("photo_invalid_gps", lang))
                elif any("quality" in e.lower() or "resolution" in e.lower() for e in errors):
                    await self._send_text(phone, get_template("photo_invalid_quality", lang))
                elif any("boundary" in e.lower() for e in errors):
                    await self._send_text(phone, get_template("photo_outside_boundary", lang))
                else:
                    await self._send_text(phone, f"⚠️ {' '.join(errors)}\n\nPlease try again.")
                return {"status": "photo_validation_failed"}
        else:
            prompt = get_photo_prompt(step, lang) or get_template("photo_welcome", lang, total_photos=total_photos)
            await self._send_text(phone, prompt)
            return {"status": "photo_prompt_sent"}

    async def _handle_support_flow(
        self, phone: str, text: str, msg_type: str, message: Dict, state: Dict
    ) -> Dict[str, Any]:
        """Handle support flow messages."""
        lang = state.get("language", "en")
        step = state.get("step", 0)

        if step == 0:
            # First message in support flow - store the issue description
            conversation_state.advance_step(phone, {"issue_description": text})

            # Create support ticket reference
            ticket_id = f"SUP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{phone[-4:]}"

            await self._send_text(phone, get_template("support_received", lang, ticket_id=ticket_id))

            # Also notify the project team / queue to human operator
            logger.info("support_ticket_created", ticket_id=ticket_id, phone=phone, issue=text[:200])

            # Reset to idle after support request
            conversation_state.delete_state(phone)

            return {"status": "support_ticket_created", "ticket_id": ticket_id}

        return {"status": "support_handled"}

    async def _start_survey(self, phone: str, state: Dict) -> Dict[str, Any]:
        """Start a new survey flow."""
        lang = state.get("language", "en")
        project_id = state.get("project_id")  # noqa: F841
        methodology = state.get("context_data", {}).get("methodology", "TPDDTEC_v4")

        conversation_state.start_flow(phone, "survey", project_id=project_id, language=lang)
        new_state = conversation_state.get_state(phone)
        new_state["context_data"] = {"methodology": methodology}
        conversation_state.set_state(phone, new_state)

        questions = get_survey_questions(methodology, lang)
        welcome = get_template("survey_welcome", lang, total_questions=len(questions))
        await self._send_text(phone, welcome)

        if questions:
            first_q = questions[0]
            msg = f"1️⃣ {first_q['text']}"
            if first_q["type"] == "choice":
                options = "\n".join(f"• {opt}" for opt in first_q["options"])
                msg += f"\n\nOptions:\n{options}"
            await self._send_text(phone, msg)

        return {"status": "survey_started", "total_questions": len(questions)}

    async def _start_photo_collection(self, phone: str, state: Dict) -> Dict[str, Any]:
        """Start a new photo collection flow."""
        lang = state.get("language", "en")
        project_id = state.get("project_id")  # noqa: F841

        conversation_state.start_flow(phone, "photo_collection", project_id=project_id, language=lang)

        total_photos = 3
        welcome = get_template("photo_welcome", lang, total_photos=total_photos)
        await self._send_text(phone, welcome)

        prompt = get_photo_prompt(0, lang)
        if prompt:
            await self._send_text(phone, prompt)

        return {"status": "photo_collection_started", "total_photos": total_photos}

    async def _start_support(self, phone: str, state: Dict) -> Dict[str, Any]:
        """Start a support flow."""
        lang = state.get("language", "en")
        project_id = state.get("project_id")  # noqa: F841

        conversation_state.start_flow(phone, "support", project_id=project_id, language=lang)

        welcome = get_template("support_welcome", lang)
        await self._send_text(phone, welcome)

        return {"status": "support_started"}

    async def _send_status(self, phone: str, state: Dict) -> Dict[str, Any]:
        """Send enumerator status summary."""
        lang = state.get("language", "en")

        # In production, query actual stats from database
        surveys_count = state.get("message_count", 0)
        photos_count = len(state.get("photos", []))
        pending_count = 0
        quality_score = 95

        status_msg = get_template(
            "status", lang,
            surveys_count=surveys_count,
            photos_count=photos_count,
            pending_count=pending_count,
            quality_score=quality_score,
        )
        await self._send_text(phone, status_msg)
        return {"status": "status_sent"}

    async def _complete_survey(self, phone: str, state: Dict) -> Dict[str, Any]:
        """Complete a survey and store responses."""
        lang = state.get("language", "en")
        responses = state.get("responses", {})
        project_id = state.get("project_id")  # noqa: F841

        # Generate reference
        ref = f"SV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{phone[-4:]}"

        # In production, store to database as SurveyResponse
        logger.info(
            "survey_completed",
            phone=phone,
            reference=ref,
            project_id=project_id,
            responses_count=len(responses),
        )

        # Clear conversation state
        conversation_state.delete_state(phone)

        completion_msg = get_template("survey_complete", lang, reference=ref)
        await self._send_text(phone, completion_msg)

        return {"status": "survey_completed", "reference": ref, "responses": responses}

    async def _process_image_message(
        self, phone: str, message: Dict, state: Dict
    ) -> Dict[str, Any]:
        """Download and validate an image message."""
        try:
            image_data = message.get("image", {})
            media_id = image_data.get("id")
            mime_type = image_data.get("mime_type", "image/jpeg")

            if not media_id:
                return {"valid": False, "errors": ["No image data received"]}

            # Download image from Meta
            image_bytes = await self.whatsapp_api.download_media(media_id)

            # Get project boundary if available
            project_boundary = state.get("context_data", {}).get("project_boundary")

            # Validate photo
            validation = photo_validator.validate(image_bytes, project_boundary)

            return {
                "valid": validation["valid"],
                "value": f"media:{media_id}",
                "errors": validation["errors"],
                "metadata": {
                    "media_id": media_id,
                    "mime_type": mime_type,
                    **validation["metadata"],
                },
            }

        except Exception as exc:
            logger.error("image_processing_error", error=str(exc), phone=phone)
            return {"valid": False, "errors": [f"Failed to process image: {str(exc)}"]}

    async def _send_text(self, phone: str, text: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp API."""
        return await self.whatsapp_api.send_text_message(phone, text)


# Global singleton
_whatsapp_bot: Optional[WhatsAppBot] = None


def get_whatsapp_bot() -> WhatsAppBot:
    global _whatsapp_bot
    if _whatsapp_bot is None:
        _whatsapp_bot = WhatsAppBot()
    return _whatsapp_bot
