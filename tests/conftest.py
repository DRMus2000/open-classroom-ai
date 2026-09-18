from datetime import datetime, timezone

import pytest

from classroom.app.classroom_service import ClassroomDB, ClassroomService
from classroom.app.classroom_service.clock import FixedClock


@pytest.fixture
def service(tmp_path):
    clock = FixedClock(datetime(2026, 9, 8, 1, 0, tzinfo=timezone.utc), "Asia/Shanghai")
    db = ClassroomDB()
    app = ClassroomService(db, data_root=tmp_path, timezone_name="Asia/Shanghai", allowed_models={"classroom-default"}, clock=clock)
    app.enroll_student("student-1", "学生一", "student1@classroom.local", must_change_password=False)
    app.enroll_student("student-2", "学生二", "student2@classroom.local", must_change_password=False)
    app.register_teacher("teacher-1")
    yield app
    db.close()
