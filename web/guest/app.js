'use strict';
const $=s=>document.querySelector(s),api='/api/classroom/v1',MAX=1000;
const params=new URLSearchParams(location.search);
const token=(params.get('t')||'').trim();
const newId=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function status(text='',error=false){$('#status').textContent=text;$('#status').className='status'+(error?' error':'')}
const md=window.markdownit({html:false,linkify:false,breaks:true});
md.renderer.rules.image=(tokens,index)=>'<span class="attachment-tag">图片：'+md.utils.escapeHtml(tokens[index].content||'图片')+'</span>';
md.renderer.rules.fence=(tokens,index)=>{const t=tokens[index],lang=(t.info||'').trim().split(/\s+/)[0];return '<div class="codeblock"><div class="codebar"><span>'+md.utils.escapeHtml(lang||'代码')+'</span><button type="button" class="copy-code">复制</button></div><pre><code>'+md.utils.escapeHtml(t.content)+'</code></pre></div>'};
const renderLink=md.renderer.rules.link_open||((tokens,index,options,env,self)=>self.renderToken(tokens,index,options));
md.renderer.rules.link_open=(tokens,index,options,env,self)=>{tokens[index].attrSet('target','_blank');tokens[index].attrSet('rel','noopener noreferrer');return renderLink(tokens,index,options,env,self)};
async function copyText(text,button){try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text)}else{const t=node('textarea');t.value=text;t.style.position='fixed';t.style.opacity='0';document.body.append(t);t.select();const copied=document.execCommand('copy');t.remove();if(!copied)throw new Error('copy failed')}button.textContent='已复制';setTimeout(()=>button.textContent='复制',1600)}catch{button.textContent='请选中文字复制'}}
function markdown(target,text){target.innerHTML=md.render(text);target.querySelectorAll('.copy-code').forEach(b=>b.onclick=()=>copyText(b.closest('.codeblock').querySelector('code').textContent,b))}
function headers(){return {'Content-Type':'application/json','Authorization':'Bearer guest:'+token}}
function closeSidebar(){$('#sidebar').classList.remove('open');$('#shade').classList.remove('open')}
function updateCharCount(){
  const box=$('#char-count'); if(!box)return;
  const n=($('#prompt').value||'').length;
  box.textContent=n+' / '+MAX;
  box.classList.toggle('warn',n>=MAX-30);
}
function resizePrompt(){$('#prompt').style.height='auto';$('#prompt').style.height=Math.min($('#prompt').scrollHeight,160)+'px'}
function updateControls(){
  const locked=!ready||paused||busy;
  $('#send').disabled=locked||!($('#prompt').value||'').trim();
  $('#prompt').disabled=!ready||paused||busy;
  $('#newchat').disabled=busy;
  $('#stop').hidden=!busy;
  $('#send').hidden=busy;
}

let model=null,ready=false,paused=false,busy=false,chatId=newId(),chats=[],current=[],abort=null,paintTimer=null,streamText='';

