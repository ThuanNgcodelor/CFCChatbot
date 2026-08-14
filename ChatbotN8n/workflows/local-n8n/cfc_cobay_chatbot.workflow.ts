import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Co Bay Chatbot
// Nodes   : 21  |  Connections: 27
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GetCfcCustomerProfile              redis                      [onError→regular] [creds] [alwaysOutput]
// MergeCfcCustomerProfile            code
// GetCfcSession                      redis                      [onError→regular] [creds] [alwaysOutput]
// GoiCfcOllamaNluLocal               httpRequest                [onError→out(1)]
// CfcDialogueManager                 code
// GetCfcKnowledgeSnapshot            redis                      [onError→regular] [creds] [alwaysOutput]
// CfcRagTimKiem                      code
// RouterCoNguon                      switch
// GoiOllamaLocal                     httpRequest                [onError→out(1)]
// KiemChung                          code
// RouterGuardrail                    if
// SaveCfcCustomerProfile             redis                      [onError→regular] [creds]
// SaveCfcSession                     redis                      [onError→regular] [creds]
// QueueCfcLearningReview             redis                      [onError→regular] [creds]
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
//      → GetCfcCustomerProfile
//        → MergeCfcCustomerProfile
//          → GetCfcSession
//            → GoiCfcOllamaNluLocal
//              → CfcDialogueManager
//                → GetCfcKnowledgeSnapshot
//                  → CfcRagTimKiem
//                    → RouterCoNguon
//                      → SaveCfcCustomerProfile
//                      → SaveCfcSession
//                        → NhanKhachAuto
//                     .out(1) → GoiOllamaLocal
//                        → KiemChung
//                          → RouterGuardrail
//                            → SaveCfcCustomerProfile (↩ loop)
//                            → SaveCfcSession (↩ loop)
//                           .out(1) → SaveCfcCustomerProfile (↩ loop)
//                           .out(1) → SaveCfcSession (↩ loop)
//                           .out(1) → QueueCfcLearningReview
//                              → PrepareTelegramAlert
//                                → NotifyTelegramOperations
//                        → KiemChung (↩ loop)
//                     .out(2) → SaveCfcCustomerProfile (↩ loop)
//                     .out(2) → SaveCfcSession (↩ loop)
//                     .out(2) → QueueCfcLearningReview (↩ loop)
//              → CfcDialogueManager (↩ loop)
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
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong', hong: 'khong',
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
    .replace(/\\b(o|tai)\\s+dua\\b/g, '$1 dau')
    .replace(/\\bgiaohang\\b/g, 'giao hang')
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
const areaWords = ['tinh', 'thanh pho', 'tp', 'huyen', 'quan', 'q', 'xa', 'phuong', 'thi xa', 'khu vuc', 'mien', 'can tho', 'thai binh', 'kien giang', 'tra noc', 'tphcm', 'ho chi minh'];
const isAreaQuestion = /(^|\\s)(o dau|tai dau|cho nao|dia chi.*o dau|mua o dau|ban o dau)(\\s|$)/.test(normalizedText);
const hasAreaInfo = !isAreaQuestion && (
  areaWords.some(word => normalizedText.includes(word)) ||
  /(^|\\s)(minh o|em o|toi o|anh o|chi o|khach hang cu o|ben minh o|o tinh|o huyen|o quan|khu vuc)\\s+[a-z0-9]/.test(normalizedText)
);
const dealerRequestWords = ['nha phan phoi', 'dai ly', 'phan phoi', 'ban le', 'mua de ban', 'mua ban le', 'lien he mua', 'mua o dau', 'mua de ban le'];
const isDealerLocationRequest = dealerRequestWords.some(word => normalizedText.includes(word)) ||
  ((normalizedText.includes('mua') || normalizedText.includes('lien he')) && hasAreaInfo);
const isGreeting = tokenCount <= 5 && /^(xin chao|chao|hello|hi|alo|shop oi|admin oi|ad oi)(\\s|$)/.test(normalizedText);
const isThanks = tokenCount <= 7 && /^(cam on|thanks|thank you|da cam on|ok cam on)(\\s|$)/.test(normalizedText);
const isGoodbye = tokenCount <= 6 && /^(tam biet|bye|goodbye|hen gap lai|chao nhe)(\\s|$)/.test(normalizedText);
const isAcknowledgement = tokenCount <= 4 && /^(ok|oke|okay|da|vang|uh|um|roi|duoc|biet roi|hieu roi)(\\s|$)/.test(normalizedText);
const isStatusCheck = tokenCount <= 6 && /^(sao roi|sao roi ad|sao roi admin|the nao roi|toi hoi sao roi|co thong tin chua|co tin gi chua|xu ly toi dau|toi dau roi)(\\s|$)/.test(normalizedText);
const isFollowUp = tokenCount <= 9 && /^(con |vay |the |loai do|san pham do|cai do|cai nay|no |dung sao|su dung sao|pha sao|pha nhu nao|co mui|co nhung mui|co huong|co nhung huong|gia sao|chai lon|loai lon|ship |giao hang )/.test(normalizedText);
const isBotComplaint = /(do ngu|ngu ngu|sao ngu|bot ngu|may ngu|m ngu|tra loi gi ky|tra loi ky|tra loi xam|xam xam|khong hieu|noi gi vay|sao tra loi|tra loi gi v|tra loi gi vay|toi chui|chui ban|lien quan gi|khong lien quan|hoi mot dang tra loi mot neo|tra loi chan|chan ghe|hai ghe|hai vl|chua on|khong on|session.*chua on|khong co session|mat ngu canh|context sai|khong nho ngu canh)/.test(normalizedText);
const isCatalogQuestion = /(san pham gi|san pham nao|co san pham|co nhung gi|ban nhung gi|ban gi|co gi ban|danh muc san pham|cac san pham|mat hang gi|hang gi|phan bon gi|co phan gi)/.test(normalizedText);
const isPriceQuestion = /(^|\\s)(gia|bang gia|bao gia|xin gia|bao nhieu tien|nhieu tien|price)(\\s|$)/.test(normalizedText);
const hasOrderQuantity = /(^|\\s)\\d+(?:[.,]\\d+)?\\s*(kg|ki|ky|kilo|kilogram|tan|ta|bao|tui|goi|thung|chai|can)(\\s|$)/.test(normalizedText);
const hasOrderProduct = /(phan bon|npk|huu co|co bay|cfc|phan)/.test(normalizedText);
const isOrderQuantityRequest = hasOrderQuantity && hasOrderProduct;
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
    isStatusCheck,
    isFollowUp,
    isBotComplaint,
    isCatalogQuestion,
    isPriceQuestion,
    isOrderQuantityRequest,
    hasForeignInputScript,
    isPromptInjection,
    isProductDiscovery: productDiscoveryWords.some(word => normalizedText.includes(word)),
    hasPhoneNumber,
    phoneNumber: hasPhoneNumber ? phoneDigits : '',
    hasAreaInfo,
    isDealerLocationRequest,
  },
}];
`,
    };

    @node({
        id: '097d8f8d-f22d-4d85-931e-7859c2412376',
        name: 'Get CFC Customer Profile',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [448, 304],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        onError: 'continueRegularOutput',
        alwaysOutputData: true,
    })
    GetCfcCustomerProfile = {
        operation: 'get',
        propertyName: 'customerProfileRaw',
        key: '={{ "cfc:customer:messenger:" + $json.senderId }}',
        keyType: 'string',
        options: {},
    };

    @node({
        id: '8106ee22-8bf8-4586-aa0e-23e2addb041f',
        name: 'Merge CFC Customer Profile',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [656, 304],
    })
    MergeCfcCustomerProfile = {
        jsCode: `
