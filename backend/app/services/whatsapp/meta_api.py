"""Meta (Facebook) WhatsApp Business API client."""

import os
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_API_VERSION = "v18.0"


class WhatsAppMetaAPI:
    """Client for Meta WhatsApp Business API."""

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: str = DEFAULT_API_VERSION,
    ):
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.access_token = access_token or os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.api_version = api_version
        self.base_url = f"https://graph.facebook.com/{api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_text_message(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> Dict[str, Any]:
        """Send a text message to a WhatsApp user."""
        if not self.access_token or not self.phone_number_id:
            logger.warning("whatsapp_credentials_missing")
            return {"success": False, "error": "WhatsApp credentials not configured"}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._format_phone(to),
            "type": "text",
            "text": {"preview_url": preview_url, "body": text},
        }

        try:
            response = await self.client.post(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            logger.info("whatsapp_message_sent", to=to, message_id=data.get("messages", [{}])[0].get("id"))
            return {"success": True, "data": data}
        except Exception as exc:
            logger.error("whatsapp_send_error", error=str(exc), to=to)
            return {"success": False, "error": str(exc)}

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        components: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send a message template."""
        if not self.access_token or not self.phone_number_id:
            return {"success": False, "error": "WhatsApp credentials not configured"}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": self._format_phone(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components

        try:
            response = await self.client.post(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=payload,
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as exc:
            logger.error("whatsapp_template_error", error=str(exc), to=to)
            return {"success": False, "error": str(exc)}

    async def send_media_message(
        self,
        to: str,
        media_type: str,  # image, document, audio, video
        media_url: str,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a media message."""
        if not self.access_token or not self.phone_number_id:
            return {"success": False, "error": "WhatsApp credentials not configured"}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": self._format_phone(to),
            "type": media_type,
            media_type: {"link": media_url},
        }
        if caption:
            payload[media_type]["caption"] = caption

        try:
            response = await self.client.post(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=payload,
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as exc:
            logger.error("whatsapp_media_error", error=str(exc), to=to)
            return {"success": False, "error": str(exc)}

    async def mark_message_read(self, message_id: str) -> Dict[str, Any]:
        """Mark a message as read."""
        if not self.access_token or not self.phone_number_id:
            return {"success": False, "error": "WhatsApp credentials not configured"}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            response = await self.client.post(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=payload,
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as exc:
            logger.error("whatsapp_read_error", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def download_media(self, media_id: str) -> bytes:
        """Download media from Meta servers."""
        if not self.access_token:
            raise ValueError("WhatsApp access token not configured")

        # First get the media URL
        url = f"{self.base_url}/{media_id}"
        try:
            response = await self.client.get(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            media_data = response.json()
            download_url = media_data.get("url")

            if not download_url:
                raise ValueError("No download URL in media response")

            # Download the actual media
            media_response = await self.client.get(
                download_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            media_response.raise_for_status()
            return media_response.content
        except Exception as exc:
            logger.error("whatsapp_download_error", error=str(exc), media_id=media_id)
            raise

    def _format_phone(self, phone: str) -> str:
        """Format phone number for WhatsApp API."""
        cleaned = phone.replace("+", "").replace(" ", "").replace("-", "")
        return cleaned

    async def verify_webhook(self, mode: str, token: str, challenge: str,
                             verify_token: str) -> Optional[str]:
        """Verify webhook subscription from Meta."""
        if mode == "subscribe" and token == verify_token:
            return challenge
        return None


# Global singleton
_whatsapp_api: Optional[WhatsAppMetaAPI] = None


def get_whatsapp_api() -> WhatsAppMetaAPI:
    global _whatsapp_api
    if _whatsapp_api is None:
        _whatsapp_api = WhatsAppMetaAPI()
    return _whatsapp_api
