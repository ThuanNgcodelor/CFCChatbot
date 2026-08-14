/** learning.js — Learning Queue Review & AI Auto-Suggest FAQ */
'use strict';

async function loadLearningQueue() {
  const container = document.getElementById('lq-container');
  if (!container) return;
  container.innerHTML = `<div style="text-align:center;padding:32px"><span class="spinner"></span> Đang tải Learning Queue...</div>`;
  try {
    const d = await fetchJSON(`/admin/learning-queue?brand=${APP.lqBrand}`);
    if (!d.items?.length) {
      container.innerHTML = `
        <div class="empty">
          <div class="empty-icon">✅</div>
          <p>Không có câu nào cần review.<br>Bot đang hoạt động rất tốt!</p>
        </div>`;
      return;
    }
    container.innerHTML = d.items.map((item, i) => `
      <div class="lq-card" id="lq-item-${i}">
        <div class="lq-meta">
          <span class="badge ${item.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${item.brand || '?'}</span>
          ${item.confidence ? `<span class="badge badge-yellow">score: ${Math.round(item.confidence * 100)}%</span>` : ''}
          ${item.timestamp ? `<span style="font-size:11px;color:var(--text3)">${new Date(item.timestamp).toLocaleString('vi-VN')}</span>` : ''}
        </div>
        <div class="lq-query">💬 "${item.user_message || item.query || item.raw || JSON.stringify(item)}"</div>
        ${item.bot_reply ? `<div class="lq-answer">Bot trả lời: ${item.bot_reply}</div>` : ''}
        <div class="lq-actions">
          <button class="btn btn-success btn-sm" onclick="approveLQ(${i}, '${item.brand?.toLowerCase() || 'zeo'}', this, '${encodeURIComponent(item.user_message || item.query || '')}')">✅ Thêm vào FAQ</button>
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

async function approveLQ(idx, brand, btn, rawQueryEncoded = '') {
  const defaultQuery = rawQueryEncoded ? decodeURIComponent(rawQueryEncoded) : '';
  const intent = prompt('Nhập intent name (ví dụ: wholesale_methods):', defaultQuery.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 30));
  if (!intent) return;
  const question = prompt('Câu hỏi mẫu (phân cách bằng ;):', defaultQuery) || defaultQuery;
  const answer = prompt('Nhập câu trả lời chuẩn:');
  if (!answer) return;

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

// ─── AI Auto-Suggest FAQ from Learning Queue (C1) ───
async function triggerAISuggestFAQ() {
  const btn = document.getElementById('btn-ai-suggest-faq');
  const resultDiv = document.getElementById('ai-suggest-results');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> AI đang phân tích Learning Queue...'; }
  toast('AI đang quét và phân tích các câu hỏi chưa trả lời...', 'success');

  try {
    const d = await fetchJSON(`/admin/learning/ai-suggest?brand=${APP.lqBrand}`);
    if (!d.suggestions?.length) {
      toast(d.message || 'Không có đề xuất nào từ AI', 'info');
      return;
    }

    resultDiv.innerHTML = `
      <div style="margin-top:16px;margin-bottom:20px;padding:16px;background:var(--bg2);border:1px solid var(--accent);border-radius:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div style="font-weight:700;color:var(--accent2)">🤖 AI Đã Đề Xuất ${d.suggestions.length} Nhóm FAQ Mới</div>
          <button class="btn btn-ghost btn-sm" onclick="document.getElementById('ai-suggest-results').innerHTML=''">✕ Đóng</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:12px">
          ${d.suggestions.map((s, idx) => `
            <div style="background:var(--bg);padding:14px;border-radius:8px;border:1px solid var(--border)" id="sug-${idx}">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span style="font-weight:700;color:var(--text);font-family:monospace">🎯 ${s.intent}</span>
                <span class="badge ${s.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${s.brand || 'ZEO'}</span>
              </div>
              <div style="font-size:12px;color:var(--text3);margin-bottom:6px">
                <b>Câu hỏi mẫu:</b> ${(s.sample_questions || []).join(' ; ') || s.intent}
              </div>
              <div style="font-size:13px;color:var(--green);background:var(--bg2);padding:10px;border-radius:6px;margin-bottom:10px">
                <b>Câu trả lời đề xuất:</b> ${s.suggested_answer}
              </div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-success btn-sm" onclick="applySuggestion(${idx}, '${s.brand?.toLowerCase() || 'zeo'}', '${s.intent}', '${encodeURIComponent((s.sample_questions || []).join(';'))}', '${encodeURIComponent(s.suggested_answer)}')">
                  ✅ Duyệt FAQ này
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    toast(`✅ AI đã gom nhóm và đề xuất ${d.suggestions.length} FAQ mới!`, 'success');
  } catch (e) {
    toast('Lỗi phân tích AI: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '🤖 AI Phân Tích &amp; Đề Xuất FAQ'; }
  }
}

async function applySuggestion(idx, brand, intent, qEncoded, aEncoded) {
  const question = decodeURIComponent(qEncoded);
  const answer = decodeURIComponent(aEncoded);
  try {
    await fetchJSON(`/admin/learning-queue/approve?brand=${brand}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, question_examples: question, answer, category: 'faq' }),
    });
    toast(`✅ Đã thêm FAQ "${intent}" vào Knowledge Base!`, 'success');
    document.getElementById(`sug-${idx}`)?.remove();
    loadLearningQueue();
  } catch (e) {
    toast('Lỗi duyệt FAQ: ' + e.message, 'error');
  }
}
