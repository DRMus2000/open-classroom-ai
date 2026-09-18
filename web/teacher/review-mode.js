'use strict';
(() => {
  const status = document.querySelector('#review-mode-status');
  const auditText = document.querySelector('#audit-prompt-text');
  const auditFeedback = document.querySelector('#audit-prompt-status');
  const auditSave = document.querySelector('#save-audit-prompt');
  const historyEl = document.querySelector('#ai-audit-history');
  const historyStatus = document.querySelector('#ai-audit-status');
  let modeConfig = null;
  let auditConfig = null;
  let saving = false;
  let auditLoading = false;

  function selectedMode() {
    const node = document.querySelector('input[name="review-mode"]:checked');
    return node ? node.value : 'teacher';
  }

  function paintMode(mode) {
    for (const input of document.querySelectorAll('input[name="review-mode"]')) {
      input.checked = input.value === mode;
    }
  }

  async function loadMode() {
    status.textContent = '正在读取审核模式…';
    try {
      modeConfig = await call('/admin/review-mode');
      paintMode(modeConfig.mode);
      status.textContent = modeConfig.mode === 'teacher'
        ? '当前：教师审核。'
        : modeConfig.mode === 'ai'
          ? '当前：AI 审核。失败将回退到教师待审。'
          : '当前：不审核，提交后直接生成。';
    } catch (e) {
      status.textContent = e.message;
    }
  }

  async function saveMode(mode) {
    if (!modeConfig || saving) return;
    saving = true;
    status.textContent = '正在保存…';
    try {
      modeConfig = await call('/admin/review-mode', {
        method: 'PUT',
        body: JSON.stringify({ mode, expected_version: modeConfig.version }),
      });
      paintMode(modeConfig.mode);
      status.textContent = '审核模式已更新。';
    } catch (e) {
      status.textContent = e.message;
      paintMode(modeConfig.mode);
    } finally {
      saving = false;
    }
  }

  async function loadAuditPrompt() {
    if (auditLoading) return;
    auditLoading = true;
    auditSave.disabled = true;
    auditFeedback.textContent = '正在读取…';
    try {
      auditConfig = await call('/admin/audit-system-prompt');
      auditText.value = auditConfig.prompt;
      auditFeedback.textContent = '用于 AI 审核模式，保存后立即生效。';
    } catch (e) {
      auditFeedback.textContent = e.message;
    } finally {
      auditLoading = false;
      auditSave.disabled = !auditConfig;
    }
  }

  async function loadHistory() {
    historyStatus.textContent = '正在读取审计历史…';
    try {
      const data = await call('/admin/ai-audit/history?limit=40');
      historyEl.textContent = '';
      if (!data.turns.length) {
        historyEl.append(el('div', '暂无 AI 审计记录。', 'empty'));
      }
      for (const turn of data.turns) {
        const row = el('div', undefined, 'audit-row');
        const labels = {approve:'通过',reject:'拒绝',fallback:'回退教师'};
        const badge = el('span', labels[turn.decision] || turn.decision, 'badge badge-' + (turn.decision === 'approve' ? 'completed' : turn.decision === 'reject' ? 'rejected' : 'pending'));
        const excerpt = (turn.question_excerpt || '').replace(/\s+/g, ' ').trim();
        const q = el('div', excerpt, 'audit-q');
        const why = (turn.reason || '').replace(/\s+/g, ' ').trim();
        q.title = excerpt + (why ? '\n→ ' + why : '');
        const reason = el('div', why ? '→ ' + why : '', 'audit-reason');
        reason.title = why;
        row.append(badge, q, reason);
        historyEl.append(row);
      }
      historyStatus.textContent = data.turns.length ? `已显示 ${data.turns.length} 条。` : '';
    } catch (e) {
      historyStatus.textContent = e.message;
    }
  }

  async function loadAll() {
    await loadMode();
    await loadAuditPrompt();
    await loadHistory();
  }

  for (const input of document.querySelectorAll('input[name="review-mode"]')) {
    input.onchange = () => saveMode(input.value);
  }
  document.querySelector('#reload-audit-prompt').onclick = loadAuditPrompt;
  document.querySelector('#default-audit-prompt').onclick = () => {
    if (auditConfig) {
      auditText.value = auditConfig.default_prompt;
      auditFeedback.textContent = '已填入默认审计提示词，点击保存后生效。';
    }
  };
  auditSave.onclick = async () => {
    if (!auditConfig || auditLoading) return;
    auditLoading = true;
    auditSave.disabled = true;
    auditFeedback.textContent = '正在保存…';
    try {
      auditConfig = await call('/admin/audit-system-prompt', {
        method: 'PUT',
        body: JSON.stringify({ prompt: auditText.value, expected_version: auditConfig.version }),
      });
      auditFeedback.textContent = '审计提示词已保存。';
    } catch (e) {
      auditFeedback.textContent = e.message;
    } finally {
      auditLoading = false;
      auditSave.disabled = false;
    }
  };
  document.querySelector('#reload-ai-audit').onclick = loadHistory;
  document.querySelector('#clear-ai-audit-session').onclick = async () => {
    if (!confirm('清空 AI 审计会话上下文？历史记录仍会保留。')) return;
    try {
      await call('/admin/ai-audit/clear-session', { method: 'POST', body: '{}' });
      historyStatus.textContent = '审计会话上下文已清空。';
    } catch (e) {
      historyStatus.textContent = e.message;
    }
  };

  panels.reviewMode = { load: loadAll, loaded: false };
  if (activeView === 'settings') {
    panels.reviewMode.loaded = true;
    loadAll();
  }
})();
