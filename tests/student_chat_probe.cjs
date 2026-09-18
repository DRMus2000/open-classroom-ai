const assert=require('node:assert/strict'),vm=require('vm'),fs=require('fs');
class Element{
  constructor(){this.children=[];this.style={};this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.scrollHeight=0;this.scrollTop=0;this.clientHeight=600;this.classList={add(){},remove(){},toggle(){}}}
  append(...n){this.children.push(...n)}replaceChildren(...n){this.children=n}querySelectorAll(){return []}setAttribute(){}focus(){}
}
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
const saved=new Map(),calls=[];let fail=true;
const student={user:{id:'student-test',roster_name:'Test'},quota:{available:4,used:0,reserved:0},allowed_models:['classroom-default'],must_change_password:false,classroom_paused:false,active_request:null};
const context={window:{markdownit:require('../web/student/vendor/markdown-it.min.js')},document:{querySelector:$,createElement:()=>new Element(),visibilityState:'hidden'},navigator:{},localStorage:{getItem:()=>null},sessionStorage:{setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k),getItem:k=>saved.get(k)},crypto:require('node:crypto').webcrypto,setTimeout(){},requestAnimationFrame:fn=>fn(),location:{replace(){}},fetch:async(url,options)=>{
 if(url.endsWith('/requests')&&options.method==='POST'){calls.push(options);if(fail)throw new Error('simulated connection loss');return {ok:true,json:async()=>({id:'request-1',chat_id:'chat-test',status:'pending',submitted_at:'2026-09-11',original_payload:JSON.parse(options.body).payload,attachments:[],output_text:''})}}
 return {ok:true,json:async()=>({...student,active_request:calls.length>1?{id:'request-1'}:null})}
}};
vm.createContext(context);const source=fs.readFileSync('classroom/web/student/app.js','utf8');vm.runInContext(source.replace(/start\(\);\s*$/,''),context);
(async()=>{
  vm.runInContext("me="+JSON.stringify(student)+";storageKey='pending-test';chat='chat-test';",context);$('#prompt').value='A question';
  await vm.runInContext('submit()',context);assert.equal(calls.length,1);assert.ok(saved.has('pending-test'));
  $('#prompt').value='Must not replace the uncertain request';fail=false;
  await vm.runInContext('submit()',context);assert.equal(calls.length,2);assert.equal(calls[0].body,calls[1].body);assert.equal(calls[0].headers['Idempotency-Key'],calls[1].headers['Idempotency-Key']);assert.equal(saved.has('pending-test'),false);
  assert.equal($('#send').hidden,true);assert.equal($('#stop').hidden,false);
  const html=vm.runInContext('md.render('+JSON.stringify('# Heading\n\n**bold** and *italic*\n\n- one\n- two\n\n```python\nprint("<script>")\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n![tracking](https://example.invalid/pixel)')+')',context);
  assert.match(html,/<h1>Heading<\/h1>/);assert.match(html,/<strong>bold<\/strong>/);assert.match(html,/<ul>/);assert.match(html,/<table>/);assert.match(html,/copy-code/);assert.doesNotMatch(html,/<script>|<img|href="javascript:/);assert.match(html,/&lt;script&gt;/);
  console.log('STUDENT_CHAT_IDEMPOTENT_RETRY_MARKDOWN_SAFETY_OK');
})().catch(e=>{console.error(e);process.exit(1)});