function parseJson(value, fallback) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try { return JSON.parse(value); } catch (_) { return fallback; }
}

const input = $('Loc Dau Vao').first().json;
const existingProfile = parseJson($input.first().json.customerProfileRaw, {});
const now = new Date().toISOString();
const profile = {
  brand: 'CFC',
  channel: 'messenger',
  sender_id: input.senderId || existingProfile.sender_id || '',
  fb_name: existingProfile.fb_name || '',
  phone: existingProfile.phone || existingProfile.customer_phone || '',
  area: existingProfile.area || existingProfile.customer_location || '',
  last_need: existingProfile.last_need || '',
  last_intent: existingProfile.last_intent || '',
  lead_stage: existingProfile.lead_stage || 'new',
  pending_slots: Array.isArray(existingProfile.pending_slots) ? existingProfile.pending_slots : ['phone', 'area'],
  conversation_summary: existingProfile.conversation_summary || '',
  first_seen_at: existingProfile.first_seen_at || now,
  last_seen_at: now,
};

return [{ json: {
  ...input,
  customerProfileRaw: JSON.stringify(profile),
  customerProfile: profile,
} }];
`,
    };

    @node({
        id: '67f7cabe-99bd-4b73-9acd-438022a97e99',
        name: 'Get CFC Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [880, 304],
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
        id: 'f2000001-0000-0000-0000-000000000001',
        name: 'Goi CFC Ollama NLU Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [1088, 304],
        onError: 'continueErrorOutput',
    })
    GoiCfcOllamaNluLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/chat',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.1, num_predict: 220 }, messages: [ { role: "system", content: "Bạn là bộ phân loại NLU cho CSKH Cò Bay/CFC. Chỉ trả về JSON hợp lệ, không markdown. Không trả lời khách. Schema: {intent,speech_act,sentiment,topic,entities,order_items,memory_updates,needs_human,confidence,use_rag}. intent ưu tiên một trong: bot_answer_complaint,greeting,thanks,goodbye,acknowledgement,status_check,order_request,wholesale_dealer,support_general,customer_profile_lookup,contact_next_step,price_request,dealer_location_request,product_faq,shipping_faq,company_faq,unknown. Nếu khách hỏi kiểu sao rồi ad, có thông tin chưa, xử lý tới đâu sau khi đang chờ admin/nhân viên, chọn status_check và use_rag=false. Nếu khách chửi bot, nói bot trả sai, nói không liên quan, chán vì câu trước, chọn bot_answer_complaint và use_rag=false. Nếu là câu hỏi sản phẩm phân bón, giao hàng, công ty, địa chỉ thì use_rag=true. Không bịa giá, liều lượng, đại lý, địa chỉ hoặc công dụng ngoài dữ liệu." }, { role: "user", content: JSON.stringify({ message: $("Loc Dau Vao").first().json.text, normalized_message: $("Loc Dau Vao").first().json.normalizedText, flags: $("Loc Dau Vao").first().json, customer_profile: $("Merge CFC Customer Profile").first().json.customerProfile, session_raw: $("Get CFC Session").first().json.sessionRaw || "{}" }) } ] } }}',
        options: {},
    };

    @node({
        id: 'f2000001-0000-0000-0000-000000000002',
        name: 'CFC Dialogue Manager',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1312, 304],
    })
    CfcDialogueManager = {
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

function parseJson(value, fallback) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try { return JSON.parse(value); } catch (_) { return fallback; }
}

function parseNlu(payload) {
  const raw = payload?.message?.content || payload?.response || payload?.text || '';
  if (!raw || typeof raw !== 'string') return {};
  const cleaned = raw.replace(/^\\s*\`\`\`(?:json)?/i, '').replace(/\`\`\`\\s*$/i, '').trim();
  const direct = parseJson(cleaned, null);
  if (direct && typeof direct === 'object') return direct;
  const match = cleaned.match(/\\{[\\s\\S]*\\}/);
  return match ? parseJson(match[0], {}) : {};
}

const input = $('Loc Dau Vao').first().json;
const session = parseJson($('Get CFC Session').first().json.sessionRaw, {});
const profileInput = $('Merge CFC Customer Profile').first().json;
const customerProfile = parseJson(profileInput.customerProfileRaw || profileInput.customerProfile, {});
const nluPayload = $input.first().json || {};
const nlu = parseNlu(nluPayload);
const lower = normalize(input.text)
  .replace(/\\bgiaohang\\b/g, 'giao hang');
const previousText = normalize([session.last_user_message, session.last_bot_reply, customerProfile.last_need, customerProfile.conversation_summary].filter(Boolean).join(' '));

const explicitBotComplaint = /(do ngu|ngu ngu|sao ngu|bot ngu|may ngu|m ngu|tra loi gi ky|tra loi ky|tra loi xam|xam xam|khong hieu|noi gi vay|sao tra loi|tra loi gi v|tra loi gi vay|toi chui|chui ban|lien quan gi|khong lien quan|hoi mot dang tra loi mot neo|tra loi chan|chan ghe|hai ghe|hai vl|chua on|khong on|session.*chua on|khong co session|mat ngu canh|context sai|khong nho ngu canh)/.test(lower);
const shortFrustrationAfterBot = /^(chan|chan ghe|met ghe|haiz|hai|that vong|bo tay|nan ghe)$/.test(lower) && Boolean(session.last_bot_reply);
const nluIntent = String(nlu.intent || '').trim();
const nluConfidence = Number(nlu.confidence || 0);
const nluComplaint = nluIntent === 'bot_answer_complaint' && nluConfidence >= 0.55;
const isBotComplaint = Boolean(input.isBotComplaint || explicitBotComplaint || shortFrustrationAfterBot || nluComplaint);

const hasDealerSignal = /(nha phan phoi|dai ly|phan phoi|mua de ban|ban le|nhap si|lay si|mua si|npp)/.test(lower);
const dealerRegistrationSignal = /(muon|can|xin|dang ky|lam|tro thanh|mo|hop tac).*(dai ly|nha phan phoi|npp|phan phoi)|(?:dai ly|nha phan phoi|npp).*(duoc khong|sao|the nao|dang ky|lam)/.test(lower);
const hasPriceSignal = /(gia sao|xin gia|bao gia|bang gia|bao nhieu tien|nhieu tien|price)/.test(lower);
const hasBusinessProduct = /(phan bon|npk|huu co|co bay|cfc|phan)/.test(lower);
const contactInfoSignal = Boolean(input.hasPhoneNumber || input.hasAreaInfo);
const previousNeedsContact = /(so dien thoai|sdt|khu vuc|tinh thanh|dia chi|admin|nhan vien|lien he|dai ly|nha phan phoi|phan phoi|chot don|xac nhan don)/.test(previousText);

let intent = nluIntent || '';
let replyType = 'knowledge_lookup';
let useRag = true;
let responseMode = '';
let fallbackReason = '';
let finalReply = '';
let needsHuman = Boolean(nlu.needs_human);

if (isBotComplaint) {
  intent = 'bot_answer_complaint';
  replyType = 'repair_wrong_answer';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'bot_answer_complaint';
  needsHuman = true;
  finalReply = 'Dạ xin lỗi bạn, câu trả lời vừa rồi chưa đúng ý. Bạn muốn mình hỗ trợ lại về sản phẩm phân bón, mua hàng, giao hàng hay đăng ký đại lý ạ?';
} else if (input.isThanks) {
  intent = 'thanks';
  replyType = 'acknowledge';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ, Cò Bay cảm ơn bạn ạ. Khi cần thêm thông tin, bạn cứ nhắn mình nhé.';
} else if (input.isGreeting) {
  intent = 'greeting';
  replyType = 'greeting';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ Cò Bay chào bạn ạ. Bạn cần mình hỗ trợ về sản phẩm phân bón, mua hàng, giao hàng, đại lý hay địa chỉ công ty ạ?';
} else if (input.isAcknowledgement) {
  intent = session.last_intent || 'acknowledgement';
  replyType = 'acknowledge';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ vâng ạ. Khi cần hỗ trợ thêm, bạn cứ nhắn Cò Bay nhé.';
} else if (input.isStatusCheck || nluIntent === 'status_check') {
  intent = 'status_check';
  replyType = 'status_check';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ, mình đang kiểm tra lại thông tin trước đó cho bạn. Nếu bạn đã gửi số điện thoại và khu vực, admin Cò Bay sẽ dựa vào đó để liên hệ hỗ trợ; nếu chưa, bạn gửi thêm giúp mình nha.';
} else if (contactInfoSignal && previousNeedsContact && !input.isOrderQuantityRequest) {
  intent = 'contact_information_received';
  replyType = 'capture_contact';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'contact_information_received';
  needsHuman = true;
} else if (input.isOrderQuantityRequest || nluIntent === 'order_request') {
  intent = 'order_request';
  replyType = 'confirm_order';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'order_request';
  needsHuman = true;
} else if (dealerRegistrationSignal || ((hasDealerSignal || nluIntent === 'wholesale_dealer') && !/o dau|gan|minh|khu vuc/.test(lower))) {
  intent = 'wholesale_dealer';
  replyType = 'wholesale_dealer';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'dealer_contact_needed';
  needsHuman = true;
} else if (hasPriceSignal && hasBusinessProduct) {
  intent = 'price_request';
  replyType = 'price_request';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'price_unverified';
  needsHuman = true;
} else if (input.isDealerLocationRequest || nluIntent === 'dealer_location_request') {
  intent = 'dealer_location_request';
  replyType = 'dealer_location_request';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'dealer_location_request';
  needsHuman = true;
} else if (/(wholesale_dealer|support_general|contact_next_step|customer_profile_lookup|price_request|status_check)/.test(nluIntent)) {
  intent = nluIntent;
  replyType = nluIntent;
  useRag = false;
}

const responsePlan = {
  reply_type: replyType,
  intent,
  use_rag: useRag,
  response_mode: responseMode,
  fallback_reason: fallbackReason,
  needs_human: needsHuman,
  final_reply: finalReply,
  ask_one_question: replyType === 'repair_wrong_answer',
  grounded_by: useRag ? 'rag' : 'dialogue_manager',
};

return [{
  json: {
    ...input,
    isBotComplaint,
    nlu: {
      raw: nlu,
      intent,
      confidence: nluConfidence || 0,
    },
    dialogue: responsePlan,
    responsePlan,
  },
}];
`,
    };

    @node({
        id: '7fd2cdbe-b8e7-4da2-b2c2-229780d29a9f',
        name: 'Get CFC Knowledge Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1536, 304],
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
        position: [1312, 304],
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
    k: 'khong', ko: 'khong', kh: 'khong', hok: 'khong', hem: 'khong', hong: 'khong',
    dc: 'duoc', dk: 'duoc', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    sdt: 'so dien thoai', dt: 'dien thoai', npp: 'nha phan phoi',
  };
  return normalize(value).split(/\\s+/).filter(Boolean).map(token => aliases[token] || token).join(' ')
    .replace(/\\b(o|tai)\\s+dua\\b/g, '$1 dau')
    .replace(/\\bgiaohang\\b/g, 'giao hang');
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

const input = $('CFC Dialogue Manager').first().json;
const dialogue = input.dialogue || input.responsePlan || {};
const nlu = input.nlu || {};
const session = parseJson($('Get CFC Session').first().json.sessionRaw, {});
const profileInput = $('Merge CFC Customer Profile').first().json;
const customerProfile = parseJson(profileInput.customerProfileRaw || profileInput.customerProfile, {});
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
    risk_level: String(item.risk_level || 'low').trim().toLowerCase(),
  }))
  .filter(item => item.active && item.answer && item.intent && item.audience !== 'internal');

