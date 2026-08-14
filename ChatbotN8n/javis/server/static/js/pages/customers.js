/** customers.js — Customers CRUD, Session & Chat History Viewer, Filter Chips, Export CSV, Admin Notes & Tags */
'use strict';

let _filterHasPhone = 'all'; // 'all' | 'yes' | 'no'
let _filterStage = 'all';

async function loadCustomers() {
  APP.allCustomers = [];
  const tbody = document.getElementById('customers-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px"><span class="spinner"></span> Đang tải danh sách khách hàng...</td></tr>`;
  try {
    const d = await fetchJSON(`/admin/customers?brand=${APP.customerBrand}&page=1&page_size=500`);
    APP.allCustomers = d.customers || [];
    APP.customerPage = 1;
    renderCustomers();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:var(--red);padding:16px">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
  }
}

function setCustomerBrand(brand, el) {
  APP.customerBrand = brand;
  document.querySelectorAll('#page-customers .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  loadCustomers();
}

function setPhoneFilter(val, el) {
  _filterHasPhone = val;
  document.querySelectorAll('.filter-phone-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  APP.customerPage = 1;
  renderCustomers();
}

function setStageFilter(val) {
  _filterStage = val;
  APP.customerPage = 1;
  renderCustomers();
}

function filterCustomers() { APP.customerPage = 1; renderCustomers(); }

function renderCustomers() {
  const search = document.getElementById('customer-search')?.value.toLowerCase() || '';
  let filtered = APP.allCustomers.filter(c => {
    // Search match
    const matchSearch = !search ||
      c.phone?.includes(search) ||
      c.fb_name?.toLowerCase().includes(search) ||
      c.area?.toLowerCase().includes(search) ||
      c.sender_id?.includes(search) ||
      c.admin_notes?.toLowerCase().includes(search);

    // Phone filter
    const hasPhone = Boolean(c.phone && c.phone.trim() && c.phone !== '—');
    const matchPhone = _filterHasPhone === 'all' ||
      (_filterHasPhone === 'yes' && hasPhone) ||
      (_filterHasPhone === 'no' && !hasPhone);

    // Stage filter
    const matchStage = _filterStage === 'all' || c.lead_stage === _filterStage;

    return matchSearch && matchPhone && matchStage;
  });

  const pageSize = 25;
  const total = filtered.length;
  const start = (APP.customerPage - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);
  const tbody = document.getElementById('customers-table');
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:32px;color:var(--text3)">Không tìm thấy khách hàng nào theo bộ lọc</td></tr>`;
  } else {
    tbody.innerHTML = items.map(c => {
      const hasNotes = Boolean(c.admin_notes && c.admin_notes.trim());
      const tags = (c.admin_tags || []).map(t => `<span class="badge badge-purple" style="font-size:10px;padding:2px 5px;margin-right:2px">${t}</span>`).join('');

      return `
      <tr>
        <td><span class="badge ${c.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${c.brand}</span></td>
        <td style="font-family:monospace;font-size:11px;color:var(--text3)">${c.sender_id?.slice(-10)}</td>
        <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          <div style="font-weight:600">${c.fb_name || '<span style="color:var(--text3)">—</span>'}</div>
          ${tags}
        </td>
        <td style="font-weight:600;color:${c.phone ? 'var(--green)' : 'var(--text3)'}">
          ${c.phone ? `<code>${c.phone}</code>` : '—'}
        </td>
        <td style="font-size:12px;color:var(--text2);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.area || '—'}</td>
        <td>${stageBadge(c.lead_stage)}</td>
        <td style="font-size:11px;color:var(--text3);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${hasNotes ? `<span title="Ghi chú: ${c.admin_notes}">📝 </span>` : ''}${c.last_intent || '—'}
        </td>
        <td>
          <div style="display:flex;gap:3px">
            <button class="btn btn-ghost btn-sm" title="Xem lịch sử chat" onclick="viewHistory('${c.brand.toLowerCase()}','${c.sender_id}')">💬 Chat</button>
            <button class="btn btn-icon btn-sm" title="Xem session raw" onclick="viewSession('${c.brand.toLowerCase()}','${c.sender_id}')">👁</button>
            <button class="btn btn-primary btn-sm" title="Chỉnh sửa & Ghi chú" onclick="openEditCustomer('${c.brand.toLowerCase()}','${c.sender_id}')">✏️</button>
            <button class="btn btn-danger btn-sm" title="Xóa hoàn toàn" onclick="deleteCustomer('${c.brand.toLowerCase()}','${c.sender_id}')">🗑</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  // Pagination
  const pages = Math.ceil(total / pageSize);
  const pagDiv = document.getElementById('customer-pagination');
  if (!pagDiv) return;
  if (pages <= 1) { pagDiv.innerHTML = `<span style="font-size:12px;color:var(--text3)">${total} khách hàng</span>`; return; }
  let html = `<span style="font-size:12px;color:var(--text3);margin-right:8px">${total} khách hàng</span>`;
  for (let i = 1; i <= Math.min(pages, 10); i++) {
    html += `<button class="page-btn ${i === APP.customerPage ? 'active' : ''}" onclick="goCustomerPage(${i})">${i}</button>`;
  }
  pagDiv.innerHTML = html;
}

function goCustomerPage(p) { APP.customerPage = p; renderCustomers(); }

async function openEditCustomer(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/session`);
    const p = d.profile || {};
    document.getElementById('edit-cust-brand').value = brand;
    document.getElementById('edit-cust-sender-id').value = senderId;
    document.getElementById('edit-cust-name').value = p.fb_name || '';
    document.getElementById('edit-cust-phone').value = p.phone || p.customer_phone || '';
    document.getElementById('edit-cust-area').value = p.area || p.customer_location || '';
    document.getElementById('edit-cust-intent').value = p.last_intent || '';
    document.getElementById('edit-cust-stage').value = p.lead_stage || 'new';
    document.getElementById('edit-cust-notes').value = p.admin_notes || '';
    document.getElementById('edit-cust-tags').value = (p.admin_tags || []).join(', ');
    document.getElementById('edit-modal-title').textContent = `✏️ Sửa & Ghi Chú — ...${senderId.slice(-8)} (${brand.toUpperCase()})`;
    document.getElementById('edit-customer-modal').classList.add('open');
  } catch (e) { toast('Lỗi tải thông tin: ' + e.message, 'error'); }
}

async function saveEditCustomer() {
  const brand = document.getElementById('edit-cust-brand').value;
  const senderId = document.getElementById('edit-cust-sender-id').value;
  const tagsStr = document.getElementById('edit-cust-tags').value.trim();
  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

  const payload = {
    fb_name:     document.getElementById('edit-cust-name').value.trim(),
    phone:       document.getElementById('edit-cust-phone').value.trim(),
    area:        document.getElementById('edit-cust-area').value.trim(),
    lead_stage:  document.getElementById('edit-cust-stage').value,
    last_intent: document.getElementById('edit-cust-intent').value.trim(),
    admin_notes: document.getElementById('edit-cust-notes').value.trim(),
    admin_tags:  tags,
  };
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    toast('✅ Đã cập nhật thông tin và ghi chú thành công!', 'success');
    closeEditModal();
    loadCustomers();
    loadStats();
  } catch (e) { toast('Lỗi lưu: ' + e.message, 'error'); }
}

async function deleteCustomer(brand, senderId) {
  if (!confirm(`⚠️ Xóa HOÀN TOÀN khách ${senderId} khỏi Redis?\nHành động này không thể hoàn tác.`)) return;
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}`, { method: 'DELETE' });
    toast(`✅ Đã xóa khách hàng!`, 'success');
    loadCustomers(); loadStats();
  } catch (e) { toast('Lỗi xóa: ' + e.message, 'error'); }
}

async function viewSession(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/session`);
    const p = d.profile || {};
    document.getElementById('modal-title').textContent = `Session — ...${senderId.slice(-10)} (${brand.toUpperCase()})`;
    document.getElementById('modal-content').innerHTML = `
      <div class="session-field"><div class="session-label">SĐT</div><div class="session-value">${p.phone || p.customer_phone || '—'}</div></div>
      <div class="session-field"><div class="session-label">Khu vực</div><div class="session-value">${p.area || p.customer_location || '—'}</div></div>
      <div class="session-field"><div class="session-label">Lead Stage</div><div class="session-value">${p.lead_stage || '—'}</div></div>
      <div class="session-field"><div class="session-label">Intent cuối</div><div class="session-value">${p.last_intent || '—'}</div></div>
      <div class="session-field"><div class="session-label">Ghi chú Admin</div><div class="session-value">${p.admin_notes || '—'}</div></div>
      <div class="session-field"><div class="session-label">Tags</div><div class="session-value">${(p.admin_tags || []).join(', ') || '—'}</div></div>
      <div class="session-field"><div class="session-label">Session JSON</div><div class="session-value code">${JSON.stringify(d.session, null, 2)}</div></div>
      <button class="btn btn-danger btn-sm" style="margin-top:12px" onclick="resetSession('${brand}','${senderId}');closeModal()">↺ Reset Session</button>
    `;
    document.getElementById('session-modal').classList.add('open');
  } catch (e) { toast('Lỗi tải session: ' + e.message, 'error'); }
}

