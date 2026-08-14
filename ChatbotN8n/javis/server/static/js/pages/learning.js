/** learning.js — Learning Queue Review */
'use strict';

async function loadLearningQueue() {
  const container = document.getElementById('lq-container');
  container.innerHTML = `<div style="text-align:center;padding:32px"><span class="spinner"></span> Đang tải...</div>`;
  try {
    const d = await fetchJSON(`/admin/learning-queue?brand=${APP.lqBrand}`);
    if (!d.items?.length) {
      container.innerHTML = `
        <div class="empty">
          <div class="empty-icon">✅</div>
          <p>Không có câu nào cần review.<br>Bot đang hoạt động tốt!</p>
        </div>`;
      return;
    }
    container.innerHTML = d.items.map((item, i) => `
      <div class="lq-card" id="lq-item-${i}">
        <div class="lq-meta">
          <span class="badge ${item.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${item.brand || '?'}</span>
          ${item.confidence ? `<span class="badge badge-yellow">score: ${item.confidence}</span>` : ''}
          ${item.timestamp ? `<span style="font-size:11px;color:var(--text3)">${new Date(item.timestamp).toLocaleString('vi-VN')}</span>` : ''}
        </div>
        <div class="lq-query">💬 "${item.user_message || item.query || item.raw || JSON.stringify(item)}"</div>
        ${item.bot_reply ? `<div class="lq-answer">Bot trả lời: ${item.bot_reply}</div>` : ''}
        <div class="lq-actions">
          <button class="btn btn-success btn-sm" onclick="approveLQ(${i}, '${item.brand?.toLowerCase() || 'zeo'}', this)">✅ Thêm vào FAQ</button>
          <button class="btn btn-danger btn-sm" onclick="document.getElementById('lq-item-${i}').style.display='none'">🗑 Bỏ qua</button>
        </div>
      </div>`).join('');
  } catch (e) {
    container.innerHTML = `
      <div class="empty">
        <div class="empty-icon">⚠️</div>
        <p>Chưa có learning queue nào.<br><small>Key format: {brand}:learning:queue</small></p>
      </div>`;
  }
}

function setLQBrand(brand, el) {
  APP.lqBrand = brand;
  document.querySelectorAll('#page-learning .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  loadLearningQueue();
}

async function approveLQ(idx, brand, btn) {
  const intent = prompt('Nhập intent name (ví dụ: shipping_methods):');
  if (!intent) return;
  const answer = prompt('Nhập câu trả lời chuẩn:');
  if (!answer) return;
  const question = prompt('Câu hỏi mẫu (phân cách bằng ;):') || '';
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    await fetchJSON(`/admin/learning-queue/approve?brand=${brand}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, question_examples: question, answer, category: 'faq' }),
    });
    toast('✅ Đã thêm vào FAQ và cập nhật Vector Index!', 'success');
    document.getElementById('lq-item-' + idx).style.display = 'none';
  } catch (e) {
    toast('Lỗi: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = '✅ Thêm vào FAQ';
  }
}
