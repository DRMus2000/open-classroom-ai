'use strict';
(() => {
  const summary = document.querySelector('#insights-summary');
  const keywords = document.querySelector('#keyword-list');
  const ranks = document.querySelector('#top-students');
  const hourly = document.querySelector('#hourly-bars');
  const canvas = document.querySelector('#wordcloud');
  const dateEl = document.querySelector('#insights-date');
  const modeEl = document.querySelector('#insights-mode');
  let loading = false;

  function drawCloud(items) {
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 640;
    const cssH = 320;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    canvas.style.width = cssW + 'px';
    canvas.style.height = cssH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    if (!items.length) {
      ctx.fillStyle = '#8a9388';
      ctx.font = '14px sans-serif';
      ctx.fillText('今日暂无足够关键词', 24, 40);
      return;
    }
    const max = items[0].count || 1;
    const colors = ['#326b58', '#24503f', '#4d7f6a', '#6b8f7c', '#9a6b12', '#26507f'];
    const placed = [];
    const cx = cssW / 2;
    const cy = cssH / 2;
    items.slice(0, 40).forEach((item, index) => {
      const size = 12 + Math.round(22 * (item.count / max));
      ctx.font = `600 ${size}px "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif`;
      const w = ctx.measureText(item.term).width;
      let x = cx - w / 2;
      let y = cy;
      let angle = index * 0.7;
      let radius = 8 + index * 7;
      let ok = false;
      for (let attempt = 0; attempt < 80; attempt++) {
        x = cx + Math.cos(angle) * radius - w / 2;
        y = cy + Math.sin(angle) * radius * 0.65;
        const box = { x, y: y - size, w, h: size + 4 };
        if (box.x < 4 || box.y < 4 || box.x + box.w > cssW - 4 || box.y + box.h > cssH - 4) {
          angle += 0.45;
          radius += 3;
          continue;
        }
        if (placed.every(p => box.x + box.w < p.x || p.x + p.w < box.x || box.y + box.h < p.y || p.y + p.h < box.y)) {
          placed.push(box);
          ok = true;
          break;
        }
        angle += 0.45;
        radius += 2;
      }
      if (!ok) return;
      ctx.fillStyle = colors[index % colors.length];
      ctx.fillText(item.term, x, y);
    });
  }

  async function load() {
    if (loading) return;
    loading = true;
    try {
      const data = await call('/admin/insights?range=today');
      const s = data.summary || {};
      dateEl.textContent = '统计日 ' + (data.quota_date || '');
      modeEl.textContent = data.review_mode === 'ai' ? 'AI 审核' : data.review_mode === 'none' ? '不审核' : '教师审核';
      modeEl.className = 'badge ' + (data.review_mode === 'ai' ? 'badge-generating' : data.review_mode === 'none' ? 'badge-completed' : 'badge-pending');
      summary.replaceChildren();
      const cards = [
        [s.total, '今日提问'],
        [s.pending, '待审核'],
        [s.approved, '已通过'],
        [s.rejected, '已拒绝'],
        [s.completed, '已完成'],
        [s.avg_wait_seconds == null ? '—' : s.avg_wait_seconds + 's', '平均等待'],
        [Math.round((s.reject_rate || 0) * 100) + '%', '拒绝率'],
        [`${s.ai_approved || 0}/${s.ai_rejected || 0}`, 'AI 过/拒'],
      ];
      for (const [value, label] of cards) {
        const card = el('div', undefined, 'stat');
        card.append(el('span', String(value)), el('small', label));
        summary.append(card);
      }
      keywords.replaceChildren();
      for (const item of (data.keywords || []).slice(0, 24)) {
        const chip = el('button', `${item.term} · ${item.count}`, 'keyword-chip');
        chip.type = 'button';
        chip.title = item.term;
        keywords.append(chip);
      }
      if (!(data.keywords || []).length) keywords.append(el('div', '暂无关键词', 'muted'));
      drawCloud(data.keywords || []);
      ranks.replaceChildren();
      if (!(data.top_students || []).length) ranks.append(el('div', '今日还没有提问。', 'empty'));
      (data.top_students || []).forEach((row, index) => {
        const line = el('div', undefined, 'rank-row');
        line.append(el('span', String(index + 1), 'rank-n'), el('strong', row.roster_name || row.user_id), el('span', row.count + ' 次', 'muted'));
        ranks.append(line);
      });
      hourly.replaceChildren();
      const maxH = Math.max(1, ...(data.hourly || [0]));
      (data.hourly || []).forEach((count, hour) => {
        const col = el('div', undefined, 'hour-col');
        const bar = el('div', undefined, 'hour-bar');
        bar.style.height = Math.max(4, Math.round(72 * count / maxH)) + 'px';
        col.append(bar, el('span', String(hour), 'hour-label'));
        if (count) col.title = hour + ' 时：' + count + ' 次';
        hourly.append(col);
      });
    } catch (e) {
      notify(e.message, 'error');
    } finally {
      loading = false;
    }
  }

  document.querySelector('#insights-refresh').onclick = () => load().catch(error);
  panels.insights = { load, loaded: false };
  if (activeView === 'insights') {
    panels.insights.loaded = true;
    load();
  }
})();
