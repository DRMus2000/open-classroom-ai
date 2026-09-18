const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('classroom/web/teacher/app.js','utf8');
function element(){return {textContent:'',hidden:false,disabled:false,style:{},children:[],append(...v){this.children.push(...v)}}}
const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
const calls=[];let rows=[{row_number:2,name:'Test',email:'test@a.b',role:'user',error_code:'WEAK_INITIAL_PASSWORD'}];
const context={$,busy:false,TextDecoder,el:(tag,text)=>Object.assign(element(),{textContent:text}),call:async(path)=>{calls.push(path);return path.endsWith('/preview')?{batch_id:'test-batch',rows}:{results:[{row_number:2,status:'completed'}]}},load:async()=>{},error:e=>{throw e}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('let importPreview='),source.indexOf("$('#export').onclick")),context);
(async()=>{
  $('#roster').files=[{arrayBuffer:async()=>Buffer.from('synthetic CSV')}];
  await $('#import').onclick();
  assert.equal(calls.length,1);assert.equal($('#commit-import').disabled,true);
  assert.match($('#import-status').textContent,/没有有效行/);
  rows=[{...rows[0],error_code:null}];
  await $('#import').onclick();
  assert.equal(calls.length,2);assert.equal($('#commit-import').disabled,false);
  await $('#commit-import').onclick();
  assert.equal(calls.length,3);assert.match(calls[2],/commit$/);
  assert.match($('#import-status').textContent,/导入成功 1 人/);
  $('#roster').onchange();assert.equal($('#commit-import').disabled,true);
  console.log('ROSTER_UI_PREVIEW_SEPARATE_COMMIT_VALIDATION_OK');
})().catch(e=>{console.error(e);process.exit(1)});
