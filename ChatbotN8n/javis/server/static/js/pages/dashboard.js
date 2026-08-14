/** dashboard.js — Dashboard: Status cards, Stat numbers, Intent charts */
'use strict';

async function loadStatus() {
  try {
    const s = await fetchJSON('/admin/status');
    const svc = s.services;
    setServiceStatus('redis', svc.redis);
    setServiceStatus('ollama', svc.ollama);
    setServiceStatus('n8n', svc.n8n);
  } catch (e) { console.error('loadStatus', e); }
}

function setServiceStatus(name, svc) {
  const dot = document.getElementById('dot-' + name);
  const detail = document.getElementById('detail-' + name);
  if (!dot || !detail) return;
  if (!svc) { dot.className = 'status-dot error'; detail.textContent = 'Lỗi'; return; }
  if (svc.status === 'ok') {
    dot.className = 'status-dot ok';
    if (name === 'redis')
      detail.textContent = `v${svc.version} · uptime ${Math.floor(svc.uptime_seconds / 3600)}h`;
    else if (name === 'ollama')
      detail.textContent = `${svc.models?.length || 0} models · bge-m3: ${svc.embed_ready ? '✅' : '⚠️'}`;
    else if (name === 'n8n')
      detail.textContent = `${svc.active_workflows}/${svc.total_workflows} active`;
  } else if (svc.status === 'no_api_key') {
    dot.className = 'status-dot warn';
    detail.textContent = 'Thiếu API key n8n';
  } else {
    dot.className = 'status-dot error';
    detail.textContent = svc.detail?.substring(0, 50) || 'Lỗi';
  }
}

async function loadStats() {
  try {
    const s = await fetchJSON('/admin/stats/today');
    document.getElementById('stat-total').textContent = s.total_customers;
    document.getElementById('stat-zeo').textContent = s.zeo?.customers || 0;
    document.getElementById('stat-cfc').textContent = s.cfc?.customers || 0;
    const lq = (s.zeo?.learning_queue_count || 0) + (s.cfc?.learning_queue_count || 0);
    document.getElementById('stat-lq').textContent = lq;
    const badge = document.getElementById('lq-badge');
    if (badge) { badge.textContent = lq; badge.className = lq > 0 ? 'nav-badge visible' : 'nav-badge'; }
    renderIntents('zeo', s.zeo?.top_intents || {});
    renderIntents('cfc', s.cfc?.top_intents || {});
    setLastUpdated();
  } catch (e) { console.error('loadStats', e); }
}

function renderIntents(brand, intents) {
  const tbody = document.getElementById('intents-' + brand);
  if (!tbody) return;
  const entries = Object.entries(intents).slice(0, 8);
  if (!entries.length) {
    tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--text3)">Chưa có dữ liệu</td></tr>`;
    return;
  }
  const max = entries[0]?.[1] || 1;
  tbody.innerHTML = entries.map(([intent, count]) => `
    <tr>
      <td>
        <div style="font-size:12px;font-weight:500;margin-bottom:3px">${intent}</div>
        <div style="height:3px;background:var(--border);border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${Math.round(count / max * 100)}%;background:var(--accent);border-radius:2px;transition:width .4s"></div>
        </div>
      </td>
      <td style="font-weight:700;text-align:right;font-size:13px">${count}</td>
    </tr>`).join('');
}
