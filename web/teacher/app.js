'use strict';
const $=s=>document.querySelector(s),api='/api/classroom/v1',selected=new Set(),requests=new Map(),panels={};
let cursor=null,paused=false,busy=false,current=null,adjustment=null,activeView='review';
const newId=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
const headers=()=>{const h={'Content-Type':'application/json'},token=localStorage.getItem('token');if(token)h.Authorization='Bearer '+token;return h};
async function call(path,opts={}){const r=await fetch(api+path,{...opts,headers:{...headers(),...opts.headers}});const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error?.message||j.detail||'请求失败');return j}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function button(text,fn,cls='btn btn-sm'){const b=el('button',text,cls);b.onclick=()=>Promise.resolve().then(fn).catch(error);return b}
function notify(message,kind='info'){const n=$('#notice');n.textContent=message||'';n.className='notice notice-'+kind;n.hidden=!message;if(message&&kind!=='error'&&typeof setTimeout==='function')setTimeout(()=>{if(n.textContent===message)n.hidden=true},6000)}
function error(e){notify(e?.message||String(e),'error')}
$('#notice').onclick=()=>{$('#notice').hidden=true};

const viewTitles={review:'审核队列',students:'学生与额度',insights:'使用概况',roster:'名册导入',settings:'课堂设置'};
function showView(name){
  if(!viewTitles[name])name='review';
  activeView=name;
  for(const b of document.querySelectorAll('.nav-item'))b.className='nav-item'+(b.dataset.view===name?' active':'');
  for(const v of document.querySelectorAll('.view'))v.hidden=v.dataset.view!==name;
  $('#view-title').textContent=viewTitles[name];
  try{localStorage.setItem('classroom-teacher-view',name)}catch(_){}
  if(name==='settings')for(const p of Object.values(panels)){if(!p.loaded){p.loaded=true;Promise.resolve().then(p.load).catch(error)}}
  if(name==='insights'&&panels.insights&&!panels.insights.loaded){panels.insights.loaded=true;Promise.resolve().then(panels.insights.load).catch(error)}
  else if(name==='insights'&&panels.insights)Promise.resolve().then(panels.insights.load).catch(error);
}
for(const b of document.querySelectorAll('.nav-item'))b.onclick=()=>showView(b.dataset.view);

