import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Chatbot
// Nodes   : 16  |  Connections: 15
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger
// LocDauVao                          code
// GetSession                         redis                      [creds] [alwaysOutput]
// GetKnowledgeSnapshot               redis                      [creds] [alwaysOutput]
// RagTimKiem                         code
// RouterCoNguon                      if
// GoiOllamaLocal                     httpRequest
// KiemChung                          code
// RouterGuardrail                    if
// SaveSession                        redis                      [creds]
// QueueLearningReview                redis                      [creds]
// PrepareTelegramAlert               code
// NotifyTelegramOperations           executeWorkflow            [onError→out(1)]
// NhanKhachAuto                      httpRequest
// NhanKhachFallback                  httpRequest
// StickyNote                         stickyNote
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// MessengerTrigger
//    → LocDauVao
//      → GetSession
//        → GetKnowledgeSnapshot
//          → RagTimKiem
//            → RouterCoNguon
//              → GoiOllamaLocal
//                → KiemChung
//                  → RouterGuardrail
//                    → SaveSession
//                      → NhanKhachAuto
//                   .out(1) → QueueLearningReview
//                      → NhanKhachFallback
//                      → PrepareTelegramAlert
//                        → NotifyTelegramOperations
//             .out(1) → QueueLearningReview (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'd7fctbMhVUmhrNG0',
    name: 'Zeo Chatbot',
    active: false,
    isArchived: false,
    settings: { executionOrder: 'v1', binaryMode: 'separate' },
})
export class ZeoChatbotWorkflow {
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
    })
    MessengerTrigger = {
        appId: '701126356010152',
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
let messageId = '';
let hasAttachment = false;

// n8n Facebook Trigger node outputs the 'entry' object directly
if (data.messaging && data.messaging.length > 0) {
  const messaging = data.messaging[0];
  text = messaging.message?.text || messaging.message?.quick_reply?.payload || '';
  senderId = messaging.sender?.id || '';
  messageId = messaging.message?.mid || messaging.message?.quick_reply?.payload || '';
  hasAttachment = Boolean(messaging.message?.attachments?.length);
}
// Hoac format don gian nhat (neu n8n boc vo sau hon nua)
else if (data.message && data.sender) {
  text = data.message?.text || data.message?.quick_reply?.payload || '';
  senderId = data.sender?.id || '';
  messageId = data.message?.mid || '';
  hasAttachment = Boolean(data.message?.attachments?.length);
} 
// Hoac data la raw webhook (body.entry...)
else {
  const messaging = data?.body?.entry?.[0]?.messaging?.[0];
  text = messaging?.message?.text || messaging?.message?.quick_reply?.payload || '';
  senderId = messaging?.sender?.id || '';
  messageId = messaging?.message?.mid || '';
  hasAttachment = Boolean(messaging?.message?.attachments?.length);
}

function normalize(str) {
  return String(str || '')
    .normalize('NFD')
    .replace(/[\\u0300-\\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

function normalizeForSearch(str) {
  const aliases = {
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin',
    bn: 'ban', mn: 'minh', nt: 'nhan tin', ship: 'giao hang',
  };
  return normalize(str)
    .replace(/[^a-z0-9\\s]/g, ' ')
    .split(/\\s+/)
    .filter(Boolean)
    .map(token => aliases[token] || token)
    .join(' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

const sensitiveWords = ['hoan tien', 'doi tra', 'khieu nai', 'lua dao', 'san pham loi', 'hang gia'];
const outOfScopeWords = ['phan bon', 'co bay', 'npk', 'phan huu co'];
const vagueProductWords = ['buon', 'do buon', 'cho vui', 'mua gi', 'ban gi', 'co gi hay', 'goi y san pham', 'tu van san pham', 'khong biet mua gi'];
const unsupportedProductWords = ['may do oxy', 'do oxy', 'zeo mini', 'thiet bi y te', 'cham soc ca nhan', 'san pham suc khoe', 'phu kien suc khoe'];
const lower = normalizeForSearch(text);
const isSensitive = sensitiveWords.some(w => lower.includes(w));
const isOutOfScope = outOfScopeWords.some(w => lower.includes(w));
const isVagueProductRequest = vagueProductWords.some(w => lower.includes(w));
const isUnsupportedProductQuestion = unsupportedProductWords.some(w => lower.includes(w));
const emptyInput = !text || !text.trim();

return [{ json: {
  text: text.trim(),
  normalizedText: lower,
  senderId,
  messageId,
  emptyInput,
  inputKind: emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text',
  isSensitive,
  isOutOfScope,
  isVagueProductRequest,
  isUnsupportedProductQuestion,
} }];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000002',
        name: 'Get Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [448, 304],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    GetSession = {
        operation: 'get',
        propertyName: 'sessionRaw',
        key: '={{ "zeo:session:messenger:" + $json.senderId }}',
        keyType: 'string',
        options: {},
    };

    @node({
        id: '126f8f96-9c0f-4f45-b397-71ddf19a80bb',
        name: 'Get Knowledge Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [656, 304],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    GetKnowledgeSnapshot = {
        operation: 'get',
        propertyName: 'knowledgeSnapshot',
        key: 'zeo:kb:basic:active',
        keyType: 'string',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000003',
        name: 'RAG Tim Kiem',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [880, 304],
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

function normalizeForSearch(str) {
  const aliases = {
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin',
    bn: 'ban', mn: 'minh', nt: 'nhan tin', ship: 'giao hang',
  };
  return normalize(str)
    .split(/\\s+/)
    .filter(Boolean)
    .map(token => aliases[token] || token)
    .join(' ')
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

function parseJson(value, fallback) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch (_) {
    return fallback;
  }
}

function parseKnowledgeSnapshot(value) {
  const snapshot = parseJson(value, null);
  if (Array.isArray(snapshot)) return snapshot;
  if (!snapshot || typeof snapshot !== 'object') return [];
  const items = snapshot.snapshot_json || snapshot.knowledgeItems || snapshot.snapshot || [];
  const parsedItems = parseJson(items, items);
  return Array.isArray(parsedItems) ? parsedItems : [];
}

const rawText     = $('Loc Dau Vao').first().json.text || '';
const senderId    = $('Loc Dau Vao').first().json.senderId;
const isSensitive = $('Loc Dau Vao').first().json.isSensitive;
const isOutOfScope = $('Loc Dau Vao').first().json.isOutOfScope;
const isVagueProductRequest = $('Loc Dau Vao').first().json.isVagueProductRequest;
const isUnsupportedProductQuestion = $('Loc Dau Vao').first().json.isUnsupportedProductQuestion;
const emptyInput = $('Loc Dau Vao').first().json.emptyInput;
const normalizedFromInput = $('Loc Dau Vao').first().json.normalizedText;
const session = parseJson($('Get Session').first().json.sessionRaw, {});
const snapshot = $input.first().json.knowledgeSnapshot;
const knowledgeItems = parseKnowledgeSnapshot(snapshot)
  .map(item => ({
    active: asBool(item.active ?? true),
    brand: String(item.brand || 'ZeO').trim(),
    intent: String(item.intent || '').trim(),
    source_id: String(item.source_id || '').trim(),
    question_examples: splitExamples(item.question_examples),
    answer: String(item.answer || item.content || '').trim(),
    priority: Number(item.priority || 0),
  }))
  .filter(item => item.active && item.answer);

const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo/oplus', 'zeo/pano', 'zeo pano oplus', 'zeo/pano/oplus']);
const userTokens = splitTokens(normalizedFromInput || rawText);
const normalizedQuestion = normalizeForSearch(normalizedFromInput || rawText);

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
const hasContext = !emptyInput && !isSensitive && !isOutOfScope && !isVagueProductRequest && !isUnsupportedProductQuestion && bestScore >= 12;

let fallbackReason = 'low_confidence';
let fallbackMessage = 'Cảm ơn bạn đã nhắn tin. Admin sẽ phản hồi bạn sớm nhất nhé!';
if (emptyInput) {
  fallbackReason = 'empty_or_unsupported_message';
  fallbackMessage = 'Bạn gửi giúp mình nội dung cần hỗ trợ bằng tin nhắn chữ nhé.';
} else if (isUnsupportedProductQuestion) {
  fallbackReason = 'unsupported_product_scope';
  fallbackMessage = 'Dạ hiện tại theo thông tin của shop, ZeO tập trung vào các sản phẩm tẩy rửa gia dụng như bột giặt, nước rửa chén, nước lau sàn, Javen, tẩy toilet, lau kính và xịt tẩy đa năng. Bên mình chưa có thông tin về thiết bị y tế hay sản phẩm sức khỏe nha bạn.';
} else if (isVagueProductRequest) {
  fallbackReason = 'product_scope_clarification';
  fallbackMessage = 'Dạ ZeO bên mình hiện có các sản phẩm tẩy rửa gia dụng như bột giặt, nước rửa chén, nước lau sàn, tẩy toilet, Javen, lau kính và xịt tẩy đa năng. Nếu bạn muốn quần áo thơm sạch thì mình gợi ý bột giặt ZeO; nếu cần dọn nhà thì có nước lau sàn hoặc xịt tẩy đa năng nha.';
} else if (isSensitive) {
  fallbackReason = 'sensitive_case';
  fallbackMessage = 'Dạ, mình đã ghi nhận thông tin. Admin sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (isOutOfScope) {
  fallbackReason = 'out_of_scope';
  fallbackMessage = 'Hiện tại mình chỉ hỗ trợ thông tin sản phẩm ZeO. Bạn cho mình biết nhu cầu cần hỗ trợ nhé.';
} else if (!snapshot) {
  fallbackReason = 'knowledge_snapshot_missing';
}

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
    isVagueProductRequest,
    isUnsupportedProductQuestion,
    emptyInput,
    sessionLastIntent: session.last_intent || '',
    context: hasContext ? context : '',
    contextAnswer: hasContext ? topItems[0].answer : '',
    matchedIntent: hasContext ? topItems[0].intent : '',
    matchedSourceId: hasContext ? topItems[0].source_id || '' : '',
    fallbackReason,
    fallbackMessage,
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
        position: [1312, 160],
    })
    GoiOllamaLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/chat',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.3, num_predict: 120 }, messages: [ { role: "system", content: "Bạn là nhân viên tư vấn khách hàng của ZeO Vietnam. BẮT BUỘC chỉ trả lời bằng tiếng Việt có dấu. Tuyệt đối không dùng tiếng Trung, tiếng Anh hoặc bất kỳ ngôn ngữ nào khác. Không tự giới thiệu là AI, Qwen, Alibaba, trợ lý ảo hoặc mô hình ngôn ngữ. Chỉ được dùng thông tin trong THÔNG TIN THAM CHIẾU. Không tự thêm sản phẩm, công dụng, chứng nhận, giá, hotline hoặc tên sản phẩm nếu không có trong tham chiếu. Nếu tham chiếu không đủ để trả lời, hãy nói chưa có thông tin và chuyển admin hỗ trợ. ZeO/PANO/Oplus trong dữ liệu này thuộc nhóm sản phẩm tẩy rửa gia dụng, không phải thiết bị y tế hay sản phẩm sức khỏe. Trả lời ngắn gọn, tự nhiên, thân thiện." }, { role: "user", content: "THÔNG TIN THAM CHIẾU:\\n" + $json.contextAnswer + "\\n\\nCÂU HỎI KHÁCH HÀNG:\\n" + $json.userMessage + "\\n\\nHãy trả lời một tin nhắn Messenger ngắn bằng tiếng Việt có dấu:" } ] } }}',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000006',
        name: 'Kiem Chung',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1536, 160],
    })
    KiemChung = {
        jsCode: `
const ollamaResult = $input.first().json;
const ragData = $('RAG Tim Kiem').first().json;

// Ollama /api/chat tra ve message.content; giu response lam fallback neu doi endpoint.
const aiText = (ollamaResult?.message?.content || ollamaResult?.response || '').trim();

// Kiem tra chieu dai va chat luong
const tooShort = aiText.length < 5;
const tooLong = aiText.length > 1000;
const hasForeignScript = /[㐀-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿຀-໿ក-៿ऀ-ॿ]/.test(aiText);
const hasVietnameseSignal = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]|\\bdạ\\b|\\bạ\\b|\\bnha\\b|\\bnhé\\b|\\bbạn\\b|\\bmình\\b|cảm ơn|thông tin|hỗ trợ|admin/i.test(aiText);
const hasRefusal = /khong biet|xin loi|i don|i cannot|i don't know|thong tin tham chieu|system prompt/i.test(aiText);
const hasEnglishLeak = /(i am|i'm|you are|please|sorry|hello|thank you|as an ai|i cannot|i don't|provide|contact us|customer service)/i.test(aiText);
const hasModelLeak = /qwen|alibaba|aliyun|tongyi|通义|阿里|阿里云|助手|人工智能|中文|language model|large language|chatbot|system prompt|developer message/i.test(aiText);
const hasPromptLeak = /[system]|[thông tin tham chiếu]|[câu hỏi khách hàng]|[trả lời]|thông tin tham chiếu:/i.test(aiText);
const hallucinatedScope = /máy đo oxy|may do oxy|zeo mini|thiết bị y tế|thiet bi y te|chăm sóc cá nhân|cham soc ca nhan|sản phẩm sức khỏe|san pham suc khoe|phụ kiện sức khỏe|phu kien suc khoe/i.test(aiText);
const nonVietnameseOutput = hasForeignScript || hasEnglishLeak || hasModelLeak || hasPromptLeak || !hasVietnameseSignal;
const passed = !tooShort && !tooLong && !hasRefusal && !hallucinatedScope && !nonVietnameseOutput;

let guardrailReason = 'ollama_guardrail_failed';
if (hallucinatedScope) guardrailReason = 'ollama_hallucinated_scope';
else if (hasForeignScript || hasEnglishLeak || !hasVietnameseSignal) guardrailReason = 'non_vietnamese_output';
else if (hasModelLeak) guardrailReason = 'model_identity_leak';
else if (hasPromptLeak) guardrailReason = 'prompt_leak';

// Giot han 1000 ky tu neu qua dai
const finalReply = passed ? aiText.substring(0, 1000) : null;

return [{ json: {
  senderId: ragData.senderId,
  userMessage: ragData.userMessage,
  finalReply,
  passed,
  isSensitive: ragData.isSensitive,
  ragScore: ragData.ragScore,
  matchedIntent: ragData.matchedIntent,
  fallbackReason: passed ? '' : guardrailReason,
  fallbackMessage: ragData.fallbackMessage,
}}];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000007',
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
        id: 'b7d1c4bc-3de0-41f1-92d1-01b1ab551b44',
        name: 'Save Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1984, 64],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    SaveSession = {
        operation: 'set',
        key: '={{ "zeo:session:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify({ last_intent: $json.matchedIntent, last_user_message: $json.userMessage, last_bot_reply: $json.finalReply, updated_at: $now.toISO() }) }}',
        expire: true,
        ttl: 1800,
    };

    @node({
        id: 'b1c5d966-6729-4ce3-bf16-5958bc8c6cad',
        name: 'Queue Learning Review',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1312, 464],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    QueueLearningReview = {
        operation: 'push',
        list: 'zeo:learning:queue',
        messageData:
            '={{ JSON.stringify({ status: "pending", channel: "messenger", sender_id: $json.senderId, message_id: $("Loc Dau Vao").first().json.messageId, user_message: $json.userMessage, fallback_reason: $json.fallbackReason, rag_score: $json.ragScore, created_at: $now.toISO() }) }}',
        tail: true,
    };

    @node({
        id: '94597224-c6db-4e43-b941-2d2a1aec3170',
        name: 'Prepare Telegram Alert',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1552, 584],
    })
    PrepareTelegramAlert = {
        jsCode: `
const event = $input.first().json;
const isUrgent = Boolean(event.isSensitive);

return [{
  json: {
    brand: 'ZeO',
    event_type: isUrgent ? 'URGENT' : 'REVIEW',
    priority: isUrgent ? 'high' : 'normal',
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
        id: '311f36f9-ed4f-4bdf-967e-14cc6d194d64',
        name: 'Notify Telegram Operations',
        type: 'n8n-nodes-base.executeWorkflow',
        version: 1.3,
        position: [1792, 584],
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
        id: 'f1000001-0000-0000-0000-000000000008',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [2208, 64],
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
        position: [1536, 464],
    })
    NhanKhachFallback = {
        method: 'POST',
        url: 'https://graph.facebook.com/v17.0/me/messages',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'facebookGraphApi',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { recipient: { id: $json.senderId }, message: { text: $json.fallbackMessage || "Cảm ơn bạn đã nhắn tin. Admin sẽ phản hồi bạn sớm nhất nhé!" } } }}',
        options: {},
    };

    @node({
        id: '9fa518cc-364d-45ef-a3d2-f1a28c73a029',
        name: 'Sticky Note',
        type: 'n8n-nodes-base.stickyNote',
        version: 1,
        position: [1136, -112],
    })
    StickyNote = {
        height: 160,
        width: 240,
        color: 1,
        content: 'Redis snapshot, session và learning queue',
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.MessengerTrigger.out(0).to(this.LocDauVao.in(0));
        this.LocDauVao.out(0).to(this.GetSession.in(0));
        this.GetSession.out(0).to(this.GetKnowledgeSnapshot.in(0));
        this.GetKnowledgeSnapshot.out(0).to(this.RagTimKiem.in(0));
        this.RagTimKiem.out(0).to(this.RouterCoNguon.in(0));
        this.RouterCoNguon.out(0).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(1).to(this.QueueLearningReview.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.SaveSession.in(0));
        this.RouterGuardrail.out(1).to(this.QueueLearningReview.in(0));
        this.SaveSession.out(0).to(this.NhanKhachAuto.in(0));
        this.QueueLearningReview.out(0).to(this.NhanKhachFallback.in(0));
        this.QueueLearningReview.out(0).to(this.PrepareTelegramAlert.in(0));
        this.PrepareTelegramAlert.out(0).to(this.NotifyTelegramOperations.in(0));
    }
}
