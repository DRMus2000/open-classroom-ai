"""Immutable classroom archive and teacher export helpers."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import zipfile

from .clock import iso
from .database import json_dumps
from .errors import ForbiddenError, ValidationError
from .service import ClassroomService


def safe_cell(value) -> str:
    text = "" if value is None else str(value)
    if text.lstrip(' \t\r\n')[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return stream.getvalue().encode("utf-8-sig")


class ClassroomExporter:
    def __init__(self, service: ClassroomService, output_root: str | Path):
        self.service = service
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def export(self, teacher_id: str, *, user_ids: list[str] | None = None, include_attachments: bool = True) -> Path:
        if user_ids is not None and (not isinstance(user_ids, list) or any(not isinstance(value, str) or not value for value in user_ids)):
            raise ValidationError("export user_ids must be a list of student IDs")
        if user_ids is None:
            user_ids = [row["user_id"] for row in self.service.db.query_all("SELECT user_id FROM students WHERE enrollment_state IN ('active','disabled','deleted_origin') ORDER BY user_id")]
        if len(set(user_ids)) != len(user_ids):
            raise ValidationError("export user_ids must not contain duplicates")
        if not user_ids or len(user_ids) > 30:
            raise ValidationError("export must target one to thirty enrolled students")
        existing = {row["user_id"] for row in self.service.db.query_all("SELECT user_id FROM students WHERE user_id IN (%s)" % ",".join("?" * len(user_ids)), tuple(user_ids))}
        if existing != set(user_ids):
            raise ForbiddenError("export contains a student outside the classroom roster")
        requests = []
        for user_id in user_ids:
            cursor = None
            while True:
                batch = self.service.list_requests(user_id=user_id, limit=100, cursor=cursor)
                requests.extend(batch)
                if len(batch) < 100:
                    break
                tail = batch[-1]
                cursor = f"{tail['submitted_at']}|{tail['id']}"
        export_id = __import__("uuid").uuid4().hex
        target = self.output_root / f"classroom-export-{export_id}.zip"
        manifest = {"format_version": 1, "export_id": export_id, "created_at": iso(self.service.now()), "teacher_id": teacher_id, "user_ids": user_ids, "request_count": len(requests), "contains_passwords": False, "contains_provider_keys": False}
        quota_rows = self.service.db.query_all("SELECT * FROM daily_quotas WHERE user_id IN (%s) ORDER BY quota_date,user_id" % ",".join("?" * len(user_ids)), tuple(user_ids))
        ledger_rows = self.service.db.query_all("SELECT * FROM quota_ledger WHERE user_id IN (%s) ORDER BY created_at,id" % ",".join("?" * len(user_ids)), tuple(user_ids))
        audit_rows = self.service.db.query_all("SELECT * FROM teacher_actions ORDER BY created_at,id")
        legacy_rows = self.service.db.query_all("SELECT * FROM legacy_records WHERE user_id IN (%s) ORDER BY source,record_type,record_id" % ','.join('?' * len(user_ids)), tuple(user_ids))
        manifest['legacy_record_count'] = len(legacy_rows)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            archive.writestr('legacy/records.json', json.dumps([dict(row) for row in legacy_rows], ensure_ascii=False, indent=2).encode('utf-8'))
            if include_attachments:
                for row in legacy_rows:
                    value = json.loads(row['payload_json'])
                    if row['record_type'] != 'file' or not value.get('classroom_blob_ref'):
                        continue
                    root = self.service.attachments.root.parent.resolve()
                    blob = (root / value['classroom_blob_ref']).resolve()
                    if root not in blob.parents:
                        raise RuntimeError('legacy attachment path escaped installation')
                    content = blob.read_bytes()
                    if __import__('hashlib').sha256(content).hexdigest() != value['classroom_blob_sha256']:
                        raise RuntimeError('legacy attachment integrity check failed')
                    archive.writestr('legacy/attachments/' + blob.name, content)
            archive.writestr("quotas.csv", _csv_bytes(["user_id", "quota_date", "base_limit", "adjustment", "used", "reserved", "available"], [[r["user_id"], r["quota_date"], r["base_limit"], r["adjustment"], r["used"], r["reserved"], int(r["base_limit"]) + int(r["adjustment"]) - int(r["used"]) - int(r["reserved"])] for r in quota_rows]))
            archive.writestr("quota-ledger.csv", _csv_bytes(["id", "user_id", "quota_date", "request_id", "kind", "delta_reserved", "delta_used", "delta_adjustment", "actor_id", "reason", "created_at"], [[r[k] for k in ["id", "user_id", "quota_date", "request_id", "kind", "delta_reserved", "delta_used", "delta_adjustment", "actor_id", "reason", "created_at"]] for r in ledger_rows]))
            archive.writestr("audit.csv", _csv_bytes(["id", "actor_id", "action", "target_ids", "result", "created_at"], [[r["id"], r["actor_id"], r["action"], r["target_ids_json"], r["result_json"], r["created_at"]] for r in audit_rows]))
            for item in requests:
                user_id = item["user_id"]
                request_id = item["id"]
                raw = json.dumps(item, ensure_ascii=False, indent=2).encode("utf-8")
                archive.writestr(f"conversations/{user_id}/{request_id}.json", raw)
                lines = [f"# Classroom request {request_id}", "", f"- Student ID: {user_id}", f"- Status: {item['status']}", f"- Submitted: {item['submitted_at']}", f"- Charge units: {item['charge_units']}", "", "## Original payload", "", "```json", json.dumps(item.get("original_payload"), ensure_ascii=False, indent=2), "```", "", "## Effective payload", "", "```json", json.dumps(item.get("effective_payload"), ensure_ascii=False, indent=2), "```", "", "## Visible answer", "", item.get("output_text") or "(no visible answer)", ""]
                archive.writestr(f"conversations/{user_id}/{request_id}.md", "\n".join(lines).encode("utf-8"))
                if include_attachments:
                    for attachment in item.get("attachments", []):
                        stored = self.service.attachments.get(attachment["id"], request_id=request_id)
                        filename = Path(attachment["original_filename"]).name
                        archive.writestr(f"conversations/{user_id}/{request_id}/attachments/{attachment['id']}-{filename}", stored["content"])
        with self.service.db.transaction() as db:
            db.execute("INSERT INTO teacher_actions(id,actor_id,action,target_ids_json,result_json,created_at) VALUES(?,?,?,?,?,?)", (__import__("uuid").uuid4().hex, teacher_id, "export", json_dumps(user_ids), json_dumps({"export_id": export_id, "path": str(target), "request_count": len(requests)}), iso(self.service.now())))
        return target
