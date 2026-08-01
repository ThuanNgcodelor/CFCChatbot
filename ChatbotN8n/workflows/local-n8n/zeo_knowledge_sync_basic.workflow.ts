import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Knowledge Sync Basic
// Nodes   : 5  |  Connections: 4
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// ReadFaqRows                        googleSheets
// NormalizeKnowledge                 code
// WriteKnowledgeSnapshot             googleSheets
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → ReadFaqRows
//      → NormalizeKnowledge
//        → WriteKnowledgeSnapshot
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
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1' },
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
    })
    ReadFaqRows = {
        authentication: 'oAuth2',
        resource: 'sheet',
        operation: 'read',
        documentId: {
            mode: 'url',
            value: '',
        },
        sheetName: {
            mode: 'name',
            value: 'FAQ',
        },
        columns: {
            mappingMode: 'defineBelow',
            value: null,
        },
        range: 'A:H',
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
        mode: 'runOnceForAllItems',
        language: 'javaScript',
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

const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo/pano/oplus']);
const knowledgeItems = $input.all()
  .map((item, index) => normalizeRow(item.json, index))
  .filter(item => item.active)
  .filter(item => allowedBrands.has(brandKey(item.brand)))
  .filter(item => item.answer && item.intent);

knowledgeItems.sort((a, b) => b.priority - a.priority || a.intent.localeCompare(b.intent));

return [{
  json: {
    snapshot_key: 'zeo_kb_basic_v1',
    brand_scope: 'ZeO/PANO/Oplus',
    knowledge_count: knowledgeItems.length,
    updated_at: new Date().toISOString(),
    snapshot_json: JSON.stringify(knowledgeItems),
  }
}];
`,
    };

    @node({
        id: 'c325b9d5-28fc-4871-af86-d289c0cdbeac',
        name: 'Write Knowledge Snapshot',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [768, 256],
    })
    WriteKnowledgeSnapshot = {
        authentication: 'oAuth2',
        resource: 'sheet',
        operation: 'appendOrUpdate',
        documentId: {
            mode: 'url',
            value: '',
        },
        sheetName: {
            mode: 'name',
            value: 'KnowledgeSnapshot',
        },
        dataMode: 'autoMapInputData',
        columns: {
            mappingMode: 'autoMapInputData',
            value: null,
            matchingColumns: ['snapshot_key'],
        },
        columnToMatchOn: 'snapshot_key',
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ReadFaqRows.out(0).to(this.NormalizeKnowledge.in(0));
        this.NormalizeKnowledge.out(0).to(this.WriteKnowledgeSnapshot.in(0));
    }
}
