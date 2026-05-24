"""WhatsApp message templates for CarbonVerify bot.

Supports English (en) and Swahili (sw) with auto-detection fallback.
"""

from typing import Dict, List, Optional

# ─── Flow Titles ──────────────────────────────────────────────────────────────

FLOW_TITLES = {
    "en": {
        "survey": "Household Survey",
        "photo_collection": "Photo Collection",
        "support": "Support Request",
        "onboarding": "Welcome to CarbonVerify",
    },
    "sw": {
        "survey": "Utafiti wa Kaya",
        "photo_collection": "Ukusanyaji wa Picha",
        "support": "Ombi la Msaada",
        "onboarding": "Karibu kwenye CarbonVerify",
    },
}

# ─── Welcome & Navigation ─────────────────────────────────────────────────────

WELCOME_MESSAGES = {
    "en": (
        "👋 Hello! I'm your CarbonVerify assistant.\n\n"
        "I can help you with:\n"
        "1️⃣ Complete household surveys\n"
        "2️⃣ Upload photos of stoves and fuel\n"
        "3️⃣ Check your submission status\n"
        "4️⃣ Get help from a human\n\n"
        "Type START to begin a survey, or HELP for assistance."
    ),
    "sw": (
        "👋 Habari! Mimi ni msaidizi wako wa CarbonVerify.\n\n"
        "Naweza kukusaidia na:\n"
        "1️⃣ Kamilisha utafiti wa kaya\n"
        "2️⃣ Pakia picha za jiko na kuni\n"
        "3️⃣ Angalia hali ya utafiti wako\n"
        "4️⃣ Pata msaada kutoka kwa mtu\n\n"
        "Andika ANZA ili kuanza utafiti, au SAIDA kwa msaada."
    ),
}

HELP_MESSAGES = {
    "en": (
        "📞 *Help Options*\n\n"
        "• Type START to begin a survey\n"
        "• Type PHOTOS to upload stove photos\n"
        "• Type STATUS to check your submissions\n"
        "• Type SUPPORT to speak to a human operator\n\n"
        "For urgent issues, an operator will respond within 2 hours."
    ),
    "sw": (
        "📞 *Chaguo za Msaada*\n\n"
        "• Andika ANZA ili kuanza utafiti\n"
        "• Andika PICHA ili kupakia picha za jiko\n"
        "• Andika HALI ili kuangalia utafiti wako\n"
        "• Andika MSAIDA ili kuzungumza na mtu\n\n"
        "Kwa masuala ya haraka, mtendaji atajibu ndani ya saa 2."
    ),
}

INVALID_INPUT_MESSAGES = {
    "en": "❌ I didn't understand that. Please reply with a valid option or type HELP for assistance.",
    "sw": "❌ Sikuelewa. Tafadhali jibu kwa chaguo sahihi au andika SAIDA kwa msaada.",
}

# ─── Survey Flow Messages ─────────────────────────────────────────────────────

SURVEY_WELCOME = {
    "en": (
        "📋 *Household Survey*\n\n"
        "I'll guide you through {total_questions} questions about this household. "
        "Please answer carefully. Type CANCEL at any time to stop.\n\n"
        "Let's begin!"
    ),
    "sw": (
        "📋 *Utafiti wa Kaya*\n\n"
        "Nitakuongoza kwenye maswali {total_questions} kuhusu kaya hii. "
        "Tafadhali jibu kwa uangalifu. Andika ACHANA wakati wowote kusitisha.\n\n"
        "Tuanze!"
    ),
}

SURVEY_PROGRESS = {
    "en": "⏳ Question {current} of {total}",
    "sw": "⏳ Swali {current} kati ya {total}",
}

