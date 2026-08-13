import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Chatbot
// Nodes   : 16  |  Connections: 18
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GetSession                         redis                      [onError→regular] [creds] [alwaysOutput]
// GetKnowledgeSnapshot               redis                      [onError→regular] [creds] [alwaysOutput]
// RagTimKiem                         code
// RouterCoNguon                      switch
// GoiOllamaLocal                     httpRequest                [onError→out(1)]
// KiemChung                          code
// RouterGuardrail                    if
// SaveSession                        redis                      [onError→regular] [creds]
// QueueLearningReview                redis                      [onError→regular] [creds]
// PrepareTelegramAlert               code
// NotifyTelegramOperations           executeWorkflow            [onError→out(1)]
// NhanKhachAuto                      httpRequest                [creds]
// NhanKhachFallback                  httpRequest                [creds]
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
//              → SaveSession
//                → NhanKhachAuto
//             .out(1) → GoiOllamaLocal
//                → KiemChung
//                  → RouterGuardrail
//                    → SaveSession (↩ loop)
//                   .out(1) → SaveSession (↩ loop)
//                   .out(1) → QueueLearningReview
//                      → PrepareTelegramAlert
//                        → NotifyTelegramOperations
//                → KiemChung (↩ loop)
//             .out(2) → SaveSession (↩ loop)
//             .out(2) → QueueLearningReview (↩ loop)
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
        credentials: { facebookGraphAppApi: { id: 'DPEr450xHI0lpcpn', name: 'ZeO' } },
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
let isEcho = false;

const messaging = data?.messaging?.[0]
  || (data?.message && data?.sender ? data : null)
  || data?.body?.entry?.[0]?.messaging?.[0]
  || data?.entry?.[0]?.messaging?.[0]
  || null;

