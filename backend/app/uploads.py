from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.agents.client import agents_enabled
from app.agents.skills.vision_ocr import SUPPORTED_MEDIA_TYPES, extract_text_from_image


TEXT_FILE_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log"}
MAX_TEXT_BYTES = 250_000
MAX_IMAGE_BYTES = 5_000_000


async def read_uploads(files: list[UploadFile]) -> tuple[str, list[dict[str, str]]]:
    extracted_chunks: list[str] = []
    uploaded_files: list[dict[str, str]] = []

    for file in files:
        if not file.filename:
            continue

        content_type = file.content_type or ""
        filename = file.filename
        suffix = Path(filename).suffix.lower()
        file_info = {
            "name": filename,
            "content_type": content_type,
            "note": "Upload received. Paste screenshot/PDF text when OCR is needed.",
        }

        if content_type.startswith("text/") or suffix in TEXT_FILE_SUFFIXES:
            raw_content = await file.read(MAX_TEXT_BYTES + 1)
            trimmed_content = raw_content[:MAX_TEXT_BYTES]
            text = decode_text_upload(trimmed_content)
            if text.strip():
                extracted_chunks.append(f"\n\n--- Uploaded file: {filename} ---\n{text.strip()}")
                file_info["note"] = "Text extracted and included in this analysis."
            else:
                file_info["note"] = "Text file was uploaded, but no readable text was found."
        elif content_type in SUPPORTED_MEDIA_TYPES:
            if agents_enabled():
                raw_content = await file.read(MAX_IMAGE_BYTES + 1)
                image_bytes = raw_content[:MAX_IMAGE_BYTES]
                text = await extract_text_from_image(image_bytes, content_type)
                if text.strip():
                    extracted_chunks.append(f"\n\n--- Uploaded screenshot: {filename} ---\n{text.strip()}")
                    file_info["note"] = "Text extracted from screenshot and included in this analysis."
                else:
                    file_info["note"] = "Screenshot uploaded, but no readable text was found."
            else:
                file_info["note"] = "Screenshot uploaded. Paste the visible text for it to be analyzed."

        uploaded_files.append(file_info)

    return "\n".join(extracted_chunks).strip(), uploaded_files


def decode_text_upload(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""
