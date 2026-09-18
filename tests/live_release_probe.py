"""HTTP acceptance against a fresh, isolated release instance; no provider call."""
import io
import json
import os
import sys
import urllib.request
import urllib.error
import zipfile

base=sys.argv[1].rstrip('/')
def call(method,path,body=None,token='',extra=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    headers.update(extra or {})
    raw=json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,data=raw,headers=headers,method=method),timeout=30) as response:
            raw=response.read()
            return response.status, json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw
    except urllib.error.HTTPError as error:
        return error.code, error.read()

def login(email,password):
    code,value=call('POST','/api/v1/auths/signin',{'email':email,'password':password})
    assert code==200,('login',code)
    return value['token']

teacher=login(os.environ['WEBUI_ADMIN_EMAIL'],os.environ['WEBUI_ADMIN_PASSWORD'])
code,preview=call('POST','/api/classroom/v1/admin/accounts/import/preview',{'content':'Name,Email,Password,Role\nHTTP Student,http-student@test.invalid,Initial-test-12345,user\n'},teacher)
assert code==200,('preview',code)
path='/api/classroom/v1/admin/accounts/import/'+preview['batch_id']+'/commit'
code,committed=call('POST',path,{},teacher)
assert code==200 and committed['status']=='completed',('commit',code,committed)
code,replayed=call('POST',path,{},teacher)
assert code==200 and replayed==committed
student=login('http-student@test.invalid','Initial-test-12345')
code,me=call('GET','/api/classroom/v1/me',token=student)
assert code==200 and me['must_change_password']
code,_=call('POST','/api/v1/auths/update/password',{'password':'Initial-test-12345','new_password':'Changed-test-67890'},student)
assert code==200,('change',code)
assert call('GET','/api/classroom/v1/me',token=student)[0]==401
student=login('http-student@test.invalid','Changed-test-67890')
code,me=call('GET','/api/classroom/v1/me',token=student)
assert code==200 and not me['must_change_password']
payload={'payload':{'model':me['allowed_models'][0],'messages':[{'role':'user','content':'Isolated release rejection test'}]}}
code,row=call('POST','/api/classroom/v1/requests',payload,student,{'Idempotency-Key':'release-http-request'})
assert code==200,('submit',code)
code,_=call('POST','/api/classroom/v1/admin/requests/'+row['id']+'/decision',{'decision':'reject','expected_version':row['version']},teacher)
assert code==200,('reject',code)
code,me=call('GET','/api/classroom/v1/me',token=student)
assert code==200 and me['quota']['used']==1 and me['quota']['reserved']==0
code,export=call('POST','/api/classroom/v1/admin/exports',{'include_attachments':True},teacher)
assert code==200,('export',code)
code,archive=call('GET',export['download'],token=teacher)
assert code==200,('download',code)
with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
    assert bundle.testzip() is None
    assert json.loads(bundle.read('manifest.json'))['request_count']==1
print('LIVE_RELEASE_IMPORT_PASSWORD_REJECTION_QUOTA_EXPORT_OK')
