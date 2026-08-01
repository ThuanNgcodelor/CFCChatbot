import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Messenger Chatbot Basic RAG
// Nodes   : 10  |  Connections: 10
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GetKnowledgeSnapshot               googleSheets               [onError→regular] [alwaysOutput]
// RagTimKiem                         code
// RouterCoNguon                      if
// GoiOllamaLocal                     httpRequest
// KiemChung                          code
// RouterGuardrail                    if
// NhanKhachAuto                      httpRequest                [creds]
// NhanKhachFallback                  httpRequest                [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// MessengerTrigger
//    → LocDauVao
//      → GetKnowledgeSnapshot
//        → RagTimKiem
//          → RouterCoNguon
//            → GoiOllamaLocal
//              → KiemChung
//                → RouterGuardrail
//                  → NhanKhachAuto
//                 .out(1) → NhanKhachFallback
//           .out(1) → NhanKhachFallback (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'd7fctbMhVUmhrNG0',
    name: 'Zeo Messenger Chatbot Basic RAG',
    active: false,
    isArchived: false,
    settings: { executionOrder: 'v1', binaryMode: 'separate' },
})
export class ZeoMessengerChatbotBasicRagWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'e0767e41-3b17-4747-b905-fd8498514194',
        webhookId: 'cd8401c0-c92f-44c4-b8d1-77b5e7344b07',
        name: 'Messenger Trigger',
        type: 'n8n-nodes-base.facebookTrigger',
        version: 1,
        position: [0, 304],
        credentials: { facebookGraphAppApi: { id: 'f5KemhyXIK0S26xj', name: 'Facebook Graph (App) account' } },
    })
    MessengerTrigger = {
        appId: '1200735049795565',
        object: 'page',
        fields: ['messages'],
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000001',
        name: 'Loc Dau Vao',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [224, 304],
    })
    LocDauVao = {
        jsCode: `
const data = $input.first().json;
let text = '';
let senderId = '';

// n8n Facebook Trigger node outputs the 'entry' object directly
if (data.messaging && data.messaging.length > 0) {
  const messaging = data.messaging[0];
  text = messaging.message?.text || '';
  senderId = messaging.sender?.id || '';
}
// Hoac format don gian nhat (neu n8n boc vo sau hon nua)
else if (data.message && data.sender) {
  text = data.message?.text || '';
  senderId = data.sender?.id || '';
} 
// Hoac data la raw webhook (body.entry...)
else {
  const messaging = data?.body?.entry?.[0]?.messaging?.[0];
  text = messaging?.message?.text || '';
  senderId = messaging?.sender?.id || '';
}

// NEU KHACH KHONG NHAN TIN CHU, DUNG LAI (tranh gui tin rac vao AI)
if (!text || !text.trim()) {
  return [];
}

function normalize(str) {
  return String(str || '')
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}
const sensitiveWords = ['hoan tien', 'doi tra', 'khieu nai', 'lua dao', 'san pham loi', 'hang gia'];
const outOfScopeWords = ['phan bon', 'co bay', 'npk', 'phan huu co'];
const lower = normalize(text);
const isSensitive = sensitiveWords.some(w => lower.includes(w));
const isOutOfScope = outOfScopeWords.some(w => lower.includes(w));
return [{ json: { text: text.trim(), senderId, isSensitive, isOutOfScope } }];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000002',
        name: 'Get Knowledge Snapshot',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [448, 304],
        onError: 'continueRegularOutput',
        alwaysOutputData: true,
    })
    GetKnowledgeSnapshot = {
        authentication: 'oAuth2',
        resource: 'sheet',
        operation: 'read',
        documentId: {
            mode: 'url',
            value: '',
        },
        sheetName: {
            mode: 'name',
            value: 'KnowledgeSnapshot',
        },
        columns: {
            mappingMode: 'autoMapInputData',
            value: null,
        },
        range: 'A:E',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000003',
        name: 'RAG Tim Kiem',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [672, 304],
    })
    RagTimKiem = {
        jsCode: `
function normalize(str) {
  return String(str || '')
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9\\s]/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

function splitTokens(str) {
  return normalize(str).split(/\\s+/).filter(t => t.length >= 2);
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(normalize(value));
}

function splitExamples(value) {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  return String(value || '').split(';').map(s => s.trim()).filter(Boolean);
}

function parseKnowledgeRows(rows) {
  const snapshotRow = rows.find(row => row.snapshot_json || row.knowledgeItems || row.snapshot);
  if (snapshotRow) {
    const raw = snapshotRow.snapshot_json || snapshotRow.knowledgeItems || snapshotRow.snapshot;
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    return Array.isArray(parsed) ? parsed : (parsed.knowledgeItems || []);
  }
  return rows;
}

const rawText     = $('Loc Dau Vao').first().json.text || '';
const senderId    = $('Loc Dau Vao').first().json.senderId;
const isSensitive = $('Loc Dau Vao').first().json.isSensitive;
const isOutOfScope = $('Loc Dau Vao').first().json.isOutOfScope;
const rows = $input.all().map(item => item.json);
const knowledgeItems = parseKnowledgeRows(rows)
  .map(item => ({
    active: asBool(item.active ?? true),
    brand: String(item.brand || 'ZeO').trim(),
    intent: String(item.intent || '').trim(),
    question_examples: splitExamples(item.question_examples),
    answer: String(item.answer || item.content || '').trim(),
    priority: Number(item.priority || 0),
  }))
  .filter(item => item.active && item.answer);

const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo pano oplus', 'zeo/pano/oplus']);
const userTokens = splitTokens(rawText);
const normalizedQuestion = normalize(rawText);

const scored = [];
for (const entry of knowledgeItems) {
  const brand = normalize(entry.brand);
  if (!allowedBrands.has(brand) || brand === 'cfc') continue;

  const exampleTexts = entry.question_examples.length ? entry.question_examples : [entry.intent, entry.answer];
  const exampleTokens = splitTokens(exampleTexts.join(' '));
  let score = 0;

  for (const example of entry.question_examples) {
    const normalizedExample = normalize(example);
    if (normalizedExample && normalizedQuestion.length >= 3 &&
        (normalizedQuestion.includes(normalizedExample) || normalizedExample.includes(normalizedQuestion))) {
      score += 50;
    }
  }

  if (entry.intent && normalizedQuestion.includes(normalize(entry.intent))) score += 12;

  const exampleOverlap = new Set();
  for (const token of userTokens) {
    if (exampleTokens.some(c => c === token || c.includes(token) || token.includes(c))) {
      exampleOverlap.add(token);
    }
  }
  score += exampleOverlap.size * 4;

  if (score > 0) scored.push({ ...entry, score: score + Math.min(entry.priority, 100) / 100 });
}

scored.sort((a, b) => b.score - a.score);
const topItems = scored.slice(0, 3);
const bestScore = topItems[0]?.score || 0;
const hasContext = !isSensitive && !isOutOfScope && bestScore >= 12;

const context = topItems.map((item, idx) => [
  'Nguon ' + (idx + 1) + ': intent=' + item.intent,
  'Answer: ' + item.answer,
].join('\\n')).join('\\n\\n');

return [{
  json: {
    senderId,
    userMessage: rawText,
    hasContext,
    isSensitive,
    isOutOfScope,
    context: hasContext ? context : '',
    contextAnswer: hasContext ? topItems[0].answer : '',
    ragScore: bestScore,
  }
}];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000004',
        name: 'Router Co Nguon',
        type: 'n8n-nodes-base.if',
        version: 2,
        position: [880, 304],
    })
    RouterCoNguon = {
        conditions: {
            options: {
                caseSensitive: true,
                leftValue: '',
                typeValidation: 'strict',
                version: 1,
            },
            conditions: [
                {
                    id: 'cond-has-context',
                    leftValue: '={{ $json.hasContext }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000005',
        name: 'Goi Ollama Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [1104, 160],
    })
    GoiOllamaLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/generate',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen3:8b", stream: false, prompt: "[SYSTEM] Bạn là nhân viên tư vấn khách hàng chuyên nghiệp của ZeO Vietnam. Dựa vào thông tin cung cấp sau đây để trả lời câu hỏi của khách hàng. Hãy trả lời cực kỳ ngắn gọn, tự nhiên, và thân thiện. Không tự bịa thêm thông tin ngoài lề.\\n\\n[THÔNG TIN ZEO VIETNAM]: " + $json.contextAnswer + "\\n\\n[CÂU HỎI KHÁCH HÀNG]: " + $json.userMessage + "\\n\\n[TRẢ LỜI]:" } }}',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000006',
        name: 'Kiem Chung',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1328, 160],
    })
    KiemChung = {
        jsCode: `
const ollamaResult = $input.first().json;
const ragData = $('RAG Tim Kiem').first().json;

// Ollama /api/generate tra ve field "response"
const aiText = (ollamaResult?.response || '').trim();

// Kiem tra chieu dai va chat luong
const tooShort = aiText.length < 5;
const hasRefusal = /khong biet|xin loi|i don|i cannot|i don't know/i.test(aiText);
const passed = !tooShort && !hasRefusal;

// Giot han 1000 ky tu neu qua dai
const finalReply = passed ? aiText.substring(0, 1000) : null;

return [{ json: {
  senderId: ragData.senderId,
  userMessage: ragData.userMessage,
  finalReply,
  passed,
  isSensitive: ragData.isSensitive,
}}];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000007',
        name: 'Router Guardrail',
        type: 'n8n-nodes-base.if',
        version: 2,
        position: [1552, 160],
    })
    RouterGuardrail = {
        conditions: {
            options: {
                caseSensitive: true,
                leftValue: '',
                typeValidation: 'strict',
                version: 1,
            },
            conditions: [
                {
                    id: 'cond-passed',
                    leftValue: '={{ $json.passed }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000008',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [1760, 64],
        credentials: { facebookGraphApi: { id: 'JyJ5NRHHJdzjsL4R', name: 'Facebook Graph account' } },
    })
    NhanKhachAuto = {
        method: 'POST',
        url: 'https://graph.facebook.com/v17.0/me/messages',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'facebookGraphApi',
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ { recipient: { id: $json.senderId }, message: { text: $json.finalReply } } }}',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000009',
        name: 'Nhan Khach Fallback',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [1104, 464],
        credentials: { facebookGraphApi: { id: 'JyJ5NRHHJdzjsL4R', name: 'Facebook Graph account' } },
    })
    NhanKhachFallback = {
        method: 'POST',
        url: 'https://graph.facebook.com/v17.0/me/messages',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'facebookGraphApi',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { recipient: { id: $json.senderId }, message: { text: "Da cam on ban da nhan tin! Admin se phan hoi som nhat nhe!" } } }}',
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.MessengerTrigger.out(0).to(this.LocDauVao.in(0));
        this.LocDauVao.out(0).to(this.GetKnowledgeSnapshot.in(0));
        this.GetKnowledgeSnapshot.out(0).to(this.RagTimKiem.in(0));
        this.RagTimKiem.out(0).to(this.RouterCoNguon.in(0));
        this.RouterCoNguon.out(0).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(1).to(this.NhanKhachFallback.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.NhanKhachAuto.in(0));
        this.RouterGuardrail.out(1).to(this.NhanKhachFallback.in(0));
    }
}
