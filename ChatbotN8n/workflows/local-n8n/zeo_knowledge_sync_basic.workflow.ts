import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Knowledge Sync Basic
// Nodes   : 6  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// ReadFaqRows                        googleSheets               [creds]
// NormalizeKnowledge                 code
// WriteRedisSnapshot                 redis                      [creds]
// WriteRedisSyncMetadata             redis                      [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → ReadFaqRows
//      → NormalizeKnowledge
//        → WriteRedisSnapshot
//          → WriteRedisSyncMetadata
// ScheduleTrigger
//    → ReadFaqRows (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'DhrLUsDsldhxtTdX',
    name: 'Zeo Knowledge Sync Basic',
    active: false,
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1', binaryMode: 'separate' },
})
export class ZeoKnowledgeSyncBasicWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'dab3bcba-1599-4b04-9c28-1a1e9f472254',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: '348d7851-139b-4e44-baaf-6542a6fc9223',
        name: 'Schedule Trigger',
        type: 'n8n-nodes-base.scheduleTrigger',
        version: 1.3,
        position: [0, 352],
    })
    ScheduleTrigger = {
        rule: {
            interval: [
                {
                    field: 'minutes',
                    minutesInterval: 30,
                },
            ],
        },
    };

    @node({
        id: '7d2703ee-b76b-45ef-939c-0ba057aae77f',
        name: 'Read FAQ Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 256],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadFaqRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1o4vk2YwTVHbuvJxPedTAELCDeQa7iAszZ1kfDKQx0nk/edit?gid=0#gid=0',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 'gid=0',
            mode: 'list',
            cachedResultName: 'FAQ',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1o4vk2YwTVHbuvJxPedTAELCDeQa7iAszZ1kfDKQx0nk/edit#gid=0',
        },
        options: {},
    };

    @node({
        id: 'ca4ea85f-f852-4c5f-b010-8045d68be80a',
        name: 'Normalize Knowledge',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    NormalizeKnowledge = {
        jsCode: `
function normalizeText(value) {
  return String(value || '').replace(/\\s+/g, ' ').trim();
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(String(value || '').trim().toLowerCase());
}

function splitExamples(value) {
  if (Array.isArray(value)) return value.map(String).map(normalizeText).filter(Boolean);
  return String(value || '').split(';').map(normalizeText).filter(Boolean);
}

function normalizeBrand(value) {
  const brand = normalizeText(value || 'ZeO');
  return brand || 'ZeO';
}

function brandKey(value) {
  return normalizeBrand(value).toLowerCase().replace(/\\s*\\/\\s*/g, '/');
}

function normalizeRow(row, index) {
  return {
    active: asBool(row.active ?? true),
    brand: normalizeBrand(row.brand),
    category: normalizeText(row.category || 'faq'),
    intent: normalizeText(row.intent || ''),
    question_examples: splitExamples(row.question_examples),
    answer: normalizeText(row.answer || ''),
    priority: Number(row.priority || 0),
    source_id: normalizeText(row.source_id || 'zeo_faq_google_sheet'),
    updated_at: normalizeText(row.updated_at || new Date().toISOString().slice(0, 10)),
    row_index: index + 1,
  };
}

function fnv1a(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo/oplus', 'zeo/pano', 'zeo/pano/oplus']);
const knowledgeItems = $input.all()
  .map((item, index) => normalizeRow(item.json, index))
  .filter(item => item.active)
  .filter(item => allowedBrands.has(brandKey(item.brand)))
  .filter(item => item.answer && item.intent);

knowledgeItems.sort((a, b) => b.priority - a.priority || a.intent.localeCompare(b.intent));
const snapshotJson = JSON.stringify(knowledgeItems);

return [{
  json: {
    snapshot_key: 'zeo:kb:basic:active',
    brand_scope: 'ZeO/PANO/Oplus',
    knowledge_count: knowledgeItems.length,
    updated_at: new Date().toISOString(),
    schema_version: 1,
    snapshot_hash: fnv1a(snapshotJson),
    snapshot_json: snapshotJson,
  }
}];
`,
    };

    @node({
        id: 'c325b9d5-28fc-4871-af86-d289c0cdbeac',
        name: 'Write Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteRedisSnapshot = {
        operation: 'set',
        key: 'zeo:kb:basic:active',
        value: '={{ JSON.stringify($json) }}',
    };

    @node({
        id: '0be28c5b-7d4d-4bd4-a9b2-1f761c08d3a8',
        name: 'Write Redis Sync Metadata',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1008, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteRedisSyncMetadata = {
        operation: 'set',
        key: 'zeo:sync:faq:basic:last-success',
        value: '={{ JSON.stringify({ snapshot_key: $("Normalize Knowledge").first().json.snapshot_key, knowledge_count: $("Normalize Knowledge").first().json.knowledge_count, updated_at: $("Normalize Knowledge").first().json.updated_at, schema_version: $("Normalize Knowledge").first().json.schema_version, snapshot_hash: $("Normalize Knowledge").first().json.snapshot_hash }) }}',
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ReadFaqRows.out(0).to(this.NormalizeKnowledge.in(0));
        this.NormalizeKnowledge.out(0).to(this.WriteRedisSnapshot.in(0));
        this.WriteRedisSnapshot.out(0).to(this.WriteRedisSyncMetadata.in(0));
    }
}