if (messaging) {
  text = messaging.message?.text || messaging.message?.quick_reply?.payload || '';
  senderId = messaging.sender?.id || '';
  messageId = messaging.message?.mid || '';
  hasAttachment = Boolean(messaging.message?.attachments?.length);
  isEcho = Boolean(messaging.message?.is_echo);
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
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong', hong: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    sdt: 'so dien thoai', dt: 'dien thoai', gia: 'gia ban', gif: 'gi', j: 'gi', z: 'vay',
    web: 'website', wed: 'website', wep: 'website', cod: 'cod',
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
const tokenCount = lower ? lower.split(' ').length : 0;
const phoneMatch = text.match(/(?:\\+?84|0)[\\d\\s.\\-]{8,14}\\d/);
const hasPhoneNumber = Boolean(phoneMatch);
const areaWords = ['tinh', 'thanh pho', 'tp', 'huyen', 'xa', 'phuong', 'thi xa', 'khu vuc', 'mien'];
const hasAreaInfo = areaWords.some(word => lower.includes(word));
const isSensitive = sensitiveWords.some(w => lower.includes(w));
const isOutOfScope = outOfScopeWords.some(w => lower.includes(w));
const isVagueProductRequest = vagueProductWords.some(w => lower.includes(w));
const isUnsupportedProductQuestion = unsupportedProductWords.some(w => lower.includes(w));
const emptyInput = !text || !text.trim();
const isGreeting = tokenCount <= 6 && (
  /^(xin chao|chao|hello|hi|he lo|alo|a lo|e|ee|ey)(\\s|$)/.test(lower)
  || /^(shop oi|admin oi|ad oi|shop|admin|ad)$/.test(lower)
);
const isThanks = tokenCount <= 7 && /^(cam on|thanks|thank you|da cam on|ok cam on)(\\s|$)/.test(lower);
const isGoodbye = tokenCount <= 7 && /^(tam biet|bye|goodbye|hen gap lai|chao nhe|toi ve|minh ve|em ve|anh ve|chi ve|ok ve|oke ve|ve nhe|di day)(\\s|$)/.test(lower);
const isAcknowledgement = tokenCount <= 4 && /^(ok|oke|okay|da|vang|uh|um|roi|duoc|biet roi|hieu roi)(\\s|$)/.test(lower);
const isEmotional = /(^|\\s)(buon|met|chan|stress|ap luc)(\\s|$)/.test(lower);
const isFollowUp = tokenCount <= 7 && /^(con |vay |the |loai do|san pham do|cai do|cai nay|no |dung sao|co thom|gia sao)/.test(lower);
const isBotComplaint = /(tra loi gi ky|tra loi ky|tra loi xam|xam xam|sao ngu|cang dot|may dot|m dot|bot ngu|khong hieu|noi gi vay|sao tra loi|cach dong|xuong dong|hoi mot dang tra loi mot neo)/.test(lower);
const isCatalogQuestion = /(san pham gi|san pham nao|co san pham|co nhung gi|ban nhung gi|ban gi|co gi ban|danh muc san pham|cac san pham|mat hang gi|hang gi)/.test(lower);
const isWebsiteQuestion = /(website|web site|trang web|link web|link website|link cong ty|duong dan|xin link|gui.*link|zeo vn|zeo\\.vn)/.test(lower);
const isShortCodQuestion = /(^|\\s)cod($|\\s)/.test(lower) || /(thanh toan khi nhan|giao hang thu tien|nhan hang tra tien|thu tien mat|tra tien mat)/.test(lower);
const isShortDetergentQuestion = /(bot giat|nuoc giat|giat do|giat quan ao)/.test(lower);
const isGenericDetergentQuestion = isShortDetergentQuestion
  && tokenCount <= 7
  && /(^|\\s)(co|ban|con|het|khong)($|\\s)/.test(lower);
const isFloorCleanerQuestion = /(nuoc lau san|lau san|san nha|floor cleaner)/.test(lower);
const isShortPanoQuestion = /\\bpano\\b/.test(lower);
const isShortZeoQuestion = /\\bzeo\\b/.test(lower) && tokenCount <= 5;
const isWarrantyQuestion = /(bao hanh|bao tri|loi san pham|san pham bi loi|hang loi)/.test(lower);
const mentionsAba = /\\baba\\b/.test(lower);
const isCfcHomecareQuestion = /(cfc homecare|homecare|cfc la cua|cfc home)/.test(lower);

return [{ json: {
  text: text.trim(),
  normalizedText: lower,
  senderId,
  messageId,
  emptyInput,
  inputKind: emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text',
  isEcho,
  isGreeting,
  isThanks,
  isGoodbye,
  isAcknowledgement,
  isEmotional,
  isFollowUp,
  isBotComplaint,
  isCatalogQuestion,
  isWebsiteQuestion,
	  isShortCodQuestion,
	  isShortDetergentQuestion,
	  isGenericDetergentQuestion,
	  isFloorCleanerQuestion,
	  isShortPanoQuestion,
	  isShortZeoQuestion,
	  isWarrantyQuestion,
  mentionsAba,
  isCfcHomecareQuestion,
  isSensitive,
  isOutOfScope,
  isVagueProductRequest,
  isUnsupportedProductQuestion,
  hasPhoneNumber,
  phoneNumber: phoneMatch ? phoneMatch[0].replace(/\\s+/g, ' ').trim() : '',
  hasAreaInfo,
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
        onError: 'continueRegularOutput',
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
        onError: 'continueRegularOutput',
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
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong', hong: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    sdt: 'so dien thoai', dt: 'dien thoai', gia: 'gia ban', gif: 'gi', j: 'gi', z: 'vay',
    web: 'website', wed: 'website', wep: 'website', cod: 'cod',
  };
  return normalize(value).split(/\\s+/).filter(Boolean).map(token => aliases[token] || token).join(' ');
}

const STOP_WORDS = new Set([
  'a', 'ad', 'admin', 'anh', 'ban', 'ben', 'bi', 'chi', 'cho', 'co', 'cua', 'da', 'dau',
  'duoc', 'em', 'gi', 'khong', 'la', 'minh', 'mot', 'nao', 'nha', 'nhe', 'oi', 'shop',
  'thi', 'toi', 'tren', 'va', 'vay', 've', 'voi',
]);

function meaningfulTokens(value) {
  return [...new Set(normalizeForSearch(value).split(' ').filter(token => token.length >= 2 && !STOP_WORDS.has(token)))];
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(normalize(value));
}

function splitExamples(value) {
  if (Array.isArray(value)) return value.map(String).map(item => item.trim()).filter(Boolean);
  return String(value || '').split(';').map(item => item.trim()).filter(Boolean);
}

function parseJson(value, fallback) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try { return JSON.parse(value); } catch (_) { return fallback; }
}

function parseSnapshotEnvelope(value) {
  const envelope = parseJson(value, null);
  if (Array.isArray(envelope)) return { items: envelope, updatedAt: '' };
  if (!envelope || typeof envelope !== 'object') return { items: [], updatedAt: '' };
  const rawItems = envelope.snapshot_json || envelope.knowledgeItems || envelope.snapshot || [];
  const items = parseJson(rawItems, rawItems);
  return { items: Array.isArray(items) ? items : [], updatedAt: envelope.updated_at || '' };
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

function findByIntent(...intents) {
  for (const intent of intents) {
    const matched = knowledgeItems.find(item => item.intent === intent);
    if (matched) return matched;
  }
  return null;
}

function findByIntentIncludes(...parts) {
  for (const part of parts) {
    const matched = knowledgeItems.find(item => item.intent.includes(part));
    if (matched) return matched;
  }
  return null;
}

function findByKnowledgeTerms(...terms) {
  const normalizedTerms = terms.map(normalizeForSearch).filter(Boolean);
  return knowledgeItems
    .map(item => {
      const searchable = normalizeForSearch([
        item.intent,
        item.category,
        item.question_examples.join(' '),
        item.answer,
      ].join(' '));
      const hits = normalizedTerms.filter(term => searchable.includes(term)).length;
      return { item, hits };
    })
    .filter(result => result.hits > 0)
    .sort((a, b) => b.hits - a.hits || b.item.priority - a.item.priority)[0]?.item || null;
}

function isLowRiskEntry(entry) {
  if (!entry) return false;
  return ['product', 'faq', 'sales', 'shipping', 'payment', 'operations', 'support', 'brand'].includes(entry.category);
}

function buildCatalogReply(items) {
  const productItems = items.filter(item => item.category === 'product' && item.answer);
  const hasDetergent = productItems.some(item => /detergent|laundry|giat/i.test(item.intent + ' ' + item.question_examples.join(' ')));
  const hasDish = productItems.some(item => /dish|chen|chén/i.test(item.intent + ' ' + item.question_examples.join(' ')));
  const hasFloor = productItems.some(item => /floor|san|sàn/i.test(item.intent + ' ' + item.question_examples.join(' ')));
  const hasBleach = productItems.some(item => /bleach|tay|tẩy|toilet|javen/i.test(item.intent + ' ' + item.question_examples.join(' ')));
  const hasPano = productItems.some(item => normalize(item.brand).includes('pano') || item.intent.includes('pano'));
  const groups = [];
  if (hasDetergent) groups.push('bột giặt, nước giặt');
  if (hasDish) groups.push('nước rửa chén');
  if (hasFloor) groups.push('nước lau sàn');
  if (hasBleach) groups.push('sản phẩm tẩy rửa');
  if (hasPano) groups.push('các dòng PANO/Oplus liên quan');
  return groups.length
    ? 'Dạ ZeO hiện có các nhóm sản phẩm như ' + groups.join(', ') + '. Bạn đang quan tâm nhóm nào để mình gửi thông tin cụ thể hơn nha?'
    : 'Dạ ZeO có các sản phẩm tẩy rửa gia dụng. Bạn cần bột giặt, nước rửa chén, nước lau sàn hay sản phẩm vệ sinh nhà cửa ạ?';
}

const input = $('Loc Dau Vao').first().json;
const session = parseJson($('Get Session').first().json.sessionRaw, {});
const snapshotRaw = $input.first().json.knowledgeSnapshot;
const snapshot = parseSnapshotEnvelope(snapshotRaw);
const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo oplus', 'zeo pano', 'zeo pano oplus']);
const knowledgeItems = snapshot.items
  .map(item => ({
    active: asBool(item.active ?? true),
    brand: String(item.brand || 'ZeO').trim(),
    category: String(item.category || 'faq').trim(),
    intent: String(item.intent || '').trim(),
    source_id: String(item.source_id || '').trim(),
    question_examples: splitExamples(item.question_examples),
    answer: String(item.answer || item.content || '').trim(),
    priority: Number(item.priority || 0),
    audience: String(item.audience || 'customer').trim().toLowerCase(),
    answer_mode: String(item.answer_mode || '').trim().toLowerCase(),
  }))
  .filter(item => item.active && item.answer && item.intent)
  .filter(item => ![
    'new_customer_welcome_template',
    'post_purchase_followup_template',
    'loyal_customer_thank_template',
    'promotion_announcement_template',
    'tone_of_voice_guidelines',
    'tone_of_voice_restrictions',
    'tiktok_reels_content_style',
    'ecommerce_product_description_style',
    'facebook_zalo_content_style',
    'email_zalo_business_style',
    'review_response_guidelines',
  ].includes(item.intent))
  .filter(item => item.audience !== 'internal' && allowedBrands.has(normalize(item.brand)));

const isDuplicate = Boolean(input.messageId && session.last_message_id && input.messageId === session.last_message_id);
const shouldIgnore = Boolean(input.isEcho || !input.senderId || isDuplicate);
const previousText = normalizeForSearch([session.last_user_message, session.last_bot_reply].filter(Boolean).join(' '));
const waitingForContact = ['so dien thoai', 'khu vuc', 'nhan vien', 'lien he', 'dai ly', 'phan phoi']
  .some(phrase => previousText.includes(phrase));
const looksLikeAreaReply = /^(toi|minh|em|anh|chi)?s*(o|tai)s+/.test(normalizeForSearch(input.text));
const isLeadInfo = Boolean(input.hasPhoneNumber || (input.hasAreaInfo && (waitingForContact || looksLikeAreaReply)));
const resolvedQuestion = input.isFollowUp && session.last_user_message
  ? normalizeForSearch(session.last_user_message + ' ' + input.text)
  : normalizeForSearch(input.normalizedText || input.text);
const sessionEntry = input.isFollowUp && session.last_source_id
  ? knowledgeItems.find(item => item.source_id === session.last_source_id && item.intent === session.last_intent)
  : null;
const scored = knowledgeItems
  .map(entry => ({ ...entry, ...scoreEntry(resolvedQuestion, entry) }))
  .filter(entry => entry.score > 0)
  .sort((a, b) => b.score - a.score || b.priority - a.priority);
let best = scored[0] || null;
if (sessionEntry && input.isFollowUp && !input.isSensitive && !input.isOutOfScope) {
  const sessionScore = scoreEntry(resolvedQuestion, sessionEntry);
  if (sessionScore.matched >= 1 && (!best || sessionScore.score >= best.score - 8)) {
    best = { ...sessionEntry, ...sessionScore };
  }
}
const secondScore = scored.find(item => !best || item.intent !== best.intent)?.score || 0;
const bestScore = Math.round((best?.score || 0) * 100) / 100;
const scoreMargin = Math.round((bestScore - secondScore) * 100) / 100;
const confidence = best?.exact || (bestScore >= 58 && scoreMargin >= 5)
  ? 'high'
  : (bestScore >= 28 && (best?.matched || 0) >= 1 && isLowRiskEntry(best) ? 'medium' : 'low');
let forcedEntry = null;
if (input.isShortCodQuestion) {
  forcedEntry = findByIntent('nationwide_shipping_no_cod', 'cod_payment')
    || findByIntentIncludes('cod')
    || findByKnowledgeTerms('cod', 'thanh toan khi nhan', 'nhan hang tra tien');
} else if (input.isWebsiteQuestion) {
  forcedEntry = findByIntent('company_website', 'website', 'company_contact_information', 'online_purchase')
    || findByIntentIncludes('website', 'contact', 'purchase')
    || findByKnowledgeTerms('zeo.vn', 'website', 'trang web');
} else if (input.isGenericDetergentQuestion) {
  forcedEntry = findByIntent('zeo_detergent_usp', 'zeo_detergent_fragrance', 'zeo_detergent_technology')
    || findByIntentIncludes('detergent', 'laundry')
    || findByKnowledgeTerms('bot giat', 'nuoc giat', 'giat quan ao');
} else if (input.isFloorCleanerQuestion) {
  forcedEntry = findByIntent('floor_cleaner_features')
    || findByIntentIncludes('floor', 'lau_san', 'floor_cleaner')
    || findByKnowledgeTerms('nuoc lau san', 'lau san');
} else if (input.isShortPanoQuestion) {
  forcedEntry = findByIntent('pano_laundry_positioning', 'pano_laundry_fragrance_options')
    || findByIntentIncludes('pano')
    || findByKnowledgeTerms('pano');
} else if (input.isShortZeoQuestion) {
  forcedEntry = findByIntent('company_contact_information')
    || findByIntentIncludes('zeo')
    || findByKnowledgeTerms('zeo');
} else if (input.isWarrantyQuestion) {
  forcedEntry = findByIntent('warranty_policy', 'return_policy_info', 'product_defect_support')
    || findByIntentIncludes('warranty', 'return', 'defect')
    || findByKnowledgeTerms('bao hanh', 'san pham bi loi', 'doi tra');
}

let responseMode = 'review';
let fallbackReason = 'low_confidence';
let finalReply = 'Dạ, bạn muốn hỏi về sản phẩm, mua hàng, giao hàng hay chính sách của ZeO ạ? Bạn nói ngắn gọn nhu cầu là được nha.';
let matchedIntent = '';
let matchedSourceId = '';
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
  finalReply = 'Dạ ZeO chào bạn ạ. Bạn cần mình hỗ trợ thông tin sản phẩm, mua hàng, giao hàng hay chính sách nào ạ?';
} else if (input.isThanks) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'thanks';
  finalReply = 'Dạ, ZeO cảm ơn bạn ạ. Khi cần thêm thông tin, bạn cứ nhắn mình nhé.';
} else if (input.isGoodbye) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'goodbye';
  finalReply = 'Dạ, cảm ơn bạn đã liên hệ ZeO. Chúc bạn một ngày vui vẻ nhé.';
} else if (input.isAcknowledgement) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = session.last_intent || 'acknowledgement';
  finalReply = 'Dạ vâng ạ. Khi cần hỗ trợ thêm, bạn cứ nhắn ZeO nhé.';
} else if (isLeadInfo) {
  responseMode = 'review';
  fallbackReason = 'contact_information_received';
  finalReply = 'Dạ, ZeO đã nhận được thông tin bạn gửi. Admin sẽ kiểm tra và liên hệ hỗ trợ bạn sớm nhất nhé.';
} else if (input.isWarrantyQuestion && !forcedEntry) {
  responseMode = 'review';
  fallbackReason = 'warranty_support_unverified';
  finalReply = 'Dạ, dữ liệu hiện tại chưa có chính sách bảo hành riêng. Nếu sản phẩm bị lỗi hoặc cần đổi trả, bạn gửi giúp mình tình trạng sản phẩm, hình ảnh và thông tin đơn hàng để admin ZeO kiểm tra hỗ trợ đúng chính sách nhé.';
} else if (input.isBotComplaint) {
  responseMode = 'review';
  fallbackReason = 'bot_answer_complaint';
  matchedIntent = session.last_intent || '';
  finalReply = 'Dạ xin lỗi bạn, câu trả lời trước chưa đúng ý. Bạn nhắn lại giúp mình câu hỏi chính hoặc tên sản phẩm cần hỗ trợ, mình sẽ kiểm tra theo dữ liệu ZeO kỹ hơn nhé.';
} else if (input.mentionsAba && input.isShortDetergentQuestion) {
  responseMode = 'review';
  fallbackReason = 'competitor_product_question';
  finalReply = 'Dạ, hiện dữ liệu của ZeO chỉ có thông tin về các sản phẩm thuộc ZeO, PANO và Oplus. Bạn muốn hỏi bột giặt ZeO hay PANO/Oplus để mình hỗ trợ đúng thông tin nha?';
} else if (input.isCfcHomecareQuestion) {
  responseMode = 'review';
  fallbackReason = 'cfc_homecare_unverified';
  finalReply = 'Dạ, thông tin này hiện chưa có trong dữ liệu ZeO nên mình chưa dám xác nhận. Admin ZeO sẽ kiểm tra và phản hồi bạn chính xác hơn nhé.';
} else if (input.isCatalogQuestion) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'product_catalog_summary';
  finalReply = buildCatalogReply(knowledgeItems);
} else if (input.isWebsiteQuestion && forcedEntry) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = forcedEntry.intent;
  matchedSourceId = forcedEntry.source_id;
  canonicalAnswer = forcedEntry.answer;
  const sheetAnswer = String(forcedEntry.answer || '');
  if (sheetAnswer.includes('https://zeo.vn')) {
    finalReply = sheetAnswer;
  } else if (sheetAnswer.includes('http://zeo.vn')) {
    finalReply = sheetAnswer.replace('http://zeo.vn', 'https://zeo.vn');
  } else if (sheetAnswer.includes('www.zeo.vn')) {
    finalReply = sheetAnswer.replace('www.zeo.vn', 'https://zeo.vn');
  } else {
    finalReply = sheetAnswer.replace('zeo.vn', 'https://zeo.vn/');
  }
} else if (input.isGenericDetergentQuestion && forcedEntry) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = forcedEntry.intent;
  matchedSourceId = forcedEntry.source_id;
  canonicalAnswer = forcedEntry.answer;
  finalReply = forcedEntry.answer;
} else if (forcedEntry) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = forcedEntry.intent;
  matchedSourceId = forcedEntry.source_id;
  canonicalAnswer = forcedEntry.answer;
  finalReply = forcedEntry.answer;
} else if (input.isVagueProductRequest) {
  responseMode = 'direct';
  fallbackReason = 'product_scope_clarification';
  matchedIntent = 'product_consultation_request';
  finalReply = 'Dạ, bạn đang cần sản phẩm cho giặt quần áo, rửa chén, lau sàn hay vệ sinh nhà cửa ạ? Bạn cho mình biết nhu cầu cụ thể để ZeO hỗ trợ đúng thông tin nhé.';
} else if (input.isSensitive) {
  responseMode = 'review';
  fallbackReason = 'sensitive_case';
  finalReply = 'Dạ, ZeO đã ghi nhận phản ánh của bạn. Admin sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (input.isUnsupportedProductQuestion) {
  responseMode = 'review';
  fallbackReason = 'unsupported_product_scope';
  finalReply = 'Dạ, theo dữ liệu hiện có ZeO chỉ hỗ trợ thông tin về các sản phẩm tẩy rửa gia dụng. Admin sẽ hỗ trợ thêm nếu bạn cần xác nhận sản phẩm khác nhé.';
} else if (input.isOutOfScope) {
  responseMode = 'review';
  fallbackReason = 'out_of_scope';
  finalReply = 'Dạ, mình đang hỗ trợ thông tin về sản phẩm và dịch vụ của ZeO. Bạn cho mình biết nhu cầu liên quan đến ZeO nhé.';
} else if (input.isEmotional && confidence === 'low') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'emotional_support';
  finalReply = 'Mình rất tiếc khi nghe bạn đang không vui. Nếu bạn cần thông tin về sản phẩm tẩy rửa ZeO, mình sẵn sàng hỗ trợ nhé.';
} else if (!snapshotRaw || !knowledgeItems.length) {
  responseMode = 'review';
  fallbackReason = 'knowledge_snapshot_missing';
  finalReply = 'Dạ, hệ thống thông tin đang được cập nhật. Admin ZeO sẽ phản hồi bạn sớm nhất nhé.';
} else if (confidence === 'high' && best) {
  canonicalAnswer = best.answer;
  finalReply = best.answer;
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  responseMode = 'direct';
  fallbackReason = '';
} else if (confidence === 'medium' && best) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  canonicalAnswer = best.answer;
  finalReply = best.answer;
} else if (best && isLowRiskEntry(best) && bestScore >= 22 && (best.matched || 0) >= 1 && scoreMargin >= 1) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  canonicalAnswer = best.answer;
  finalReply = best.answer;
}

