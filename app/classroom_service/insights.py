"""Teacher insights: keyword frequency and today's classroom usage overview."""

from __future__ import annotations

import re
from collections import Counter

from .ai_auditor import extract_question_text
from .clock import local_date_and_next_midnight, parse_iso, teacher_zone
from .database import json_loads

STOPWORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "这", "那", "有", "在", "和", "与", "或", "及",
    "就", "都", "也", "很", "还", "又", "被", "把", "让", "给", "从", "到", "对", "为", "以", "而",
    "什么", "怎么", "怎样", "为什么", "哪个", "哪些", "一个", "一些", "可以", "没有", "不是", "一下",
    "请问", "老师", "同学", "帮我", "帮忙", "谢谢", "如何", "是否", "因为", "所以", "然后", "但是",
    "如果", "已经", "自己", "这个", "那个", "这样", "那样", "我们", "你们", "他们", "什么是",
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on", "for", "with", "how", "what",
    "why", "this", "that", "please", "help", "code",
}

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_+#\-]{1,}")

# Only questions that already passed review. Restart turns generating -> interrupted_unknown;
# those still count. Pending / rejected / expired leftover rows never do.
_KEYWORD_STATUSES = {
    "approved_queued",
    "generating",
    "completed",
    "stopped_by_student_after_output",
    "interrupted",
    "interrupted_unknown",
}
_BLOCKED_DECISIONS = {None, "", "reject"}


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    counts: list[str] = []
    for run in _CJK_RUN.findall(text):
        if len(run) <= 4 and run not in STOPWORDS:
            counts.append(run)
        for n in (2, 3):
            if len(run) < n:
                continue
            for i in range(len(run) - n + 1):
                gram = run[i:i + n]
                if gram not in STOPWORDS:
                    counts.append(gram)
    for token in _LATIN.findall(text):
        lower = token.lower()
        if lower not in STOPWORDS and len(lower) >= 2:
            counts.append(lower)
    return counts


def build_insights(service, *, range_name: str = "today") -> dict:
    now = service.now()
    if range_name != "today":
        range_name = "today"
    day, _ = local_date_and_next_midnight(now, service.timezone_name)
    zone = teacher_zone(service.timezone_name)
    rows = service.db.query_all(
        "SELECT id,user_id,status,review_channel,submitted_at,decided_at,decision_kind,original_snapshot_id "
        "FROM review_requests WHERE quota_date=? ORDER BY submitted_at",
        (day,),
    )
    status_counts = Counter()
    ai_counts = Counter()
    hourly = [0] * 24
    per_student = Counter()
    wait_seconds: list[float] = []
    words = Counter()
    for row in rows:
        status_counts[row["status"]] += 1
        per_student[row["user_id"]] += 1
        channel = row["review_channel"] if "review_channel" in row.keys() else "teacher"
        if channel == "ai":
            if row["status"] == "rejected":
                ai_counts["rejected"] += 1
            elif row["status"] == "pending":
                ai_counts["pending"] += 1
            elif row["status"] not in {"expired", "cancelled_before_output"}:
                ai_counts["approved"] += 1
        if row["submitted_at"]:
            try:
                hour = parse_iso(row["submitted_at"]).astimezone(zone).hour
                hourly[hour] += 1
            except Exception:
                pass
        if row["decided_at"] and row["submitted_at"]:
            try:
                a = parse_iso(row["submitted_at"])
                b = parse_iso(row["decided_at"])
                wait_seconds.append(max(0.0, (b - a).total_seconds()))
            except Exception:
                pass
        snap = service.db.query_one("SELECT payload_json FROM snapshots WHERE id=?", (row["original_snapshot_id"],))
        kind = row["decision_kind"] if "decision_kind" in row.keys() else None
        if snap and row["status"] in _KEYWORD_STATUSES and kind not in _BLOCKED_DECISIONS:
            payload = json_loads(snap["payload_json"], {})
            for term in tokenize(extract_question_text(payload)):
                words[term] += 1

    names = {
        r["user_id"]: r["roster_name"]
        for r in service.db.query_all("SELECT user_id,roster_name FROM students")
    }
    top_students = [
        {"user_id": uid, "roster_name": names.get(uid, uid), "count": count}
        for uid, count in per_student.most_common(15)
    ]
    keywords = [{"term": term, "count": count} for term, count in words.most_common(80)]
    total = len(rows)
    rejected = status_counts.get("rejected", 0)
    approved_like = (
        status_counts.get("approved_queued", 0)
        + status_counts.get("generating", 0)
        + status_counts.get("completed", 0)
        + status_counts.get("stopped_by_student_after_output", 0)
    )
    return {
        "range": range_name,
        "quota_date": day,
        "review_mode": service.get_review_mode()["mode"],
        "summary": {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "approved": approved_like,
            "rejected": rejected,
            "completed": status_counts.get("completed", 0) + status_counts.get("stopped_by_student_after_output", 0),
            "generating": status_counts.get("generating", 0) + status_counts.get("approved_queued", 0),
            "reject_rate": round(rejected / total, 3) if total else 0.0,
            "avg_wait_seconds": round(sum(wait_seconds) / len(wait_seconds), 1) if wait_seconds else None,
            "ai_approved": ai_counts.get("approved", 0),
            "ai_rejected": ai_counts.get("rejected", 0),
            "ai_pending": ai_counts.get("pending", 0),
        },
        "hourly": hourly,
        "top_students": top_students,
        "keywords": keywords,
    }
