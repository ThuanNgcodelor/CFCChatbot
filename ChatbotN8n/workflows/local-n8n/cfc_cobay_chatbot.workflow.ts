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
        credentials: { facebookGraphAppApi: { id: 'H7jFvG3kDaEFuBjD', name: 'CFC Cò Bay' } },
    })
    MessengerTrigger = {
        appId: '946909570780806',
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
const outOfScopeWords = ['bot giat', 'nuoc rua chen', 'nuoc lau san', 'tay toilet', 'javen', 'lau kinh', 'zeo', 'pano', 'oplus', 'may do oxy', 'thiet bi y te', 'san pham suc khoe'];
const greetingWords = ['xin chao', 'chao', 'hello', 'hi', 'alo', 'shop oi', 'admin oi', 'ad oi'];
const productDiscoveryWords = ['ban gi', 'co gi', 'san pham gi', 'co san pham nao', 'tu van san pham', 'phan bon gi', 'co phan gi', 'mua gi'];
const normalizedText = normalizeForSearch(text);
const emptyInput = !text || !text.trim();
const phoneDigits = text.replace(/\\D/g, '');
const hasPhoneNumber = /(0\\d[\\d\\s.\\-]{7,12}\\d|\\+?84[\\d\\s.\\-]{8,12}\\d)/.test(text) || /^\\d{9,11}$/.test(phoneDigits);
const areaWords = ['tinh', 'thanh pho', 'tp', 'huyen', 'xa', 'phuong', 'thi xa', 'khu vuc', 'mien', 'can tho', 'thai binh', 'kien giang', 'tra noc'];
const hasAreaInfo = areaWords.some(word => normalizedText.includes(word)) ||
  /(^|\\s)(minh o|em o|toi o|khach hang cu o|ben minh o|o tinh|o huyen|khu vuc)\\s+[a-z]/.test(normalizedText);
const dealerRequestWords = ['nha phan phoi', 'dai ly', 'phan phoi', 'ban le', 'mua de ban', 'mua ban le', 'lien he mua', 'mua o dau', 'mua de ban le'];
const isDealerLocationRequest = dealerRequestWords.some(word => normalizedText.includes(word)) ||
  ((normalizedText.includes('mua') || normalizedText.includes('lien he')) && hasAreaInfo);

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
    isGreeting: greetingWords.some(word => normalizedText === word || normalizedText.startsWith(word + ' ') || normalizedText.includes(' ' + word)),
    isProductDiscovery: productDiscoveryWords.some(word => normalizedText.includes(word)),
    hasPhoneNumber,
    hasAreaInfo,
    isDealerLocationRequest,
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
const session = parseJson($('Get CFC Session').first().json.sessionRaw, {});
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
const productLineItem = knowledgeItems.find(item => item.intent === 'product_lines');
const directAnswer = input.isGreeting
  ? 'Dạ Cò Bay chào bạn ạ. Bên mình hỗ trợ tư vấn phân bón Cò Bay như NPK, phân hữu cơ, mua hàng, giao hàng, đại lý và địa chỉ công ty nha.'
  : (input.isProductDiscovery && productLineItem ? productLineItem.answer : '');
const directIntent = input.isGreeting ? 'greeting' : (input.isProductDiscovery && productLineItem ? productLineItem.intent : '');
const hasDirectContext = Boolean(directAnswer) && !input.emptyInput && !input.isSensitive && !input.isOutOfScope;
const previousText = normalizeForSearch([session.last_user_message, session.last_bot_reply, session.last_intent].filter(Boolean).join(' '));
const waitingForContact = ['so dien thoai', 'khu vuc', 'nhan vien', 'lien he', 'dai ly', 'phan phoi'].some(word => previousText.includes(word));
const looksLikeAreaReply = /(^|\\s)(minh o|em o|toi o|khach hang cu o|ben minh o|o tinh|o huyen|khu vuc)\\s+[a-z]/.test(input.normalizedText || '');
const isLeadInfo = Boolean(input.hasPhoneNumber || (input.hasAreaInfo && (waitingForContact || looksLikeAreaReply)));
const hasContext = hasDirectContext || (!isLeadInfo && !input.isDealerLocationRequest && !input.emptyInput && !input.isSensitive && !input.isOutOfScope && bestScore >= 12);

let fallbackReason = 'low_confidence';
let fallbackMessage = 'Dạ, thông tin này mình chưa có. Bạn để lại số điện thoại và khu vực, admin Cò Bay sẽ hỗ trợ bạn sớm nhất nha.';
if (input.emptyInput) {
  fallbackReason = 'empty_or_unsupported_message';
  fallbackMessage = 'Bạn gửi giúp mình nội dung cần hỗ trợ bằng tin nhắn chữ nhé.';
} else if (isLeadInfo) {
  fallbackReason = input.hasPhoneNumber && input.hasAreaInfo ? 'lead_contact_received' : (input.hasPhoneNumber ? 'lead_phone_received' : 'lead_area_received');
  fallbackMessage = input.hasPhoneNumber
    ? 'Dạ Cò Bay đã nhận được thông tin của bạn. Admin hoặc nhân viên khu vực sẽ liên hệ hỗ trợ bạn sớm nhất nha.'
    : 'Dạ Cò Bay đã nhận được khu vực của bạn. Bạn gửi thêm số điện thoại để admin hoặc nhân viên khu vực liên hệ hỗ trợ sớm nhất nha.';
} else if (input.isDealerLocationRequest) {
  fallbackReason = 'dealer_location_request';
  fallbackMessage = 'Dạ bạn gửi giúp Cò Bay số điện thoại và khu vực cụ thể, admin sẽ chuyển nhân viên hoặc nhà phân phối khu vực liên hệ hỗ trợ mua hàng sớm nhất nha.';
} else if (input.isSensitive) {
  fallbackReason = 'sensitive_case';
  fallbackMessage = 'Dạ, mình đã ghi nhận thông tin. Admin Cò Bay sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (input.isOutOfScope) {
  fallbackReason = 'out_of_scope';
  fallbackMessage = 'Dạ, hiện mình chỉ hỗ trợ thông tin về phân bón Cò Bay như NPK, phân hữu cơ, mua hàng, giao hàng, đại lý và địa chỉ công ty nha.';
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
    contextAnswer: hasContext ? (directAnswer || topItems[0].answer) : '',
    matchedIntent: hasContext ? (directIntent || topItems[0].intent) : '',
    fallbackReason,
    fallbackMessage,
    ragScore: bestScore,
    isLeadInfo,
    isDealerLocationRequest: Boolean(input.isDealerLocationRequest),
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
        url: 'http://127.0.0.1:11434/api/chat',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.3, num_predict: 120 }, messages: [ { role: "system", content: "Bạn là nhân viên tư vấn khách hàng của Cò Bay (CFC). BẮT BUỘC chỉ trả lời bằng tiếng Việt có dấu. Tuyệt đối không dùng tiếng Trung, tiếng Anh hoặc bất kỳ ngôn ngữ nào khác. Không tự giới thiệu là AI, Qwen, Alibaba, trợ lý ảo hoặc mô hình ngôn ngữ. Chỉ được dùng đúng THÔNG TIN THAM CHIẾU. Không tự thêm giá, công dụng, liều lượng, cây trồng, chương trình khuyến mãi, hotline hoặc sản phẩm nếu không có trong tham chiếu. CFC Cò Bay trong dữ liệu này chỉ có thông tin cơ bản về phân bón NPK, phân hữu cơ, mua hàng, giao hàng, đại lý, giờ mở cửa và địa chỉ. Nếu tham chiếu không đủ để trả lời, hãy nói chưa có thông tin và xin số điện thoại/khu vực để admin hỗ trợ. Trả lời ngắn gọn, tự nhiên, thân thiện." }, { role: "user", content: "THÔNG TIN THAM CHIẾU:\\n" + $json.contextAnswer + "\\n\\nCÂU HỎI KHÁCH HÀNG:\\n" + $json.userMessage + "\\n\\nHãy trả lời một tin nhắn Messenger ngắn bằng tiếng Việt có dấu:" } ] } }}',
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
const aiText = (ollamaResult?.message?.content || ollamaResult?.response || '').trim();
const tooShort = aiText.length < 5;
const tooLong = aiText.length > 1000;
const hasForeignScript = /[㐀-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿຀-໿ក-៿ऀ-ॿ]/.test(aiText);
const hasVietnameseSignal = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]|\\bdạ\\b|\\bạ\\b|\\bnha\\b|\\bnhé\\b|\\bbạn\\b|\\bmình\\b|cảm ơn|thông tin|hỗ trợ|admin/i.test(aiText);
const hasRefusal = /khong biet|xin loi|i don|i cannot|i don't know|thong tin tham chieu|system prompt/i.test(aiText);
const hasEnglishLeak = /(i am|i'm|you are|please|sorry|hello|thank you|as an ai|i cannot|i don't|provide|contact us|customer service)/i.test(aiText);
const hasModelLeak = /qwen|alibaba|aliyun|tongyi|通义|阿里|阿里云|助手|人工智能|中文|language model|large language|chatbot|system prompt|developer message/i.test(aiText);
const hasPromptLeak = /[system]|[thông tin tham chiếu]|[câu hỏi khách hàng]|[trả lời]|thông tin tham chiếu:/i.test(aiText);
const mentionsOtherBrand = /zeo|pano|oplus|bot giat/i.test(aiText);
const hallucinatedScope = /nước rửa chén|nuoc rua chen|nước lau sàn|nuoc lau san|javen|toilet|lau kính|lau kinh|máy đo oxy|may do oxy|thiết bị y tế|thiet bi y te|sản phẩm sức khỏe|san pham suc khoe|thuốc trừ sâu|thuoc tru sau|liều lượng|lieu luong|giá bán|gia ban|bao nhiêu tiền|bao nhieu tien/i.test(aiText);
const nonVietnameseOutput = hasForeignScript || hasEnglishLeak || hasModelLeak || hasPromptLeak || !hasVietnameseSignal;
const passed = !tooShort && !tooLong && !hasRefusal && !mentionsOtherBrand && !hallucinatedScope && !nonVietnameseOutput;

let guardrailReason = 'ollama_guardrail_failed';
if (hallucinatedScope || mentionsOtherBrand) guardrailReason = 'ollama_hallucinated_scope';
else if (hasForeignScript || hasEnglishLeak || !hasVietnameseSignal) guardrailReason = 'non_vietnamese_output';
else if (hasModelLeak) guardrailReason = 'model_identity_leak';
else if (hasPromptLeak) guardrailReason = 'prompt_leak';

return [{
  json: {
    senderId: ragData.senderId,
    userMessage: ragData.userMessage,
    finalReply: passed ? aiText.substring(0, 1000) : null,
    passed,
    ragScore: ragData.ragScore,
    matchedIntent: ragData.matchedIntent,
    fallbackReason: passed ? '' : guardrailReason,
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
        credentials: { facebookGraphApi: { id: 'cKx1OHWWIdDjOUuM', name: 'Cò bay' } },
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
        credentials: { facebookGraphApi: { id: 'cKx1OHWWIdDjOUuM', name: 'Cò bay' } },
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
        position: [1776, 592],
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
        position: [2016, 592],
        onError: 'continueErrorOutput',
    })
    NotifyTelegramOperations = {
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
