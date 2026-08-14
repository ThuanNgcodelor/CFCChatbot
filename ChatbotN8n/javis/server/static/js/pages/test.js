/** test.js — Test Bot query */
'use strict';

function setTestBrand(brand, el) {
  APP.testBrand = brand;
  document.querySelectorAll('#page-test .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

async function runTest() {
  const query = document.getElementById('test-query').value.trim();
  if (!query) { toast('Nhập câu hỏi trước', 'error'); return; }
  const btn = document.getElementById('test-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Đang test...';
  const result = document.getElementById('test-result');
  result.style.display = 'none';
  try {
    const d = await fetchJSON(`/admin/test/query?query=${encodeURIComponent(query)}&brand=${APP.testBrand}`, { method: 'POST' });
    document.getElementById('res-intent').textContent = d.intent || '(không khớp)';
    document.getElementById('res-answer').textContent = d.answer || '—';
    const score = Math.round((d.score || 0) * 100);
    document.getElementById('res-score').textContent = `${score}%${d.score_margin ? ' (+' + Math.round(d.score_margin * 100) + '% margin)' : ''}`;
    document.getElementById('res-bar').style.width = score + '%';
    document.getElementById('res-bar').style.background = score >= 78 ? 'var(--green)' : score >= 55 ? 'var(--yellow)' : 'var(--red)';
    const confMap = { high: ['badge-green', '✅ High'], medium: ['badge-yellow', '⚠️ Medium'], low: ['badge-red', '❌ Low'] };
    const [cls, lbl] = confMap[d.confidence] || ['badge-gray', '? Unknown'];
    const badge = document.getElementById('res-confidence-badge');
    badge.className = 'badge ' + cls;
    badge.textContent = lbl;
    document.getElementById('res-top5').innerHTML = (d.results || []).map((r, i) => `
      <div style="display:flex;gap:10px;align-items:center;padding:8px 10px;background:${i === 0 ? 'var(--bg3)' : 'var(--bg2)'};border-radius:6px;margin-bottom:4px;border:1px solid ${i === 0 ? 'var(--accent)' : 'var(--border)'}">
        <span style="font-size:10.5px;color:var(--text3);min-width:22px">#${i + 1}</span>
        <span style="flex:1;font-size:12px">${r.intent}</span>
        <span style="font-size:11px;font-weight:700;color:${r.score >= 0.78 ? 'var(--green)' : r.score >= 0.55 ? 'var(--yellow)' : 'var(--text3)'}">${Math.round(r.score * 100)}%</span>
        <span style="font-size:10.5px;color:var(--text3)">${r.category}</span>
      </div>`).join('');
    result.style.display = 'block';
  } catch (e) { toast('Lỗi test: ' + e.message, 'error'); }
  finally { btn.disabled = false; btn.innerHTML = '▶ Test'; }
}
