import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Chatbot
// Nodes   : 23  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GoiFastApiChatPipeline             httpRequest                [onError→out(1)]
// PrepareMessengerReply              code
// GetCustomerProfile                 redis                      [onError→regular] [creds] [alwaysOutput]
// MergeCustomerProfile               code
// GetSession                         redis                      [onError→regular] [creds] [alwaysOutput]
// GoiOllamaNluLocal                  httpRequest                [onError→out(1)]
// DialogueManager                    code
// GetKnowledgeSnapshot               redis                      [onError→regular] [creds] [alwaysOutput]
// RagTimKiem                         code
// RouterCoNguon                      switch
// GoiOllamaLocal                     httpRequest                [onError→out(1)]
// KiemChung                          code
// RouterGuardrail                    if
// SaveCustomerProfile                redis                      [onError→regular] [creds]
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
//      → GoiFastApiChatPipeline
//        → PrepareMessengerReply
//          → NhanKhachAuto
//        → PrepareMessengerReply (↩ loop)
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
    dc: 'duoc', dk: 'duoc', giac: 'giat', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    li: 'ly',
    sdt: 'so dien thoai', dt: 'dien thoai', gia: 'gia ban', gif: 'gi', j: 'gi', z: 'vay',
    web: 'website', wed: 'website', wep: 'website', cod: 'cod',
  };
  return normalize(str)
    .replace(/[^a-z0-9\\s]/g, ' ')
    .split(/\\s+/)
    .filter(Boolean)
    .map(token => aliases[token] || token)
    .join(' ')
    .replace(/\\b(o|tai)\\s+dua\\b/g, '$1 dau')
    .replace(/\\bda\\s+(sao|bao nhieu|bn|nhiu)\\b/g, 'gia $1')
    .replace(/\\bbao\\s+da\\b/g, 'bao gia')
    .replace(/\\s+/g, ' ')
    .trim();
}

const sensitiveWords = ['hoan tien', 'doi tra', 'khieu nai', 'lua dao', 'san pham loi', 'hang gia'];
const outOfScopeWords = ['phan bon', 'co bay', 'npk', 'phan huu co'];
const vagueProductWords = ['buon', 'do buon', 'cho vui', 'mua gi', 'ban gi', 'co gi hay', 'goi y san pham', 'tu van san pham', 'khong biet mua gi'];
const unsupportedProductWords = ['may do oxy', 'do oxy', 'zeo mini', 'thiet bi y te', 'cham soc ca nhan', 'san pham suc khoe', 'phu kien suc khoe', 'nuoc xa vai', 'xa vai', 'fabric softener'];
const lower = normalizeForSearch(text);
const tokenCount = lower ? lower.split(' ').length : 0;
// FIX: Regex chuẩn sdt VN 10 số (đầu số 03x/05x/07x/08x/09x hoặc +84). Dùng word-boundary  để không nuốt số nhà.
const phoneMatch = text.match(/(?:\\+84|84|0)(?:3[2-9]|5[2689]|7[06789]|8[0-9]|9[0-9])[0-9]{7}\\b/);
const hasPhoneNumber = Boolean(phoneMatch);
const lowerTokens = lower.split(' ').filter(Boolean);
const areaPhraseWords = ['thanh pho', 'thi xa', 'khu vuc', 'can tho', 'binh duong', 'ho chi minh', 'thu duc', 'kien giang', 'rach gia', 'long an', 'dong nai', 'vung tau', 'da nang', 'ha noi', 'hai phong'];
const areaSingleWords = new Set(['tinh', 'tp', 'huyen', 'quan', 'q', 'xa', 'phuong', 'mien', 'tphcm']);
const isAreaQuestion = /(^|\\s)(o dau|tai dau|cho nao|dia chi.*o dau|mua o dau|ban o dau)(\\s|$)/.test(lower);
const hasAreaKeyword = areaPhraseWords.some(word => lower.includes(word))
  || lowerTokens.some(token => areaSingleWords.has(token));
// FIX: Nới lỏng: nếu có sdt và phần chữ còn lại (sau tách sdt) đủ dài → coi là có khu vực
const textWithoutPhone = phoneMatch ? text.replace(phoneMatch[0], '').trim() : '';
const hasAreaInfo = !isAreaQuestion && (
  hasAreaKeyword ||
  /(^|\\s)(minh o|em o|toi o|anh o|chi o|ben minh o|o tinh|o huyen|o quan|khu vuc)\\s+[a-z0-9]/.test(lower) ||
  (Boolean(phoneMatch) && textWithoutPhone.replace(/[/\\-.,\\s0-9]/g, '').length >= 4)
);
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
const isFollowUp = tokenCount <= 7 && /^(con |vay |the |loai do|san pham do|cai do|cai nay|no |dung sao|co thom|gia sao|it vay|it the|chi vay)/.test(lower);
const isBotComplaint = /(do ngu|ngu ngu|sao ngu|bot ngu|may ngu|m ngu|cang dot|may dot|m dot|vl|vcl|vai lon|tra loi gi ky|tra loi ky|tra loi xam|xam xam|khong hieu|noi gi vay|sao tra loi|tra loi gi v|tra loi gi vay|toi chui|chui ban|lien quan gi|khong lien quan|cach dong|xuong dong|hoi mot dang tra loi mot neo|tra loi chan|chan ghe|hai ghe|hai vl|chua on|khong on|session.*chua on|khong co session|mat ngu canh|context sai|khong nho ngu canh)/.test(lower);
const isCatalogQuestion = /(san pham gi|san pham nao|co san pham|co nhung gi|ban nhung gi|ban gi|co gi ban|danh muc san pham|cac san pham|dong san pham|co dong nao|co nhom nao|mat hang gi|mat hang nao|hang gi)/.test(lower);
const isWebsiteQuestion = /(website|web site|trang web|link web|link website|link cong ty|duong dan|xin link|gui.*link|zeo vn|zeo\\.vn)/.test(lower);
const isShortCodQuestion = /(^|\\s)cod($|\\s)/.test(lower) || /(thanh toan khi nhan|giao hang thu tien|nhan hang tra tien|thu tien mat|tra tien mat)/.test(lower);
const isShortDetergentQuestion = /(bot giat|nuoc giat|giat do|giat quan ao)/.test(lower);
const isFabricSoftenerQuestion = /(nuoc xa vai|xa vai|fabric softener)/.test(lower);
const hasOrderQuantity = /(^|\\s)\\d+(?:[.,]\\d+)?\\s*(kg|ki|ky|kilo|kilogram|lit|l|ml|chai|can|bich|bich|tui|goi|thung|hop)(\\s|$)/.test(lower);
const hasOrderProduct = /(nuoc giat|bot giat|thuoc tay|nuoc tay|javen|javel|tay javen|tay toilet|nuoc rua chen|rua chen|nuoc lau san|lau san|lau kinh|xit tay|tay da nang|pano|oplus|zeo)/.test(lower);
const isOrderQuantityRequest = hasOrderQuantity && hasOrderProduct;
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
  isFabricSoftenerQuestion,
	  isOrderQuantityRequest,
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
  phoneNumber: phoneMatch ? phoneMatch[0].trim() : '',
  hasAreaInfo,
} }];
`,
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000003',
        name: 'Goi Fast API Chat Pipeline',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [448, 160],
        onError: 'continueErrorOutput',
    })
    GoiFastApiChatPipeline = {
        method: 'POST',
        url: 'http://127.0.0.1:8000/api/chat-pipeline',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { brand: "zeo", sender_id: $json.senderId, text: $json.text, fb_name: $json.fb_name || "", message_id: $json.messageId || "" } }}',
        options: {
            timeout: 8000,
        },
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000004',
        name: 'Prepare Messenger Reply',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [680, 160],
    })
    PrepareMessengerReply = {
        jsCode: `