SURVEY_COMPLETION = {
    "en": (
        "✅ *Survey Complete!*\n\n"
        "Thank you for your time. Your responses have been recorded.\n\n"
        "Reference: *{reference}*\n\n"
        "Type START to do another survey, or STATUS to check your submissions."
    ),
    "sw": (
        "✅ *Utafiti Umekamilika!*\n\n"
        "Asante kwa muda wako. Majibu yako yamehifadhiwa.\n\n"
        "Kumbukumbu: *{reference}*\n\n"
        "Andika ANZA kwa utafiti mwingine, au HALI kuangalia utafiti wako."
    ),
}

SURVEY_CANCELLED = {
    "en": "❌ Survey cancelled. Your partial responses have been discarded. Type START to begin again.",
    "sw": "❌ Utafiti umeachishwa. Majibu yako yamefutwa. Andika ANZA kuanza upya.",
}

# ─── Photo Collection Flow Messages ───────────────────────────────────────────

PHOTO_WELCOME = {
    "en": (
        "📸 *Photo Collection*\n\n"
        "I'll guide you through taking {total_photos} photos. "
        "Please make sure GPS location is enabled on your phone.\n\n"
        "Let's start with the first photo!"
    ),
    "sw": (
        "📸 *Ukusanyaji wa Picha*\n\n"
        "Nitakuongoza kuchukua picha {total_photos}. "
        "Hakikisha mahali pa GPS imewashwa kwenye simu yako.\n\n"
        "Tuanze na picha ya kwanza!"
    ),
}

PHOTO_PROMPTS = {
    "en": [
        "1️⃣ Please send a photo of the *stove with a pot* on it.",
        "2️⃣ Please send a photo of the *fuel storage area*.",
        "3️⃣ Please send a photo of a *household member using the stove*.",
    ],
    "sw": [
        "1️⃣ Tafadhali tuma picha ya *jiko na sufuria* juu yake.",
        "2️⃣ Tafadhali tuma picha ya *eneo la kuhifadhi kuni*.",
        "3️⃣ Tafadhali tuma picha ya *mwanakaya akijitumia jiko*.",
    ],
}

PHOTO_RECEIVED = {
    "en": "✅ Photo received! ({current}/{total})",
    "sw": "✅ Picha imepokelewa! ({current}/{total})",
}

PHOTO_INVALID_GPS = {
    "en": (
        "⚠️ Photo received but *GPS location is missing*.\n\n"
        "Please enable location services on your phone and resend the photo.\n"
        "The photo must include GPS coordinates for verification."
    ),
    "sw": (
        "⚠️ Picha imepokelewa lakini *mahali pa GPS halipo*.\n\n"
        "Tafadhali washa huduma za mahali kwenye simu yako na tuma picha upya.\n"
        "Picha lazima iwe na kuratibu za GPS kwa uthibitisho."
    ),
}

PHOTO_INVALID_QUALITY = {
    "en": (
        "⚠️ Photo quality is too low.\n\n"
        "Please retake the photo with better lighting and make sure the subject is clearly visible."
    ),
    "sw": (
        "⚠️ Ubora wa picha ni wa chini sana.\n\n"
        "Tafadhali piga picha upya na mwanga bora na hakikisha kitu kinaonekana vizuri."
    ),
}

PHOTO_OUTSIDE_BOUNDARY = {
    "en": (
        "⚠️ GPS coordinates in the photo are *outside the project boundary*.\n\n"
        "Please verify you are in the correct location and resend."
    ),
    "sw": (
        "⚠️ Kuratibu za GPS katika picha ziko *nje ya mpaka wa mradi*.\n\n"
        "Tafadhali thibitisha uko katika eneo sahihi na tuma upya."
    ),
}

# ─── Support Flow Messages ────────────────────────────────────────────────────