async function viewHistory(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/history`);
    const modal = document.getElementById('history-modal');
    document.getElementById('history-modal-title').textContent = `💬 Lịch Sử Chat — ...${senderId.slice(-10)} (${brand.toUpperCase()})`;

    const msgs = d.messages || [];
    const container = document.getElementById('history-messages-container');

    if (!msgs.length) {
      container.innerHTML = `<div class="empty" style="padding:24px"><p>Chưa có lịch sử tin nhắn được lưu trong Redis cho khách này.</p></div>`;
    } else {
      container.innerHTML = msgs.map((m, i) => {
        const isUser = m.role === 'user' || m.sender === 'user' || m.from === 'user' || m.user_message;
        const text = m.text || m.content || m.user_message || m.bot_reply || m.raw || JSON.stringify(m);
        const time = m.timestamp ? new Date(m.timestamp).toLocaleTimeString('vi-VN') : '';
        const intent = m.intent ? `<span class="badge badge-purple" style="font-size:10px">${m.intent}</span>` : '';

        return `
          <div class="chat-bubble ${isUser ? 'chat-user' : 'chat-bot'}">
            <div class="chat-header">
              <span class="chat-sender">${isUser ? '👤 Khách' : '🤖 CFC Bot'}</span>
              ${time ? `<span class="chat-time">${time}</span>` : ''}
              ${intent}
            </div>
            <div class="chat-text">${text}</div>
          </div>
        `;
      }).join('');
    }

    modal.classList.add('open');
  } catch (e) {
    toast('Lỗi tải lịch sử chat: ' + e.message, 'error');
  }
}

function closeHistoryModal() {
  document.getElementById('history-modal')?.classList.remove('open');
}

async function resetSession(brand, senderId) {
  if (!confirm(`Reset session của ${senderId}?`)) return;
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}/session`, { method: 'DELETE' });
    toast('Đã reset session!', 'success');
    loadCustomers();
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

function exportCustomersCSV() {
  const brand = APP.customerBrand;
  const hasPhoneParam = _filterHasPhone === 'yes' ? '&has_phone=true' : _filterHasPhone === 'no' ? '&has_phone=false' : '';
  const stageParam = _filterStage !== 'all' ? `&lead_stage=${_filterStage}` : '';
  const url = `/admin/customers/export?brand=${brand}${hasPhoneParam}${stageParam}`;

  toast('Đang xuất file CSV...', 'success');
  window.open(url, '_blank');
}
