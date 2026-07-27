from __future__ import annotations

import base64

from app.agents.client import VISION_MODEL, get_client

SYSTEM_PROMPT = (
    "Extract all readable text from this image exactly as written, in reading order. "
    "If it is a screenshot of a chat, email, or job post, preserve line breaks. "
    "Respond with ONLY the extracted text, no commentary. If there is no readable text, "
    "respond with an empty string."
)

SUPPORTED_MEDIA_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


async def extract_text_from_image(image_bytes: bytes, media_type: str) -> str:
    client = get_client()
    if client is None or media_type not in SUPPORTED_MEDIA_TYPES:
        return ""

    try:
        response = await client.messages.create(
            model=VISION_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": "Extract the text from this image."},
                    ],
                }
            ],
        )
        return response.content[0].text.strip() if response.content else ""
    except Exception:
        return ""
