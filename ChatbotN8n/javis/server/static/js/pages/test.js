/** test.js — Test Bot query */
'use strict';

function setTestBrand(brand, el) {
  APP.testBrand = brand;
  document.querySelectorAll('#page-test .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

async function runTest() {
  const query = document.getElementById('test-query').value.trim();
  if (!query) { toast('Vui lòng nhập câu hỏi trước', 'error'); return; }
  const btn = document.getElementById('test-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> <span>Đang vector search...</span>';
  const result = document.getElementById('test-result');
  result.style.display = 'none';
  try {
    const d = await fetchJSON(`/admin/test/query?query=${encodeURIComponent(query)}&brand=${APP.testBrand}`, { method: 'POST' });
    document.getElementById('res-intent').textContent = d.intent || '(không khớp intent nào)';
    document.getElementById('res-answer').textContent = d.answer || '—';
    const score = Math.round((d.score || 0) * 100);
    document.getElementById('res-score').textContent = `${score}%${d.score_margin ? ' (+' + Math.round(d.score_margin * 100) + '% margin)' : ''}`;
    document.getElementById('res-bar').style.width = score + '%';
    document.getElementById('res-bar').style.background = score >= 78 ? 'var(--success)' : score >= 55 ? 'var(--warning)' : 'var(--danger)';
    const confMap = { high: ['badge-green', 'High Confidence'], medium: ['badge-yellow', 'Medium Confidence'], low: ['badge-red', 'Low / Fallback'] };
    const [cls, lbl] = confMap[d.confidence] || ['badge-gray', 'Unknown'];
    const badge = document.getElementById('res-confidence-badge');
    badge.className = 'badge ' + cls;
    badge.textContent = lbl;
    document.getElementById('res-top5').innerHTML = (d.results || []).map((r, i) => `
      <div style="display:flex;gap:12px;align-items:center;padding:10px 14px;background:${i === 0 ? 'var(--bg-surface2)' : 'var(--bg-card)'};border-radius:var(--r-sm);margin-bottom:6px;border:1px solid ${i === 0 ? 'var(--primary)' : 'var(--border)'}">
        <span style="font-size:11px;color:var(--text-dim);min-width:24px;font-family:'JetBrains Mono',monospace">#${i + 1}</span>
        <span style="flex:1;font-size:13px;font-weight:${i === 0 ? '600' : '400'};color:var(--text-main)">${r.intent}</span>
        <span style="font-size:12px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${r.score >= 0.78 ? 'var(--success)' : r.score >= 0.55 ? 'var(--warning)' : 'var(--text-dim)'}">${Math.round(r.score * 100)}%</span>
        <span class="badge badge-gray" style="font-size:10.5px">${r.category}</span>
      </div>`).join('');
    result.style.display = 'block';
    refreshIcons();
  } catch (e) { toast('Lỗi test: ' + e.message, 'error'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="play"></i><span>Thực Hiện Test</span>';
    refreshIcons();
  }
}