let studentRows=[],studentPage=1,studentPageSize=10;
try{const saved=Number(localStorage.getItem('classroom-student-page-size'));if([10,20,30,50].includes(saved))studentPageSize=saved}catch(_){}
const requestStates={pending:'待审核',approved_queued:'已批准排队',generating:'生成中',completed:'已完成',rejected:'已拒绝',expired:'已过期',interrupted:'已中断',cancelled_before_output:'已取消',stopped_by_student_after_output:'已停止',interrupted_unknown:'状态待确认'};
const studentName=id=>studentRows.find(s=>s.user_id===id)?.roster_name||id;
function formatTime(value){const d=new Date(value);return isNaN(d)?String(value??''):d.toLocaleString('zh-CN',{hour12:false,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}
function badge(status){return el('span',requestStates[status]||status,'badge badge-'+status)}
function questionText(item){
  const message=(item.original_payload?.messages||[]).filter(m=>m.role==='user').at(-1);
  if(typeof message?.content==='string')return message.content;
  if(Array.isArray(message?.content))return message.content.map(p=>p.type==='text'?p.text:'[图片附件]').filter(Boolean).join('\n');
  return '（请查看附件）';
}
function updateStudentSelection(){
  const visible=studentRows.slice((studentPage-1)*studentPageSize,studentPage*studentPageSize);
  const checked=visible.filter(s=>selected.has(s.user_id)).length;
  $('#selectall').checked=!!visible.length&&checked===visible.length;
  $('#selectall').indeterminate=checked>0&&checked<visible.length;
  $('#student-selection-info').textContent=`已选 ${selected.size} 人（保留跨页选择）`;
}
function renderStats(){
  $('#stat-total').textContent=String(studentRows.length);
  $('#stat-available').textContent=String(studentRows.reduce((n,s)=>n+(s.quota?.available||0),0));
  $('#stat-active').textContent=String(studentRows.filter(s=>s.active_request).length);
  $('#stat-paused').textContent=String(studentRows.filter(s=>!s.ai_enabled).length);
}
function renderStudents(){
  const pages=Math.max(1,Math.ceil(studentRows.length/studentPageSize));studentPage=Math.min(studentPage,pages);
  $('#student-page-size').value=String(studentPageSize);
  $('#student-page-info').textContent=`第 ${studentPage} / ${pages} 页，共 ${studentRows.length} 人`;
  $('#student-prev').disabled=studentPage<=1;$('#student-next').disabled=studentPage>=pages;
  const list=$('#students');list.textContent='';
  const visible=studentRows.slice((studentPage-1)*studentPageSize,studentPage*studentPageSize);
  if(!visible.length)list.append(el('div','还没有学生。请在「名册导入」中添加。','empty'));
  for(const student of visible){
    const row=el('div',undefined,'list-row student-row');
    const check=el('input');check.type='checkbox';check.checked=selected.has(student.user_id);
    check.onchange=()=>{if(check.checked)selected.add(student.user_id);else selected.delete(student.user_id);updateStudentSelection()};
    const info=el('div',undefined,'info');info.append(el('strong',student.roster_name),el('div',student.login_identifier,'login'));
    const quota=el('div',undefined,'quota');quota.append(el('div',`可用 ${student.quota.available} 次`,'quota-main'),el('div',`已用 ${student.quota.used} · 预留 ${student.quota.reserved}`,'quota-sub'));
    const state=el('div',undefined,'state');
    state.append(student.ai_enabled?el('span','AI 开启','badge badge-on'):el('span','AI 已暂停','badge badge-off'));
    if(student.active_request)state.append(badge(student.active_request.status));
    const actions=el('div',undefined,'row-actions');
    actions.append(
      button(student.ai_enabled?'暂停 AI':'启用 AI',async()=>{await call('/admin/students/'+student.user_id,{method:'PATCH',body:JSON.stringify({ai_enabled:!student.ai_enabled})});await load()},student.ai_enabled?'btn btn-sm btn-danger-outline':'btn btn-sm btn-primary'),
      button('改名',async()=>{const name=prompt('课堂姓名',student.roster_name);if(name){await call('/admin/students/'+student.user_id,{method:'PATCH',body:JSON.stringify({roster_name:name})});await load()}}),
      button('重置密码',()=>resetPassword(student.user_id)));
    row.append(check,info,quota,state,actions);list.append(row);
  }
  updateStudentSelection();renderStats();
}
$('#student-prev').onclick=()=>{if(studentPage>1){studentPage--;renderStudents()}};
$('#student-next').onclick=()=>{if(studentPage*studentPageSize<studentRows.length){studentPage++;renderStudents()}};
$('#student-page-size').onchange=()=>{const value=Number($('#student-page-size').value);if(![10,20,30,50].includes(value))return;studentPageSize=value;studentPage=1;try{localStorage.setItem('classroom-student-page-size',String(value))}catch(_){}renderStudents()};
$('#clear-student-selection').onclick=()=>{selected.clear();renderStudents()};

async function refreshStudents(){
  const s=await call('/admin/students');studentRows=s.students;
  const ids=new Set(studentRows.map(s=>s.user_id));for(const id of selected)if(!ids.has(id))selected.delete(id);
  renderStudents();
}
async function load({includeQueue=true,includeStudents=true}={}){
  if(busy)return;
  const detailOpen=!!$('#detail').open;
  const h=await call('/admin/health');paused=h.classroom_paused;
  const health=$('#health');health.className='pill '+(h.ready?'pill-ok':'pill-warn');
  health.textContent=(h.ready?'服务已就绪':'服务未就绪')+' · 时区 '+h.timezone+(paused?' · 全班已暂停':'');
  const pauseBtn=$('#pause');pauseBtn.textContent=paused?'恢复全班 AI':'暂停全班 AI';pauseBtn.className=paused?'btn btn-primary':'btn btn-danger';
  if(includeStudents)await refreshStudents();
  if(includeQueue&&!detailOpen&&activeView==='review')await queue(true);
}
let queueKey='';
async function queue(reset){
  const chosen=new Set([...document.querySelectorAll('#queue input:checked')].map(x=>x.dataset.id));
  const list=$('#queue');
  const status=$('#filter').value;
  const q=await call('/admin/requests?limit=30'+(status?'&status='+status:'')+(reset?'':(cursor?'&cursor='+encodeURIComponent(cursor):'')));
  if(reset){
    const key=status+'|'+q.requests.map(i=>i.id+':'+i.version+':'+i.status+':'+(i.review_channel||'')+':'+(i.decision_note||'')).join(',');
    if(key===queueKey&&list.querySelector?.('.request-row')){
      for(const item of q.requests)requests.set(item.id,item);
      return;
    }
    queueKey=key;
    cursor=null;list.textContent='';requests.clear();
  }
  const main=document.querySelector('.main');const keep=main?main.scrollTop:0;
  if(reset&&!q.requests.length)list.append(el('div',status==='pending'?'暂无待审核请求。':'没有符合条件的记录。','empty'));
  for(const item of q.requests){
    requests.set(item.id,item);
    const row=el('div',undefined,'list-row request-row'+(item.status==='pending'?' is-pending':''));
    const check=el('input');check.type='checkbox';check.dataset.id=item.id;check.checked=chosen.has(item.id);check.disabled=item.status!=='pending';
    const head=el('div',undefined,'row-head');head.append(el('strong',studentName(item.user_id)),badge(item.status));
    if(item.review_channel==='ai')head.append(el('span','AI 审','badge badge-generating'));
    else if(item.review_channel==='none')head.append(el('span','免审','badge badge-completed'));
    else if((item.decision_note||'').includes('AI 审核失败'))head.append(el('span','AI回退','badge badge-interrupted'));
    head.append(el('span',formatTime(item.submitted_at),'time'));
    const pre=el('pre',questionText(item),'question');
    const actions=el('div',undefined,'row-actions');
    actions.append(button('查看原文 / 附件',()=>detail(item),'btn btn-sm btn-ghost'));
    if(item.status==='pending')actions.append(
      button('批准',()=>decide(item,'approve'),'btn btn-sm btn-primary'),
      button('拒绝并扣 1 次',async()=>{const note=prompt('拒绝原因');if(note!==null)await decide(item,'reject',note)},'btn btn-sm btn-danger-outline'));
    if(['approved_queued','generating'].includes(item.status))actions.append(button('教师停止（不扣次）',async()=>{await call('/admin/requests/'+item.id+'/stop',{method:'POST',body:'{}'});await queue(true)}));
    row.append(check,head,pre,actions);list.append(row);
  }
  if(reset&&status==='pending'){const n=q.requests.length;$('#nav-pending').textContent=n?(n>=30?'30+':String(n)):''}
  const last=q.requests.at(-1);cursor=last?last.submitted_at+'|'+last.id:null;$('#more').hidden=q.requests.length<30;
  if(main)main.scrollTop=keep;
}
async function decide(item,decision,note='',edited_payload){
  if(item._busy)return;item._busy=true;
  try{
    await call('/admin/requests/'+item.id+'/decision',{method:'POST',body:JSON.stringify({decision,expected_version:item.version,note,edited_payload})});
    requests.delete(item.id);queueKey='';
    document.querySelector('#queue input[data-id="'+item.id+'"]')?.closest('.list-row')?.remove();
    await queue(true);
  }finally{item._busy=false}
}
async function detail(item){
  current=item;
  $('#detail-title').textContent=studentName(item.user_id)+' · '+(requestStates[item.status]||item.status);
  $('#original').textContent='学生本次提问：\n'+questionText(item)+(item.output_text?'\n\n回答：\n'+item.output_text:'');
  const payload=structuredClone(item.original_payload);payload.messages=[payload.messages.filter(m=>m.role==='user').at(-1)];payload.attachments=item.attachments.map(a=>({id:a.id,sha256:a.sha256}));
  $('#edited').value=JSON.stringify(payload,null,2);$('#note').value='';
  $('#attachments').textContent='';
  for(const a of item.attachments){
    const link=el('a',a.original_filename+' · '+a.size_bytes+' bytes');link.href=api+'/attachments/'+a.id+'/content?download=true';link.target='_blank';link.rel='noopener';$('#attachments').append(link);
    if(a.media_type.startsWith('image/')){const img=el('img');img.src=api+'/attachments/'+a.id+'/content';$('#attachments').append(img)}
    else{const res=await fetch(api+'/attachments/'+a.id+'/content',{headers:headers()});if(!res.ok)throw new Error('附件读取失败');const buffer=await res.arrayBuffer();$('#attachments').append(el('pre',new TextDecoder(a.text_encoding||'utf-8').decode(buffer)))}
  }
  $('#editapprove').disabled=item.status!=='pending';$('#detail').showModal();
}
async function bulk(decision){
  const rows=[...document.querySelectorAll('#queue input:checked')].map(x=>requests.get(x.dataset.id)).filter(Boolean);
  if(!rows.length)throw new Error('请先勾选待审核的请求');
  if(!confirm(`确认${decision==='approve'?'批准':'拒绝并扣次'} ${rows.length} 项请求？`))return;
  const r=await call('/admin/requests/bulk-decision',{method:'POST',body:JSON.stringify({decision,requests:rows.map(x=>({id:x.id,version:x.version}))})});
  const failed=r.results.filter(x=>!x.result);
  if(failed.length)notify(`已处理 ${r.results.length-failed.length} 项，${failed.length} 项失败：`+failed.map(x=>x.error?.message||x.id).join('；'),'error');
  else notify(`已处理 ${r.results.length} 项请求`);
  await load();
}
async function adjust(delta){
  if(!Number.isInteger(delta)||delta===0)throw new Error('请输入非零整数');
  if(!selected.size)throw new Error('请先选择学生');
  busy=true;
  try{
    if(!adjustment){
      const ids=[...selected],preview=await call('/admin/quotas/preview',{method:'POST',body:JSON.stringify({user_ids:ids,delta})});
      $('#quota-status').textContent=preview.rows.map(r=>studentName(r.user_id)+'：'+r.before.available+' → '+r.after_available).join('；');
      if(!preview.valid)throw new Error('部分学生额度不足，未做任何修改');
      if(!confirm('确认上述额度调整？'))return;
      adjustment={key:newId(),body:{user_ids:ids,delta,date:preview.date,expected_versions:Object.fromEntries(preview.rows.map(r=>[r.user_id,r.before.version])),reason:$('#reason').value}};
    }
    await call('/admin/quotas/adjust',{method:'POST',headers:{'Idempotency-Key':adjustment.key},body:JSON.stringify(adjustment.body)});
    adjustment=null;$('#quota-status').textContent='';notify('额度调整已完成');
  }finally{busy=false}
  await load();
}
async function resetPassword(id){
  const password=prompt('输入临时密码（至少八位）');if(password===null)return;
  await call('/admin/students/'+id+'/reset-password',{method:'POST',body:JSON.stringify({new_password:password})});
  notify('密码已重置，旧会话已撤销。学生须重新登录并改密。');
}
$('#selectall').onchange=()=>{const checked=$('#selectall').checked;for(const c of document.querySelectorAll('#students input[type=checkbox]')){c.checked=checked;c.onchange()}};
$('#plus').onclick=()=>adjust(1).catch(error);$('#minus').onclick=()=>adjust(-1).catch(error);$('#custom').onclick=()=>adjust(Number($('#delta').value)).catch(error);
$('#approveall').onclick=()=>bulk('approve').catch(error);$('#rejectall').onclick=()=>bulk('reject').catch(error);
$('#filter').onchange=()=>queue(true).catch(error);$('#more').onclick=()=>queue(false).catch(error);$('#refresh').onclick=()=>load().catch(error);
$('#pause').onclick=async()=>{try{await call('/admin/classroom/state',{method:'PUT',body:JSON.stringify({paused:!paused,reason:'教师课堂控制'})});await load()}catch(e){error(e)}};
$('#close').onclick=()=>$('#detail').close();
$('#editapprove').onclick=async()=>{try{const edited=JSON.parse($('#edited').value);await decide(current,'edit',$('#note').value,edited);$('#detail').close();await load()}catch(e){error(e)}};

let importPreview=null;
const importErrors={INVALID_NAME:'姓名不能为空，最多 120 字',INVALID_EMAIL:'账号格式不正确，例如 zhangsan@a.b',DUPLICATE_EMAIL:'文件内账号重复',WEAK_INITIAL_PASSWORD:'初始密码至少 8 位',ROLE_NOT_ALLOWED:'Role 必须填写 user',ACCOUNT_EXISTS:'账号已存在',NATIVE_ACCOUNT_OPERATION_FAILED:'Open WebUI 拒绝创建，请检查账号和密码',NATIVE_ACCOUNT_UNAVAILABLE:'账号服务暂时不可用，请稍后重新预览并重试'};
function importMessage(code){return importErrors[code]||('未能导入：'+code)}
function resetImportPreview(){importPreview=null;$('#commit-import').hidden=true;$('#commit-import').disabled=true;$('#import-preview').textContent='';$('#import-status').textContent='';$('#account-status').textContent=''}
$('#roster').onchange=resetImportPreview;
$('#import').onclick=async()=>{
  if(busy)return;busy=true;resetImportPreview();$('#import').disabled=true;$('#roster').disabled=true;
  try{
    const file=$('#roster').files[0];if(!file)throw new Error('请先选择 CSV 文件');
    let content;try{content=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer())}catch{throw new Error('文件不是 UTF-8 编码，请在 Excel 中另存为 CSV UTF-8 后重试')}
    const p=await call('/admin/accounts/import/preview',{method:'POST',body:JSON.stringify({content})});
    const table=el('table'),head=el('tr');for(const title of ['CSV 行号','姓名','登录账号','角色','校验结果'])head.append(el('th',title));table.append(head);
    for(const r of p.rows){const tr=el('tr');if(r.error_code)tr.className='error';for(const value of [r.row_number,r.name,r.email,r.role,r.error_code?importMessage(r.error_code):'可导入'])tr.append(el('td',String(value)));table.append(tr)}
    $('#import-preview').append(table);const valid=p.rows.filter(r=>!r.error_code).length;
    $('#import-status').textContent=`共 ${p.rows.length} 人，可导入 ${valid} 人，需要修改 ${p.rows.length-valid} 人。`+(valid?'请检查下表，再点击确认导入；错误行会跳过。':'没有有效行，请修改文件后重新选择并预览。');
    importPreview=p;$('#commit-import').hidden=false;$('#commit-import').disabled=!valid;
  }catch(e){$('#import-status').textContent=e.message}finally{busy=false;$('#import').disabled=false;$('#roster').disabled=false}
};
$('#commit-import').onclick=async()=>{
  if(busy||!importPreview)return;busy=true;$('#commit-import').disabled=true;$('#import').disabled=true;$('#roster').disabled=true;
  try{
    const p=importPreview,result=await call('/admin/accounts/import/'+p.batch_id+'/commit',{method:'POST',body:'{}'});
    const done=result.results.filter(r=>r.status==='completed').length,failed=result.results.filter(r=>r.status!=='completed'),skipped=p.rows.filter(r=>r.error_code).length;
    $('#import-status').textContent=`导入成功 ${done} 人，失败 ${failed.length} 人，跳过无效行 ${skipped} 人。`;
    $('#account-status').textContent=failed.map(r=>`第 ${r.row_number} 行：${importMessage(r.error_code)}`).join('\n');
    importPreview=null;$('#commit-import').hidden=true;
    if(!failed.length&&!skipped)$('#roster').value='';
  }catch(e){$('#import-status').textContent=e.message+' 请重新预览后重试。';importPreview=null;$('#commit-import').hidden=true}
  finally{busy=false;$('#import').disabled=false;$('#roster').disabled=false}await load().catch(error)
};
$('#export').onclick=async()=>{try{const r=await call('/admin/exports',{method:'POST',body:JSON.stringify({include_attachments:true,user_ids:selected.size?[...selected]:undefined})});const a=el('a','下载导出 ZIP');a.href=r.download;$('#export-status').replaceChildren(a);a.click()}catch(e){error(e)}};
function csvEscape(value){const text=String(value??'');return /["\n\r,]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text}
$('#add-student').onclick=async()=>{
  if(busy)return;
  const name=($('#single-name').value||'').trim(),email=($('#single-email').value||'').trim(),password=$('#single-password').value||'';
  if(!name)return notify('请填写姓名','error');
  if(!email)return notify('请填写登录账号','error');
  if(password.length<8)return notify('初始密码至少 8 位','error');
  busy=true;$('#add-student').disabled=true;$('#import-status').textContent='正在添加…';
  try{
    const content=['Name,Email,Password,Role',[csvEscape(name),csvEscape(email),csvEscape(password),'user'].join(',')].join('\n');
    const preview=await call('/admin/accounts/import/preview',{method:'POST',body:JSON.stringify({content})});
    const bad=preview.rows.find(r=>r.error_code);
    if(bad)throw new Error(importMessage(bad.error_code));
    const result=await call('/admin/accounts/import/'+preview.batch_id+'/commit',{method:'POST',body:'{}'});
    const row=result.results[0];
    if(!row||row.status!=='completed')throw new Error(importMessage(row?.error_code||'NATIVE_ACCOUNT_OPERATION_FAILED'));
    $('#import-status').textContent='已添加学生 '+name+'（'+email+'）。对方首次登录须修改密码。';
    $('#single-name').value='';$('#single-email').value='';$('#single-password').value='';
    busy=false;await load();
  }catch(e){$('#import-status').textContent=e.message;error(e)}
  finally{busy=false;$('#add-student').disabled=false}
};

let initialView='review';try{initialView=localStorage.getItem('classroom-teacher-view')||'review'}catch(_){}
showView(initialView);
load().catch(error);setInterval(()=>{
  if(busy||document.hidden)return;
  if(activeView==='review')load({includeStudents:false}).catch(error);
  else if(activeView==='students')load({includeQueue:false}).catch(error);
  else load({includeQueue:false,includeStudents:false}).catch(error);
},2000);
