"""Preflight and identity repair for schema v5. The v5 SQL checksum is frozen."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PREFLIGHT_CODE = "SCHEMA_V5_PREFLIGHT"


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def inspect_v5_identity_gaps(db: sqlite3.Connection) -> dict:
    """List attachment and native-file user ids that lack security_states."""
    gaps = {
        "attachment_owners": [],
        "native_users": [],
        "repairable_students": [],
        "repairable_teachers": [],
        "unknown": [],
    }
    if not _table_exists(db, "attachments") or not _table_exists(db, "security_states"):
        return gaps
    owners = [row[0] for row in db.execute(
        "SELECT DISTINCT owner_user_id FROM attachments WHERE owner_user_id NOT IN (SELECT user_id FROM security_states)"
    )]
    native_users = []
    if _table_exists(db, "native_attachments"):
        native_users = [row[0] for row in db.execute(
            "SELECT DISTINCT user_id FROM native_attachments WHERE user_id NOT IN (SELECT user_id FROM security_states)"
        )]
    gaps["attachment_owners"] = owners
    gaps["native_users"] = native_users
    missing = list(dict.fromkeys(owners + native_users))
    students = {row[0] for row in db.execute("SELECT user_id FROM students")} if _table_exists(db, "students") else set()
    teachers = set()
    if _table_exists(db, "teacher_actions"):
        teachers = {row[0] for row in db.execute(
            "SELECT DISTINCT actor_id FROM teacher_actions WHERE action='teacher_registered' AND actor_id IS NOT NULL"
        )}
    for user_id in missing:
        if user_id in students:
            gaps["repairable_students"].append(user_id)
        elif user_id in teachers:
            gaps["repairable_teachers"].append(user_id)
        else:
            gaps["unknown"].append(user_id)
    return gaps


def format_preflight_error(gaps: dict) -> str:
    owners = len(gaps["attachment_owners"])
    native = len(gaps["native_users"])
    unknown = gaps["unknown"]
    repairable = len(gaps["repairable_students"]) + len(gaps["repairable_teachers"])
    unknown_text = "、".join(unknown[:8]) + ("…" if len(unknown) > 8 else "")
    extra = f" 无法自动修复的身份：{unknown_text}。" if unknown else ""
    return (
        f"{PREFLIGHT_CODE}: 升级到课堂库 v5 前发现 {owners} 个附件主人、{native} 个原生文件映射用户缺少 security_states"
        f"（其中 {repairable} 个可由名册或已登记教师修复）。"
        "请先联合备份，再运行 scripts/Repair-V5Identities.ps1 查看修复指引；"
        "不要删除附件，也不要手工插入可登录账号。"
        f"{extra}"
    )


def preflight_schema_v5(db: sqlite3.Connection) -> None:
    gaps = inspect_v5_identity_gaps(db)
    if gaps["attachment_owners"] or gaps["native_users"]:
        raise RuntimeError(format_preflight_error(gaps))


def repair_v5_identities(path: str | Path, *, apply: bool = False) -> dict:
    """Backfill security_states only for enrolled students or registered teachers."""
    db_path = Path(path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        gaps = inspect_v5_identity_gaps(connection)
        repaired = []
        if apply:
            now_text = datetime.now(timezone.utc).isoformat()
            connection.execute("BEGIN IMMEDIATE")
            try:
                for user_id in gaps["repairable_students"] + gaps["repairable_teachers"]:
                    connection.execute(
                        "INSERT OR IGNORE INTO security_states(user_id,must_change_password,auth_epoch,"
                        "credential_operation_state,updated_at) VALUES(?,0,0,'ready',?)",
                        (user_id, now_text),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0]:
                        repaired.append(user_id)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            gaps = inspect_v5_identity_gaps(connection)
        blocking = bool(gaps["attachment_owners"] or gaps["native_users"])
        return {
            "database": str(db_path),
            "apply": apply,
            "repaired": repaired,
            "gaps": gaps,
            "ready_for_v5": not blocking,
            "guidance": (
                "已具备 v5 升级条件。"
                if not blocking
                else "仍有缺少安全身份的附件或原生映射。仅当用户已在学生名册或 teacher_registered 记录中时才会补 security_states；"
                     "未知身份需要人工核验后加入名册或登记教师，然后再次运行本工具。不要删除附件。"
            ),
        }
    finally:
        connection.close()


def main() -> None:  # pragma: no cover - command wrapper
    parser = argparse.ArgumentParser(description="Inspect or repair identities required by classroom schema v5")
    parser.add_argument("--db", required=True)
    parser.add_argument("--apply", action="store_true", help="backfill security_states for enrolled students and registered teachers")
    args = parser.parse_args()
    result = repair_v5_identities(args.db, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ready_for_v5"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
