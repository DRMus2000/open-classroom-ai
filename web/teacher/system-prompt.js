'use strict';
(() => {
  const text=document.querySelector('#system-prompt-text'),feedback=document.querySelector('#system-prompt-status'),save=document.querySelector('#save-system-prompt');
  let config=null,loading=false;
  async function read(){if(loading)return;loading=true;save.disabled=true;feedback.textContent='正在读取…';try{config=await call('/admin/system-prompt');text.value=config.prompt;feedback.textContent='用于学生新对话与访客链接，保存后立即生效。'}catch(e){feedback.textContent=e.message}finally{loading=false;save.disabled=!config}}
  document.querySelector('#reload-system-prompt').onclick=read;
  document.querySelector('#default-system-prompt').onclick=()=>{if(config){text.value=config.default_prompt;feedback.textContent='已填入默认提示词，点击保存后生效。'}};
  save.onclick=async()=>{if(!config||loading)return;loading=true;save.disabled=true;feedback.textContent='正在保存…';try{const result=await call('/admin/system-prompt',{method:'PUT',body:JSON.stringify({prompt:text.value,expected_version:config.version})});config=result;feedback.textContent='已保存。学生新对话与访客链接会使用此提示词；已有学生对话和已提交请求保持不变。'}catch(e){feedback.textContent=e.message}finally{loading=false;save.disabled=false}};
  // app.js 在切换到「课堂设置」时调用 load；若页面直接打开在该分区，则立即读取。
  panels.systemPrompt={load:read,loaded:false};
  if(activeView==='settings'){panels.systemPrompt.loaded=true;read()}
})();
