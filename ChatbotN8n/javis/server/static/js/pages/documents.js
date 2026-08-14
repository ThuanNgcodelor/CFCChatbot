/** documents.js — Document list, Sync, Extract FAQ */
'use strict';

async function loadDocuments() {
  const tbody = document.getElementById('documents-table');
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px"><span class="spinner"></span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/documents');
    if (!d.documents?.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text3)">Chưa có file tài liệu trong thư mục <code>knowledge/</code></td></tr>`;
      return;
    }
    tbody.innerHTML = d.documents.map(doc => `
      <tr>
        <td style="font-weight:600">📄 ${doc.name}</td>
        <td><span class="badge ${doc.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${doc.brand}</span></td>
        <td style="font-size:12px;color:var(--text3)">${doc.size_kb} KB</td>
        <td style="font-size:12px;color:var(--text3)">${doc.modified_at}</td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="extractFaqFromDoc('${doc.name}', '${doc.brand.toLowerCase()}')">⚡ Trích xuất FAQ</button>
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red);padding:16px">Lỗi tải danh sách: ${e.message}</td></tr>`;
  }
}

async function syncDocuments() {
  toast('Đang đồng bộ và vector hóa toàn bộ tài liệu .md...', 'success');
  try {
    const d = await fetchJSON('/admin/documents/sync', { method: 'POST' });
    toast(`✅ Đã đồng bộ ${d.result?.total_files || 0} tài liệu vào Vector Index!`, 'success');
    loadDocuments();
  } catch (e) { toast('Lỗi đồng bộ: ' + e.message, 'error'); }
}

async function extractFaqFromDoc(docName, brand) {
  toast(`AI đang đọc và trích xuất FAQ từ "${docName}"...`, 'success');
  try {
    const d = await fetchJSON('/admin/documents/extract-faq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_name: docName, brand }),
    });
    if (d.faqs?.length) {
      alert(`✅ AI đã trích xuất thành công ${d.faqs.length} cặp FAQ từ tài liệu!\n\nVí dụ:\n- Intent: ${d.faqs[0].intent}\n- Câu hỏi: ${d.faqs[0].question_examples}\n- Trả lời: ${d.faqs[0].answer}`);
    } else {
      toast('Không tìm thấy FAQ phù hợp trong tài liệu', 'error');
    }
  } catch (e) { toast('Lỗi trích xuất: ' + e.message, 'error'); }
}
