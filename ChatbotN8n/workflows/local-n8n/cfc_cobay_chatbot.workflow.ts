import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Co Bay Chatbot
// Nodes   : 15  |  Connections: 17
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GetCfcSession                      redis                      [onError→regular] [creds] [alwaysOutput]
// GetCfcKnowledgeSnapshot            redis                      [onError→regular] [creds] [alwaysOutput]
// CfcRagTimKiem                      code
// RouterCoNguon                      switch
// GoiOllamaLocal                     httpRequest                [onError→out(1)]
// KiemChung                          code
// RouterGuardrail                    if
// SaveCfcSession                     redis                      [onError→regular] [creds]
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
//              → SaveCfcSession
//                → NhanKhachAuto
//             .out(1) → GoiOllamaLocal
//                → KiemChung
//                  → RouterGuardrail
//                    → SaveCfcSession (↩ loop)
//                   .out(1) → SaveCfcSession (↩ loop)
//                   .out(1) → PrepareTelegramAlert
//                      → NotifyTelegramOperations
//                → KiemChung (↩ loop)
//             .out(2) → SaveCfcSession (↩ loop)
//             .out(2) → PrepareTelegramAlert (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'uJOo6NQO2mJZhUAr',
    name: 'CFC Co Bay Chatbot',
    active: true,
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
let isEcho = false;

const messaging = data?.messaging?.[0]
  || (data?.message && data?.sender ? data : null)
  || data?.body?.entry?.[0]?.messaging?.[0]
  || data?.entry?.[0]?.messaging?.[0]
  || null;