SUPPORT_WELCOME = {
    "en": (
        "🎧 *Support Request*\n\n"
        "Please describe your issue in one message. Include:\n"
        "• What you were trying to do\n"
        "• What went wrong\n"
        "• Your enumerator ID (if you have one)\n\n"
        "A human operator will respond within 2 hours."
    ),
    "sw": (
        "🎧 *Ombi la Msaada*\n\n"
        "Tafadhali eleza shida lako katika ujumbe mmoja. Jumlisha:\n"
        "• Ulikuwa unajaribu kufanya nini\n"
        "• Nini kilikwenda vibaya\n"
        "• Kitambulisho chako cha mkusanyaji (ikiwa unacho)\n\n"
        "Mtendaji atajibu ndani ya saa 2."
    ),
}

SUPPORT_RECEIVED = {
    "en": (
        "✅ *Support request received!*\n\n"
        "Ticket ID: *{ticket_id}*\n"
        "An operator will respond within 2 hours.\n\n"
        "You can check status by typing STATUS at any time."
    ),
    "sw": (
        "✅ *Ombi la msaada limpokelewa!*\n\n"
        "Kitambulisho cha Tikiti: *{ticket_id}*\n"
        "Mtendaji atajibu ndani ya saa 2.\n\n"
        "Unaweza kuangalia hali kwa kuandika HALI wakati wowote."
    ),
}

# ─── Status Check Messages ────────────────────────────────────────────────────

STATUS_RESPONSE = {
    "en": (
        "📊 *Your Status*\n\n"
        "Surveys completed: {surveys_count}\n"
        "Photos uploaded: {photos_count}\n"
        "Pending reviews: {pending_count}\n"
        "Data quality score: {quality_score}/100\n\n"
        "Keep up the great work!"
    ),
    "sw": (
        "📊 *Hali Yako*\n\n"
        "Utafiti ulio kamilika: {surveys_count}\n"
        "Picha zilizopakiwa: {photos_count}\n"
        "Mapitio yanayosubiri: {pending_count}\n"
        "Alama ya ubora wa data: {quality_score}/100\n\n"
        "Endelea na kazi nzuri!"
    ),
}

# ─── Survey Questions (Methodology-Aware) ─────────────────────────────────────

SURVEY_QUESTIONS = {
    "TPDDTEC_v4": {
        "en": [
            {
                "id": "people_cooked",
                "text": "How many people cooked in this household yesterday?",
                "type": "number",
                "validation": {"min": 1, "max": 20},
            },
            {
                "id": "fuel_type",
                "text": "What fuel did you primarily use for cooking yesterday?",
                "type": "choice",
                "options": ["wood", "charcoal", "gas", "electricity", "other"],
            },
            {
                "id": "cooking_hours",
                "text": "How many hours did you spend cooking yesterday?",
                "type": "number",
                "validation": {"min": 0.5, "max": 12},
            },
            {
                "id": "stove_photo",
                "text": "Please send a photo of the stove in use.",
                "type": "image",
            },
            {
                "id": "fuel_amount",
                "text": "Approximately how many kg of fuel did you use yesterday?",
                "type": "number",
                "validation": {"min": 0.1, "max": 50},
            },
            {
                "id": "meals_cooked",
                "text": "How many meals did you cook yesterday?",
                "type": "number",
                "validation": {"min": 1, "max": 10},
            },
        ],
        "sw": [
            {
                "id": "people_cooked",
                "text": "Watu wangapi walipika katika kaya hii jana?",
                "type": "number",
                "validation": {"min": 1, "max": 20},
            },
            {
                "id": "fuel_type",
                "text": "Ni mafuta gani uliyotumia kupika jana?",
                "type": "choice",
                "options": ["kuni", "mkaa", "gesi", "umeme", "nyingine"],
            },
            {
                "id": "cooking_hours",
                "text": "Ulitumia masaa mangapi kupika jana?",
                "type": "number",
                "validation": {"min": 0.5, "max": 12},
            },
            {
                "id": "stove_photo",
                "text": "Tafadhali tuma picha ya jiko likitumika.",
                "type": "image",
            },
            {
                "id": "fuel_amount",
                "text": "Kwa takriban kilogramu ngapi za kuni ulitumia jana?",
                "type": "number",
                "validation": {"min": 0.1, "max": 50},
            },
            {
                "id": "meals_cooked",
                "text": "Ulipika mlo wangapi jana?",
                "type": "number",
                "validation": {"min": 1, "max": 10},
            },
        ],
    },
    "VM0050": {
        "en": [
            {
                "id": "device_id",
                "text": "What is the stove/device ID? (Scan QR code or type ID)",
                "type": "text",
            },
            {
                "id": "usage_hours",
                "text": "How many hours was the device used yesterday?",
                "type": "number",
                "validation": {"min": 0, "max": 24},
            },
            {
                "id": "energy_consumed",
                "text": "How much energy was consumed (kWh)?",
                "type": "number",
                "validation": {"min": 0, "max": 50},
            },
            {
                "id": "stove_photo",
                "text": "Please send a photo of the meter reading.",
                "type": "image",
            },
        ],
        "sw": [
            {
                "id": "device_id",
                "text": "Kitambulisho cha jiko/kifaa ni nini? (Changanua QR au andika ID)",
                "type": "text",
            },
            {
                "id": "usage_hours",
                "text": "Kifaa kilitumika kwa masaa mangapi jana?",
                "type": "number",
                "validation": {"min": 0, "max": 24},
            },
            {
                "id": "energy_consumed",
                "text": "Nishati kiasi gani kilitumika (kWh)?",
                "type": "number",
                "validation": {"min": 0, "max": 50},
            },
            {
                "id": "stove_photo",
                "text": "Tafadhali tuma picha ya kisomaji cha mita.",
                "type": "image",
            },
        ],
    },
}


