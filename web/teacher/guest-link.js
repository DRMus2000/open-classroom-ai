'use strict';
(() => {
  const enabled = document.querySelector('#guest-enabled');
  const urlInput = document.querySelector('#guest-url');
  const status = document.querySelector('#guest-status');
  const copyBtn = document.querySelector('#guest-copy');
  const rotateBtn = document.querySelector('#guest-rotate');
  let config = null;
  let saving = false;
  let lastTokenUrl = '';

  function absoluteShare(path) {
    if (!path) return '';
    try { return new URL(path, location.origin).href; } catch (_) { return path; }
  }

  function showUrl(pathOrUrl) {
    const href = pathOrUrl && pathOrUrl.startsWith('http') ? pathOrUrl : absoluteShare(pathOrUrl);
    lastTokenUrl = href || '';
    urlInput.value = href || (config && config.enabled && config.has_token
      ? '已开启。刷新后不显示明文令牌，需要新链接请点「重新生成链接」。'
      : '');
    copyBtn.hidden = !href;
  }

  async function read() {
    status.textContent = '正在读取…';
    try {
      config = await call('/admin/guest-access');
      enabled.checked = !!config.enabled;
      if (!lastTokenUrl) showUrl('');
      status.textContent = config.enabled
        ? '访客链接已开启。关闭后立即失效。'
        : '访客链接已关闭。';
    } catch (e) {
      status.textContent = e.message;
    }
  }

  async function save({ rotate = false } = {}) {
    if (!config || saving) return;
    saving = true;
    rotateBtn.disabled = true;
    enabled.disabled = true;
    status.textContent = rotate ? '正在重新生成…' : '正在保存…';
    try {
      const result = await call('/admin/guest-access', {
        method: 'PUT',
        body: JSON.stringify({
          enabled: enabled.checked,
          rotate,
          expected_version: config.version,
        }),
      });
      config = result;
      if (result.share_url_path || result.token) {
        showUrl(result.share_url_path || ('/classroom/guest/?t=' + result.token));
        status.textContent = '已更新。请立即复制链接；刷新页面后明文不会再次显示。';
      } else {
        lastTokenUrl = '';
        showUrl('');
        status.textContent = result.enabled ? '已开启（沿用现有令牌）。' : '已关闭，旧链接立即失效。';
      }
    } catch (e) {
      status.textContent = e.message;
      enabled.checked = !!(config && config.enabled);
    } finally {
      saving = false;
      rotateBtn.disabled = false;
      enabled.disabled = false;
    }
  }

  // app.js 在切换到「课堂设置」时调用 load；若页面直接打开在该分区，则立即读取。
  panels.guestLink = { load: read, loaded: false };
  if (activeView === 'settings') { panels.guestLink.loaded = true; read(); }
  enabled.onchange = () => save({ rotate: enabled.checked && !(config && config.has_token) });
  rotateBtn.onclick = () => {
    if (!enabled.checked) {
      enabled.checked = true;
    }
    save({ rotate: true });
  };
  copyBtn.onclick = async () => {
    if (!lastTokenUrl) return;
    try {
      await navigator.clipboard.writeText(lastTokenUrl);
      status.textContent = '链接已复制到剪贴板。';
    } catch (_) {
      urlInput.select();
      status.textContent = '请手动复制输入框中的链接。';
    }
  };
})();