if (messaging) {
  text = messaging?.message?.text || messaging?.message?.quick_reply?.payload || '';
  senderId = messaging?.sender?.id || '';
  messageId = messaging?.message?.mid || '';
  hasAttachment = Boolean(messaging?.message?.attachments?.length);
  isEcho = Boolean(messaging?.message?.is_echo);
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
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    sdt: 'so dien thoai', dt: 'dien thoai', npp: 'nha phan phoi',
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
const productDiscoveryWords = ['ban gi', 'co gi', 'san pham gi', 'co san pham nao', 'tu van san pham', 'phan bon gi', 'co phan gi', 'mua gi'];
const normalizedText = normalizeForSearch(text);
const emptyInput = !text || !text.trim();
const tokenCount = normalizedText ? normalizedText.split(' ').length : 0;
const phoneDigits = text.replace(/\\D/g, '');
const contextualPhone = /(so dien thoai|dien thoai|so cua toi|goi toi|lien he)/.test(normalizedText) && /^\\d{8,12}$/.test(phoneDigits);
const hasPhoneNumber = /(0\\d[\\d\\s.\\-]{7,12}\\d|\\+?84[\\d\\s.\\-]{8,12}\\d)/.test(text) || /^\\d{9,11}$/.test(phoneDigits) || contextualPhone;
const areaWords = ['tinh', 'thanh pho', 'tp', 'huyen', 'xa', 'phuong', 'thi xa', 'khu vuc', 'mien', 'can tho', 'thai binh', 'kien giang', 'tra noc'];
const hasAreaInfo = areaWords.some(word => normalizedText.includes(word)) ||
  /(^|\\s)(minh o|em o|toi o|khach hang cu o|ben minh o|o tinh|o huyen|khu vuc)\\s+[a-z]/.test(normalizedText);
const dealerRequestWords = ['nha phan phoi', 'dai ly', 'phan phoi', 'ban le', 'mua de ban', 'mua ban le', 'lien he mua', 'mua o dau', 'mua de ban le'];
const isDealerLocationRequest = dealerRequestWords.some(word => normalizedText.includes(word)) ||
  ((normalizedText.includes('mua') || normalizedText.includes('lien he')) && hasAreaInfo);
const isGreeting = tokenCount <= 5 && /^(xin chao|chao|hello|hi|alo|shop oi|admin oi|ad oi)(\\s|$)/.test(normalizedText);
const isThanks = tokenCount <= 7 && /^(cam on|thanks|thank you|da cam on|ok cam on)(\\s|$)/.test(normalizedText);
const isGoodbye = tokenCount <= 6 && /^(tam biet|bye|goodbye|hen gap lai|chao nhe)(\\s|$)/.test(normalizedText);
const isAcknowledgement = tokenCount <= 4 && /^(ok|oke|okay|da|vang|uh|um|roi|duoc|biet roi|hieu roi)(\\s|$)/.test(normalizedText);
const isFollowUp = tokenCount <= 9 && /^(con |vay |the |loai do|san pham do|cai do|cai nay|no |dung sao|su dung sao|pha sao|pha nhu nao|co mui|co nhung mui|co huong|co nhung huong|gia sao|chai lon|loai lon|ship |giao hang )/.test(normalizedText);
const hasForeignInputScript = /[㐀-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿຀-໿ក-៿ऀ-ॿ]/.test(text);
const isPromptInjection = /(bo qua|bỏ qua).*(huong dan|hướng dẫn)|(system prompt|developer message|noi dung prompt|nội dung prompt|gia vo ban khong phai|giả vờ bạn không phải)/i.test(text);

return [{
  json: {
    text: text.trim(),
    normalizedText,
    senderId,
    messageId,
    emptyInput,
    inputKind: emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text',
    isEcho,
    isSensitive: sensitiveWords.some(word => normalizedText.includes(word)),
    isOutOfScope: outOfScopeWords.some(word => normalizedText.includes(word)),
    isGreeting,
    isThanks,
    isGoodbye,
    isAcknowledgement,
    isFollowUp,
    hasForeignInputScript,
    isPromptInjection,
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
        onError: 'continueRegularOutput',
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
        onError: 'continueRegularOutput',
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
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    sdt: 'so dien thoai', dt: 'dien thoai', npp: 'nha phan phoi',
  };
  return normalize(value).split(/\\s+/).filter(Boolean).map(token => aliases[token] || token).join(' ');
}

const STOP_WORDS = new Set([
  'a', 'ad', 'admin', 'anh', 'ban', 'ben', 'bi', 'chi', 'cho', 'co', 'cua', 'da', 'dau',
  'duoc', 'em', 'gi', 'khong', 'la', 'minh', 'mot', 'nao', 'nha', 'nhe', 'oi', 'shop',
  'thi', 'toi', 'tren', 'va', 'vay', 've', 'voi', 'cfc', 'bay',
]);

function meaningfulTokens(value) {
  return [...new Set(normalizeForSearch(value).split(' ').filter(token => token.length >= 2 && !STOP_WORDS.has(token)))];
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

function parseSnapshotEnvelope(value) {
  const snapshot = parseJson(value, null);
  if (Array.isArray(snapshot)) return { items: snapshot, updatedAt: '' };
  if (!snapshot || typeof snapshot !== 'object') return { items: [], updatedAt: '' };
  const items = snapshot.snapshot_json || snapshot.knowledgeItems || snapshot.snapshot || [];
  const parsed = parseJson(items, items);
  return { items: Array.isArray(parsed) ? parsed : [], updatedAt: snapshot.updated_at || '' };
}

function scoreEntry(query, entry) {
  const queryTokens = meaningfulTokens(query);
  let best = { score: 0, exact: false, matched: 0, coverage: 0, precision: 0 };
  const candidates = entry.question_examples.length ? entry.question_examples : [entry.intent];
  for (const example of candidates) {
    const normalizedExample = normalizeForSearch(example);
    const exampleTokens = meaningfulTokens(example);
    const exact = Boolean(normalizedExample) && query === normalizedExample;
    const phrase = query.length >= 8 && normalizedExample.length >= 8
      && (query.includes(normalizedExample) || normalizedExample.includes(query));
    const matched = queryTokens.filter(token => exampleTokens.includes(token)).length;
    const coverage = queryTokens.length ? matched / queryTokens.length : 0;
    const precision = exampleTokens.length ? matched / exampleTokens.length : 0;
    let score = exact ? 100 : (phrase ? 88 : Math.round((coverage * 60) + (precision * 25) + Math.min(matched, 3) * 5));
    score += Math.min(Math.max(entry.priority, 0), 100) / 100;
    if (score > best.score) best = { score, exact, matched, coverage, precision };
  }
  return best;
}

const input = $('Loc Dau Vao').first().json;
const session = parseJson($('Get CFC Session').first().json.sessionRaw, {});
const snapshotRaw = $input.first().json.knowledgeSnapshot;
const snapshot = parseSnapshotEnvelope(snapshotRaw);
const knowledgeItems = snapshot.items
  .map(item => ({
    active: asBool(item.active ?? true),
    brand: String(item.brand || 'CFC').trim(),
    category: String(item.category || 'faq').trim(),
    intent: String(item.intent || '').trim(),
    source_id: String(item.source_id || '').trim(),
    question_examples: examples(item.question_examples),
    answer: String(item.answer || item.content || '').trim(),
    priority: Number(item.priority || 0),
    audience: String(item.audience || 'customer').trim().toLowerCase(),
    answer_mode: String(item.answer_mode || '').trim().toLowerCase(),
  }))
  .filter(item => item.active && item.answer && item.intent && item.audience !== 'internal');

const allowedBrands = new Set(['cfc', 'co bay', 'cfc/co bay', 'cfc co bay']);
const currentQuestion = normalizeForSearch(input.normalizedText || input.text);
const contextQuestion = input.isFollowUp && session.last_user_message
  ? normalizeForSearch(session.last_user_message + ' ' + input.text)
  : currentQuestion;
const sessionEntry = input.isFollowUp && session.last_source_id
  ? knowledgeItems.find(item => item.source_id === session.last_source_id && item.intent === session.last_intent)
  : null;
const scored = knowledgeItems
  .filter(entry => allowedBrands.has(normalize(entry.brand)))
  .map(entry => ({ ...entry, ...scoreEntry(currentQuestion, entry) }))
  .filter(entry => entry.score > 0)
  .sort((a, b) => b.score - a.score || b.priority - a.priority);
let best = scored[0] || null;
const currentSecondScore = scored.find(item => !best || item.intent !== best.intent)?.score || 0;
const currentAmbiguous = !best?.exact && ((best?.score || 0) - currentSecondScore < 8);
if (sessionEntry && input.isFollowUp && !input.isSensitive && !input.isOutOfScope) {
  const sessionScore = scoreEntry(contextQuestion, sessionEntry);
  const newTokens = meaningfulTokens(currentQuestion);
  const sessionEvidence = meaningfulTokens([sessionEntry.intent, ...sessionEntry.question_examples, sessionEntry.answer].join(' '));
  const supportsNewQuestion = newTokens.some(token => sessionEvidence.includes(token));
  if (supportsNewQuestion && sessionScore.matched >= 1 && (!best || currentAmbiguous || sessionScore.score >= best.score - 8)) {
    best = { ...sessionEntry, ...sessionScore };
  }
}
const secondScore = scored.find(item => !best || item.intent !== best.intent)?.score || 0;
const bestScore = Math.round((best?.score || 0) * 100) / 100;
const scoreMargin = Math.round((bestScore - secondScore) * 100) / 100;
const contextResolved = Boolean(sessionEntry && best && best.intent === sessionEntry.intent && input.isFollowUp);
const confidence = contextResolved || best?.exact || (bestScore >= 76 && scoreMargin >= 12)
  ? 'high'
  : (bestScore >= 48 && scoreMargin >= 8 && (best?.matched || 0) >= 2 ? 'medium' : 'low');
const productLineItem = knowledgeItems.find(item => item.intent === 'product_lines');
const previousText = normalizeForSearch([session.last_user_message, session.last_bot_reply, session.last_intent].filter(Boolean).join(' '));
const waitingForContact = ['so dien thoai', 'khu vuc', 'nhan vien', 'lien he', 'dai ly', 'phan phoi'].some(word => previousText.includes(word));
const looksLikeAreaReply = /(^|\\s)(minh o|em o|toi o|khach hang cu o|ben minh o|o tinh|o huyen|khu vuc)\\s+[a-z]/.test(input.normalizedText || '');
const isLeadInfo = Boolean(input.hasPhoneNumber || (input.hasAreaInfo && (waitingForContact || looksLikeAreaReply || input.isDealerLocationRequest)));
const isDuplicate = Boolean(input.messageId && session.last_message_id && input.messageId === session.last_message_id);
const shouldIgnore = Boolean(input.isEcho || !input.senderId || isDuplicate);

let responseMode = 'review';
let fallbackReason = 'low_confidence';
let finalReply = 'Dạ, mình chưa đủ dữ liệu để trả lời chính xác nội dung này. Bạn cho mình biết thêm nhu cầu về sản phẩm, mua hàng, giao hàng, đại lý hoặc địa chỉ nhé.';
let matchedIntent = '';
let matchedSourceId = '';
let matchedCategory = '';
let canonicalAnswer = '';

if (shouldIgnore) {
  responseMode = 'ignore';
  fallbackReason = input.isEcho ? 'echo_event' : (isDuplicate ? 'duplicate_message' : 'invalid_sender');
  finalReply = '';
} else if (input.emptyInput) {
  responseMode = 'direct';
  fallbackReason = 'empty_or_unsupported_message';
  finalReply = 'Bạn gửi giúp mình nội dung cần hỗ trợ bằng tin nhắn chữ nhé.';
} else if (input.isGreeting) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'greeting';
  finalReply = 'Dạ Cò Bay chào bạn ạ. Bạn cần mình hỗ trợ về sản phẩm phân bón, mua hàng, giao hàng, đại lý hay địa chỉ công ty ạ?';
} else if (input.isThanks) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'thanks';
  finalReply = 'Dạ, Cò Bay cảm ơn bạn ạ. Khi cần thêm thông tin, bạn cứ nhắn mình nhé.';
} else if (input.isGoodbye) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'goodbye';
  finalReply = 'Dạ, cảm ơn bạn đã liên hệ Cò Bay. Chúc bạn một ngày vui vẻ nhé.';
} else if (input.isAcknowledgement) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = session.last_intent || 'acknowledgement';
  finalReply = 'Dạ vâng ạ. Khi cần hỗ trợ thêm, bạn cứ nhắn Cò Bay nhé.';
} else if (input.isPromptInjection) {
  responseMode = 'review';
  fallbackReason = 'prompt_injection';
  finalReply = 'Dạ, mình chỉ có thể hỗ trợ thông tin sản phẩm và dịch vụ của Cò Bay. Bạn cho mình biết nội dung cần hỗ trợ nhé.';
} else if (input.hasForeignInputScript) {
  responseMode = 'direct';
  fallbackReason = 'unsupported_input_language';
  finalReply = 'Dạ, hiện Cò Bay hỗ trợ bằng tiếng Việt. Bạn gửi lại nội dung bằng tiếng Việt giúp mình nhé.';
} else if (isLeadInfo) {
  responseMode = 'review';
  fallbackReason = input.hasPhoneNumber && input.hasAreaInfo ? 'lead_contact_received' : (input.hasPhoneNumber ? 'lead_phone_received' : 'lead_area_received');
  finalReply = input.hasPhoneNumber
    ? 'Dạ, Cò Bay đã nhận được số điện thoại và thông tin bạn gửi. Admin hoặc nhân viên khu vực sẽ liên hệ hỗ trợ bạn sớm nhất nha.'
    : 'Dạ Cò Bay đã nhận được khu vực của bạn. Bạn gửi thêm số điện thoại để admin hoặc nhân viên khu vực liên hệ hỗ trợ sớm nhất nha.';
} else if (input.isDealerLocationRequest) {
  responseMode = 'review';
  fallbackReason = 'dealer_location_request';
  finalReply = 'Dạ, bạn gửi giúp Cò Bay số điện thoại và khu vực cụ thể. Admin sẽ chuyển nhân viên hoặc nhà phân phối khu vực liên hệ hỗ trợ mua hàng sớm nhất nha.';
} else if (input.isSensitive) {
  responseMode = 'review';
  fallbackReason = 'sensitive_case';
  finalReply = 'Dạ, Cò Bay đã ghi nhận phản ánh của bạn. Admin sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (input.isOutOfScope) {
  responseMode = 'review';
  fallbackReason = 'out_of_scope';
  finalReply = 'Dạ, mình đang hỗ trợ thông tin về phân bón và dịch vụ của Cò Bay. Bạn cho mình biết nhu cầu liên quan đến Cò Bay nhé.';
} else if (input.isProductDiscovery && productLineItem) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = productLineItem.intent;
  matchedSourceId = productLineItem.source_id;
  matchedCategory = productLineItem.category;
  canonicalAnswer = productLineItem.answer;
  finalReply = productLineItem.answer;
} else if (!snapshotRaw || !knowledgeItems.length) {
  responseMode = 'review';
  fallbackReason = 'knowledge_snapshot_missing';
  finalReply = 'Dạ, cảm ơn câu hỏi của bạn. Admin Cò Bay sẽ phản hồi bạn sớm nhất nhé.';
} else if (confidence === 'high' && best) {
  canonicalAnswer = best.answer;
  finalReply = best.answer;
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  matchedCategory = best.category;
  responseMode = best.answer_mode === 'rewrite' ? 'rewrite' : 'direct';
  fallbackReason = '';
} else if (confidence === 'medium' && best) {
  responseMode = 'direct';
  fallbackReason = 'clarification_needed';
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  matchedCategory = best.category;
  finalReply = 'Dạ, bạn đang muốn hỏi về ' + (best.question_examples[0] || best.intent.replace(/_/g, ' ')) + ' đúng không ạ?';
}

