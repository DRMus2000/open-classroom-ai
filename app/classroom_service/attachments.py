"""Immutable local attachment validation and storage.

Only image bytes and teaching-oriented text files are accepted.  A Python file
is read as text and is never imported, executed, or passed to a shell.
"""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path, PurePath
import re
import uuid

from .clock import iso
from .database import ClassroomDB
from .errors import ForbiddenError, ValidationError


IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
TEXT_EXTENSIONS = {".py", ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log"}
MAX_IMAGE = 5 * 1024 * 1024
MAX_TEXT = 1 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_FILES = 5
MAX_TOTAL = 10 * 1024 * 1024


def _safe_filename(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 255:
        raise ValidationError("invalid attachment filename")
    if "\x00" in name or "\\" in name or "/" in name:
        raise ValidationError("attachment filename cannot contain a path")
    clean = PurePath(name).name
    if clean != name or name in {".", ".."}:
        raise ValidationError("attachment filename cannot contain a path")
    return name


def _image_info(data: bytes, media_type: str) -> tuple[int, int]:
    from PIL import Image
    expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if image.format != expected[media_type] or width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise ValueError("invalid image format or dimensions")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("animated images are not supported")
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
        return width, height
    except Exception as exc:
        raise ValidationError("image cannot be safely decoded or exceeds the classroom limit") from exc


class AttachmentStore:
    def __init__(self, db: ClassroomDB, root: str | Path, *, clock=None):
        self.db = db
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock

    def _now(self):
        return self.clock.now() if self.clock else __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    def add(self, user_id: str, filename: str, content: bytes, *, media_type: str | None = None,
            request_id: str | None = None, encoding: str | None = None) -> dict:
        filename = _safe_filename(filename)
        if not isinstance(content, (bytes, bytearray)):
            raise ValidationError("attachment content must be bytes")
        content = bytes(content)
        pending = self.db.query_one("SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM attachments WHERE owner_user_id=? AND request_id IS NULL", (user_id,))
        if pending[0] >= 30 or pending[1] + len(content) > 30 * 1024 * 1024:
            raise ValidationError("temporary attachment allowance exceeded", status=429)
        suffix = Path(filename).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            expected = IMAGE_EXTENSIONS[suffix]
            if media_type and media_type != expected:
                raise ValidationError("image media type does not match filename")
            if len(content) > MAX_IMAGE:
                raise ValidationError("image is too large")
            media_type = expected
            width, height = _image_info(content, media_type)
            text_encoding = None
        elif suffix in TEXT_EXTENSIONS:
            if len(content) > MAX_TEXT:
                raise ValidationError("text attachment is too large")
            media_type = "text/plain"
            try:
                if encoding not in {None, "utf-8", "utf-8-sig", "gb18030"}:
                    raise ValidationError("supported text encodings: UTF-8 and GB18030")
                text_encoding = encoding or "utf-8-sig"
                content.decode(text_encoding)
            except (LookupError, UnicodeDecodeError) as exc:
                if encoding is None:
                    raise ValidationError("text is not valid UTF-8; choose an explicit encoding") from exc
                raise ValidationError("text cannot be decoded with the requested encoding") from exc
            width = height = None
        else:
            raise ValidationError("file type is not supported for classroom attachments")
        digest = hashlib.sha256(content).hexdigest()
        attachment_id = uuid.uuid4().hex
        rel = Path("blobs") / digest[:2] / f"{attachment_id}.bin"
        absolute = self.root / rel
        absolute.parent.mkdir(parents=True, exist_ok=True)
        temp = absolute.with_suffix(".tmp")
        temp.write_bytes(content)
        os.replace(temp, absolute)
        now_text = iso(self._now())
        with self.db.transaction() as db:
            pending = db.execute("SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM attachments WHERE owner_user_id=? AND request_id IS NULL", (user_id,)).fetchone()
            if pending[0] >= 30 or pending[1] + len(content) > 30 * 1024 * 1024:
                absolute.unlink(missing_ok=True)
                raise ValidationError("temporary attachment allowance exceeded", status=429)
            if not db.execute("SELECT 1 FROM students WHERE user_id=?", (user_id,)).fetchone():
                absolute.unlink(missing_ok=True)
                raise ForbiddenError("student is not enrolled")
            db.execute(
                """INSERT INTO attachments
                (id,owner_user_id,request_id,original_filename,media_type,size_bytes,sha256,blob_ref,text_encoding,image_width,image_height,created_at,retention_class)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (attachment_id, user_id, request_id, filename, media_type, len(content), digest, str(rel).replace("\\", "/"), text_encoding, width, height, now_text, 'permanent' if request_id else 'temporary'),
            )
        return {
            "id": attachment_id, "owner_user_id": user_id, "filename": filename,
            "media_type": media_type, "size_bytes": len(content), "sha256": digest,
            "blob_ref": str(rel).replace("\\", "/"), "encoding": text_encoding,
            "width": width, "height": height,
        }

    def get(self, attachment_id: str, *, user_id: str | None = None, request_id: str | None = None) -> dict:
        row = self.db.query_one("SELECT * FROM attachments WHERE id=?", (attachment_id,))
        if not row:
            raise ValidationError("attachment not found", code="ATTACHMENT_NOT_FOUND", status=404)
        if user_id and row["owner_user_id"] != user_id:
            raise ForbiddenError("attachment does not belong to this student")
        if request_id and row["request_id"] not in {None, request_id}:
            raise ForbiddenError("attachment is not attached to this request")
        path = self.root / row["blob_ref"]
        resolved = path.resolve()
        if self.root.resolve() not in resolved.parents:
            raise RuntimeError("attachment path escaped storage root")
        content = resolved.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise RuntimeError("attachment integrity check failed")
        result = dict(row)
        result["content"] = content
        return result

    def attach_to_request(self, request_id: str, user_id: str, ids: list[str]) -> None:
        if len(ids) > MAX_FILES:
            raise ValidationError("too many attachments")
        seen = set()
        total = 0
        with self.db.transaction() as db:
            for aid in ids:
                if aid in seen:
                    raise ValidationError("duplicate attachment")
                seen.add(aid)
                row = db.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()
                if not row or row["owner_user_id"] != user_id or row["request_id"] not in {None, request_id}:
                    raise ForbiddenError("attachment is not available to this request")
                total += int(row["size_bytes"])
            if total > MAX_TOTAL:
                raise ValidationError("attachments exceed request total size")
            for aid in ids:
                db.execute("UPDATE attachments SET request_id=?,retention_class='permanent' WHERE id=? AND request_id IS NULL", (request_id, aid))

    def cleanup_temporary(self, *, hours=24) -> int:
        from datetime import timedelta
        cutoff = iso(self._now() - timedelta(hours=hours))
        removed = 0
        with self.db.transaction() as db:
            rows = db.execute("SELECT id,blob_ref FROM attachments WHERE request_id IS NULL AND retention_class='temporary' AND created_at<?", (cutoff,)).fetchall()
            for row in rows:
                path = (self.root / row['blob_ref']).resolve()
                if self.root.resolve() not in path.parents:
                    raise RuntimeError('attachment path escaped storage root')
                # Hold the same DB write lock as submission so a newly attached
                # file can never be collected during its permanent transition.
                path.unlink(missing_ok=True)
                db.execute('DELETE FROM native_attachment_copies WHERE attachment_id=?', (row['id'],))
                db.execute('DELETE FROM native_attachments WHERE attachment_id=?', (row['id'],))
                db.execute('DELETE FROM attachments WHERE id=?', (row['id'],))
                removed += 1
        return removed

