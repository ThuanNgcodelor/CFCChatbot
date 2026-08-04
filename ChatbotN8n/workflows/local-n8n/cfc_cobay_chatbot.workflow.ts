import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Co Bay Chatbot
// Nodes   : 15  |  Connections: 15
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GetCfcSession                      redis                      [creds] [alwaysOutput]
// GetCfcKnowledgeSnapshot            redis                      [creds] [alwaysOutput]
// CfcRagTimKiem                      code
// RouterCoNguon                      if
// GoiOllamaLocal                     httpRequest
// KiemChung                          code
// RouterGuardrail                    if
// SaveCfcSession                     redis                      [creds]
// NhanKhachAuto                      httpRequest                [creds]
// NhanKhachFallback                  httpRequest                [creds]
// PrepareTelegramAlert               code
// NotifyTelegramOperations           executeWorkflow            [onError→out(1)]
// CfcSetupNote                       stickyNote
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// MessengerTrigger
//    → LocDauVao
//      → GetCfcSession
//        → GetCfcKnowledgeSnapshot
//          → CfcRagTimKiem
//            → RouterCoNguon
//              → GoiOllamaLocal
//                → KiemChung
//                  → RouterGuardrail
//                    → SaveCfcSession
//                      → NhanKhachAuto
//                   .out(1) → NhanKhachFallback
//                   .out(1) → PrepareTelegramAlert
//                      → NotifyTelegramOperations
//             .out(1) → NhanKhachFallback (↩ loop)
//             .out(1) → PrepareTelegramAlert (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'uJOo6NQO2mJZhUAr',
    name: 'CFC Co Bay Chatbot',
    active: false,
    isArchived: false,
    settings: { executionOrder: 'v1', binaryMode: 'separate' },
})
export class CfcCoBayChatbotWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'e91ecffd-fd90-42de-ad11-6bc8ce3f7d00',
        webhookId: '98ef5c46-bab4-4f70-b110-63007639e882',
        name: 'Messenger Trigger',
        type: 'n8n-nodes-base.facebookTrigger',
        version: 1,
        position: [0, 304],
        credentials: { facebookGraphAppApi: { id: 'f5KemhyXIK0S26xj', name: 'Facebook Graph (App) account' } },
    })
    MessengerTrigger = {
        appId: '963255793393378',
        object: 'page',
        fields: ['messages'],
        options: {},
    };

    @node({
        id: '78996a74-05e4-470e-8a9d-e65f082773f0',
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
let messageId = '';
let hasAttachment = false;

if (data.messaging && data.messaging.length > 0) {
  const messaging = data.messaging[0];
  text = messaging.message?.text || messaging.message?.quick_reply?.payload || '';
  senderId = messaging.sender?.id || '';
  messageId = messaging.message?.mid || messaging.message?.quick_reply?.payload || '';
  hasAttachment = Boolean(messaging.message?.attachments?.length);
} else if (data.message && data.sender) {
  text = data.message?.text || data.message?.quick_reply?.payload || '';
  senderId = data.sender?.id || '';
  messageId = data.message?.mid || '';
  hasAttachment = Boolean(data.message?.attachments?.length);
} else {
  const messaging = data?.body?.entry?.[0]?.messaging?.[0];
  text = messaging?.message?.text || messaging?.message?.quick_reply?.payload || '';
  senderId = messaging?.sender?.id || '';
  messageId = messaging?.message?.mid || '';
  hasAttachment = Boolean(messaging?.message?.attachments?.length);
}

function normalize(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

function normalizeForSearch(value) {
  const aliases = {
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin',
    bn: 'ban', mn: 'minh', nt: 'nhan tin', ship: 'giao hang',
  };
  return normalize(value)
    .replace(/[^a-z0-9\\s]/g, ' ')
    .split(/\\s+/)
    .filter(Boolean)
    .map(token => aliases[token] || token)
    .join(' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

const sensitiveWords = ['hoan tien', 'doi tra', 'khieu nai', 'lua dao', 'san pham loi', 'hang gia'];
const outOfScopeWords = ['bot giat', 'zeo', 'pano', 'oplus'];
const normalizedText = normalizeForSearch(text);
const emptyInput = !text || !text.trim();

return [{
  json: {
    text: text.trim(),
    normalizedText,
    senderId,
    messageId,
    emptyInput,
    inputKind: emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text',
    isSensitive: sensitiveWords.some(word => normalizedText.includes(word)),
    isOutOfScope: outOfScopeWords.some(word => normalizedText.includes(word)),
  },
}];
`,
    };

    @node({
        id: '67f7cabe-99bd-4b73-9acd-438022a97e99',
        name: 'Get CFC Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [448, 304],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    GetCfcSession = {
        operation: 'get',
        propertyName: 'sessionRaw',
        key: '={{ "cfc:session:messenger:" + $json.senderId }}',
        keyType: 'string',
        options: {},
    };

    @node({
        id: '7fd2cdbe-b8e7-4da2-b2c2-229780d29a9f',
        name: 'Get CFC Knowledge Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [656, 304],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    GetCfcKnowledgeSnapshot = {
        operation: 'get',
        propertyName: 'knowledgeSnapshot',
        key: 'cfc:kb:basic:active',
        keyType: 'string',
        options: {},
    };

    @node({
        id: '524d8cb5-0700-40d9-8208-cbc289bff804',
        name: 'CFC RAG Tim Kiem',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [880, 304],
    })
    CfcRagTimKiem = {
        jsCode: `
function normalize(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9\\s]/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

function normalizeForSearch(value) {
  const aliases = {
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin',
    bn: 'ban', mn: 'minh', nt: 'nhan tin', ship: 'giao hang',
  };
  return normalize(value).split(/\\s+/).filter(Boolean).map(token => aliases[token] || token).join(' ');
}

function tokens(value) {
  return normalize(value).split(/\\s+/).filter(token => token.length >= 2);
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(normalize(value));
}

function examples(value) {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  return String(value || '').split(';').map(item => item.trim()).filter(Boolean);
}

function parseJson(value, fallback) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try { return JSON.parse(value); } catch (_) { return fallback; }
}

function parseSnapshot(value) {
  const snapshot = parseJson(value, null);
  if (Array.isArray(snapshot)) return snapshot;
  if (!snapshot || typeof snapshot !== 'object') return [];
  const items = snapshot.snapshot_json || snapshot.knowledgeItems || snapshot.snapshot || [];
  const parsed = parseJson(items, items);
  return Array.isArray(parsed) ? parsed : [];
}

const input = $('Loc Dau Vao').first().json;
const snapshot = $input.first().json.knowledgeSnapshot;
const knowledgeItems = parseSnapshot(snapshot)
  .map(item => ({
    active: asBool(item.active ?? true),
    brand: String(item.brand || 'CFC').trim(),
    intent: String(item.intent || '').trim(),
    source_id: String(item.source_id || '').trim(),
    question_examples: examples(item.question_examples),
    answer: String(item.answer || item.content || '').trim(),
    priority: Number(item.priority || 0),
  }))
  .filter(item => item.active && item.answer);

const allowedBrands = new Set(['cfc', 'co bay', 'cfc/co bay', 'cfc co bay']);
const userTokens = tokens(input.normalizedText || input.text);
const question = normalizeForSearch(input.normalizedText || input.text);
const scored = [];

for (const entry of knowledgeItems) {
  if (!allowedBrands.has(normalize(entry.brand))) continue;
  const exampleTexts = entry.question_examples.length ? entry.question_examples : [entry.intent, entry.answer];
  const exampleTokens = tokens(exampleTexts.join(' '));
  let score = 0;

  for (const example of entry.question_examples) {
    const normalizedExample = normalize(example);
    if (normalizedExample && question.length >= 3 &&
        (question.includes(normalizedExample) || normalizedExample.includes(question))) {
      score += 50;
    }
  }

  if (entry.intent && question.includes(normalize(entry.intent))) score += 12;
  const overlap = new Set();
  for (const token of userTokens) {
    if (exampleTokens.some(candidate => candidate === token || candidate.includes(token) || token.includes(candidate))) overlap.add(token);
  }
  score += overlap.size * 4;
  if (score > 0) scored.push({ ...entry, score: score + Math.min(entry.priority, 100) / 100 });
}

scored.sort((a, b) => b.score - a.score);
const topItems = scored.slice(0, 3);
const bestScore = topItems[0]?.score || 0;
const hasContext = !input.emptyInput && !input.isSensitive && !input.isOutOfScope && bestScore >= 12;

let fallbackReason = 'low_confidence';
let fallbackMessage = 'Dạ, thông tin này mình chưa có. Bạn để lại số điện thoại và khu vực, admin Cò Bay sẽ hỗ trợ bạn sớm nhất nha.';
if (input.emptyInput) {
  fallbackReason = 'empty_or_unsupported_message';
  fallbackMessage = 'Bạn gửi giúp mình nội dung cần hỗ trợ bằng tin nhắn chữ nhé.';
} else if (input.isSensitive) {
  fallbackReason = 'sensitive_case';
  fallbackMessage = 'Dạ, mình đã ghi nhận thông tin. Admin Cò Bay sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (input.isOutOfScope) {
  fallbackReason = 'out_of_scope';
  fallbackMessage = 'Dạ, mình đang hỗ trợ thông tin sản phẩm Cò Bay. Bạn cần tư vấn về sản phẩm hoặc dịch vụ nào ạ?';
} else if (!snapshot) {
  fallbackReason = 'knowledge_snapshot_missing';
}

const context = topItems.map((item, index) => [
  'Nguon ' + (index + 1) + ': intent=' + item.intent,
  'Answer: ' + item.answer,
].join('\\n')).join('\\n\\n');

return [{
  json: {
    senderId: input.senderId,
    userMessage: input.text,
    hasContext,
    contextAnswer: hasContext ? topItems[0].answer : '',
    matchedIntent: hasContext ? topItems[0].intent : '',
    fallbackReason,
    fallbackMessage,
    ragScore: bestScore,
  },
}];
`,
    };

    @node({
        id: '1c3c5481-d335-462b-9cc6-460edb2c5a48',
        name: 'Router Co Nguon',
        type: 'n8n-nodes-base.if',
        version: 2,
        position: [1088, 304],
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
                    id: 'cfc-has-context',
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
        id: '51e55064-a36d-49ef-a998-a060271d41a6',
        name: 'Goi Ollama Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [1312, 160],
    })
    GoiOllamaLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/generate',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0.2, num_predict: 120 }, prompt: "[SYSTEM] Bạn là nhân viên tư vấn khách hàng của Cò Bay (CFC). Chỉ dùng thông tin tham chiếu bên dưới. Không tự bịa thêm thông tin. Trả lời ngắn gọn, tự nhiên, thân thiện và bằng tiếng Việt có dấu.\\n\\n[THÔNG TIN THAM CHIẾU]: " + $json.contextAnswer + "\\n\\n[CÂU HỎI KHÁCH HÀNG]: " + $json.userMessage + "\\n\\n[TRẢ LỜI]:" } }}',
        options: {},
    };

    @node({
        id: 'cd26a86f-1e00-4533-a6e7-25ee677663ef',
        name: 'Kiem Chung',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1536, 160],
    })
    KiemChung = {
        jsCode: `
const ollamaResult = $input.first().json;
const ragData = $('CFC RAG Tim Kiem').first().json;
const aiText = (ollamaResult?.response || '').trim();
const tooShort = aiText.length < 5;
const tooLong = aiText.length > 1000;
const hasRefusal = /khong biet|xin loi|i don|i cannot|i don't know|thong tin tham chieu|system prompt/i.test(aiText);
const mentionsOtherBrand = /zeo|pano|oplus|bot giat/i.test(aiText);
const passed = !tooShort && !tooLong && !hasRefusal && !mentionsOtherBrand;

return [{
  json: {
    senderId: ragData.senderId,
    userMessage: ragData.userMessage,
    finalReply: passed ? aiText.substring(0, 1000) : null,
    passed,
    ragScore: ragData.ragScore,
    matchedIntent: ragData.matchedIntent,
    fallbackReason: passed ? '' : 'ollama_guardrail_failed',
    fallbackMessage: ragData.fallbackMessage,
  },
}];
`,
    };

    @node({
        id: 'c8d75ddb-ef5f-4e98-887a-a8f6c50f1e80',
        name: 'Router Guardrail',
        type: 'n8n-nodes-base.if',
        version: 2,
        position: [1760, 160],
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
                    id: 'cfc-passed',
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
        id: 'af8566d8-4b53-4cb5-b2c5-dfa1717df123',
        name: 'Save CFC Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1984, 64],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    SaveCfcSession = {
        operation: 'set',
        key: '={{ "cfc:session:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify({ last_intent: $json.matchedIntent, last_user_message: $json.userMessage, last_bot_reply: $json.finalReply, updated_at: $now.toISO() }) }}',
        expire: true,
        ttl: 1800,
    };

    @node({
        id: '965d18a8-f64f-458d-adb9-3c1538209a80',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [2208, 64],
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
        id: 'a5e52216-a205-4813-a205-d2f0e4e3cdd6',
        name: 'Nhan Khach Fallback',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [1536, 464],
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
            '={{ { recipient: { id: $json.senderId }, message: { text: $json.fallbackMessage || "Dạ, admin Cò Bay sẽ phản hồi bạn sớm nhất nhé." } } }}',
        options: {},
    };

    @node({
        id: 'e128792b-7337-4200-b73e-6948519fba8b',
        name: 'Prepare Telegram Alert',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1776, 584],
    })
    PrepareTelegramAlert = {
        jsCode: `
const event = $input.first().json;

return [{
  json: {
    brand: 'CFC',
    event_type: event.isSensitive ? 'URGENT' : 'REVIEW',
    priority: event.isSensitive ? 'high' : 'normal',
    sender_id: event.senderId || '',
    user_message: event.userMessage || '',
    bot_reply: event.finalReply || event.fallbackMessage || '',
    fallback_reason: event.fallbackReason || 'unknown',
    rag_score: Number(event.ragScore || 0),
    created_at: new Date().toISOString(),
  },
}];
`,
    };

    @node({
        id: 'c94ba04a-60cb-4fef-9dd4-7f4bea08794d',
        name: 'Notify Telegram Operations',
        type: 'n8n-nodes-base.executeWorkflow',
        version: 1.3,
        position: [2016, 584],
        onError: 'continueErrorOutput',
    })
    NotifyTelegramOperations = {
        operation: 'call_workflow',
        source: 'database',
        workflowId: 'f2IjxVj9sW3KQRAw',
        workflowInputs: {
            mappingMode: 'passthrough',
            value: {},
        },
        mode: 'each',
        options: {
            waitForSubWorkflow: false,
        },
    };

    @node({
        id: '47a44df8-7039-4efa-b954-c0484555ca4b',
        name: 'CFC Setup Note',
        type: 'n8n-nodes-base.stickyNote',
        version: 1,
        position: [1392, -192],
    })
    CfcSetupNote = {
        content:
            'CFC uses cfc:* Redis keys. Configure the dedicated CFC Facebook App and Page credentials before publishing.',
        height: 160,
        width: 300,
        color: 5,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.MessengerTrigger.out(0).to(this.LocDauVao.in(0));
        this.LocDauVao.out(0).to(this.GetCfcSession.in(0));
        this.GetCfcSession.out(0).to(this.GetCfcKnowledgeSnapshot.in(0));
        this.GetCfcKnowledgeSnapshot.out(0).to(this.CfcRagTimKiem.in(0));
        this.CfcRagTimKiem.out(0).to(this.RouterCoNguon.in(0));
        this.RouterCoNguon.out(0).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(1).to(this.NhanKhachFallback.in(0));
        this.RouterCoNguon.out(1).to(this.PrepareTelegramAlert.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.SaveCfcSession.in(0));
        this.RouterGuardrail.out(1).to(this.NhanKhachFallback.in(0));
        this.RouterGuardrail.out(1).to(this.PrepareTelegramAlert.in(0));
        this.SaveCfcSession.out(0).to(this.NhanKhachAuto.in(0));
        this.PrepareTelegramAlert.out(0).to(this.NotifyTelegramOperations.in(0));
    }
}
