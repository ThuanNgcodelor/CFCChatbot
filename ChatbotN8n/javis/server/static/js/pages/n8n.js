/** n8n.js — n8n Workflows, Executions, KB Sync */
'use strict';

async function loadN8nWorkflows() {
  const tbody = document.getElementById('workflows-table');
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px"><span class="spinner"></span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/n8n/workflows');
    if (d.error) { tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red);padding:16px">${d.error}</td></tr>`; return; }
    tbody.innerHTML = d.workflows.map(w => `
      <tr>
        <td style="font-weight:500">${w.name}</td>
        <td style="font-family:monospace;font-size:11px;color:var(--text3)">${w.id}</td>
        <td><span class="badge ${w.active ? 'badge-green' : 'badge-gray'}">${w.active ? '▶ Active' : '⏸ Inactive'}</span></td>
        <td style="font-size:11.5px;color:var(--text3)">${w.updatedAt ? new Date(w.updatedAt).toLocaleDateString('vi-VN') : '—'}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="toggleWorkflow('${w.id}','${w.name}',${w.active})">
            ${w.active ? '⏸ Tắt' : '▶ Bật'}
          </button>
        </td>
      </tr>`).join('') || `<tr><td colspan="5" style="text-align:center;color:var(--text3)">Không có workflow</td></tr>`;
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red);padding:16px">Lỗi kết nối n8n. Hãy kiểm tra API key trong Cài đặt.</td></tr>`;
  }
}

async function toggleWorkflow(id, name, isActive) {
  if (!confirm(`${isActive ? 'Tắt' : 'Bật'} workflow "${name}"?`)) return;
  try {
    await fetchJSON(`/admin/n8n/workflows/${id}/toggle`, { method: 'POST' });
    toast(`${isActive ? '⏸ Đã tắt' : '▶ Đã bật'} "${name}"`, 'success');
    loadN8nWorkflows();
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

async function loadExecutions() {
  const tbody = document.getElementById('executions-table');
  tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px"><span class="spinner"></span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/n8n/executions?limit=20');
    if (!d.executions?.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text3)">Chưa có execution</td></tr>`;
      return;
    }
    const statusMap = { success: 'badge-green', error: 'badge-red', running: 'badge-blue', waiting: 'badge-yellow' };
    tbody.innerHTML = d.executions.map(e => `
      <tr>
        <td style="font-weight:500">${e.workflowName}</td>
        <td><span class="badge ${statusMap[e.status] || 'badge-gray'}">${e.status}</span></td>
        <td style="font-size:11.5px;color:var(--text3)">${e.startedAt ? new Date(e.startedAt).toLocaleString('vi-VN') : '—'}</td>
        <td style="font-size:11.5px;color:var(--text3)">${e.stoppedAt ? new Date(e.stoppedAt).toLocaleString('vi-VN') : '—'}</td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--red)">Lỗi kết nối n8n</td></tr>`;
  }
}

async function triggerSync(brand) {
  toast(`Đang sync Knowledge Base (${brand})...`, 'success');
  try {
    const r = await fetchJSON(`/admin/n8n/sync-knowledge?brand=${brand}`, { method: 'POST' });
    const synced = brand === 'all'
      ? `ZeO: ${r.zeo?.synced || 0}, CFC: ${r.cfc?.synced || 0}`
      : `${r.synced} items`;
    toast(`✅ Sync xong! ${synced} FAQ đã vector hóa`, 'success');
  } catch (e) { toast('Lỗi sync: ' + e.message, 'error'); }
}
