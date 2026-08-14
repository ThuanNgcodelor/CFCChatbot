/** shopee.js — Shopee Catalog View */
'use strict';

async function loadShopee() {
  const tbody = document.getElementById('shopee-table');
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px"><span class="spinner"></span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/shopee/catalog');
    const countEl = document.getElementById('shopee-count');
    if (countEl) countEl.textContent = `${d.total || 0} sản phẩm`;
    if (!d.products?.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text3)">Chưa có sản phẩm trong Shopee Catalog</td></tr>`;
      return;
    }
    tbody.innerHTML = d.products.map(p => `
      <tr>
        <td><span class="badge ${p.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${p.brand}</span></td>
        <td style="font-weight:600">${p.name}</td>
        <td style="font-size:12px;color:var(--text2)">${p.variant || '—'}</td>
        <td style="font-weight:700;color:var(--green)">${p.price || '—'}</td>
        <td style="font-size:11.5px;color:var(--yellow)">${p.promotion || '—'}</td>
        <td>
          <a href="${p.shopee_url}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">🔗 Mở Link</a>
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--red);padding:16px">Lỗi tải Shopee catalog: ${e.message}</td></tr>`;
  }
}