const routeIndex = responseMode === 'direct' ? 0 : responseMode === 'rewrite' ? 1 : responseMode === 'review' ? 2 : 3;
const sessionState = {
  ...session,
  last_intent: matchedIntent || session.last_intent || '',
  last_source_id: matchedSourceId || session.last_source_id || '',
  last_user_message: input.text,
  last_bot_reply: finalReply,
  last_message_id: input.messageId || session.last_message_id || '',
  customer_phone: input.phoneNumber || session.customer_phone || '',
  customer_location: isLeadInfo && input.hasAreaInfo ? input.text : (session.customer_location || ''),
  updated_at: new Date().toISOString(),
};

return [{ json: {
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
  canonicalAnswer,
  contextAnswer: canonicalAnswer,
  finalReply,
  fallbackMessage: finalReply,
  fallbackReason,
  isSensitive: Boolean(input.isSensitive),
  isLeadInfo,
  shouldIgnore,
  sessionState,
} }];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000004',
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
        id: 'f1000001-0000-0000-0000-000000000005',
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
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.2, num_predict: 100 }, messages: [ { role: "system", content: "Bạn chỉ biên tập lại CÂU TRẢ LỜI GỐC thành một tin nhắn Messenger tự nhiên bằng tiếng Việt có dấu. Không trả lời theo kiến thức riêng. Không thêm, suy đoán hoặc thay đổi bất kỳ dữ kiện nào. Không dùng tiếng Trung, tiếng Anh, ký tự lạ, markdown, tiêu đề hay lời giới thiệu. Không nhắc đến AI, Qwen, prompt hoặc thông tin tham chiếu. Giữ nguyên tên thương hiệu, sản phẩm, số điện thoại, địa chỉ, công dụng và mọi con số có trong câu gốc. Trả lời tối đa 3 câu. Nếu không thể biên tập an toàn, hãy chép nguyên văn CÂU TRẢ LỜI GỐC." }, { role: "user", content: "CÂU TRẢ LỜI GỐC:\\n" + $json.canonicalAnswer + "\\n\\nCÂU HỎI KHÁCH:\\n" + $json.userMessage } ] } }}',
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
const aiText = (ollamaResult?.message?.content || ollamaResult?.response || '').trim();
const tooShort = aiText.length < 5;
const tooLong = aiText.length > 1000;
const hasForeignScript = /[㐀-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿຀-໿ក-៿ऀ-ॿ]/.test(aiText);
const hasEnglishLeak = /\\b(i am|i'm|you are|please|sorry|hello|thank you|as an ai|i cannot|i don't|provide|contact us|customer service)\\b/i.test(aiText);
const hasModelLeak = /qwen|alibaba|aliyun|tongyi|通义|阿里|阿里云|助手|人工智能|中文|language model|large language|chatbot|system prompt|developer message/i.test(aiText);
const hasPromptLeak = /thông tin tham chiếu|câu hỏi khách hàng|câu trả lời gốc|system prompt|developer message/i.test(aiText);
const hallucinatedScope = /máy đo oxy|may do oxy|zeo mini|thiết bị y tế|thiet bi y te|chăm sóc cá nhân|cham soc ca nhan|sản phẩm sức khỏe|san pham suc khoe|phụ kiện sức khỏe|phu kien suc khoe/i.test(aiText);
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
const passed = !tooShort && !tooLong && !hasForeignScript && !hasEnglishLeak && !hasModelLeak && !hasPromptLeak && !hallucinatedScope && !changedFacts;

