const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
class Element{
  constructor(tag='div'){this.tag=tag;this.children=[];this.style={};this.dataset={};this.value='';this.checked=false;this.open=false}
  set textContent(value){this.text=value;this.children=[]}get textContent(){return this.text||''}
  append(...nodes){this.children.push(...nodes)}
}
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
const students=Array.from({length:25},(_,i)=>({user_id:'s'+i,roster_name:'Student '+i,login_identifier:'s'+i+'@a.b',quota:{available:5,used:0,reserved:0},ai_enabled:true}));
const item={id:'r1',user_id:'s0',status:'pending',submitted_at:'test time',original_payload:{messages:[{role:'system',content:'Do not display me'},{role:'user',content:'Old question'},{role:'assistant',content:'Old answer'},{role:'user',content:'My current question'}]}};
const checks=()=>$('#students').children.flatMap(row=>row.children.filter(n=>n.tag==='input'));
const context={document:{querySelector:$,createElement:tag=>new Element(tag),querySelectorAll:s=>s.startsWith('#students')?checks():[]},localStorage:{getItem:()=>null,setItem(){}},setInterval(){},crypto:require('node:crypto').webcrypto,TextDecoder,
  fetch:async url=>({ok:true,json:async()=>url.endsWith('/admin/health')?{ready:true,timezone:'test'}:url.endsWith('/admin/students')?{students}:{requests:[item]}})};
vm.createContext(context);vm.runInContext(fs.readFileSync('classroom/web/teacher/app.js','utf8'),context);
(async()=>{
  await tick();assert.equal($('#students').children.length,10);
  assert.match($('#student-page-info').textContent,/1 \/ 3/);
  $('#selectall').checked=true;$('#selectall').onchange();
  assert.match($('#student-selection-info').textContent,/已选 10 人/);
  $('#student-next').onclick();assert.equal(checks().filter(c=>c.checked).length,0);
  assert.match($('#student-page-info').textContent,/2 \/ 3/);
  checks()[0].checked=true;checks()[0].onchange();
  $('#student-prev').onclick();assert.equal(checks().filter(c=>c.checked).length,10);
  assert.match($('#student-selection-info').textContent,/已选 11 人/);
  $('#student-page-size').value='20';$('#student-page-size').onchange();
  assert.equal($('#students').children.length,20);assert.equal(checks().filter(c=>c.checked).length,11);
  $('#student-next').onclick();assert.equal($('#students').children.length,5);assert.equal($('#student-next').disabled,true);
  await vm.runInContext('load()',context);assert.match($('#student-page-info').textContent,/2 \/ 2/);
  const preview=$('#queue').children[0].children.find(n=>n.tag==='pre');
  assert.equal(preview.textContent,'My current question');
  assert.equal(vm.runInContext("questionText({original_payload:{messages:[{role:'user',content:[{type:'text',text:'Look here'},{type:'image_url'}]}]}})",context),'Look here\n[图片附件]');
  $('#clear-student-selection').onclick();assert.match($('#student-selection-info').textContent,/已选 0 人/);
  const native=fs.readFileSync('classroom/web/native.js','utf8');
  for(const [path,quota,expected] of [['/',{},true],['/auth',{},true],['/c/old',{},true],['/',null,false],['/classroom/student/',{},false]]){
    const redirects=[];const ctx={location:{pathname:path,replace:v=>redirects.push(v)},localStorage:{getItem:()=>null},setTimeout(){},fetch:async()=>({ok:true,json:async()=>({quota})})};
    vm.runInNewContext(native,ctx);await tick();assert.equal(redirects.length,expected?1:0);if(expected)assert.equal(redirects[0],'/classroom/student/');
  }
  console.log('STUDENT_REDIRECT_PAGINATION_SELECTION_CURRENT_QUESTION_OK');
})().catch(e=>{console.error(e);process.exit(1)});
