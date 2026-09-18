"""Strict, deterministic request payload normalization."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import ValidationError


MAX_MESSAGES = 80
MAX_TEXT = 200_000
MAX_SYSTEM = 20_000


def _text_length(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def normalize_content(content: Any) -> Any:
    if isinstance(content, str):
        if not content.strip():
            raise ValidationError("user content cannot be empty")
        if len(content) > MAX_TEXT:
            raise ValidationError("message is too large")
        return content
    if not isinstance(content, list) or not content:
        raise ValidationError("message content must be text or a non-empty part list")
    result = []
    has_visible = False
    for part in content:
        if not isinstance(part, dict) or not isinstance(part.get("type"), str):
            raise ValidationError("invalid content part")
        kind = part["type"]
        if kind == "text":
            text = part.get("text")
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                raise ValidationError("invalid text content part")
            if text.strip():
                has_visible = True
            result.append({"type": "text", "text": text})
        elif kind in {"image_url", "input_image"}:
            value = part.get("image_url", part.get("image"))
            if isinstance(value, dict):
                value = value.get("url")
            if not isinstance(value, str) or not value or not value.startswith("attachment:"):
                raise ValidationError("image content must reference an uploaded classroom attachment")
            # The worker replaces this immutable attachment reference with a
            # locally verified data URL; arbitrary remote URLs never reach the
            # managed provider.
            result.append({"type": kind, "image": value})
            has_visible = True
        else:
            raise ValidationError(f"unsupported content part: {kind}")
    if not has_visible:
        raise ValidationError("message content cannot be empty")
    return result


def normalize_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a JSON object")
    allowed = {"messages", "model", "temperature", "max_tokens", "attachments", "metadata"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValidationError("unsupported control field in payload")
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValidationError("a managed model is required")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
        raise ValidationError("messages must be a non-empty bounded list")
    normalized_messages = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}:
            raise ValidationError("invalid message role")
        role = item["role"]
        content = normalize_content(item.get("content"))
        if role == "system" and _text_length(content) > MAX_SYSTEM:
            raise ValidationError("system prompt is too large")
        normalized_messages.append({"role": role, "content": content})
    attachments = payload.get("attachments", [])
    if not isinstance(attachments, list) or len(attachments) > 5:
        raise ValidationError("too many attachments")
    normalized_attachments = []
    for item in attachments:
        if not isinstance(item, dict):
            raise ValidationError("invalid attachment reference")
        aid = item.get("id")
        digest = item.get("sha256")
        if not isinstance(aid, str) or not aid or not isinstance(digest, str) or len(digest) != 64:
            raise ValidationError("attachment references must include id and sha256")
        normalized_attachments.append({"id": aid, "sha256": digest.lower()})
    result = {
        "model": model.strip(),
        "messages": normalized_messages,
        "attachments": normalized_attachments,
    }
    for key in ("temperature", "max_tokens"):
        if key in payload:
            value = payload[key]
            if key == "temperature" and (not isinstance(value, (int, float)) or not 0 <= value <= 2):
                raise ValidationError("temperature is outside the managed range")
            if key == "max_tokens" and (not isinstance(value, int) or not 1 <= value <= 100_000):
                raise ValidationError("max_tokens is outside the managed range")
            result[key] = value
    # metadata is intentionally reduced to safe display data; it can never
    # carry identity, approval, provider, or tool control fields.
    if "metadata" in payload:
        metadata = payload["metadata"]
        if metadata is not None and not isinstance(metadata, dict):
            raise ValidationError("metadata must be an object")
        if isinstance(metadata, dict):
            result["metadata"] = {"chat_id": str(metadata.get("chat_id", ""))[:200]}
    return result


def payload_digest(user_id: str, operation_id: str, payload: dict) -> str:
    value = {"user_id": user_id, "operation_id": operation_id, "payload": payload}
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
