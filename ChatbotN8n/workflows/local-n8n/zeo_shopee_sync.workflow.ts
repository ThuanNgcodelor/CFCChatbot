import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Shopee Catalog Sync
// Nodes   : 6  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTriggerAtMidnight          scheduleTrigger
// ReadShopeeSheetRows                googleSheets               [creds]
// NormalizeShopeeCatalog             code
// WriteShopeeRedisSnapshot           redis                      [creds]
// NotifyFastapiShopeeCache           httpRequest                [onError→regular]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → ReadShopeeSheetRows
//      → NormalizeShopeeCatalog
//        → WriteShopeeRedisSnapshot
//          → NotifyFastapiShopeeCache
// ScheduleTriggerAtMidnight
//    → ReadShopeeSheetRows (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'ivng9UpBOEGTnVvr',
    name: 'Zeo Shopee Catalog Sync',
    active: false,
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1', binaryMode: 'separate' },
})
export class ZeoShopeeCatalogSyncWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: '1a000001-0000-0000-0000-000000000001',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: '1a000001-0000-0000-0000-000000000002',
        name: 'Schedule Trigger at Midnight',
        type: 'n8n-nodes-base.scheduleTrigger',
        version: 1.3,
        position: [0, 352],
    })
    ScheduleTriggerAtMidnight = {
        rule: {
            interval: [
                {
                    field: 'cronExpression',
                    expression: '0 0 * * *',
                },
            ],
        },
    };

    @node({
        id: '1a000001-0000-0000-0000-000000000003',
        name: 'Read Shopee Sheet Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 256],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadShopeeSheetRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1o4vk2YwTVHbuvJxPedTAELCDeQa7iAszZ1kfDKQx0nk/edit?gid=0#gid=0',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 'Shopee_Catalog',
            mode: 'name',
        },
        options: {},
    };

    @node({
        id: '1a000001-0000-0000-0000-000000000004',
        name: 'Normalize Shopee Catalog',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    NormalizeShopeeCatalog = {
        jsCode: `
function text(v) {
  return String(v || '').replace(/\\s+/g, ' ').trim();
}

function asBool(v) {
  if (typeof v === 'boolean') return v;
  return ['true', '1', 'yes', 'y'].includes(String(v || '').trim().toLowerCase());
}

function parseList(v) {
  if (Array.isArray(v)) return v.map(text).filter(Boolean);
  return String(v || '').split(/[;|,]/).map(text).filter(Boolean);
}

const rows = $input.all().map(item => item.json);
const products = [];

for (const r of rows) {
  const active = asBool(r.active ?? true);
  const name = text(r.name);
  const link = text(r.link_shopee || r.shopee_url || r.link);
  if (!active || !name || !link) continue;

  const priceNum = Number(String(r.price || 0).replace(/[^0-9]/g, ''));
  const origPriceNum = Number(String(r.original_price || priceNum).replace(/[^0-9]/g, ''));

  products.push({
    item_id: text(r.item_id || r.id || name),
    name: name,
    brand: text(r.brand || 'ZeO'),
    category: text(r.category || 'Tẩy rửa & Giặt giũ'),
    price: priceNum,
    original_price: origPriceNum,
    discount: text(r.discount || 'Ưu đãi'),
    specs: text(r.specs || name),
    keywords: parseList(r.keywords),
    variants: parseList(r.variants),
    link_shopee: link,
    in_stock: asBool(r.in_stock ?? true),
    updated_at: new Date().toISOString(),
  });
}

if (products.length < 1) {
  throw new Error('Từ chối ghi Redis: Danh mục Shopee không có sản phẩm hợp lệ.');
}

const snapshotJson = JSON.stringify(products);

return [{
  json: {
    snapshot_key: 'zeo:shopee:catalog:active',
    product_count: products.length,
    updated_at: new Date().toISOString(),
    snapshot_json: snapshotJson,
  }
}];
`,
    };

    @node({
        id: '1a000001-0000-0000-0000-000000000005',
        name: 'Write Shopee Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteShopeeRedisSnapshot = {
        operation: 'set',
        key: 'zeo:shopee:catalog:active',
        value: '={{ $json.snapshot_json }}',
    };

    @node({
        id: '1a000001-0000-0000-0000-000000000006',
        name: 'Notify FastAPI Shopee Cache',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1024, 256],
        onError: 'continueRegularOutput',
    })
    NotifyFastapiShopeeCache = {
        method: 'POST',
        url: 'http://127.0.0.1:7777/api/shopee/refresh-cache',
        options: {
            timeout: 10000,
        },
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.ReadShopeeSheetRows.in(0));
        this.ScheduleTriggerAtMidnight.out(0).to(this.ReadShopeeSheetRows.in(0));
        this.ReadShopeeSheetRows.out(0).to(this.NormalizeShopeeCatalog.in(0));
        this.NormalizeShopeeCatalog.out(0).to(this.WriteShopeeRedisSnapshot.in(0));
        this.WriteShopeeRedisSnapshot.out(0).to(this.NotifyFastapiShopeeCache.in(0));
    }
}
