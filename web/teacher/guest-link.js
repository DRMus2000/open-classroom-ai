'use strict';
(() => {
  const enabled = document.querySelector('#guest-enabled');
  const urlInput = document.querySelector('#guest-url');
  const originInput = document.querySelector('#guest-origin');
  const originPick = document.querySelector('#guest-origin-pick');
  const origins = document.querySelector('#guest-origins');
  const status = document.querySelector('#guest-status');
  const copyBtn = document.querySelector('#guest-copy');
  const rotateBtn = document.querySelector('#guest-rotate');
  const rememberedKey = 'classroom-guest-origin';
  let config = null;
  let saving = false;
  let lastTokenUrl = '';
  let sharePath = '';

  function validOrigin(value) {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash ||
        /^(localhost\.?|127(?:\.\d+){3}|\[::1\]|0\.0\.0\.0|\[::\])$/i.test(url.hostname)) {
      throw new Error('请填写学生可访问的教师机地址，不能使用 localhost 或 127.0.0.1。');
    }
    return url.origin;
  }

  function kindLabel(kind) {
    if (kind === 'vpn') return 'VPN，学生可能访问不到';
    if (kind === 'virtual') return '虚拟网卡';
    return '局域网';
  }

  function rememberedOrigin() {
    try { return localStorage.getItem(rememberedKey) || ''; }
    catch (_) { return ''; }
  }

  function rememberOrigin(value) {
    try { if (value) localStorage.setItem(rememberedKey, value); }
    catch (_) {}
  }

  function configureOrigins(interfaces, hosts) {
    origins.replaceChildren();
    originPick.replaceChildren();
    const manual = document.createElement('option');
    manual.value = '';
    manual.textContent = '手动填写下方地址';
    originPick.append(manual);
    const current = new URL(location.origin);
    const rows = (interfaces && interfaces.length)
      ? interfaces
      : (hosts || []).map(address => ({address, name: address, kind: 'physical'}));
    for (const item of rows) {
      const candidate = new URL(current.origin);
      candidate.hostname = item.address || item;
      const origin = candidate.origin;
      const option = document.createElement('option');
      option.value = origin;
      origins.append(option);
      const pick = document.createElement('option');
      pick.value = origin;
      pick.textContent = (item.name || item.address) + ' · ' + (item.address || item) + '（' + kindLabel(item.kind) + '）';
      originPick.append(pick);
    }
    const remembered = rememberedOrigin();
    if (remembered) {
      try { originInput.value = validOrigin(remembered); originPick.value = originInput.value; return; }
      catch (_) {}
    }
    if (!originInput.value) {
      try { originInput.value = validOrigin(current.origin); }
      catch (_) { originInput.value = originPick.options[1]?.value || ''; }
    }
    originPick.value = [...originPick.options].some(option => option.value === originInput.value)
      ? originInput.value : '';
  }

  function showUrl(pathOrUrl) {
    sharePath = pathOrUrl || '';
    let href = '';
    if (sharePath) {
      try { href = new URL(sharePath, validOrigin(originInput.value)).href; }
      catch (_) {
        lastTokenUrl = '';urlInput.value = '';copyBtn.hidden = true;
        status.textContent = '链接已生成，请先填写学生可访问的教师机局域网地址。';
        return false;
      }
    }
    lastTokenUrl = href;
    urlInput.value = href || (config && config.enabled && config.has_token
      ? '已开启。刷新后不显示明文令牌，需要新链接请点「重新生成链接」。'
      : '');
    copyBtn.hidden = !href;
    return true;
  }

  async function read() {
    status.textContent = '正在读取…';
    try {
      config = await call('/admin/guest-access');
      configureOrigins(config.share_interfaces, config.share_hosts);
      enabled.checked = !!config.enabled;
      if (!lastTokenUrl) showUrl('');
      status.textContent = config.enabled
        ? '访客链接已开启。请用学生设备打开链接确认能访问。'
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
        if (showUrl(result.share_url_path || ('/classroom/guest/?t=' + result.token))) {
          status.textContent = '已更新。请立即复制，并用学生设备验证能打开；刷新后明文不会再次显示。';
        }
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

  panels.guestLink = { load: read, loaded: false };
  if (activeView === 'settings') { panels.guestLink.loaded = true; read(); }
  enabled.onchange = () => save({ rotate: enabled.checked && !(config && config.has_token) });
  originInput.oninput = () => {
    rememberOrigin(originInput.value);
    originPick.value = [...originPick.options].some(option => option.value === originInput.value)
      ? originInput.value : '';
    if (sharePath && showUrl(sharePath)) status.textContent = '分享地址已更新，可以复制链接。请用学生设备验证。';
  };
  originPick.onchange = () => {
    if (originPick.value) originInput.value = originPick.value;
    originInput.oninput();
  };
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
      status.textContent = '链接已复制。请用学生设备打开确认能访问。';
    } catch (_) {
      urlInput.select();
      status.textContent = '请手动复制输入框中的链接，并用学生设备验证。';
    }
  };
})();