const input = $('Loc Dau Vao').first().json;
let pipelineRes = {};
try {
  pipelineRes = $input.first().json || {};
} catch (e) {
  pipelineRes = {};
}
const finalReply = pipelineRes.answer || "Dạ ZeO Vietnam đã nhận được tin nhắn của bạn. Bạn để lại nhu cầu cụ thể hoặc số điện thoại, admin sẽ hỗ trợ giải đáp ngay cho mình nha!";

return [{
  json: {
    senderId: input.senderId,
    finalReply: finalReply,
    intent: pipelineRes.intent || 'fastapi_degraded_fallback',
    confidence: pipelineRes.confidence || 'medium',
    score: pipelineRes.score || 0,
    hasPhone: pipelineRes.has_phone || false,
    latencyMs: pipelineRes.latency_ms || 0,
  }
}];
`,
    };

    @node({
        id: '8b86d1f4-1ac9-44cf-9db9-2f42fb237c71',
        name: 'Get Customer Profile',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [448, 380],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        onError: 'continueRegularOutput',
        alwaysOutputData: true,
    })
    GetCustomerProfile = {
        operation: 'get',
        propertyName: 'customerProfileRaw',
        key: '={{ "zeo:customer:messenger:" + $json.senderId }}',
        keyType: 'string',
        options: {},
    };

    @node({
        id: 'be606f18-31ac-44f5-a9c5-c2c095cb5795',
        name: 'Merge Customer Profile',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [240, 624],
    })
    MergeCustomerProfile = {
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
  brand: 'ZeO',
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
        id: 'f1000001-0000-0000-0000-000000000002',
        name: 'Get Session',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [448, 640],
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
        id: 'f1000001-0000-0000-0000-000000000010',
        name: 'Goi Ollama NLU Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [672, 416],
        onError: 'continueErrorOutput',
    })
    GoiOllamaNluLocal = {
        method: 'POST',
        url: 'http://127.0.0.1:11434/api/chat',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { model: "qwen2.5:7b-instruct", stream: false, think: false, keep_alive: "20m", options: { temperature: 0, top_p: 0.1, num_predict: 220 }, messages: [ { role: "system", content: "Bạn là bộ phân loại NLU cho CSKH ZeO. Chỉ trả về JSON hợp lệ, không markdown. Không trả lời khách. Schema: {intent,speech_act,sentiment,topic,entities,order_items,memory_updates,needs_human,confidence,use_rag}. intent ưu tiên một trong: bot_answer_complaint,greeting,thanks,goodbye,acknowledgement,order_request,wholesale_inquiry,general_support_request,product_consultation_request,customer_profile_lookup,contact_next_step,price_request,distributor_availability,product_faq,policy_faq,company_faq,unknown. Nếu khách chửi bot, nói bot trả sai, nói không liên quan, chán vì câu trước, chọn bot_answer_complaint và use_rag=false. Nếu là câu hỏi sản phẩm/chính sách/công ty thì use_rag=true. Không bịa dữ kiện." }, { role: "user", content: JSON.stringify({ message: $("Loc Dau Vao").first().json.text, normalized_message: $("Loc Dau Vao").first().json.normalizedText, flags: $("Loc Dau Vao").first().json, customer_profile: $("Merge Customer Profile").first().json.customerProfile, session_raw: $("Get Session").first().json.sessionRaw || "{}" }) } ] } }}',
        options: {},
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000011',
        name: 'Dialogue Manager',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [896, 416],
    })
    DialogueManager = {
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
const session = parseJson($('Get Session').first().json.sessionRaw, {});
const profileInput = $('Merge Customer Profile').first().json;
const customerProfile = parseJson(profileInput.customerProfileRaw || profileInput.customerProfile, {});
const nluPayload = $input.first().json || {};
const nlu = parseNlu(nluPayload);
const lower = normalize(input.text);
const previousText = normalize([session.last_user_message, session.last_bot_reply, customerProfile.last_need, customerProfile.conversation_summary].filter(Boolean).join(' '));

const explicitBotComplaint = /(do ngu|ngu ngu|sao ngu|bot ngu|may ngu|m ngu|cang dot|may dot|m dot|vl|vcl|vai lon|tra loi gi ky|tra loi ky|tra loi xam|xam xam|khong hieu|noi gi vay|sao tra loi|tra loi gi v|tra loi gi vay|toi chui|chui ban|lien quan gi|khong lien quan|hoi mot dang tra loi mot neo|tra loi chan|chan ghe|hai ghe|hai vl|chua on|khong on|session.*chua on|khong co session|mat ngu canh|context sai|khong nho ngu canh)/.test(lower);
const shortFrustrationAfterBot = /^(chan|chan ghe|met ghe|haiz|hai|that vong|bo tay|nan ghe)$/.test(lower) && Boolean(session.last_bot_reply);
const nluIntent = String(nlu.intent || '').trim();
const nluConfidence = Number(nlu.confidence || 0);
const nluComplaint = nluIntent === 'bot_answer_complaint' && nluConfidence >= 0.55;
const isBotComplaint = Boolean(input.isBotComplaint || explicitBotComplaint || shortFrustrationAfterBot || nluComplaint);
const businessLower = lower
  .replace(/\\bgiac\\b/g, 'giat')
  .replace(/\\bda\\s+(sao|bao nhieu|bn|nhiu)\\b/g, 'gia $1')
  .replace(/\\bbao\\s+da\\b/g, 'bao gia');
const hasWholesaleSignal = /(mua si|lay si|nhap si|gia si|si gia|ban si|mua.*\\bsi\\b|dai ly|phan phoi)/.test(businessLower);
const hasPriceSignal = /(gia sao|xin gia|bao gia|bang gia|bao nhieu tien|nhieu tien|price)/.test(businessLower);
const hasBusinessProduct = /(nuoc giat|bot giat|giat do|pano|zeo|oplus|thuoc tay|nuoc tay|javen|javel|tay toilet|nuoc rua chen|rua chen|nuoc lau san|lau san|lau kinh|xit tay|tay da nang)/.test(businessLower);
const dealerRegistrationSignal = /(muon|can|xin|dang ky|lam|tro thanh|mo|hop tac).*(dai ly|nha phan phoi)|(?:dai ly|nha phan phoi).*(duoc khong|sao|the nao|dang ky|lam)/.test(businessLower);
const contactInfoSignal = Boolean(input.hasPhoneNumber || input.hasAreaInfo);
const previousNeedsContact = /(so dien thoai|sdt|khu vuc|tinh thanh|dia chi|admin|chot don|xac nhan don|dai ly|lay si|nhap si)/.test(previousText);

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
  finalReply = 'Dạ xin lỗi bạn, câu trả lời vừa rồi chưa đúng ý. Bạn muốn mình hỗ trợ lại về mua hàng, sản phẩm, đơn hàng hay đăng ký đại lý ạ?';
} else if (input.isThanks) {
  intent = 'thanks';
  replyType = 'acknowledge';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ, ZeO cảm ơn bạn ạ. Khi cần thêm thông tin, bạn cứ nhắn mình nhé.';
} else if (input.isGreeting) {
  intent = 'greeting';
  replyType = 'greeting';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ ZeO chào bạn ạ. Bạn cần mình hỗ trợ thông tin sản phẩm, mua hàng, giao hàng hay chính sách nào ạ?';
} else if (input.isAcknowledgement) {
  intent = session.last_intent || 'acknowledgement';
  replyType = 'acknowledge';
  useRag = false;
  responseMode = 'direct';
  finalReply = 'Dạ vâng ạ. Khi cần hỗ trợ thêm, bạn cứ nhắn ZeO nhé.';
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
} else if (dealerRegistrationSignal) {
  intent = 'wholesale_inquiry';
  replyType = 'wholesale_inquiry';
  useRag = false;
  responseMode = 'review';
  fallbackReason = 'wholesale_contact_needed';
  needsHuman = true;
} else if ((hasWholesaleSignal || hasPriceSignal) && hasBusinessProduct) {
  intent = hasPriceSignal ? 'price_request' : 'wholesale_inquiry';
  replyType = hasPriceSignal ? 'price_request' : 'wholesale_inquiry';
  useRag = false;
  responseMode = 'review';
  fallbackReason = hasPriceSignal ? 'price_unverified' : 'wholesale_contact_needed';
  needsHuman = true;
} else if (/(wholesale_inquiry|price_request|distributor_availability|contact_next_step|customer_profile_lookup)/.test(nluIntent)) {
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
      intent,
      speech_act: nlu.speech_act || (isBotComplaint ? 'complaint' : ''),
      sentiment: nlu.sentiment || (isBotComplaint ? 'frustrated' : ''),
      topic: nlu.topic || '',
      entities: nlu.entities || {},
      order_items: Array.isArray(nlu.order_items) ? nlu.order_items : [],
      memory_updates: nlu.memory_updates || {},
      needs_human: needsHuman,
      confidence: nluConfidence || (isBotComplaint ? 0.95 : 0),
      raw: nlu,
      nlu_error: Boolean(nluPayload.error),
    },
    dialogue: responsePlan,
    responsePlan,
    customerProfile,
    previousText,
  },
}];
`,
    };

    @node({
        id: '126f8f96-9c0f-4f45-b397-71ddf19a80bb',
        name: 'Get Knowledge Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [672, 656],
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
        position: [1264, 288],
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
    dc: 'duoc', dk: 'duoc', giac: 'giat', sp: 'san pham', ib: 'nhan tin', nt: 'nhan tin',
    bn: 'ban', mn: 'minh', ship: 'giao hang', cty: 'cong ty',
    li: 'ly',
    sdt: 'so dien thoai', dt: 'dien thoai', gia: 'gia ban', gif: 'gi', j: 'gi', z: 'vay',
    web: 'website', wed: 'website', wep: 'website', cod: 'cod',
  };
  return normalize(value).split(/\\s+/).filter(Boolean).map(token => aliases[token] || token).join(' ')
    .replace(/\\b(o|tai)\\s+dua\\b/g, '$1 dau')
    .replace(/\\bda\\s+(sao|bao nhieu|bn|nhiu)\\b/g, 'gia $1')
    .replace(/\\bbao\\s+da\\b/g, 'bao gia');
}

