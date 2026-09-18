"""
title: Classroom Review Gate
author: Classroom AI
version: 1.1.0
description: Require teacher approval before a student message reaches an AI model.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Filter:
    # A global classroom gate must not depend on a per-user filter toggle.
    toggle = False

    class Valves(BaseModel):
        review_url: str = Field(default="http://127.0.0.1:8790", description="教师审核服务地址")
        review_token: str = Field(default="", description="审核服务令牌")
        poll_seconds: float = Field(default=1.0, ge=0.2, le=10, description="审核状态轮询间隔")
        timeout_seconds: int = Field(default=3600, ge=30, le=86400, description="最长等待时间")
        enabled: bool = Field(default=True, description="是否启用强制审核")
        allow_admins: bool = Field(default=True, description="管理员账号不进入审核队列")

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Review-Token", token)
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _last_user_message(body: dict) -> tuple[int, dict] | tuple[None, None]:
        messages = body.get("messages") or []
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].get("role") == "user":
                return index, messages[index]
        return None, None

    @staticmethod
    def _message_text(message: dict) -> str:
        content: Any = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text", "")))
            return "\n".join(parts)
        return str(content)

    async def _emit_status(self, emitter, description: str, done: bool = False):
        if emitter:
            await emitter({"type": "status", "data": {"description": description, "done": done, "hidden": False}})

    async def inlet(self, body: dict, __user__: dict | None = None, __metadata__: dict | None = None, __event_emitter__=None) -> dict:
        if not self.valves.enabled:
            return body
        if self.valves.allow_admins and (__user__ or {}).get("role") == "admin":
            return body
        index, message = self._last_user_message(body)
        if message is None:
            return body
        text = self._message_text(message).strip()
        if not text:
            return body
        metadata = __metadata__ or {}
        user = __user__ or {}
        chat_id = str(metadata.get("chat_id") or body.get("chat_id") or "")
        message_id = str(metadata.get("message_id") or body.get("id") or "")
        user_id = str(user.get("id") or "")
        stable = f"{user_id}|{chat_id}|{message_id}"
        request_key = stable if message_id or chat_id else hashlib.sha256(f"{stable}|{uuid.uuid4().hex}".encode()).hexdigest()
        base = self.valves.review_url.rstrip("/")
        payload = {
            "request_key": request_key,
            "user_id": user_id,
            "user_name": str(user.get("name") or ""),
            "user_email": str(user.get("email") or ""),
            "chat_id": chat_id,
            "message_id": message_id,
            "message": text,
        }
        try:
            request = await asyncio.to_thread(self._request, "POST", f"{base}/api/requests", self.valves.review_token, payload)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise RuntimeError("教师审核服务不可用，已阻止本次请求。") from exc
        request_id = request.get("id")
        if not request_id:
            raise RuntimeError("教师审核服务返回了无效请求。")
        await self._emit_status(__event_emitter__, "已提交教师审核，等待批准…")
        deadline = time.monotonic() + self.valves.timeout_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(self.valves.poll_seconds)
            try:
                state = await asyncio.to_thread(self._request, "GET", f"{base}/api/requests/{request_id}", self.valves.review_token)
            except (OSError, urllib.error.URLError, ValueError):
                continue
            if state.get("status") == "approved":
                edited = str(state.get("edited_message") or "").strip()
                if edited:
                    body["messages"][index]["content"] = edited
                await self._emit_status(__event_emitter__, "教师已批准，正在生成回答…", done=True)
                return body
            if state.get("status") == "rejected":
                note = str(state.get("note") or "").strip()
                suffix = f"（原因：{note}）" if note else ""
                raise RuntimeError(f"该问题未通过教师审核{suffix}")
        raise RuntimeError("等待教师审核超时，请重新提交问题。")