const routeIndex = responseMode === 'direct' ? 0 : responseMode === 'rewrite' ? 1 : responseMode === 'review' ? 2 : 3;
const previousHistory = Array.isArray(session.history) ? session.history : [];
const historyUserText = isLeadInfo ? '[Khách đã cung cấp thông tin liên hệ]' : input.text;
const history = shouldIgnore || !input.text
  ? previousHistory.slice(-8)
  : [...previousHistory,
      { role: 'user', text: historyUserText },
      { role: 'assistant', text: finalReply, intent: matchedIntent, source_id: matchedSourceId },
    ].slice(-8);
const sessionState = {
  ...session,
  current_brand: 'CFC',
  current_topic: matchedIntent || session.current_topic || '',
  current_product: matchedCategory === 'product' ? matchedIntent : (session.current_product || ''),
  last_intent: matchedIntent || session.last_intent || '',
  last_source_id: matchedSourceId || session.last_source_id || '',
  last_answer_source: matchedSourceId || session.last_answer_source || '',
  last_user_message: input.text,
  last_bot_reply: finalReply,
  last_message_id: input.messageId || session.last_message_id || '',
  customer_phone: input.hasPhoneNumber ? input.text.replace(/\\D/g, '') : (session.customer_phone || ''),
  customer_location: isLeadInfo && input.hasAreaInfo ? input.text : (session.customer_location || ''),
  pending_question: fallbackReason === 'clarification_needed' || responseMode === 'review' ? input.text : '',
  has_greeted: Boolean(session.has_greeted || input.isGreeting),
  history,
  updated_at: new Date().toISOString(),
};

