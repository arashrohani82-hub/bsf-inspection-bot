"""Configurable Anthropic vision runtime with model fallback."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any

import inspection_bot as bot

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-3-5-haiku-20241022"


def _model_candidates() -> list[str]:
    configured = os.getenv("ANTHROPIC_MODEL", "").strip()
    candidates = [configured, DEFAULT_MODEL, "claude-3-haiku-20240307"]
    result: list[str] = []
    for model in candidates:
        if model and model not in result:
            result.append(model)
    return result


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    payload = json.loads(cleaned.strip())
    if not isinstance(payload, dict):
        raise ValueError("Anthropic response must be a JSON object")
    severity = str(payload.get("severity", "minor")).lower()
    if severity not in {"critical", "major", "moderate", "minor", "ok"}:
        severity = "minor"
    return {
        "caption_fr": str(payload.get("caption_fr", "Observation à compléter")),
        "caption_en": str(payload.get("caption_en", "Observation to be completed")),
        "severity": severity,
    }


def analyse_photo(image_bytes: bytes, element_type: str, location: str, problem: str) -> dict[str, Any]:
    encoded = base64.standard_b64encode(image_bytes).decode("ascii")
    prompt = f"""You are an engineering inspection assistant.
Describe only what is visibly supported by the photograph. Do not claim code compliance,
structural capacity, or test results that cannot be verified from the image.
Context: element={element_type}, location={location}, user observation={problem or 'none'}.
Return ONLY valid JSON in this exact shape:
{{"caption_fr":"...","caption_en":"...","severity":"critical|major|moderate|minor|ok"}}"""

    last_error: Exception | None = None
    for model in _model_candidates():
        for attempt in range(2):
            try:
                response = bot.anthropic_client.messages.create(
                    model=model,
                    max_tokens=300,
                    timeout=60,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": encoded,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                )
                parsed = _parse_json(response.content[0].text)
                log.info("Anthropic vision analysis succeeded with model %s", model)
                return parsed
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                log.warning(
                    "Anthropic model %s attempt %s failed: %s",
                    model,
                    attempt + 1,
                    exc,
                )
                # A missing/inaccessible model will not recover by retrying it.
                if "404" in message or "not_found" in message or "model" in message and "not found" in message:
                    break
                if attempt == 0:
                    time.sleep(2)

    raise RuntimeError(f"All configured Anthropic models failed: {last_error}")


def install_ai_runtime() -> None:
    bot.analyse_photo = analyse_photo
    log.info("Anthropic model candidates: %s", ", ".join(_model_candidates()))
