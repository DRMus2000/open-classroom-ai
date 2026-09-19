'use strict';
const $=s=>document.querySelector(s),api='/api/classroom/v1';
const labels={pending:'等待老师审核',pending_ai:'等待 AI 审核',approved_queued:'已进入生成队列',generating:'正在回答',completed:'已完成',rejected:'老师未批准这次提问',rejected_ai:'AI助教未批准这次提问',expired:'请求已过期',interrupted:'回答中断，请重新提问',interrupted_unknown:'回答状态待确认',cancelled_before_output:'已取消',stopped_by_student_after_output:'已停止回答'};
const running=r=>r&&['pending','approved_queued','generating'].includes(r.status);
const continuable=r=>r&&['completed','stopped_by_student_after_output'].includes(r.status);
const newId=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
const records=new Map();let me=null,chat=newId(),thread=[],parent=null,active=null,pending=null,storageKey=null,files=[],sending=false,cursor=null,loadingThread=false,opening=0;
let eventAfter=0,streamText='',streamId=null,lastMeAt=0,lastStatusAt=0,mdTimer=null;
const headers=()=>{const h={'Content-Type':'application/json'},token=localStorage.getItem('token');if(token)h.Authorization='Bearer '+token;return h};
async function call(path,options={}){const response=await fetch(api+path,{...options,headers:{...headers(),...options.headers}});const data=await response.json().catch(()=>({}));if(!response.ok){const e=new Error(data.error?.message||data.detail||'连接暂时不可用，请稍后重试');e.status=response.status;throw e}return data}
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function status(text='',error=false){$('#status').textContent=text;$('#status').className='status'+(error?' error':'')}
function question(r){const m=(r.original_payload?.messages||[]).filter(m=>m.role==='user').at(-1);return typeof m?.content==='string'?m.content:(m?.content||[]).filter(p=>p.type==='text').map(p=>p.text).join('\n')}
function statusLabel(r){if(!r)return '';if(r.status==='pending'&&r.review_channel==='ai')return labels.pending_ai;if(r.status==='rejected'&&r.review_channel==='ai')return labels.rejected_ai;return labels[r.status]||r.status}
const md=window.markdownit({html:false,linkify:false,breaks:true});
md.renderer.rules.image=(tokens,index)=>'<span class="attachment-tag">图片：'+md.utils.escapeHtml(tokens[index].content||'图片')+'</span>';
md.renderer.rules.fence=(tokens,index)=>{const t=tokens[index],lang=(t.info||'').trim().split(/\s+/)[0];return '<div class="codeblock"><div class="codebar"><span>'+md.utils.escapeHtml(lang||'代码')+'</span><button type="button" class="copy-code">复制</button></div><pre><code>'+md.utils.escapeHtml(t.content)+'</code></pre></div>'};
const renderLink=md.renderer.rules.link_open||((tokens,index,options,env,self)=>self.renderToken(tokens,index,options));
md.renderer.rules.link_open=(tokens,index,options,env,self)=>{tokens[index].attrSet('target','_blank');tokens[index].attrSet('rel','noopener noreferrer');return renderLink(tokens,index,options,env,self)};
async function copyText(text,button){try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text)}else{const t=node('textarea');t.value=text;t.style.position='fixed';t.style.opacity='0';document.body.append(t);t.select();const copied=document.execCommand('copy');t.remove();if(!copied)throw new Error('copy failed')}button.textContent='已复制';setTimeout(()=>button.textContent='复制',1600)}catch{button.textContent='请选中文字复制'}}
function markdown(target,text){target.innerHTML=md.render(text);target.querySelectorAll('.copy-code').forEach(b=>b.onclick=()=>copyText(b.closest('.codeblock').querySelector('code').textContent,b))}
function rememberPending(){if(storageKey){if(pending)sessionStorage.setItem(storageKey,JSON.stringify(pending));else sessionStorage.removeItem(storageKey)}}
function updateCharCount(){
  const box=$('#char-count'); if(!box)return;
  const n=($('#prompt').value||'').length;
  box.textContent=n+' / 1000';
  if(typeof box.classList.toggle==='function') box.classList.toggle('warn',n>=970);
  else if(n>=970) box.classList.add('warn'); else box.classList.remove('warn');
}
function resizePrompt(){$('#prompt').style.height='auto';$('#prompt').style.height=Math.min($('#prompt').scrollHeight,160)+'px'}
function updateControls(){const locked=!me||me.must_change_password||me.classroom_paused||!!active||sending||loadingThread;
  $('#send').disabled=locked;$('#prompt').disabled=!!me?.must_change_password||sending||!!pending;$('#attach').disabled=locked||!!pending;$('#newchat').disabled=sending||!!active||loadingThread;
  $('#stop').hidden=!active||!!me?.must_change_password;$('#send').hidden=!!active;$('#send-label').textContent=pending?'重试发送':'发送';
  if(me?.classroom_paused)status('老师已暂停课堂 AI，请稍候。');
}
function renderQuota(){
  if(!me?.quota){$('#quota').textContent='课堂 AI';$('#quota').title='';return}
  const q=me.quota;
  $('#quota').textContent=`今日可用 ${q.available} · 已用 ${q.used} · 处理中 ${q.reserved}`;
  $('#quota').title=`可用 ${q.available} 次 · 已用 ${q.used} 次 · 处理中（预留）${q.reserved} 次`;
}
function renderThread(forceScroll=false){
  const scroller=$('#scroll'),nearBottom=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<140;
  const anchor=nearBottom||forceScroll;$('#messages').replaceChildren();
  const visible=thread.filter(r=>r.chat_id===chat||!r.chat_id);
  $('#welcome').hidden=visible.length>0||!!pending;$('#messages').hidden=!visible.length&&!pending;
  for(const r of visible){
    const turn=node('article','turn');turn.dataset.requestId=r.id;
    const user=node('div','user-message'),bubble=node('div','user-bubble',question(r));
    if(r.attachments?.length){const tags=node('div','attachment-tags');for(const a of r.attachments)tags.append(node('span','attachment-tag',a.original_filename));bubble.append(tags)}user.append(bubble);turn.append(user);
    const heading=node('div','assistant-head');heading.innerHTML='<svg aria-hidden="true"><use href="#spark"/></svg><span>课堂 AI</span>';turn.append(heading);
    const answer=node('div','answer');answer.dataset.role='answer';
    const text=r.id===active&&streamText?streamText:r.output_text;
    if(text){markdown(answer,text);if(r.status==='generating')answer.classList.add('streaming')}
    else{answer.append(node('div',running(r)?'waiting':'',statusLabel(r)))}
    turn.append(answer);
    const meta=node('div','message-meta',text?statusLabel(r):'');if(r.charge_units)meta.append(node('span','',`已用 ${r.charge_units} 次`));
    if(text){const b=node('button','','复制');b.onclick=()=>copyText(text,b);meta.append(b)}turn.append(meta);$('#messages').append(turn);
  }
  if(pending&&pending.body.chat_id===chat){const wrap=node('div','user-message');wrap.append(node('div','user-bubble',pending.body.payload.messages[0].content));$('#messages').append(wrap)}
  if(anchor)requestAnimationFrame(()=>scroller.scrollTop=scroller.scrollHeight);
  renderHistory();
}
function paintStream(){
  const answer=document.querySelector(`.turn[data-request-id="${active}"] [data-role=answer]`);
  if(!answer||!streamText){renderThread();return}
  markdown(answer,streamText);answer.classList.add('streaming');
  const scroller=$('#scroll');if(scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<160)scroller.scrollTop=scroller.scrollHeight;
}
function schedulePaint(){if(mdTimer)return;mdTimer=setTimeout(()=>{mdTimer=null;paintStream()},32)}
function renderHistory(){
  const groups=new Map();for(const r of [...records.values()].sort((a,b)=>b.submitted_at.localeCompare(a.submitted_at))){const key=r.chat_id||r.id;if(!groups.has(key))groups.set(key,r)}
  $('#history').replaceChildren();for(const [key,r] of groups){const b=node('button',key===chat?'active':'',question(r).replace(/\s+/g,' ').slice(0,45)||'附件提问');b.title=question(r);b.disabled=!!pending||sending;b.onclick=()=>openThread(r.id).catch(e=>status(e.message,true));$('#history').append(b)}
  if(!groups.size)$('#history').append(node('p','history-empty','你的对话会保存在这里'));
}
async function history(reset=false){if(reset)cursor=null;const data=await call('/requests?limit=20'+(cursor?'&cursor='+encodeURIComponent(cursor):''));for(const r of data.requests)records.set(r.id,r);const last=data.requests.at(-1);cursor=last?last.submitted_at+'|'+last.id:null;$('#more').hidden=data.requests.length<20;renderHistory()}
function closeSidebar(){$('#sidebar').classList.remove('open');$('#shade').classList.remove('open')}
function resetStream(){eventAfter=0;streamText='';streamId=active;lastStatusAt=0;if(mdTimer){clearTimeout(mdTimer);mdTimer=null}}
async function openThread(id){
  if(sending)return;const turn=++opening;loadingThread=true;updateControls();
  try{const chain=[],seen=new Set();let next=id;
    while(next&&chain.length<50){if(seen.has(next))break;seen.add(next);const r=await call('/requests/'+encodeURIComponent(next));records.set(r.id,r);chain.unshift(r);next=r.parent_request_id}
    if(turn!==opening)return;thread=chain;const tail=chain.at(-1);chat=tail.chat_id||tail.id;parent=continuable(tail)?tail.id:null;
    if(pending&&tail.client_operation_id===pending.key){pending=null;rememberPending()}
    if(active===tail.id&&tail.status==='generating'){streamId=tail.id;streamText=tail.output_text||'';eventAfter=tail.output_seq||0}else if(!active)resetStream();
    renderThread(true);closeSidebar();await acknowledge(tail);
  }finally{if(turn===opening){loadingThread=false;updateControls()}}
}
async function refreshMe(){me=await call('/me');if(!active&&me.active_request?.id){active=me.active_request.id;resetStream()}lastMeAt=Date.now();
  const name=me.user.roster_name||'同学';$('#student-name').textContent=name;$('#profile-icon').textContent=name.slice(0,1);
  renderQuota();
  $('#change').hidden=!me.must_change_password;$('#compose').hidden=me.must_change_password;$('#scroll').hidden=me.must_change_password;$('#newchat').hidden=me.must_change_password;
  updateControls();return me;
}
const acked=new Map();
async function acknowledge(r){if(!r?.output_seq||document.visibilityState!=='visible'||!thread.some(x=>x.id===r.id))return;if((acked.get(r.id)||0)>=r.output_seq)return;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));if(document.visibilityState==='visible'&&thread.some(x=>x.id===r.id)){await call('/requests/'+r.id+'/delivery',{method:'POST',body:JSON.stringify({seq:r.output_seq})});acked.set(r.id,r.output_seq)}}
async function pullEvents(id){
  if(streamId!==id)resetStream();
  const data=await call('/requests/'+id+'/events?after_seq='+eventAfter);
  if(active!==id||streamId!==id)return false;
  let changed=false,ended=false;
  for(const ev of data.events||[]){
    if(ev.seq<=eventAfter)continue;
    eventAfter=Math.max(eventAfter,ev.seq||0);
    if(ev.event_type==='delta'&&typeof ev.payload?.text==='string'&&ev.payload.text){streamText+=ev.payload.text;changed=true}
    if(ev.event_type==='completed'||ev.event_type==='interrupted'||ev.event_type==='error'||ev.event_type==='stopped')ended=true;
  }
  if(changed){
    const index=thread.findIndex(x=>x.id===id);
    if(index>=0){thread[index]={...thread[index],output_text:streamText,output_seq:eventAfter,status:'generating'};records.set(id,thread[index])}
    schedulePaint();
    acknowledge({id,output_seq:eventAfter}).catch(e=>status(e.message,true));
  }
  return ended;
}
async function finishActive(id,r){
  records.set(r.id,r);const index=thread.findIndex(x=>x.id===id);
  if(index>=0){thread[index]=r;streamText=r.output_text||'';renderThread();await acknowledge(r)}
  if(!running(r)){active=null;resetStream();if(index>=0&&index===thread.length-1&&continuable(r))parent=r.id;await refreshMe();await history(true);if(!me.classroom_paused)status('')}
}
async function poll(){try{if(!me?.must_change_password){
  const id=active;
  if(id){
    if(Date.now()-lastMeAt>4000)await refreshMe().catch(()=>{});
    const known=records.get(id);
    if(known?.status==='generating'){
      const ended=await pullEvents(id);
      if(ended||Date.now()-lastStatusAt>1500){
        lastStatusAt=Date.now();
        const r=await call('/requests/'+id);records.set(r.id,r);
        if(r.status!=='generating')await finishActive(id,r);
      }
    }else{
      const r=await call('/requests/'+id);records.set(r.id,r);const index=thread.findIndex(x=>x.id===id);
      if(r.status==='generating'){
          lastStatusAt=Date.now();
          if(index>=0)thread[index]={...thread[index],...r,output_text:streamText||''};
          await pullEvents(id);
      }else{
          await finishActive(id,r);
      }
    }
  }else if(me){await refreshMe();if(active&&thread.length===0)await openThread(active)}
}}catch(e){status(e.message,true)}finally{const st=active&&records.get(active)?.status;setTimeout(poll,st==='generating'?50:active?400:4000)}}
async function upload(file){const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);return call('/attachments',{method:'POST',body:JSON.stringify({filename:file.name,content_base64:btoa(binary),encoding:$('#encoding').value})})}
function renderFiles(){$('#file-list').replaceChildren();files.forEach((file,index)=>{const chip=node('div','file-chip');chip.append(node('span','',file.name));const remove=node('button','','×');remove.setAttribute('aria-label','移除 '+file.name);remove.disabled=sending;remove.onclick=()=>{files.splice(index,1);renderFiles()};chip.append(remove);$('#file-list').append(chip)});$('#encoding').hidden=!files.length}
async function submit(){if(sending||active||!me||me.must_change_password||me.classroom_paused)return;if(!pending&&!$('#prompt').value.trim())return;
  if(!pending&&($('#prompt').value||'').length>1000)return status('提问不能超过 1000 字',true);
  sending=true;status('');updateControls();
  try{if(!pending){const attachments=[];for(const file of files)attachments.push(await upload(file));pending={key:newId(),body:{chat_id:chat,parent_request_id:parent,payload:{model:me.allowed_models[0],messages:[{role:'user',content:$('#prompt').value}],attachments:attachments.map(a=>({id:a.id,sha256:a.sha256}))},attachment_ids:attachments.map(a=>a.id)}};rememberPending()}
    renderThread(true);const r=await call('/requests',{method:'POST',headers:{'Idempotency-Key':pending.key},body:JSON.stringify(pending.body)});
    pending=null;rememberPending();records.set(r.id,r);if(!thread.some(x=>x.id===r.id))thread.push(r);active=running(r)?r.id:null;resetStream();
    if(continuable(r))parent=r.id;files=[];renderFiles();$('#files').value='';$('#prompt').value='';$('#prompt').style.height='';updateCharCount();renderThread(true);await refreshMe();
  }catch(e){status(e.message+(pending?' 可点击“重试发送”，不会重复提交。':''),true)}finally{sending=false;updateControls()}
}
$('#send').onclick=submit;
$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit()}};
$('#prompt').oninput=()=>{resizePrompt();updateCharCount()};
$('#attach').onclick=()=>$('#files').click();
$('#files').onchange=()=>{const next=[...files,...$('#files').files];$('#files').value='';if(next.length>5||next.reduce((sum,f)=>sum+f.size,0)>10*1024*1024){status('最多上传 5 个附件，合计不超过 10 MiB。',true);return}files=next;renderFiles()};
$('#stop').onclick=async()=>{if(!active)return;$('#stop').disabled=true;try{const r=await call('/requests/'+active+'/cancel',{method:'POST',body:'{}'});await finishActive(r.id,r);await refreshMe()}catch(e){status(e.message,true)}finally{$('#stop').disabled=false}};
$('#newchat').onclick=()=>{if(active||sending)return;opening++;chat=newId();parent=null;thread=[];pending=null;rememberPending();files=[];renderFiles();$('#prompt').value='';updateCharCount();status('');resetStream();renderThread();updateControls();closeSidebar();$('#prompt').focus()};
$('#changebtn').onclick=async()=>{$('#changebtn').disabled=true;try{await call('/account/change-initial-password',{method:'POST',body:JSON.stringify({current_password:$('#current').value,new_password:$('#newpass').value})});$('#current').value='';$('#newpass').value='';localStorage.removeItem('token');location.replace('/auth')}catch(e){$('#change-status').textContent=e.message}finally{$('#changebtn').disabled=false}};
$('#menu').onclick=()=>{$('#sidebar').classList.add('open');$('#shade').classList.add('open')};$('#shade').onclick=closeSidebar;$('#close-menu').onclick=closeSidebar;
$('#more').onclick=()=>history().catch(e=>status(e.message,true));
async function start(){try{await refreshMe();storageKey='classroom-pending-'+me.user.id;try{pending=JSON.parse(sessionStorage.getItem(storageKey)||'null')}catch{pending=null}if(pending){chat=pending.body.chat_id;parent=pending.body.parent_request_id;$('#prompt').value=pending.body.payload.messages[0].content}
  updateCharCount();
  if(!me.must_change_password){await history();const id=active||me.latest_request?.id;if(id&&(!pending||records.get(id)?.client_operation_id===pending.key))await openThread(id);else if(active)await openThread(active);else renderThread();updateControls()}
}catch(e){if(e.status===401)location.replace('/auth');else status(e.message,true)}finally{poll()}}
start();