function currentChat(){return chats.find(c=>c.id===chatId)}
function titleOf(messages){const u=messages.find(m=>m.role==='user');return ((u&&u.content)||'').replace(/\s+/g,' ').slice(0,45)||'新对话'}
function rememberChat(){
  const existing=currentChat();
  const title=titleOf(current);
  if(existing){existing.messages=current;existing.title=title}
  else if(current.length) chats.unshift({id:chatId,title,messages:current})
}
function renderHistory(){
  $('#history').replaceChildren();
  for(const c of chats){
    const b=node('button',c.id===chatId?'active':'',c.title);
    b.title=c.title;b.disabled=busy;b.onclick=()=>openChat(c.id);
    $('#history').append(b);
  }
  if(!chats.length)$('#history').append(node('p','history-empty','本页对话只留在当前浏览器'));
}
function renderThread(forceScroll=false){
  const scroller=$('#scroll'),nearBottom=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<140;
  const anchor=nearBottom||forceScroll;$('#messages').replaceChildren();
  $('#welcome').hidden=current.length>0;$('#messages').hidden=!current.length;
  for(let i=0;i<current.length;i++){
    const m=current[i];
    if(m.role==='user'){
      const turn=node('article','turn');
      const user=node('div','user-message');user.append(node('div','user-bubble',m.content));turn.append(user);
      const next=current[i+1];
      if(next&&next.role==='assistant'){
        const heading=node('div','assistant-head');heading.innerHTML='<svg aria-hidden="true"><use href="#spark"/></svg><span>课堂 AI</span>';turn.append(heading);
        const answer=node('div','answer');answer.dataset.role='answer';
        const text=(busy&&i===current.length-2)?(streamText||next.content):next.content;
        if(text){markdown(answer,text);if(busy&&i===current.length-2)answer.classList.add('streaming')}
        else answer.append(node('div','waiting','正在回答'));
        turn.append(answer);
        const meta=node('div','message-meta','');
        if(text&&!(busy&&i===current.length-2)){const b=node('button','','复制');b.onclick=()=>copyText(text,b);meta.append(b)}
        if(meta.childNodes.length)turn.append(meta);
        i++;
      }else if(busy&&i===current.length-1){
        const heading=node('div','assistant-head');heading.innerHTML='<svg aria-hidden="true"><use href="#spark"/></svg><span>课堂 AI</span>';turn.append(heading);
        const answer=node('div','answer streaming');answer.dataset.role='answer';
        if(streamText)markdown(answer,streamText);else answer.append(node('div','waiting','正在回答'));
        turn.append(answer);
      }
      $('#messages').append(turn);
    }
  }
  renderHistory();
  if(anchor)requestAnimationFrame(()=>scroller.scrollTop=scroller.scrollHeight);
}
function paintStream(){
  const answer=document.querySelector('[data-role=answer].streaming')||document.querySelector('.turn:last-child [data-role=answer]');
  if(!answer||!streamText){renderThread();return}
  markdown(answer,streamText);answer.classList.add('streaming');
  const scroller=$('#scroll');if(scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<160)scroller.scrollTop=scroller.scrollHeight;
}
function schedulePaint(){if(paintTimer)return;paintTimer=setTimeout(()=>{paintTimer=null;paintStream()},80)}
function showGate(message){
  $('#gate-text').textContent=message;
  $('#gate').hidden=false;$('#compose').hidden=true;$('#scroll').hidden=true;$('#newchat').hidden=true;
}
function openChat(id){
  if(busy)return;
  rememberChat();
  const found=chats.find(c=>c.id===id);
  if(!found)return;
  chatId=found.id;current=found.messages.slice();
  renderThread(true);closeSidebar();updateControls();
}
async function boot(){
  updateCharCount();
  if(!token){showGate('缺少访客令牌。请使用老师提供的完整链接。');return}
  try{
    const response=await fetch(api+'/guest/status',{headers:headers()});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error?.message||'链接无效或已关闭');
    if(data.classroom_paused){paused=true;throw new Error('全班 AI 已暂停，访客链接暂时不可用')}
    model=data.model;
    if(!model)throw new Error('课堂尚未配置可用模型');
    ready=true;updateControls();renderHistory();
  }catch(e){showGate(e.message);status(e.message,true)}
}
async function submit(){
  if(busy||!ready||paused)return;
  const text=($('#prompt').value||'').trim();
  if(!text)return;
  if(text.length>MAX)return status('提问不能超过 1000 字',true);
  busy=true;streamText='';status('');updateControls();
  current=current.concat([{role:'user',content:text}]);
  rememberChat();
  $('#prompt').value='';$('#prompt').style.height='';updateCharCount();
  renderThread(true);
  abort=new AbortController();
  const payload={model,messages:current.filter(m=>m.role==='user'||(m.role==='assistant'&&m.content)).slice(-40)};
  try{
    const response=await fetch(api+'/guest/chat/completions',{method:'POST',headers:headers(),body:JSON.stringify(payload),signal:abort.signal});
    if(!response.ok){
      const data=await response.json().catch(()=>({}));
      throw new Error(data.error?.message||'请求失败');
    }
    const reader=response.body.getReader();
    const decoder=new TextDecoder();
    let buffer='',answer='';
    while(true){
      const {value,done}=await reader.read();
      if(done)break;
      buffer+=decoder.decode(value,{stream:true});
      const parts=buffer.split('\n');buffer=parts.pop()||'';
      for(const line of parts){
        const row=line.trim();
        if(!row.startsWith('data:'))continue;
        const raw=row.slice(5).trim();
        if(raw==='[DONE]')continue;
        let event;try{event=JSON.parse(raw)}catch{continue}
        if(event.error?.message)throw new Error(event.error.message);
        const delta=event.choices?.[0]?.delta?.content;
        if(typeof delta==='string'&&delta){answer+=delta;streamText=answer;schedulePaint()}
      }
    }
    current=current.concat([{role:'assistant',content:answer||'（没有返回内容）'}]);
    rememberChat();
  }catch(e){
    if(e.name==='AbortError'){
      if(streamText) current=current.concat([{role:'assistant',content:streamText}]);
      rememberChat();
    }else status(e.message,true);
  }finally{
    abort=null;busy=false;streamText='';if(paintTimer){clearTimeout(paintTimer);paintTimer=null}
    renderThread(true);updateControls();$('#prompt').focus();
  }
}
$('#send').onclick=submit;
$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit()}};
$('#prompt').oninput=()=>{resizePrompt();updateCharCount();updateControls()};
$('#stop').onclick=()=>{if(abort)abort.abort()};
$('#newchat').onclick=()=>{if(busy)return;rememberChat();chatId=newId();current=[];$('#prompt').value='';updateCharCount();status('');renderThread();updateControls();closeSidebar();$('#prompt').focus()};
$('#menu').onclick=()=>{$('#sidebar').classList.add('open');$('#shade').classList.add('open')};
$('#shade').onclick=closeSidebar;$('#close-menu').onclick=closeSidebar;
boot();
