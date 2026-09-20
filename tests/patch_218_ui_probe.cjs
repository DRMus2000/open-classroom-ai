const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.style={};this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.scrollHeight=0;this.scrollTop=0;this.clientHeight=600;this.classList={add(){},remove(){},toggle(){}}}
  append(...x){this.children.push(...x)} replaceChildren(...x){this.children=x} querySelectorAll(){return []} setAttribute(){} focus(){} select(){}
  get firstElementChild(){return this.children[0]}
  get options(){return this.children}
}
function setup(kind){
  const nodes=new Map(),$=s=>{if(!nodes.has(s))nodes.set(s,new Element());return nodes.get(s)};
  const c={document:{querySelector:$,querySelectorAll:()=>[],createElement:()=>new Element(),visibilityState:'hidden'},window:{markdownit:require('../web/student/vendor/markdown-it.min.js')},localStorage:{getItem:()=>null,setItem(){}},sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},crypto:require('node:crypto').webcrypto,navigator:{},setTimeout(){},clearTimeout(){},setInterval(){},requestAnimationFrame:fn=>fn(),location:{replace(){},origin:'http://127.0.0.1:3000'},confirm:()=>true,URL};
  vm.createContext(c);
  let src=fs.readFileSync('classroom/web/'+kind+'/app.js','utf8');
  if(kind==='student')src=src.replace(/start\(\);\s*$/,'');
  else src=src.slice(0,src.indexOf("let initialView='review'"));
  vm.runInContext(src,c);return {c,$};
}
const ok=data=>({ok:true,json:async()=>data});
async function quotaConflict(){
  const {c,$}=setup('teacher');let previews=0;const posts=[];
  c.fetch=async(url,opts)=>{
    if(url.endsWith('/preview')){previews++;return ok({date:'2026-09-19',valid:true,rows:[{user_id:'s1',before:{available:3,version:previews},after_available:4}]})}
    if(url.endsWith('/adjust')){posts.push(opts);if(posts.length===1)return {ok:false,status:409,json:async()=>({error:{code:'QUOTA_VERSION_CONFLICT',message:'stale version'}})};return ok({})}
    if(url.endsWith('/health'))return ok({ready:true,timezone:'test'});
    if(url.endsWith('/students'))return ok({students:[]});
    return ok({requests:[]});
  };
  vm.runInContext("selected.add('s1')",c);
  await assert.rejects(vm.runInContext('adjust(1)',c),/stale/);
  await vm.runInContext('adjust(1)',c);
  assert.equal(previews,2);assert.equal(JSON.parse(posts[1].body).expected_versions.s1,2);
  assert.notEqual(posts[0].headers['Idempotency-Key'],posts[1].headers['Idempotency-Key']);
  assert.equal(vm.runInContext('adjustment',c),null);
  let attempts=0;const uncertain=[];
  vm.runInContext("selected.add('s1')",c);
  c.fetch=async(url,opts)=>{
    if(url.endsWith('/preview'))return ok({date:'2026-09-19',valid:true,rows:[{user_id:'s1',before:{available:3,version:3},after_available:4}]});
    uncertain.push(opts);attempts++;throw new Error('network interruption');
  };
  await assert.rejects(vm.runInContext('adjust(1)',c),/network/);
  await assert.rejects(vm.runInContext('adjust(1)',c),/network/);
  assert.equal(attempts,2);assert.equal(uncertain[0].body,uncertain[1].body);
  assert.equal(uncertain[0].headers['Idempotency-Key'],uncertain[1].headers['Idempotency-Key']);
}
async function recoverCompletion(restarted){
  const {c}=setup('student');
  const me={user:{id:'s1',roster_name:'S'},quota:{available:2,used:1,reserved:0},allowed_models:['m'],active_request:null};
  const row={id:'r1',chat_id:'c1',status:'generating',submitted_at:'2026-09-19',output_text:'partial',output_seq:2,original_payload:{messages:[{role:'user',content:'Q'}]}};
  const final={...row,status:restarted?'interrupted_unknown':'completed',output_text:'complete answer',output_seq:3};
  vm.runInContext(`me=${JSON.stringify(me)};active='r1';streamId='r1';chat='c1';thread=[${JSON.stringify(row)}];records.set('r1',thread[0]);streamText='partial';eventAfter=2;lastMeAt=0;lastStatusAt=${restarted?'0':'Date.now()'};`,c);
  let fail=!restarted,detailCalls=0;
  c.fetch=async url=>{
    if(url.includes('/events')){if(fail){fail=false;throw new Error('one lost response')}return ok({events:restarted?[]:[{seq:3,event_type:'completed',payload:{}}]})}
    if(url.endsWith('/requests/r1')){detailCalls++;return ok(final)}
    if(url.includes('/requests?'))return ok({requests:[final]});
    return ok(me);
  };
  await vm.runInContext('poll()',c);
  if(!restarted)assert.equal(vm.runInContext('active',c),'r1');
  await vm.runInContext('poll()',c);
  assert.ok(detailCalls);assert.equal(vm.runInContext('thread[0].status',c),final.status);
  assert.equal(vm.runInContext('thread[0].output_text',c),'complete answer');
  assert.equal(vm.runInContext('active',c),null);
}
async function guestShare(){
  const {c,$}=setup('teacher');
  vm.runInContext("activeView='review'",c);
  c.fetch=async()=>ok({enabled:true,version:1,has_token:true,share_hosts:['192.168.1.10','192.168.2.10'],
    share_interfaces:[{address:'192.168.1.10',name:'以太网',kind:'physical',rank:0},{address:'192.168.2.10',name:'VPN',kind:'vpn',rank:2}]});
  vm.runInContext(fs.readFileSync('classroom/web/teacher/guest-link.js','utf8'),c);
  await vm.runInContext('panels.guestLink.load()',c);
  assert.equal($('#guest-origin').value,'http://192.168.1.10:3000');
  c.fetch=async()=>ok({enabled:true,version:2,share_url_path:'/classroom/guest/?t=fixture'});
  $('#guest-enabled').checked=true;await $('#guest-enabled').onchange();
  assert.equal($('#guest-url').value,'http://192.168.1.10:3000/classroom/guest/?t=fixture');
  $('#guest-origin').value='http://127.0.0.1:3000';$('#guest-origin').oninput();
  assert.equal($('#guest-copy').hidden,true);assert.equal($('#guest-url').value,'');
  $('#guest-origin').value='http://192.168.2.10:3000';$('#guest-origin').oninput();
  assert.equal($('#guest-copy').hidden,false);assert.equal($('#guest-url').value,'http://192.168.2.10:3000/classroom/guest/?t=fixture');
}
(async()=>{
  await quotaConflict();await recoverCompletion(false);await recoverCompletion(true);await guestShare();
  console.log('PATCH_218_QUOTA_RETRY_COMPLETION_RECOVERY_LAN_SHARE_OK');
})().catch(e=>{console.error(e);process.exit(1)});
