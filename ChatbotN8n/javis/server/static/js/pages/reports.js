/** reports.js — AI Executive Reports */
'use strict';

async function loadReports() {
  const container = document.getElementById('report-container');
  try {
    const d = await fetchJSON('/admin/reports/latest');
    if (!d.has_report || !d.report) {
      container.innerHTML = `
        <div class="empty">
          <div class="empty-icon">📈</div>
          <p>Chưa có báo cáo nào được tạo hôm nay.<br>Bấm nút <b>"⚡ Tạo Báo Cáo AI Hôm Nay"</b> để bắt đầu!</p>
        </div>`;
      return;
    }
    renderReport(d.report);
  } catch (e) {
    container.innerHTML = `<div style="color:var(--red);padding:16px">Lỗi tải báo cáo: ${e.message}</div>`;
  }
}

function renderReport(r) {
  const container = document.getElementById('report-container');
  const m = r.metrics || {};
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;border-bottom:1px solid var(--border);padding-bottom:14px;flex-wrap:wrap;gap:10px">
      <div>
        <div style="font-size:15px;font-weight:700">Bản Tin Ngày ${m.date || r.date}</div>
        <div style="font-size:11.5px;color:var(--text3);margin-top:3px">
          Sinh bởi: <span class="badge badge-purple">${r.ai_provider}</span>
          lúc ${new Date(r.generated_at).toLocaleTimeString('vi-VN')}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <span class="badge badge-blue">👥 ${m.total_customers || 0} Khách</span>
        <span class="badge badge-green">📞 ${m.total_leads || 0} Leads</span>
        <span class="badge badge-yellow">❓ ${m.learning_queue_count || 0} LQ</span>
      </div>
    </div>
    <div style="font-size:13.5px;line-height:1.75;color:var(--text);white-space:pre-wrap;font-family:inherit">${r.report_markdown}</div>
  `;
}

async function generateReport(sendTelegram) {
  const btn = document.getElementById('btn-gen-report');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Đang phân tích dữ liệu...';
  toast('AI đang quét dữ liệu và viết báo cáo...', 'success');
  try {
    const d = await fetchJSON(`/admin/reports/generate?send_telegram=${sendTelegram}`, { method: 'POST' });
    if (d.success && d.report) {
      renderReport(d.report);
      toast(sendTelegram ? '✅ Đã tạo báo cáo & gửi qua Telegram!' : '✅ Đã tạo báo cáo thành công!', 'success');
    }
  } catch (e) { toast('Lỗi tạo báo cáo: ' + e.message, 'error'); }
  finally { btn.disabled = false; btn.innerHTML = '⚡ Tạo Báo Cáo AI Hôm Nay'; }
}