const evidencePacket = {
  intent: matchedIntent,
  category: matchedCategory,
  canonical_answer: canonicalAnswer,
  source_ids: matchedSourceId ? [matchedSourceId] : [],
  answer_mode: responseMode,
  confidence,
  prohibited_claims: ['Không thêm giá, liều lượng, công dụng, đại lý, địa chỉ, chính sách hoặc thông tin sản phẩm ngoài canonical_answer.'],
};

return [{
  json: {
    requestId: input.messageId || ('cfc-' + input.senderId),
    senderId: input.senderId,
    messageId: input.messageId,
    userMessage: input.text,
    responseMode,
    routeIndex,
    confidence,
    ragScore: bestScore,
    scoreMargin,
    matchedIntent,
    matchedSourceId,
    matchedSourceIds: matchedSourceId ? [matchedSourceId] : [],
    normalizedQuery: currentQuestion,
    resolvedQuery: contextQuestion,
    canonicalAnswer,
    contextAnswer: canonicalAnswer,
    evidencePacket,
    answerMode: responseMode,
    ollamaUsed: responseMode === 'rewrite',
    guardrailResult: responseMode === 'rewrite' ? 'pending' : 'not_used',
    latencyMs: 0,
    finalReply,
    fallbackReason,
    fallbackMessage: finalReply,
    isSensitive: Boolean(input.isSensitive),
    isLeadInfo,
    isDealerLocationRequest: Boolean(input.isDealerLocationRequest),
    shouldIgnore,
    sessionState,
  },
}];
`,
    };

    @node({
        id: '1c3c5481-d335-462b-9cc6-460edb2c5a48',
        name: 'Router Co Nguon',
        type: 'n8n-nodes-base.switch',
        version: 3.4,
        position: [1088, 304],
    })
    RouterCoNguon = {
        mode: 'expression',
        numberOutputs: 4,
        output: '={{ Number($json.routeIndex) }}',
    };

    @node({
        id: '51e55064-a36d-49ef-a998-a060271d41a6',
        name: 'Goi Ollama Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [1312, 160],
        onError: 'continueErrorOutput',
    })
    GoiOllamaLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/chat',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.2, num_predict: 100 }, messages: [ { role: "system", content: "Bạn chỉ biên tập lại CÂU TRẢ LỜI GỐC thành một tin nhắn Messenger tự nhiên bằng tiếng Việt có dấu. Không trả lời theo kiến thức riêng. Không thêm, suy đoán hoặc thay đổi bất kỳ dữ kiện nào. Không dùng tiếng Trung, tiếng Anh, ký tự lạ, markdown, tiêu đề hay lời giới thiệu. Không nhắc đến AI, Qwen, prompt hoặc thông tin tham chiếu. Giữ nguyên tên Cò Bay, sản phẩm, số điện thoại, địa chỉ và mọi con số có trong câu gốc. Trả lời tối đa 3 câu. Nếu không thể biên tập an toàn, hãy chép nguyên văn CÂU TRẢ LỜI GỐC." }, { role: "user", content: "CÂU TRẢ LỜI GỐC:\\n" + $json.canonicalAnswer + "\\n\\nCÂU HỎI KHÁCH:\\n" + $json.userMessage } ] } }}',
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
const hasEnglishLeak = /\\b(i am|i'm|you are|please|sorry|hello|thank you|as an ai|i cannot|i don't|provide|contact us|customer service)\\b/i.test(aiText);
const hasModelLeak = /qwen|alibaba|aliyun|tongyi|通义|阿里|阿里云|助手|人工智能|中文|language model|large language|chatbot|system prompt|developer message/i.test(aiText);
const hasPromptLeak = /thông tin tham chiếu|câu hỏi khách hàng|câu trả lời gốc|system prompt|developer message/i.test(aiText);
const mentionsOtherBrand = /zeo|pano|oplus|bot giat/i.test(aiText);
const hallucinatedScope = /nước rửa chén|nuoc rua chen|nước lau sàn|nuoc lau san|javen|toilet|lau kính|lau kinh|máy đo oxy|may do oxy|thiết bị y tế|thiet bi y te|sản phẩm sức khỏe|san pham suc khoe|thuốc trừ sâu|thuoc tru sau|liều lượng|lieu luong|giá bán|gia ban|bao nhiêu tiền|bao nhieu tien/i.test(aiText);
const canonicalAnswer = String(ragData.canonicalAnswer || '').trim();
const normalizeFacts = value => String(value || '')
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .replace(/đ/g, 'd')
  .replace(/Đ/g, 'D')
  .toLowerCase()
  .replace(/[^a-z0-9s]/g, ' ')
  .replace(/s+/g, ' ')
  .trim();
const styleWords = new Set('da ban minh ben shop hien tai co la va de duoc se som nhat nhe nha vui long cam on thong tin ho tro xin chao a voi cho neu can khi them giup'.split(' '));
const canonicalTokens = new Set(normalizeFacts(canonicalAnswer).split(' ').filter(token => token.length >= 3));
const unsupportedFacts = [...new Set(normalizeFacts(aiText).split(' ')
  .filter(token => token.length >= 3 && !canonicalTokens.has(token) && !styleWords.has(token)))];
const canonicalNumbers = canonicalAnswer.match(/d[d.,:/-]*/g) || [];
const missingCanonicalNumber = canonicalNumbers.some(number => !aiText.includes(number));
const changedFacts = unsupportedFacts.length > 0 || missingCanonicalNumber;
const passed = !tooShort && !tooLong && !hasForeignScript && !hasEnglishLeak && !hasModelLeak && !hasPromptLeak && !mentionsOtherBrand && !hallucinatedScope && !changedFacts;

let guardrailReason = 'ollama_guardrail_failed';
if (hallucinatedScope || mentionsOtherBrand) guardrailReason = 'ollama_hallucinated_scope';
else if (hasForeignScript || hasEnglishLeak) guardrailReason = 'non_vietnamese_output';
else if (hasModelLeak) guardrailReason = 'model_identity_leak';
else if (hasPromptLeak) guardrailReason = 'prompt_leak';
else if (changedFacts) guardrailReason = 'ollama_changed_canonical_facts';

const finalReply = passed ? aiText.substring(0, 1000) : canonicalAnswer;
const sessionState = {
  ...(ragData.sessionState || {}),
  last_bot_reply: finalReply,
  updated_at: new Date().toISOString(),
};

return [{
  json: {
    ...ragData,
    finalReply,
    passed,
    ollamaUsed: true,
    guardrailResult: passed ? 'passed' : 'canonical_fallback',
    fallbackReason: passed ? '' : guardrailReason,
    fallbackMessage: finalReply,
    sessionState,
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
        onError: 'continueRegularOutput',
    })
    SaveCfcSession = {
        operation: 'set',
        key: '={{ "cfc:session:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify($json.sessionState) }}',
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
        jsonBody: '={{ { recipient: { id: $json.senderId }, message: { text: $json.finalReply } } }}',
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
        this.RouterCoNguon.out(0).to(this.SaveCfcSession.in(0));
        this.RouterCoNguon.out(1).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(2).to(this.SaveCfcSession.in(0));
        this.RouterCoNguon.out(2).to(this.PrepareTelegramAlert.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.GoiOllamaLocal.error().to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.SaveCfcSession.in(0));
        this.RouterGuardrail.out(1).to(this.SaveCfcSession.in(0));
        this.RouterGuardrail.out(1).to(this.PrepareTelegramAlert.in(0));
        this.SaveCfcSession.out(0).to(this.NhanKhachAuto.in(0));
        this.PrepareTelegramAlert.out(0).to(this.NotifyTelegramOperations.in(0));
    }
}