const STOP_WORDS = new Set([
  'a', 'ad', 'admin', 'anh', 'ban', 'ben', 'bi', 'chi', 'cho', 'co', 'cua', 'da', 'dau',
  'do', 'duoc', 'em', 'gi', 'haha', 'hihi', 'khong', 'la', 'lai', 'minh', 'mot', 'nao',
  'nha', 'nhe', 'ngu', 'oi', 'roi', 'shop', 'thi', 'toi', 'tren', 'va', 'vay', 've',
  'vl', 'vcl', 'voi',
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

function answerModeFor(entry) {
  return entry?.answer_mode === 'rewrite' ? 'rewrite' : 'direct';
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
    ? 'Dạ ZeO hiện có các nhóm sản phẩm như ' + groups.join(', ') + '. Bạn đang quan tâm nhóm nào để mình gửi thông tin cụ thể hơn ạ?'
    : 'Dạ ZeO có các sản phẩm tẩy rửa gia dụng. Bạn cần bột giặt, nước rửa chén, nước lau sàn hay sản phẩm vệ sinh nhà cửa ạ?';
}

function buildDetailedCatalogReply() {
  return [
    'Dạ ZeO có thể hỗ trợ các nhóm sản phẩm chính như:',
    '1. Giặt giũ: bột giặt/nước giặt ZeO, PANO và Oplus.',
    '2. Rửa chén: ZeO/ZIF, PANO Chanh, PANO Vitamin E và Oplus.',
    '3. Lau sàn: nước lau sàn ZeO/Oplus với các hương như Y Lan, Bạc Hà, Sả Chanh, Hoa Hạ và Baby.',
    '4. Tẩy rửa vệ sinh: Javen ZeO, tẩy toilet ZeO, tẩy màu ZeO, lau kính ZeO và xịt tẩy đa năng PANO.',
    'Bạn muốn xem chi tiết nhóm nào trước ạ?'
  ].join('\\n');
}

const input = $('Dialogue Manager').first().json;
const dialogue = input.dialogue || input.responsePlan || {};
const nlu = input.nlu || {};
const session = parseJson($('Get Session').first().json.sessionRaw, {});
const profileInput = $('Merge Customer Profile').first().json;
const customerProfile = parseJson(profileInput.customerProfileRaw || profileInput.customerProfile, {});
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
const previousText = normalizeForSearch([session.last_user_message, session.last_bot_reply, customerProfile.last_need, customerProfile.conversation_summary].filter(Boolean).join(' '));
const waitingForContact = ['so dien thoai', 'khu vuc', 'nhan vien', 'lien he', 'dai ly', 'phan phoi']
  .some(phrase => previousText.includes(phrase));
const normalizedInputText = normalizeForSearch(input.text);
const isAreaQuestion = /(^|\\s)(o dau|tai dau|cho nao|dia chi.*o dau|mua o dau|ban o dau)(\\s|$)/.test(normalizedInputText);
const looksLikeAreaReply = !isAreaQuestion && /^(toi|minh|em|anh|chi)?\\s*(o|tai)\\s+/.test(normalizedInputText);
const profilePhone = String(customerProfile.phone || session.customer_phone || '').trim();
const profileArea = String(customerProfile.area || session.customer_location || '').trim();
const inputPhone = String(input.phoneNumber || '').trim();
function stripPhoneFromArea(value) {
  // FIX: dùng regex chuẩn 10 số để không cắt mất số nhà/địa chỉ
  return String(value || '')
    .replace(/(?:\\+84|84|0)(?:3[2-9]|5[2689]|7[06789]|8[0-9]|9[0-9])[0-9]{7}\\b/g, '')
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
const isLeadInfo = Boolean(input.hasPhoneNumber || (input.hasAreaInfo && (waitingForContact || looksLikeAreaReply || profilePhone)));
function contactFallbackReason() {
  if (knownPhone && knownArea) return 'lead_contact_ready';
  if (knownPhone) return 'lead_phone_received';
  if (knownArea) return 'lead_area_received';
  return 'contact_information_received';
}
function contactReply(prefix) {
  if (knownPhone && knownArea) {
    return 'Dạ, ZeO đã lưu số điện thoại ' + knownPhone + ' và khu vực ' + knownArea + '. Bạn cho mình biết thêm nhu cầu cụ thể để ZeO hỗ trợ đúng hơn nha.';
  }
  if (knownPhone) {
    return (prefix || 'Dạ, ZeO đã nhận được số điện thoại của bạn.') + ' Bạn gửi thêm khu vực/tỉnh thành để admin hỗ trợ đúng khu vực nha.';
  }
  if (knownArea) {
    return (prefix || 'Dạ, ZeO đã nhận được khu vực của bạn.') + ' Bạn gửi thêm số điện thoại để admin liên hệ hỗ trợ sớm nhất nha.';
  }
  return 'Dạ, bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành để ZeO chuyển admin hoặc nhân viên phụ trách hỗ trợ nha.';
}
function contactReadyReply(intent, prefix) {
  if (!hasFullContact) return contactReply(prefix);
  const needText = normalizeForSearch([input.text, intent, session.last_intent, customerProfile.last_need, session.last_user_message, session.last_bot_reply].filter(Boolean).join(' '));
  if (/(wholesale|dai ly|phan phoi|lay si|nhap si|hop tac)/.test(needText)) {
    return 'Dạ, ZeO đã ghi nhận nhu cầu đại lý/lấy sỉ của bạn tại ' + knownArea + ' với số ' + knownPhone + '. Admin sẽ kiểm tra khu vực phụ trách, điều kiện hợp tác và liên hệ tư vấn tiếp. Bạn có thể nhắn thêm dòng sản phẩm hoặc số lượng dự kiến để admin chuẩn bị kỹ hơn nha.';
  }
  if (/(order_request|dat hang|chot don|xac nhan don|don hang)|(^|\\s)\\d+(?:[.,]\\d+)?\\s*(kg|ki|ky|kilo|lit|l|ml|chai|can|bich|tui|goi|thung|hop)(\\s|$)/.test(needText)) {
    const orderText = String(session.last_user_message || customerProfile.last_user_message || '').replace(/\\s+/g, ' ').trim();
    return 'Dạ, ZeO đã nhận được số ' + knownPhone + ' và khu vực ' + knownArea + ' cho đơn bạn vừa đặt' + (orderText ? ': ' + orderText : '') + '. Admin sẽ kiểm tra đúng sản phẩm, quy cách, tồn hàng và giá rồi liên hệ xác nhận đơn nha.';
  }
  if (/(online_purchase|mua|dat hang|link shopee|shopee|tiktok shop|pano|zeo|oplus)/.test(needText)) {
    return 'Dạ, ZeO đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + ' để hỗ trợ mua hàng. Bước tiếp theo là admin kiểm tra sản phẩm/link chính thức hoặc nhân viên phù hợp khu vực rồi liên hệ lại. Bạn nhắn giúp mình dòng sản phẩm muốn mua, ví dụ PANO, ZeO hay Oplus nha.';
  }
  if (/(distributor|nha phan phoi|dai ly|khu vuc)/.test(needText)) {
    return 'Dạ, ZeO đã có số ' + knownPhone + ' và khu vực ' + knownArea + '. Admin sẽ kiểm tra nhà phân phối/nhân viên phụ trách đúng khu vực rồi phản hồi bạn, tránh báo nhầm thông tin nha.';
  }
  if (/(support|ho tro|tu van|van de|don hang)/.test(needText)) {
    return 'Dạ, ZeO đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Bạn mô tả thêm vấn đề cần hỗ trợ, ví dụ sản phẩm, đơn hàng, giao hàng hay đổi trả, để mình chuyển đúng nội dung cho admin xử lý nha.';
  }
  return 'Dạ, ZeO đã lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Bước tiếp theo là bạn nhắn rõ nhu cầu cần hỗ trợ; nếu cần người xử lý, admin sẽ dựa vào thông tin này để liên hệ đúng khu vực nha.';
}
function shouldEscalateReadyLead(intent) {
  if (!hasFullContact) return false;
  const text = normalizeForSearch(input.text);
  const wantsHuman = /(nhan vien|goi lai|lien he|admin|lay si|nhap si|hop tac|dang ky dai ly|lam dai ly)/.test(text);
  return wantsHuman || ['wholesale_inquiry'].includes(intent) && /(lay si|nhap si|hop tac|dang ky|lam dai ly)/.test(text);
}
const asksSavedArea = /(^|\\s)(toi|minh|em|anh|chi|oi)\\s+(o|tai)\\s+dau(\\s|$)/.test(normalizedInputText)
  || /(con nho|nho).*(toi|minh|em|anh|chi).*(o dau|khu vuc|dia chi)/.test(normalizedInputText)
  || /(khu vuc|dia chi).*(toi|minh|em).*(la gi|o dau|da luu)/.test(normalizedInputText);
const asksSavedPhone = /(sdt|so dien thoai|dien thoai).*(cua )?(toi|minh|em|anh|chi)/.test(normalizedInputText)
  || /(cho|xin|gui).*(lai )?(sdt|so dien thoai|dien thoai)/.test(normalizedInputText)
  || /(con nho|nho).*(toi|minh|em|anh|chi).*(sdt|so dien thoai|dien thoai)/.test(normalizedInputText)
  || /(da luu|co luu).*(sdt|so dien thoai|dien thoai)/.test(normalizedInputText)
  || /(cho|xin|gui).*(lai )?so(\\s|$)/.test(normalizedInputText)
  || /(hoi|can|muon).*(lai )?so(\\s|$)/.test(normalizedInputText);
const asksProfileRecall = /(^|\\s)(con|on)?\\s*nho\\s+(toi|minh|em|anh|chi)(\\s|$)/.test(normalizedInputText)
  || /(con nho|nho).*(khach cu|thong tin|ho so)/.test(normalizedInputText);
const selectedHotlineBranch02 = /^(2|02)$/.test(normalizedInputText)
  && /(1900\\s*5307|hotline|phim nhanh|nhanh so)/.test(previousText)
  && /(^|\\s)0?2(\\s|$)/.test(previousText);
const isPurchaseIntent = /(mua|dat hang|dat mua|link mua|link shopee|shopee|tiki|lazada|tiktok shop|san thuong mai|cua hang|gio hang)/.test(normalizedInputText);
const isPriceQuestion = /(^|\\s)(gia|bang gia|bao gia|xin gia|bao nhieu tien|nhieu tien|price)(\\s|$)/.test(normalizedInputText);
const isUnderwhelmedCatalogFollowUp = /^(it vay|it the|it vay thoi|chi vay|chi co vay|co vay thoi)(\\s|$)/.test(normalizedInputText);
const isDistributorAvailabilityQuestion = /(nha phan phoi|dai ly).*(chua|co khong|o dau|gan|khu vuc)|(^|\\s)[a-z0-9 ]+\\s+co\\s+(nha phan phoi|dai ly)\\s+chua/.test(normalizedInputText);
const isDetailedCatalogQuestion = /(chi tiet|cu the|ke ro|danh sach|liet ke).*(san pham|mat hang|nhom)|san pham.*(chi tiet|cu the|gom nhung gi|co nhung dong)/.test(normalizedInputText);
const isBroadCleaningProductQuestion = /^(nuoc )?tay rua$/.test(normalizedInputText)
  || /^(san pham |nhom )?tay rua$/.test(normalizedInputText)
  || ((/(\\bnuoc tay rua\\b|\\bsan pham tay rua\\b|\\bnhom tay rua\\b)/.test(normalizedInputText))
    && !/(javen|javel|toilet|bon cau|mau|kinh|da nang|rua chen|lau san)/.test(normalizedInputText));
const isLaundryGroupQuestion = /(giat giu|nhom giat|do giat|giat quan ao|nuoc giat|bot giat).*(san pham|co nhung gi|gom nhung gi|loai nao|nhung loai nao|mat hang|co khong|co ko|co k)/
  .test(normalizedInputText)
  || /(san pham|mat hang|nhom).*(giat giu|giat quan ao|nuoc giat|bot giat)/.test(normalizedInputText);
const distributorAreaMatch = input.text.match(/^\\s*(.+?)\\s+(có|co)\\s+(nhà phân phối|nha phan phoi|đại lý|dai ly)/i)
  || input.text.match(/(nhà phân phối|nha phan phoi|đại lý|dai ly).*(ở|o|tại|tai)\\s+(.+)/i);
const requestedDistributorArea = distributorAreaMatch
  ? String(distributorAreaMatch[1] || distributorAreaMatch[3] || '').replace(/[?.!,]+$/g, '').trim()
  : '';
const asksContactNextStep = /(co|da co|co roi).*(so dien thoai|sdt|khu vuc).*(lam gi|de lam gi|thi sao|roi sao|sao nua)/
  .test(normalizedInputText)
  || /(so dien thoai|sdt|khu vuc).*(lam gi|de lam gi|thi sao|roi sao|sao nua)/.test(normalizedInputText);
const asksProductType = /(la san pham gi|san pham gi kia|la loai gi|thuoc dong gi|dong san pham gi|loai san pham gi|mat hang gi)/.test(normalizedInputText);
const panoContext = /\\bpano\\b/.test(normalizedInputText)
  || /\\bpano\\b/.test(previousText)
  || /pano/.test(String(session.last_intent || customerProfile.last_intent || customerProfile.last_need || ''));
const asksPanoProductType = panoContext && (asksProductType || /\\bpano\\b.*(la gi|san pham gi|loai gi)/.test(normalizedInputText));
const websiteOnlyQuestion = input.isWebsiteQuestion && !/(hotline|so dien thoai|dia chi|o dau|lien he|mua hang|shopee|tiktok|tiki)/.test(normalizedInputText);
const resolvedQuestion = input.isFollowUp && session.last_user_message
  ? normalizeForSearch(session.last_user_message + ' ' + input.text)
  : normalizeForSearch(input.normalizedText || input.text);
const sessionEntry = input.isFollowUp && session.last_source_id
  ? knowledgeItems.find(item => item.source_id === session.last_source_id && item.intent === session.last_intent)
  : null;
const shouldUseRag = dialogue.use_rag !== false;
const scored = shouldUseRag ? knowledgeItems
  .map(entry => ({ ...entry, ...scoreEntry(resolvedQuestion, entry) }))
  .filter(entry => entry.score > 0)
  .sort((a, b) => b.score - a.score || b.priority - a.priority) : [];
let best = scored[0] || null;
if (shouldUseRag && sessionEntry && input.isFollowUp && !input.isSensitive && !input.isOutOfScope) {
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
if (!shouldUseRag) {
  forcedEntry = null;
} else if (input.isShortCodQuestion) {
  forcedEntry = findByIntent('nationwide_shipping_no_cod', 'cod_payment')
    || findByIntentIncludes('cod')
    || findByKnowledgeTerms('cod', 'thanh toan khi nhan', 'nhan hang tra tien');
} else if (isPurchaseIntent) {
  forcedEntry = findByIntent('online_purchase')
    || findByIntentIncludes('purchase', 'buy', 'online')
    || findByKnowledgeTerms('mua hang', 'hotline');
} else if (input.isWebsiteQuestion) {
  forcedEntry = findByIntent('company_website', 'website', 'company_contact_information', 'online_purchase')
    || findByIntentIncludes('website', 'contact', 'purchase')
    || findByKnowledgeTerms('zeo.vn', 'website', 'trang web');
} else if (isLaundryGroupQuestion) {
  forcedEntry = findByIntent('zeo_laundry_product_overview')
    || findByKnowledgeTerms('giat giu', 'nuoc giat', 'bot giat');
} else if (input.isGenericDetergentQuestion) {
  forcedEntry = findByIntent('zeo_laundry_product_overview', 'zeo_detergent_usp', 'zeo_detergent_fragrance', 'zeo_detergent_technology')
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
} else if (asksSavedArea || asksSavedPhone) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'customer_profile_lookup';
  if (asksSavedArea && asksSavedPhone && knownArea && knownPhone) {
    finalReply = 'Dạ, ZeO đang lưu khu vực của bạn là: ' + knownArea + ', số điện thoại là: ' + knownPhone + '.';
  } else if (asksSavedArea && knownArea) {
    finalReply = 'Dạ, thông tin khu vực ZeO đang lưu của bạn là: ' + knownArea + '.';
  } else if (asksSavedPhone && knownPhone) {
    finalReply = 'Dạ, số điện thoại ZeO đang lưu của bạn là: ' + knownPhone + '.';
  } else {
    finalReply = 'Dạ, hiện ZeO chưa có đủ thông tin này trong hồ sơ chat. Bạn gửi lại giúp mình để ZeO lưu và hỗ trợ đúng hơn nha.';
  }
} else if (asksProfileRecall) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'customer_profile_lookup';
  if (knownArea && knownPhone) {
    finalReply = 'Dạ có, ZeO đang lưu khu vực của bạn là: ' + knownArea + ', số điện thoại là: ' + knownPhone + '.';
  } else if (knownArea || knownPhone) {
    finalReply = 'Dạ có, ZeO đang lưu ' + (knownArea ? 'khu vực của bạn là: ' + knownArea : 'số điện thoại của bạn là: ' + knownPhone) + '. Bạn gửi thêm thông tin còn thiếu để ZeO hỗ trợ đúng hơn nha.';
  } else {
    finalReply = 'Dạ, hiện ZeO chưa có đủ thông tin trong hồ sơ chat này. Bạn gửi lại số điện thoại và khu vực để ZeO lưu và hỗ trợ tiếp nha.';
  }
} else if (dialogue.intent === 'customer_profile_lookup') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'customer_profile_lookup';
  if (knownArea && knownPhone) {
    finalReply = 'Dạ, ZeO đang lưu khu vực của bạn là: ' + knownArea + ', số điện thoại là: ' + knownPhone + '.';
  } else if (knownArea || knownPhone) {
    finalReply = 'Dạ, ZeO đang lưu ' + (knownArea ? 'khu vực của bạn là: ' + knownArea : 'số điện thoại của bạn là: ' + knownPhone) + '. Bạn gửi thêm thông tin còn thiếu để ZeO hỗ trợ đúng hơn nha.';
  } else {
    finalReply = 'Dạ, hiện ZeO chưa có đủ thông tin này trong hồ sơ chat. Bạn gửi lại giúp mình để ZeO lưu và hỗ trợ đúng hơn nha.';
  }
} else if (selectedHotlineBranch02) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'online_purchase';
  if (hasFullContact) {
    finalReply = 'Dạ, số 02 là phím nhánh mua hàng khi bạn gọi hotline 1900 5307. ' + contactReadyReply('online_purchase');
  } else {
    finalReply = 'Dạ, bạn gọi hotline 1900 5307 rồi bấm phím nhánh số 02 để được hỗ trợ mua hàng ZeO nha. Nếu muốn admin liên hệ lại, bạn gửi thêm số điện thoại và khu vực/tỉnh thành giúp mình.';
  }
} else if (asksContactNextStep || dialogue.intent === 'contact_next_step') {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'contact_next_step';
  finalReply = contactReadyReply(session.last_intent || customerProfile.last_need || '');
} else if ((dialogue.intent === 'contact_information_received' || isLeadInfo) && !input.isOrderQuantityRequest) {
  responseMode = 'review';
  fallbackReason = contactFallbackReason();
  matchedIntent = session.last_intent || customerProfile.last_need || dialogue.intent || '';
  finalReply = hasFullContact
    ? contactReadyReply(matchedIntent, 'Dạ, ZeO đã nhận được thông tin liên hệ bạn gửi.')
    : contactReply('Dạ, ZeO đã nhận được thông tin bạn gửi.');
} else if (dialogue.intent === 'wholesale_inquiry') {
  responseMode = hasFullContact ? 'review' : 'direct';
  fallbackReason = hasFullContact ? 'lead_contact_ready' : '';
  matchedIntent = 'wholesale_inquiry';
  if (hasFullContact) {
    finalReply = contactReadyReply(matchedIntent);
  } else if (!knownPhone && !knownArea) {
    finalReply = 'Dạ, ZeO đã ghi nhận nhu cầu đăng ký đại lý/lấy sỉ của bạn. Bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành muốn kinh doanh để admin chuyển đúng nhân viên phụ trách nha.';
  } else {
    finalReply = contactReply('Dạ, ZeO đã ghi nhận nhu cầu đại lý/lấy sỉ của bạn.');
  }
} else if (input.isOrderQuantityRequest || dialogue.intent === 'order_request') {
  responseMode = 'review';
  matchedIntent = 'order_request';
  fallbackReason = hasFullContact ? 'order_contact_ready' : 'order_contact_missing';
  if (hasFullContact) {
    finalReply = 'Dạ, ZeO đã ghi nhận bạn muốn: ' + input.text + '. ZeO đang lưu số ' + knownPhone + ' và khu vực ' + knownArea + '. Admin sẽ kiểm tra đúng sản phẩm/quy cách, tồn hàng và giá rồi liên hệ xác nhận đơn cho bạn nha. Nếu bạn muốn rõ thương hiệu PANO, ZeO hay Oplus thì nhắn thêm giúp mình.';
  } else {
    finalReply = 'Dạ, ZeO đã ghi nhận bạn muốn: ' + input.text + '. Bạn gửi thêm số điện thoại và khu vực/tỉnh thành để admin kiểm tra đúng sản phẩm, giá và hỗ trợ chốt đơn nha.';
  }
} else if (isUnderwhelmedCatalogFollowUp) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'zeo_product_catalog_overview';
  const catalogEntry = findByIntent('zeo_product_catalog_overview', 'catalog_overview');
  finalReply = catalogEntry?.answer || 'Dạ không chỉ một nhóm đâu ạ. ZeO Vietnam hiện có 4 nhóm chính: Giặt giũ, Rửa chén, Lau sàn và Tẩy rửa vệ sinh. Bạn muốn mình liệt kê chi tiết nhóm nào trước nha?';
} else if (isPriceQuestion || dialogue.intent === 'price_request') {
  responseMode = 'review';
  fallbackReason = 'price_unverified';
  matchedIntent = 'price_request';
  if (hasFullContact) {
    finalReply = 'Dạ, hiện dữ liệu chat chưa có bảng giá chi tiết để mình báo chính xác. ZeO đã có số điện thoại và khu vực của bạn, admin sẽ kiểm tra giá sản phẩm phù hợp và liên hệ hỗ trợ nha.';
  } else {
    finalReply = 'Dạ, hiện dữ liệu chat chưa có bảng giá chi tiết để mình báo chính xác. Bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành, admin ZeO sẽ kiểm tra giá sản phẩm phù hợp và liên hệ hỗ trợ nha.';
  }
} else if (isDistributorAvailabilityQuestion || dialogue.intent === 'distributor_availability') {
  responseMode = 'review';
  fallbackReason = 'distributor_availability_check';
  matchedIntent = 'distributor_availability';
  const areaText = requestedDistributorArea || knownArea || 'khu vực bạn hỏi';
  if (hasFullContact) {
    finalReply = 'Dạ, để xác nhận nhà phân phối tại ' + areaText + ', ZeO sẽ chuyển admin kiểm tra đúng khu vực rồi phản hồi bạn. ZeO đang lưu số ' + knownPhone + ' và khu vực ' + knownArea + ' để tiện liên hệ nha.';
  } else {
    finalReply = 'Dạ, để kiểm tra nhà phân phối tại ' + areaText + ', bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành. Admin ZeO sẽ xác nhận đúng khu vực rồi phản hồi bạn nha.';
  }
} else if (isLeadInfo) {
  responseMode = 'review';
  fallbackReason = contactFallbackReason();
  finalReply = hasFullContact
    ? contactReadyReply(session.last_intent || customerProfile.last_need || '', 'Dạ, ZeO đã nhận được thông tin bạn gửi.')
    : contactReply('Dạ, ZeO đã nhận được thông tin bạn gửi.');
} else if (input.isWarrantyQuestion && !forcedEntry) {
  responseMode = 'review';
  fallbackReason = 'warranty_support_unverified';
  finalReply = 'Dạ, dữ liệu hiện tại chưa có chính sách bảo hành riêng. Nếu sản phẩm bị lỗi hoặc cần đổi trả, bạn gửi giúp mình tình trạng sản phẩm, hình ảnh và thông tin đơn hàng để admin ZeO kiểm tra hỗ trợ đúng chính sách nhé.';
} else if (input.isBotComplaint || dialogue.intent === 'bot_answer_complaint') {
  responseMode = 'review';
  fallbackReason = 'bot_answer_complaint';
  matchedIntent = 'bot_answer_complaint';
  finalReply = dialogue.final_reply || 'Dạ xin lỗi bạn, câu trả lời trước chưa đúng ý. Bạn nhắn lại giúp mình câu hỏi chính hoặc tên sản phẩm cần hỗ trợ, mình sẽ kiểm tra theo dữ liệu ZeO kỹ hơn nhé.';
} else if (input.mentionsAba && input.isShortDetergentQuestion) {
  responseMode = 'review';
  fallbackReason = 'competitor_product_question';
  finalReply = 'Dạ, hiện dữ liệu của ZeO chỉ có thông tin về các sản phẩm thuộc ZeO, PANO và Oplus. Bạn muốn hỏi bột giặt ZeO hay PANO/Oplus để mình hỗ trợ đúng thông tin ạ?';
} else if (input.isCfcHomecareQuestion) {
  responseMode = 'review';
  fallbackReason = 'cfc_homecare_unverified';
  finalReply = 'Dạ, thông tin này hiện chưa có trong dữ liệu ZeO nên mình chưa dám xác nhận. Admin ZeO sẽ kiểm tra và phản hồi bạn chính xác hơn nhé.';
} else if (isDetailedCatalogQuestion) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'product_catalog_detail';
  finalReply = buildDetailedCatalogReply();
} else if (isBroadCleaningProductQuestion) {
  responseMode = 'direct';
  fallbackReason = 'product_scope_clarification';
  matchedIntent = 'cleaning_product_group_clarification';
  finalReply = 'Dạ nhóm tẩy rửa của ZeO có nhiều loại như Javen, tẩy toilet, tẩy màu, lau kính và xịt tẩy đa năng PANO. Bạn muốn loại tẩy rửa cho quần áo, nhà vệ sinh, kính, bếp hay rửa chén ạ?';
} else if (isLaundryGroupQuestion) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'zeo_laundry_product_overview';
  const laundryEntry = findByIntent('zeo_laundry_product_overview');
  finalReply = laundryEntry?.answer || 'Dạ nhóm giặt giũ hiện có Bột giặt & Nước giặt sinh học ZeO, PANO và Oplus. Bạn muốn mình tư vấn theo nhu cầu sạch sâu, thơm lâu, dịu nhẹ hay tiết kiệm hơn ạ?';
} else if (asksPanoProductType) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'pano_product_type';
  const panoEntry = findByIntent('pano_product_type');
  finalReply = panoEntry?.answer || 'Dạ, PANO là dòng sản phẩm tẩy rửa gia dụng thuộc hệ ZeO/PANO/Oplus. Trong dữ liệu hiện có, PANO gồm sản phẩm giặt giũ, nước rửa chén và xịt tẩy đa năng. Nếu bạn hỏi riêng nhóm giặt giũ, PANO có bột giặt/nước giặt với nhiều lựa chọn hương.';
} else if (websiteOnlyQuestion) {
  responseMode = 'direct';
  fallbackReason = '';
  matchedIntent = 'company_website';
  finalReply = 'Dạ website chính thức của ZeO là https://zeo.vn/ nha bạn.';
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
  responseMode = answerModeFor(forcedEntry);
  fallbackReason = '';
  matchedIntent = forcedEntry.intent;
  matchedSourceId = forcedEntry.source_id;
  canonicalAnswer = forcedEntry.answer;
  finalReply = forcedEntry.answer;
} else if (forcedEntry) {
  responseMode = answerModeFor(forcedEntry);
  fallbackReason = '';
  matchedIntent = forcedEntry.intent;
  matchedSourceId = forcedEntry.source_id;
  canonicalAnswer = forcedEntry.answer;
  finalReply = forcedEntry.answer;
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (matchedIntent === 'wholesale_inquiry' && (knownPhone || knownArea)) {
    finalReply = hasFullContact ? contactReadyReply(matchedIntent) : contactReply('Dạ, ZeO đã nhận được một phần thông tin của bạn.');
  }
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
  fallbackReason = input.isFabricSoftenerQuestion ? 'product_not_in_knowledge' : 'unsupported_product_scope';
  matchedIntent = input.isFabricSoftenerQuestion ? 'oplus_fabric_softener_unverified' : '';
  matchedSourceId = input.isFabricSoftenerQuestion ? 'zeo_runtime_regression_v1' : '';
  finalReply = input.isFabricSoftenerQuestion
    ? 'Dạ, hiện dữ liệu ZeO chưa có thông tin xác nhận về nước xả vải Oplus. Mình chỉ đang có thông tin về bột giặt/nước giặt Oplus và các sản phẩm tẩy rửa khác. Admin ZeO sẽ kiểm tra thêm nếu bạn cần xác nhận sản phẩm này nha.'
    : 'Dạ, theo dữ liệu hiện có ZeO chỉ hỗ trợ thông tin về các sản phẩm tẩy rửa gia dụng. Admin sẽ hỗ trợ thêm nếu bạn cần xác nhận sản phẩm khác nhé.';
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
  responseMode = answerModeFor(best);
  fallbackReason = '';
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (matchedIntent === 'wholesale_inquiry' && (knownPhone || knownArea)) {
    finalReply = hasFullContact ? contactReadyReply(matchedIntent) : contactReply('Dạ, ZeO đã nhận được một phần thông tin của bạn.');
  }
} else if (confidence === 'medium' && best) {
  responseMode = answerModeFor(best);
  fallbackReason = '';
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  canonicalAnswer = best.answer;
  finalReply = best.answer;
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (matchedIntent === 'wholesale_inquiry' && (knownPhone || knownArea)) {
    finalReply = hasFullContact ? contactReadyReply(matchedIntent) : contactReply('Dạ, ZeO đã nhận được một phần thông tin của bạn.');
  }
} else if (best && isLowRiskEntry(best) && bestScore >= 22 && (best.matched || 0) >= 1 && scoreMargin >= 1) {
  responseMode = answerModeFor(best);
  fallbackReason = '';
  matchedIntent = best.intent;
  matchedSourceId = best.source_id;
  canonicalAnswer = best.answer;
  finalReply = best.answer;
  if (shouldEscalateReadyLead(matchedIntent)) {
    responseMode = 'review';
    fallbackReason = 'lead_contact_ready';
    finalReply = contactReadyReply(matchedIntent);
  } else if (matchedIntent === 'wholesale_inquiry' && (knownPhone || knownArea)) {
    finalReply = hasFullContact ? contactReadyReply(matchedIntent) : contactReply('Dạ, ZeO đã nhận được một phần thông tin của bạn.');
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
const pendingSlots = [];
if (!knownPhone) pendingSlots.push('phone');
if (!knownArea) pendingSlots.push('area');
const leadStage = hasFullContact
  ? (responseMode === 'review' ? 'qualified' : (customerProfile.lead_stage || 'qualified'))
  : ((knownPhone || knownArea) ? 'collecting_contact' : (customerProfile.lead_stage || 'new'));
const customerProfileState = {
  ...customerProfile,
  brand: 'ZeO',
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
  last_intent: matchedIntent || session.last_intent || '',
  last_source_id: matchedSourceId || session.last_source_id || '',
  last_user_message: input.text,
  last_bot_reply: finalReply,
  last_message_id: input.messageId || session.last_message_id || '',
  customer_phone: knownPhone,
  customer_location: knownArea,
  lead_stage: leadStage,
  pending_slots: pendingSlots,
  last_reply_type: replyType,
  use_rag: shouldUseRag,
  response_plan: responsePlanState,
  nlu,
  order_items: Array.isArray(nlu.order_items) ? nlu.order_items : [],
  conversation_summary: conversationSummary,
  updated_at: new Date().toISOString(),
};

return [{ json: {
  senderId: input.senderId,
  messageId: input.messageId,
  userMessage: input.text,
  responseMode,
  routeIndex,
  confidence,
  normalizedMessage: input.normalizedText || normalizedInputText,
  replyType,
  useRag: shouldUseRag,
  responsePlan: responsePlanState,
  nlu,
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
  customerProfileState,
  sessionState,
} }];
`,
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000004',
        name: 'Router Co Nguon',
        type: 'n8n-nodes-base.switch',
        version: 3.4,
        position: [672, -112],
    })
    RouterCoNguon = {
        mode: 'expression',
        output: '={{ Number($json.routeIndex) }}',
    };

    @node({
        id: 'f1000001-0000-0000-0000-000000000005',
        name: 'Goi Ollama Local',
        type: 'n8n-nodes-base.httpRequest',
        version: 4,
        position: [1136, 96],
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
const passed = !tooShort && !tooLong && !hasForeignScript && !hasEnglishLeak && !hasModelLeak && !hasPromptLeak && !hallucinatedScope && !changedFacts;

let guardrailReason = 'ollama_guardrail_failed';
if (hallucinatedScope) guardrailReason = 'ollama_hallucinated_scope';
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

return [{ json: {
  ...ragData,
  finalReply,
  passed,
  fallbackReason: passed ? '' : guardrailReason,
  fallbackMessage: finalReply,
  sessionState,
  customerProfileState,
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
        id: '9d6307b1-c3c4-4ed8-a3eb-2a164b80d9a4',
        name: 'Save Customer Profile',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1984, -96],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        onError: 'continueRegularOutput',
    })
    SaveCustomerProfile = {
        operation: 'set',
        key: '={{ "zeo:customer:messenger:" + $json.senderId }}',
        value: '={{ JSON.stringify($json.customerProfileState || {}) }}',
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
            '={{ JSON.stringify({ status: "pending", channel: "messenger", sender_id: $json.senderId, message_id: $("Loc Dau Vao").first().json.messageId, user_message: $json.userMessage, normalized_message: $json.normalizedMessage, fallback_reason: $json.fallbackReason, matched_intent: $json.matchedIntent, matched_source_id: $json.matchedSourceId, reply_type: $json.replyType, response_mode: $json.responseMode, use_rag: $json.useRag, rag_score: $json.ragScore, score_margin: $json.scoreMargin, nlu: $json.nlu, response_plan: $json.responsePlan, session_summary: $json.sessionState?.conversation_summary, customer_profile: { phone: $json.customerProfileState?.phone, area: $json.customerProfileState?.area, lead_stage: $json.customerProfileState?.lead_stage, last_need: $json.customerProfileState?.last_need }, bot_reply: $json.finalReply, created_at: $now.toISO() }) }}',
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
        content: 'Redis snapshot, session và learning queue',
        height: 144,
        width: 256,
        color: 5,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.MessengerTrigger.out(0).to(this.LocDauVao.in(0));
        this.LocDauVao.out(0).to(this.GoiFastApiChatPipeline.in(0));
        this.GoiFastApiChatPipeline.out(0).to(this.PrepareMessengerReply.in(0));
        this.GoiFastApiChatPipeline.error().to(this.PrepareMessengerReply.in(0));
        this.PrepareMessengerReply.out(0).to(this.NhanKhachAuto.in(0));
    }
}