def get_template(key: str, language: str = "en", **kwargs) -> str:
    """Get a message template by key and language."""
    language = language if language in ("en", "sw") else "en"
    mapping = {
        "welcome": WELCOME_MESSAGES,
        "help": HELP_MESSAGES,
        "invalid": INVALID_INPUT_MESSAGES,
        "survey_welcome": SURVEY_WELCOME,
        "survey_progress": SURVEY_PROGRESS,
        "survey_complete": SURVEY_COMPLETION,
        "survey_cancelled": SURVEY_CANCELLED,
        "photo_welcome": PHOTO_WELCOME,
        "photo_received": PHOTO_RECEIVED,
        "photo_invalid_gps": PHOTO_INVALID_GPS,
        "photo_invalid_quality": PHOTO_INVALID_QUALITY,
        "photo_outside_boundary": PHOTO_OUTSIDE_BOUNDARY,
        "support_welcome": SUPPORT_WELCOME,
        "support_received": SUPPORT_RECEIVED,
        "status": STATUS_RESPONSE,
    }
    template_dict = mapping.get(key, {})
    template = template_dict.get(language, template_dict.get("en", ""))
    return template.format(**kwargs) if kwargs else template


def get_photo_prompt(index: int, language: str = "en") -> Optional[str]:
    """Get a photo prompt by index."""
    language = language if language in ("en", "sw") else "en"
    prompts = PHOTO_PROMPTS.get(language, [])
    if 0 <= index < len(prompts):
        return prompts[index]
    return None


def get_survey_questions(methodology: str, language: str = "en") -> List[dict]:
    """Get survey questions for a methodology and language."""
    language = language if language in ("en", "sw") else "en"
    return SURVEY_QUESTIONS.get(methodology, SURVEY_QUESTIONS["TPDDTEC_v4"]).get(language, [])


def detect_language(text: str) -> str:
    """Simple language detection for English vs Swahili."""
    swahili_markers = [
        "habari", "karibu", "asante", "tafadhali", "ndio", "hapana",
        "anza", "picha", "msaada", "saida", "hali", "achana", "jiko",
        "kuni", "mkaa", "kaya", "watoto", "chakula", "kuamka",
    ]
    text_lower = text.lower()
    sw_score = sum(1 for marker in swahili_markers if marker in text_lower)
    return "sw" if sw_score >= 1 else "en"
