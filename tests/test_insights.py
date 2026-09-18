"""Insights keyword extraction and summary."""
from classroom.app.classroom_service.insights import tokenize, build_insights


def test_tokenize_extracts_cjk_and_latin():
    tokens = tokenize('请解释一下什么是二分查找 binary search 算法')
    assert '二分' in tokens or '查找' in tokens
    assert 'binary' in tokens or 'search' in tokens
    assert '什么' not in tokens


def test_insights_empty_day(service):
    service.set_ready(True)
    data = build_insights(service)
    assert data['summary']['total'] == 0
    assert data['keywords'] == []
    assert data['hourly'] == [0] * 24
    assert data['review_mode'] in {'teacher', 'ai', 'none'}


def test_insights_with_request(service):
    service.set_ready(True)
    service.submit('student-1', 'op-ins-1', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '请解释递归与分治算法'}],
    }, chat_id='c-ins')
    pending = service.classroom_insights()
    assert pending['summary']['total'] == 1
    assert pending['summary']['pending'] == 1
    assert pending['keywords'] == []
    service.set_review_mode('teacher-1', 'none', service.get_review_mode()['version'])
    service.submit('student-2', 'op-ins-2', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '请解释递归与分治算法'}],
    }, chat_id='c-ins-2')
    data = service.classroom_insights()
    assert data['summary']['approved'] == 1
    assert data['top_students']
    assert data['keywords']


def test_rejected_questions_not_in_keywords(service):
    service.set_ready(True)
    request = service.submit('student-1', 'op-ins-rej', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '请解释递归与分治算法'}],
    }, chat_id='c-ins-rej')
    service.decide(request['id'], 'teacher-1', 'reject', expected_version=request['version'], note='不通过')
    data = service.classroom_insights()
    assert data['summary']['rejected'] == 1
    assert data['keywords'] == []


def test_pending_survives_restart_without_entering_keywords(service):
    service.set_ready(True)
    pending = service.submit('student-1', 'op-ins-pending-restart', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '哈吉米南北绿豆独有词云探测'}],
    }, chat_id='c-ins-pending-restart')
    assert pending['status'] == 'pending'
    service.recover_after_restart()
    data = service.classroom_insights()
    assert data['summary']['pending'] == 1
    terms = {item['term'] for item in data['keywords']}
    assert '哈吉米' not in terms
    assert '绿豆' not in terms
    assert data['keywords'] == []


def test_approved_then_restart_keeps_only_approved_keywords(service):
    from classroom.app.classroom_service.worker import ClassroomWorker, RecordingUpstream

    service.set_ready(True)
    pending = service.submit('student-1', 'op-ins-keep-pending', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '哈吉米南北绿豆独有词云探测'}],
    }, chat_id='c-pending-keep')
    queued = service.submit('student-2', 'op-ins-keep-approved', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '请解释二叉搜索树旋转'}],
    }, chat_id='c-approved-keep')
    queued = service.decide(queued['id'], 'teacher-1', 'approve', expected_version=queued['version'])
    ClassroomWorker(service, RecordingUpstream(default=['ok'])).run_one()
    generating = service.submit('student-2', 'op-ins-keep-generating', {
        'model': 'classroom-default',
        'messages': [{'role': 'user', 'content': '请说明红黑树插入修复'}],
    }, chat_id='c-approved-keep')
    generating = service.decide(generating['id'], 'teacher-1', 'approve', expected_version=generating['version'])
    claimed = service.claim_next()
    assert claimed and claimed['request']['id'] == generating['id']
    service.recover_after_restart()
    fresh_pending = service.get_request(pending['id'])
    fresh_generating = service.get_request(generating['id'])
    assert fresh_pending['status'] == 'pending'
    assert fresh_generating['status'] == 'interrupted_unknown'
    data = service.classroom_insights()
    blob = ' '.join(item['term'] for item in data['keywords'])
    assert '哈吉米' not in blob
    assert '绿豆' not in blob
    assert '二叉' in blob or '搜索' in blob or '红黑' in blob or '插入' in blob