let guardrailReason = 'ollama_guardrail_failed';
if (hallucinatedScope) guardrailReason = 'ollama_hallucinated_scope';
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

return [{ json: {
  ...ragData,
  finalReply,
  passed,
  fallbackReason: passed ? '' : guardrailReason,
  fallbackMessage: finalReply,
  sessionState,
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
        onError: 'continueRegularOutput',
    })
    SaveSession = {
        operation: 'set',
        key: '={{ "zeo:session:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify($json.sessionState) }}',
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
        onError: 'continueRegularOutput',
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
        position: [1552, 592],
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
        position: [1792, 592],
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
        id: 'f1000001-0000-0000-0000-000000000008',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [2208, 64],
        credentials: { facebookGraphApi: { id: 'JyJ5NRHHJdzjsL4R', name: 'ZeO' } },
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
        credentials: { facebookGraphApi: { id: 'JyJ5NRHHJdzjsL4R', name: 'ZeO' } },
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
        this.RouterCoNguon.out(0).to(this.SaveSession.in(0));
        this.RouterCoNguon.out(1).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(2).to(this.SaveSession.in(0));
        this.RouterCoNguon.out(2).to(this.QueueLearningReview.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.GoiOllamaLocal.error().to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.SaveSession.in(0));
        this.RouterGuardrail.out(1).to(this.SaveSession.in(0));
        this.RouterGuardrail.out(1).to(this.QueueLearningReview.in(0));
        this.SaveSession.out(0).to(this.NhanKhachAuto.in(0));
        this.QueueLearningReview.out(0).to(this.PrepareTelegramAlert.in(0));
        this.PrepareTelegramAlert.out(0).to(this.NotifyTelegramOperations.in(0));
    }
}
