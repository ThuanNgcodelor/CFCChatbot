/** shopee.js — Shopee Catalog CRUD & Google Sheets Sync */
'use strict';

let _shopeeProducts = [];

async function loadShopee() {
  const tbody = document.getElementById('shopee-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px"><span class="spinner"></span> Đang tải Shopee Catalog...</td></tr>`;
  try {
    const d = await fetchJSON('/admin/shopee/catalog');
    _shopeeProducts = d.products || [];
    const countEl = document.getElementById('shopee-count');
    if (countEl) countEl.textContent = `${d.total || 0} sản phẩm`;

    // Load last sync time
    loadShopeeLastSync();

    if (!_shopeeProducts.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text3)">Chưa có sản phẩm trong Shopee Catalog. Bấm <b>"➕ Thêm Sản Phẩm"</b> để tạo mới!</td></tr>`;
      return;
    }
    tbody.innerHTML = _shopeeProducts.map((p, i) => `
      <tr>
        <td><span class="badge ${p.brand === 'ZEO' ? 'badge-purple' : 'badge-blue'}">${p.brand}</span></td>
        <td style="font-weight:600">${p.name}</td>
        <td style="font-size:12px;color:var(--text2)">${p.variant || '—'}</td>
        <td style="font-weight:700;color:var(--green)">${p.price || '—'}</td>
        <td style="font-size:11.5px;color:var(--yellow)">${p.promotion || '—'}</td>
        <td>
          <a href="${p.shopee_url}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm" style="text-decoration:none">🔗 Link</a>
        </td>
        <td>
          <div style="display:flex;gap:4px">
            <button class="btn btn-primary btn-sm" onclick="openEditShopeeModal(${p._idx !== undefined ? p._idx : i})">✏️ Sửa</button>
            <button class="btn btn-danger btn-sm" onclick="deleteShopeeProduct(${p._idx !== undefined ? p._idx : i})">🗑</button>
          </div>
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--red);padding:16px">Lỗi tải Shopee catalog: ${e.message}</td></tr>`;
  }
}

async function loadShopeeLastSync() {
  const syncEl = document.getElementById('shopee-last-sync');
  if (!syncEl) return;
  try {
    const d = await fetchJSON('/admin/shopee/last-sync');
    if (d.last_sync) {
      syncEl.textContent = `Sync lần cuối: ${timeSince(d.last_sync)}`;
    } else {
      syncEl.textContent = '';
    }
  } catch (_) {}
}

function openAddShopeeModal() {
  document.getElementById('shopee-modal-title').textContent = '➕ Thêm Sản Phẩm Shopee Mới';
  document.getElementById('shopee-edit-idx').value = '-1';
  document.getElementById('shopee-form-brand').value = 'ZEO';
  document.getElementById('shopee-form-name').value = '';
  document.getElementById('shopee-form-variant').value = '';
  document.getElementById('shopee-form-price').value = '';
  document.getElementById('shopee-form-promotion').value = '';
  document.getElementById('shopee-form-url').value = '';
  document.getElementById('shopee-form-keywords').value = '';
  document.getElementById('shopee-modal').classList.add('open');
}

function openEditShopeeModal(idx) {
  const p = _shopeeProducts.find(item => (item._idx !== undefined ? item._idx : -1) === idx) || _shopeeProducts[idx];
  if (!p) return;

  document.getElementById('shopee-modal-title').textContent = `✏️ Chỉnh Sửa Sản Phẩm — ${p.name}`;
  document.getElementById('shopee-edit-idx').value = idx;
  document.getElementById('shopee-form-brand').value = p.brand || 'ZEO';
  document.getElementById('shopee-form-name').value = p.name || '';
  document.getElementById('shopee-form-variant').value = p.variant || '';
  document.getElementById('shopee-form-price').value = p.price || '';
  document.getElementById('shopee-form-promotion').value = p.promotion || '';
  document.getElementById('shopee-form-url').value = p.shopee_url || '';
  document.getElementById('shopee-form-keywords').value = (p.keywords || []).join(', ');
  document.getElementById('shopee-modal').classList.add('open');
}

function closeShopeeModal() {
  document.getElementById('shopee-modal')?.classList.remove('open');
}

async function saveShopeeProduct() {
  const idx = parseInt(document.getElementById('shopee-edit-idx').value);
  const brand = document.getElementById('shopee-form-brand').value;
  const name = document.getElementById('shopee-form-name').value.trim();
  const variant = document.getElementById('shopee-form-variant').value.trim();
  const price = document.getElementById('shopee-form-price').value.trim();
  const promotion = document.getElementById('shopee-form-promotion').value.trim();
  const url = document.getElementById('shopee-form-url').value.trim();
  const keywordsStr = document.getElementById('shopee-form-keywords').value.trim();
  const keywords = keywordsStr ? keywordsStr.split(',').map(k => k.trim()).filter(Boolean) : [];

  if (!name || !url) {
    toast('Vui lòng nhập đầy đủ Tên sản phẩm và Link Shopee', 'error');
    return;
  }

  const payload = {
    brand,
    name,
    variant,
    price,
    promotion,
    shopee_url: url,
    keywords,
  };

  try {
    if (idx >= 0) {
      // Update
      await fetchJSON(`/admin/shopee/products/${idx}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      toast(`✅ Đã cập nhật sản phẩm "${name}"!`, 'success');
    } else {
      // Add new
      await fetchJSON('/admin/shopee/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      toast(`✅ Đã thêm sản phẩm "${name}" vào Shopee Catalog!`, 'success');
    }
    closeShopeeModal();
    loadShopee();
  } catch (e) {
    toast('Lỗi lưu sản phẩm: ' + e.message, 'error');
  }
}

async function deleteShopeeProduct(idx) {
  const p = _shopeeProducts.find(item => (item._idx !== undefined ? item._idx : -1) === idx) || _shopeeProducts[idx];
  const name = p?.name || 'sản phẩm này';
  if (!confirm(`Xóa sản phẩm "${name}" khỏi Shopee Catalog?`)) return;

  try {
    await fetchJSON(`/admin/shopee/products/${idx}`, { method: 'DELETE' });
    toast(`✅ Đã xóa "${name}"!`, 'success');
    loadShopee();
  } catch (e) {
    toast('Lỗi xóa sản phẩm: ' + e.message, 'error');
  }
}

async function syncShopeeSheetNow() {
  toast('Đang đồng bộ danh mục Shopee từ Google Sheets...', 'success');
  try {
    const res = await fetchJSON('/admin/shopee/sync-sheet', { method: 'POST' });
    toast(`✅ Sync thành công ${res.synced_count} sản phẩm từ Google Sheets!`, 'success');
    loadShopee();
  } catch (e) {
    toast('Lỗi sync Google Sheets: ' + e.message, 'error');
  }
}