function findByIntent(...intents) {
  const wanted = new Set(intents.map(item => normalizeForSearch(item)));
  return knowledgeItems.find(item => wanted.has(normalizeForSearch(item.intent))) || null;
}

function findByKnowledgeTerms(...terms) {
  const normalizedTerms = terms.map(normalizeForSearch).filter(Boolean);
  return knowledgeItems.find(item => {
    const haystack = normalizeForSearch([item.intent, item.category, item.question_examples.join(' '), item.answer].join(' '));
    return normalizedTerms.every(term => haystack.includes(term));
  }) || null;
}

function answerModeFor(entry) {
  return entry?.answer_mode === 'rewrite' ? 'rewrite' : 'direct';
}

function canAnswerMedium(entry) {
  if (!entry) return false;
  return entry.risk_level === 'low' || ['product', 'shipping', 'faq', 'company', 'operations'].includes(entry.category);
}

const allowedBrands = new Set(['cfc', 'co bay', 'cfc/co bay', 'cfc co bay']);
const currentQuestion = normalizeForSearch(input.normalizedText || input.text);
const contextQuestion = input.isFollowUp && session.last_user_message
  ? normalizeForSearch(session.last_user_message + ' ' + input.text)
  : currentQuestion;
const sessionEntry = input.isFollowUp && session.last_source_id
  ? knowledgeItems.find(item => item.source_id === session.last_source_id && item.intent === session.last_intent)
  : null;
