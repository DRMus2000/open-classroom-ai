"""One process owns dispatch, recovery and the classroom database lifecycle."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from .clock import iso, parse_iso

from .worker import ClassroomWorker
from .ai_auditor import AIAuditor


class InstanceLock:
    """OS lock released by process exit, including an unclean shutdown."""
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            handle.close()
            raise RuntimeError("another classroom service owns this data directory") from None
        self.file = handle
        return self

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


class ClassroomRuntime:
    def __init__(self, service, upstream, *, interval=0.25):
        self.service = service
        self.worker = ClassroomWorker(service, upstream)
        self.auditor = AIAuditor(service, upstream)
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None
        self.failure = None
        self.futures = set()
        self.pool = None
        self.high_water = None
        self.last_cleanup = None
        service.set_ready(False)

    def start(self):
        if self.thread is not None:
            raise RuntimeError("runtime already started")
        # Caller holds InstanceLock before opening the DB or running recovery.
        self.service.recover_after_restart()
        self.check_health()
        self.service.quota.expire_pending()
        self.service.sessions.cleanup()
        self.pool = ThreadPoolExecutor(max_workers=self.service.max_concurrency, thread_name_prefix="classroom-executor")
        self.service.set_ready(True)
        self.thread = threading.Thread(target=self._loop, name="classroom-scheduler", daemon=True)
        self.thread.start()

    def _loop(self):
        try:
            while not self.stop_event.is_set():
                self.check_health()
                self.service.quota.expire_pending()
                now = self.service.now()
                if self.last_cleanup is None or (now - self.last_cleanup).total_seconds() >= 3600:
                    self.service.attachments.cleanup_temporary()
                    self.service.sessions.cleanup()
                    self.last_cleanup = now
                self.auditor.tick()
                for future in tuple(self.futures):
                    if future.done():
                        future.result()
                        self.futures.remove(future)
                for _ in range(self.service.max_concurrency - len(self.futures)):
                    self.futures.add(self.pool.submit(self.worker.run_one))
                self.stop_event.wait(self.interval)
        except Exception as exc:
            self.failure = type(exc).__name__
            self.service.set_ready(False)
            self.stop_event.set()

    def check_health(self):
        now = self.service.now()
        with self.service.db.transaction() as db:
            row = db.execute("SELECT value_json FROM classroom_settings WHERE key='clock_high_water'").fetchone()
            previous = parse_iso(__import__('json').loads(row[0])) if row else None
            if previous and (previous - now).total_seconds() > 5:
                raise RuntimeError("system clock moved backwards; restore teacher clock before resuming")
            if previous is None or now > previous:
                db.execute("INSERT INTO classroom_settings(key,value_json,version,updated_at,updated_by) VALUES('clock_high_water',?,1,?,'system') ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (__import__('json').dumps(iso(now)), iso(now)))
            mismatch = db.execute("""SELECT q.user_id FROM daily_quotas q LEFT JOIN
                (SELECT user_id,quota_date,SUM(delta_used) used,SUM(delta_reserved) reserved,SUM(delta_adjustment) adjustment
                 FROM quota_ledger GROUP BY user_id,quota_date) l
                ON l.user_id=q.user_id AND l.quota_date=q.quota_date
                WHERE q.used<>COALESCE(l.used,0) OR q.reserved<>COALESCE(l.reserved,0)
                   OR q.adjustment<>COALESCE(l.adjustment,0) LIMIT 1""").fetchone()
            if mismatch:
                raise RuntimeError("quota ledger reconciliation failed")

    def close(self):
        self.stop_event.set()
        self.service.set_ready(False)
        if self.thread:
            self.thread.join()
        rows = self.service.db.query_all("SELECT id,user_id FROM review_requests WHERE status='generating'")
        for row in rows:
            self.service.cancel(row["id"], row["user_id"], source="maintenance")
        if self.pool:
            # Do not release the instance lock until every transport has closed.
            self.pool.shutdown(wait=True)