const shouldUseRag = dialogue.use_rag !== false;
const scored = shouldUseRag ? knowledgeItems
  .filter(entry => allowedBrands.has(normalize(entry.brand)))
  .map(entry => ({ ...entry, ...scoreEntry(currentQuestion, entry) }))
  .filter(entry => entry.score > 0)
  .sort((a, b) => b.score - a.score || b.priority - a.priority) : [];
let best = scored[0] || null;
const currentSecondScore = scored.find(item => !best || item.intent !== best.intent)?.score || 0;
const currentAmbiguous = !best?.exact && ((best?.score || 0) - currentSecondScore < 8);
if (shouldUseRag && sessionEntry && input.isFollowUp && !input.isSensitive && !input.isOutOfScope) {
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
const previousText = normalizeForSearch([session.last_user_message, session.last_bot_reply, session.last_intent, customerProfile.last_need, customerProfile.conversation_summary].filter(Boolean).join(' '));
const waitingForContact = ['so dien thoai', 'khu vuc', 'nhan vien', 'lien he', 'dai ly', 'phan phoi'].some(word => previousText.includes(word));
const normalizedInputText = normalizeForSearch(input.text);
const isAreaQuestion = /(^|\\s)(o dau|tai dau|cho nao|dia chi.*o dau|mua o dau|ban o dau)(\\s|$)/.test(normalizedInputText);
const looksLikeAreaReply = !isAreaQuestion && /(^|\\s)(minh o|em o|toi o|khach hang cu o|ben minh o|o tinh|o huyen|khu vuc)\\s+[a-z]/.test(input.normalizedText || '');
const profilePhone = String(customerProfile.phone || session.customer_phone || '').trim();
const profileArea = String(customerProfile.area || session.customer_location || '').trim();
const inputPhone = String(input.phoneNumber || '').trim();
function stripPhoneFromArea(value) {
  return String(value || '')
    .replace(/(?:\\+?84|0)[\\d\\s.\\-]{8,14}\\d/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}
const rawAreaFromContactMessage = stripPhoneFromArea(input.text);
const inputArea = (input.hasAreaInfo || (input.hasPhoneNumber && waitingForContact && rawAreaFromContactMessage))
  ? rawAreaFromContactMessage
  : '';
const knownPhone = inputPhone || profilePhone;
const knownArea = inputArea || profileArea;
const hasFullContact = Boolean(knownPhone && knownArea);
const isLeadInfo = Boolean(input.hasPhoneNumber || (input.hasAreaInfo && (waitingForContact || looksLikeAreaReply || input.isDealerLocationRequest || profilePhone)));
function contactFallbackReason() {
  if (knownPhone && knownArea) return 'lead_contact_ready';
  if (knownPhone) return 'lead_phone_received';
  if (knownArea) return 'lead_area_received';
  return 'lead_contact_received';
}
function contactReply(prefix) {
  if (knownPhone && knownArea) {
    return 'Dạ, Cò Bay đã có số điện thoại và khu vực của bạn. Admin hoặc nhân viên khu vực sẽ liên hệ hỗ trợ bạn sớm nhất nha.';
  }
  if (knownPhone) {
    return (prefix || 'Dạ, Cò Bay đã nhận được số điện thoại của bạn.') + ' Bạn gửi thêm khu vực/tỉnh thành để admin hoặc nhân viên khu vực hỗ trợ đúng nơi nha.';
  }
  if (knownArea) {
    return (prefix || 'Dạ Cò Bay đã nhận được khu vực của bạn.') + ' Bạn gửi thêm số điện thoại để admin hoặc nhân viên khu vực liên hệ hỗ trợ sớm nhất nha.';
  }
  return 'Dạ, bạn gửi giúp Cò Bay số điện thoại và khu vực cụ thể. Admin sẽ chuyển nhân viên hoặc nhà phân phối khu vực liên hệ hỗ trợ sớm nhất nha.';
}
function contactReadyReply(intent, prefix) {
  if (!hasFullContact) return contactReply(prefix);
  const needText = normalizeForSearch([input.text, intent, session.last_intent, customerProfile.last_need, session.last_user_message, session.last_bot_reply].filter(Boolean).join(' '));
  if (/(wholesale|dai ly|nha phan phoi|phan phoi|npp|lay si|nhap si|ban le|mua de ban|hop tac)/.test(needText)) {
    return 'Dạ, Cò Bay đã ghi nhận nhu cầu đại lý/nhà phân phối của bạn tại ' + knownArea + ' với số ' + knownPhone + '. Admin sẽ kiểm tra khu vực phụ trách và liên hệ tư vấn tiếp cho bạn nha.';
  }
  if (/(order_request|dat hang|chot don|xac nhan don|don hang)|(^|\\s)\\d+(?:[.,]\\d+)?\\s*(kg|ki|ky|kilo|tan|ta|bao|tui|goi|thung)(\\s|$)/.test(needText)) {
    const orderText = String(session.last_user_message || customerProfile.last_user_message || '').replace(/\\s+/g, ' ').trim();
    return 'Dạ, Cò Bay đã nhận được số ' + knownPhone + ' và khu vực ' + knownArea + ' cho nhu cầu bạn vừa gửi' + (orderText ? ': ' + orderText : '') + '. Admin sẽ kiểm tra đúng sản phẩm, quy cách, tồn hàng và liên hệ xác nhận nha.';
  }
  if (/(buy_online|mua|dat hang|mua hang|phan bon|npk|huu co|co bay|cfc)/.test(needText)) {
    return 'Dạ, Cò Bay đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + ' để hỗ trợ mua hàng. Admin hoặc nhân viên khu vực sẽ liên hệ tư vấn sản phẩm phù hợp cho bạn nha.';
  }
  if (/(support|ho tro|tu van|van de)/.test(needText)) {
    return 'Dạ, Cò Bay đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Bạn mô tả thêm vấn đề cần hỗ trợ để admin chuyển đúng nhân viên xử lý nha.';
  }
  return 'Dạ, Cò Bay đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Admin hoặc nhân viên khu vực sẽ liên hệ hỗ trợ bạn sớm nhất nha.';
}
function shouldEscalateReadyLead(intent) {
  if (!hasFullContact) return false;
  const text = normalizeForSearch(input.text);
  const wantsHuman = /(nhan vien|goi|lien he|tu van|admin|dai ly|nha phan phoi|phan phoi|nhap si|ban le|mua phan bon|mua hang)/.test(text);
  return wantsHuman || ['wholesale_dealer', 'support_general', 'buy_online'].includes(intent);
}
const asksSavedArea = /(^|\\s)(toi|minh|em|anh|chi|oi)\\s+(o|tai)\\s+dau(\\s|$)/.test(normalizedInputText)
  || /(con nho|nho).*(toi|minh|em|anh|chi).*(o dau|khu vuc|dia chi)/.test(normalizedInputText)
  || /(khu vuc|dia chi).*(toi|minh|em).*(la gi|o dau|da luu)/.test(normalizedInputText);
const asksSavedPhone = /(sdt|so dien thoai|dien thoai).*(cua )?(toi|minh|em|anh|chi)/.test(normalizedInputText)
  || /(cho|xin|gui).*(lai )?(sdt|so dien thoai|dien thoai)/.test(normalizedInputText)
  || /(con nho|nho).*(toi|minh|em|anh|chi).*(sdt|so dien thoai|dien thoai)/.test(normalizedInputText)
  || /(da luu|co luu).*(sdt|so dien thoai|dien thoai)/.test(normalizedInputText);
const isCompanyOverviewQuestion = /(gioi thieu|thong tin).*(cong ty|cfc|co bay)|((cong ty|cfc|co bay).*(la gi|lam gi|ve gi|gioi thieu))/.test(normalizedInputText);
const isCompanyAddressQuestion = /(dia chi|cong ty|cfc|co bay|nha may).*(o dau|tai dau|cho nao|tra noc)|((o dau|tai dau|cho nao).*(cong ty|cfc|co bay|nha may))/.test(normalizedInputText);
let forcedEntry = null;
if (!shouldUseRag) {
  forcedEntry = null;
} else if (isCompanyOverviewQuestion) {
  forcedEntry = findByIntent('company_overview')
    || findByKnowledgeTerms('gioi thieu', 'cong ty')
    || findByKnowledgeTerms('cfc', 'phan bon');
} else if (isCompanyAddressQuestion) {
  forcedEntry = findByIntent('address')
    || findByKnowledgeTerms('dia chi', 'cong ty')
    || findByKnowledgeTerms('tra noc');
}
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
} else if (input.isStatusCheck || dialogue.intent === 'status_check') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = session.last_intent || customerProfile.last_need || 'status_check';
  if (hasFullContact) {
    finalReply = 'Dạ, Cò Bay đã có số ' + knownPhone + ' và khu vực ' + knownArea + '. Admin hoặc nhân viên khu vực sẽ kiểm tra lại thông tin và liên hệ hỗ trợ bạn sớm nhất nha.';
  } else if (knownPhone || knownArea) {
    finalReply = contactReply('Dạ, mình đang kiểm tra lại thông tin trước đó cho bạn.');
  } else {
    finalReply = 'Dạ, bạn đang muốn hỏi tiếp về nội dung nào ạ? Nếu cần admin/nhân viên Cò Bay liên hệ, bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành nha.';
  }
} else if (asksSavedArea || asksSavedPhone) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'customer_profile_lookup';
  if (asksSavedArea && asksSavedPhone && knownArea && knownPhone) {
    finalReply = 'Dạ, Cò Bay đang lưu khu vực của bạn là: ' + knownArea + ', số điện thoại là: ' + knownPhone + '.';
  } else if (asksSavedArea && knownArea) {
    finalReply = 'Dạ, thông tin khu vực Cò Bay đang lưu của bạn là: ' + knownArea + '.';
  } else if (asksSavedPhone && knownPhone) {
    finalReply = 'Dạ, số điện thoại Cò Bay đang lưu của bạn là: ' + knownPhone + '.';
  } else {
    finalReply = 'Dạ, hiện Cò Bay chưa có đủ thông tin này trong hồ sơ chat. Bạn gửi lại giúp mình để Cò Bay lưu và hỗ trợ đúng hơn nha.';
  }
} else if (dialogue.intent === 'customer_profile_lookup') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'customer_profile_lookup';
  if (knownArea && knownPhone) {
    finalReply = 'Dạ, Cò Bay đang lưu khu vực của bạn là: ' + knownArea + ', số điện thoại là: ' + knownPhone + '.';
  } else if (knownArea || knownPhone) {
    finalReply = 'Dạ, Cò Bay đang lưu ' + (knownArea ? 'khu vực của bạn là: ' + knownArea : 'số điện thoại của bạn là: ' + knownPhone) + '. Bạn gửi thêm thông tin còn thiếu để Cò Bay hỗ trợ đúng hơn nha.';
  } else {
    finalReply = 'Dạ, hiện Cò Bay chưa có đủ thông tin này trong hồ sơ chat. Bạn gửi lại giúp mình để Cò Bay lưu và hỗ trợ đúng hơn nha.';
  }
} else if (dialogue.intent === 'contact_next_step') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'contact_next_step';
  finalReply = contactReadyReply(session.last_intent || customerProfile.last_need || '');
} else if ((dialogue.intent === 'contact_information_received' || isLeadInfo) && !input.isOrderQuantityRequest) {
  responseMode = 'review';
  fallbackReason = contactFallbackReason();
  matchedIntent = session.last_intent || customerProfile.last_need || dialogue.intent || '';
  finalReply = hasFullContact
    ? contactReadyReply(matchedIntent, 'Dạ, Cò Bay đã nhận được thông tin liên hệ bạn gửi.')
    : contactReply('Dạ, Cò Bay đã nhận được thông tin bạn gửi.');
} else if (dialogue.intent === 'wholesale_dealer') {
  responseMode = hasFullContact ? 'review' : 'direct';
  fallbackReason = hasFullContact ? 'lead_contact_ready' : '';
  matchedIntent = 'wholesale_dealer';
  matchedCategory = 'wholesale';
  if (hasFullContact) {
    finalReply = contactReadyReply(matchedIntent);
  } else if (!knownPhone && !knownArea) {
    finalReply = 'Dạ, Cò Bay đã ghi nhận nhu cầu đại lý/nhà phân phối của bạn. Bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành muốn kinh doanh để admin chuyển đúng nhân viên phụ trách nha.';
  } else {
    finalReply = contactReply('Dạ, Cò Bay đã ghi nhận nhu cầu đại lý/nhà phân phối của bạn.');
  }
} else if (input.isOrderQuantityRequest || dialogue.intent === 'order_request') {
  responseMode = 'review';
  matchedIntent = 'order_request';
  matchedCategory = 'sales';
  fallbackReason = hasFullContact ? 'order_contact_ready' : 'order_contact_missing';
  if (hasFullContact) {
    finalReply = 'Dạ, Cò Bay đã ghi nhận bạn muốn: ' + input.text + '. Cò Bay đang lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Admin sẽ kiểm tra đúng sản phẩm/quy cách, tồn hàng và liên hệ xác nhận cho bạn nha.';
  } else {
    finalReply = 'Dạ, Cò Bay đã ghi nhận bạn muốn: ' + input.text + '. Bạn gửi thêm số điện thoại và khu vực/tỉnh thành để admin kiểm tra đúng sản phẩm, quy cách và hỗ trợ chốt nhu cầu nha.';
  }
} else if (input.isPriceQuestion || dialogue.intent === 'price_request') {
  responseMode = 'review';
  fallbackReason = 'price_unverified';
  matchedIntent = 'price_request';
  matchedCategory = 'sales';
  if (hasFullContact) {
    finalReply = 'Dạ, hiện dữ liệu chat chưa có bảng giá chi tiết để mình báo chính xác. Cò Bay đã có số điện thoại và khu vực của bạn, admin sẽ kiểm tra giá sản phẩm phù hợp và liên hệ hỗ trợ nha.';
  } else {
    finalReply = 'Dạ, hiện dữ liệu chat chưa có bảng giá chi tiết để mình báo chính xác. Bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành, admin Cò Bay sẽ kiểm tra giá sản phẩm phù hợp và liên hệ hỗ trợ nha.';
  }
} else if (input.isBotComplaint || dialogue.intent === 'bot_answer_complaint') {
  responseMode = 'review';
  fallbackReason = 'bot_answer_complaint';
  matchedIntent = 'bot_answer_complaint';
  finalReply = dialogue.final_reply || 'Dạ xin lỗi bạn, câu trả lời trước chưa đúng ý. Bạn nhắn lại giúp mình câu hỏi chính về sản phẩm phân bón, mua hàng, giao hàng hoặc đại lý để mình kiểm tra kỹ hơn nhé.';
} else if (dialogue.intent === 'support_general') {
  matchedIntent = 'support_general';
  matchedCategory = 'support';
  if (hasFullContact && /(nhan vien|goi|lien he|admin|tu van)/.test(normalizedInputText)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else {
    responseMode = 'direct';
    fallbackReason = '';
    finalReply = 'Dạ mình sẵn sàng hỗ trợ ạ. Bạn đang cần tư vấn về sản phẩm phân bón, mua hàng, giao hàng hay đại lý Cò Bay nha?';
  }
} else if (input.isPromptInjection) {
  responseMode = 'review';
  fallbackReason = 'prompt_injection';
  finalReply = 'Dạ, mình chỉ có thể hỗ trợ thông tin sản phẩm và dịch vụ của Cò Bay. Bạn cho mình biết nội dung cần hỗ trợ nhé.';
} else if (input.hasForeignInputScript) {
  responseMode = 'direct';
  fallbackReason = 'unsupported_input_language';
  finalReply = 'Dạ, hiện Cò Bay hỗ trợ bằng tiếng Việt. Bạn gửi lại nội dung bằng tiếng Việt giúp mình nhé.';
} else if (input.isDealerLocationRequest) {
  responseMode = 'review';
  fallbackReason = hasFullContact ? 'lead_contact_ready' : 'dealer_location_request';
  finalReply = hasFullContact ? contactReadyReply('dealer_location_request') : contactReply();
} else if (input.isSensitive) {
  responseMode = 'review';
  fallbackReason = 'sensitive_case';
  finalReply = 'Dạ, Cò Bay đã ghi nhận phản ánh của bạn. Admin sẽ kiểm tra và phản hồi bạn sớm nhất nhé.';
} else if (input.isOutOfScope) {
  responseMode = 'review';
  fallbackReason = 'out_of_scope';
  finalReply = 'Dạ, mình đang hỗ trợ thông tin về phân bón và dịch vụ của Cò Bay. Bạn cho mình biết nhu cầu liên quan đến Cò Bay nhé.';
} else if (forcedEntry || isCompanyOverviewQuestion || isCompanyAddressQuestion) {
  fallbackReason = '';
  const fallbackIntent = isCompanyAddressQuestion ? 'address' : 'company_overview';
  const fallbackCategory = isCompanyAddressQuestion ? 'operations' : 'company';
  const fallbackAnswer = isCompanyAddressQuestion
    ? 'Dạ địa chỉ Công ty ở Trục chính KCN Trà Nóc 1, phường Thới An Đông, thành phố Cần Thơ ạ.'
    : 'Dạ, Cò Bay là thương hiệu phân bón của CFC, hiện cung cấp các dòng phân bón như NPK và phân hữu cơ. Công ty ở Trục chính KCN Trà Nóc 1, phường Thới An Đông, thành phố Cần Thơ ạ.';
  matchedIntent = forcedEntry?.intent || fallbackIntent;
  matchedSourceId = forcedEntry?.source_id || '';
  matchedCategory = forcedEntry?.category || fallbackCategory;
  canonicalAnswer = forcedEntry?.answer || '';
  finalReply = forcedEntry?.answer || fallbackAnswer;
  responseMode = forcedEntry ? answerModeFor(forcedEntry) : 'direct';
} else if (input.isProductDiscovery && productLineItem) {
  responseMode = answerModeFor(productLineItem);
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
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (['wholesale_dealer', 'support_general', 'buy_online'].includes(matchedIntent) && (knownPhone || knownArea)) {
    finalReply = contactReply('Dạ, Cò Bay đã nhận được một phần thông tin của bạn.');
  }
} else if (confidence === 'medium' && best) {
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  matchedCategory = best.category;
  if (canAnswerMedium(best)) {
    responseMode = answerModeFor(best);
    fallbackReason = '';
    canonicalAnswer = best.answer;
    finalReply = best.answer;
  } else {
    responseMode = 'direct';
    fallbackReason = 'clarification_needed';
    finalReply = 'Dạ, bạn đang muốn hỏi về ' + (best.question_examples[0] || best.intent.replace(/_/g, ' ')) + ' đúng không ạ?';
  }
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (['wholesale_dealer', 'support_general', 'buy_online'].includes(matchedIntent) && (knownPhone || knownArea)) {
    finalReply = contactReply('Dạ, Cò Bay đã nhận được một phần thông tin của bạn.');
  }
}

function compactText(value, maxLength) {
  const text = String(value || '').replace(/\\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return text.slice(text.length - maxLength).trim();
}

function buildConversationSummary(previous, intent, replyType, message, reply) {
  const parts = [];
  const prev = compactText(previous, 420);
  if (prev) parts.push(prev);
  const facts = [];
  if (knownPhone) facts.push('SĐT ' + knownPhone);
  if (knownArea) facts.push('khu vực ' + knownArea);
  if (intent) facts.push('intent ' + intent);
  if (replyType) facts.push('reply_type ' + replyType);
  const latest = 'Lượt gần nhất: khách nói "' + compactText(message, 120) + '"; bot trả "' + compactText(reply, 160) + '".';
  parts.push((facts.length ? '[' + facts.join(', ') + '] ' : '') + latest);
  return compactText(parts.join(' '), 700);
}

const replyType = dialogue.reply_type || (
  matchedIntent === 'order_request' ? 'confirm_order'
  : matchedIntent === 'bot_answer_complaint' ? 'repair_wrong_answer'
  : responseMode === 'review' ? 'handoff_admin'
  : responseMode === 'rewrite' ? 'compose_from_knowledge'
  : 'direct_answer'
);
const responsePlanState = {
  ...(dialogue || {}),
  reply_type: replyType,
  intent: matchedIntent || dialogue.intent || '',
  use_rag: shouldUseRag,
  response_mode: responseMode,
  fallback_reason: fallbackReason,
  matched_source_id: matchedSourceId,
  rag_score: bestScore,
  score_margin: scoreMargin,
};
const conversationSummary = buildConversationSummary(
  customerProfile.conversation_summary || session.conversation_summary || '',
  matchedIntent || dialogue.intent || '',
  replyType,
  input.text,
  finalReply
);
const memoryIntent = ['bot_answer_complaint', 'thanks', 'greeting', 'goodbye', 'acknowledgement'].includes(matchedIntent)
  ? (customerProfile.last_need || session.last_intent || '')
  : (matchedIntent || customerProfile.last_need || session.last_intent || '');
const routeIndex = responseMode === 'direct' ? 0 : responseMode === 'rewrite' ? 1 : responseMode === 'review' ? 2 : 3;
const previousHistory = Array.isArray(session.history) ? session.history : [];
const historyUserText = isLeadInfo ? '[Khách đã cung cấp thông tin liên hệ]' : input.text;
const history = shouldIgnore || !input.text
  ? previousHistory.slice(-8)
  : [...previousHistory,
      { role: 'user', text: historyUserText },
      { role: 'assistant', text: finalReply, intent: matchedIntent, source_id: matchedSourceId },
    ].slice(-8);
const pendingSlots = [];
if (!knownPhone) pendingSlots.push('phone');
if (!knownArea) pendingSlots.push('area');
const leadStage = hasFullContact
  ? (responseMode === 'review' ? 'qualified' : (customerProfile.lead_stage || 'qualified'))
  : ((knownPhone || knownArea) ? 'collecting_contact' : (customerProfile.lead_stage || 'new'));
const customerProfileState = {
  ...customerProfile,
  brand: 'CFC',
  channel: 'messenger',
  sender_id: input.senderId || customerProfile.sender_id || '',
  phone: knownPhone,
  area: knownArea,
  last_need: memoryIntent,
  last_intent: matchedIntent || customerProfile.last_intent || '',
  lead_stage: leadStage,
  pending_slots: pendingSlots,
  last_user_message: input.text,
  last_bot_reply: finalReply,
  last_reply_type: replyType,
  conversation_summary: conversationSummary,
  response_plan: responsePlanState,
  nlu,
  first_seen_at: customerProfile.first_seen_at || new Date().toISOString(),
  last_seen_at: new Date().toISOString(),
};
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
  customer_phone: knownPhone,
  customer_location: knownArea,
  pending_question: fallbackReason === 'clarification_needed' || responseMode === 'review' ? input.text : '',
  lead_stage: leadStage,
  pending_slots: pendingSlots,
  last_reply_type: replyType,
  use_rag: shouldUseRag,
  response_plan: responsePlanState,
  nlu,
  order_items: Array.isArray(nlu.raw?.order_items) ? nlu.raw.order_items : [],
  conversation_summary: conversationSummary,
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
    normalizedMessage: input.normalizedText || currentQuestion,
    replyType,
    useRag: shouldUseRag,
    responsePlan: responsePlanState,
    nlu,
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
    customerProfileState,
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
  .replace(/[^a-z0-9\\s]/g, ' ')
  .replace(/\\s+/g, ' ')
  .trim();
const styleWords = new Set('da ban minh ben shop hien tai co la va de duoc se som nhat nhe nha vui long cam on thong tin ho tro xin chao a voi cho neu can khi them giup'.split(' '));
const canonicalTokens = new Set(normalizeFacts(canonicalAnswer).split(' ').filter(token => token.length >= 3));
const unsupportedFacts = [...new Set(normalizeFacts(aiText).split(' ')
  .filter(token => token.length >= 3 && !canonicalTokens.has(token) && !styleWords.has(token)))];
const canonicalNumbers = canonicalAnswer.match(/\\d[\\d.,:/-]*/g) || [];
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
const previousReply = String(ragData.finalReply || '').trim();
const previousSummary = String(ragData.sessionState?.conversation_summary || ragData.customerProfileState?.conversation_summary || '');
const updatedSummary = previousReply
  ? previousSummary.replace(previousReply, finalReply).slice(-700)
  : previousSummary;
const sessionState = {
  ...(ragData.sessionState || {}),
  last_bot_reply: finalReply,
  conversation_summary: updatedSummary,
  updated_at: new Date().toISOString(),
};
const customerProfileState = {
  ...(ragData.customerProfileState || {}),
  last_bot_reply: finalReply,
  conversation_summary: updatedSummary,
  last_seen_at: new Date().toISOString(),
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
    customerProfileState,
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
        id: '73ae8e5d-2b9d-450d-9870-974d41452f3a',
        name: 'Save CFC Customer Profile',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1984, -96],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        onError: 'continueRegularOutput',
    })
    SaveCfcCustomerProfile = {
        operation: 'set',
        key: '={{ "cfc:customer:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify($json.customerProfileState || {}) }}',
        expire: false,
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
        id: 'f2000001-0000-0000-0000-000000000003',
        name: 'Queue CFC Learning Review',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1776, 464],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        onError: 'continueRegularOutput',
    })
    QueueCfcLearningReview = {
        operation: 'push',
        list: 'cfc:learning:queue',
        messageData:
            '={{ JSON.stringify({ status: "pending", brand: "CFC", channel: "messenger", sender_id: $json.senderId, message_id: $("Loc Dau Vao").first().json.messageId, user_message: $json.userMessage, normalized_message: $json.normalizedMessage || $json.normalizedQuery, fallback_reason: $json.fallbackReason, matched_intent: $json.matchedIntent, matched_source_id: $json.matchedSourceId, reply_type: $json.replyType, response_mode: $json.responseMode, use_rag: $json.useRag, rag_score: $json.ragScore, score_margin: $json.scoreMargin, nlu: $json.nlu, response_plan: $json.responsePlan, session_summary: $json.sessionState?.conversation_summary, customer_profile: { phone: $json.customerProfileState?.phone, area: $json.customerProfileState?.area, lead_stage: $json.customerProfileState?.lead_stage, last_need: $json.customerProfileState?.last_need }, bot_reply: $json.finalReply, created_at: $now.toISO() }) }}',
        tail: true,
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
        this.LocDauVao.out(0).to(this.GetCfcCustomerProfile.in(0));
        this.GetCfcCustomerProfile.out(0).to(this.MergeCfcCustomerProfile.in(0));
        this.MergeCfcCustomerProfile.out(0).to(this.GetCfcSession.in(0));
        this.GetCfcSession.out(0).to(this.GoiCfcOllamaNluLocal.in(0));
        this.GoiCfcOllamaNluLocal.out(0).to(this.CfcDialogueManager.in(0));
        this.GoiCfcOllamaNluLocal.error().to(this.CfcDialogueManager.in(0));
        this.CfcDialogueManager.out(0).to(this.GetCfcKnowledgeSnapshot.in(0));
        this.GetCfcKnowledgeSnapshot.out(0).to(this.CfcRagTimKiem.in(0));
        this.CfcRagTimKiem.out(0).to(this.RouterCoNguon.in(0));
        this.RouterCoNguon.out(0).to(this.SaveCfcCustomerProfile.in(0));
        this.RouterCoNguon.out(0).to(this.SaveCfcSession.in(0));
        this.RouterCoNguon.out(1).to(this.GoiOllamaLocal.in(0));
        this.RouterCoNguon.out(2).to(this.SaveCfcCustomerProfile.in(0));
        this.RouterCoNguon.out(2).to(this.SaveCfcSession.in(0));
        this.RouterCoNguon.out(2).to(this.QueueCfcLearningReview.in(0));
        this.GoiOllamaLocal.out(0).to(this.KiemChung.in(0));
        this.GoiOllamaLocal.error().to(this.KiemChung.in(0));
        this.KiemChung.out(0).to(this.RouterGuardrail.in(0));
        this.RouterGuardrail.out(0).to(this.SaveCfcCustomerProfile.in(0));
        this.RouterGuardrail.out(0).to(this.SaveCfcSession.in(0));
        this.RouterGuardrail.out(1).to(this.SaveCfcCustomerProfile.in(0));
        this.RouterGuardrail.out(1).to(this.SaveCfcSession.in(0));
        this.RouterGuardrail.out(1).to(this.QueueCfcLearningReview.in(0));
        this.SaveCfcSession.out(0).to(this.NhanKhachAuto.in(0));
        this.QueueCfcLearningReview.out(0).to(this.PrepareTelegramAlert.in(0));
        this.PrepareTelegramAlert.out(0).to(this.NotifyTelegramOperations.in(0));
    }
}
