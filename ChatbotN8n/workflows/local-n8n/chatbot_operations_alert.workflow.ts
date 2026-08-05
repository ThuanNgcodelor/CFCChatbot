import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Chatbot Operations Alert
// Nodes   : 8  |  Connections: 7
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// WhenExecutedByAnotherWorkflow      executeWorkflowTrigger
// ManualTrigger                      manualTrigger
// CreateTestAlert                    code
// NormalizeAlert                     code
// GetRecentDuplicate                 redis                      [creds] [alwaysOutput]
// SkipRecentDuplicate                code
// SendTelegramAlert                  telegram                   [onError→out(1)]
// RememberTelegramAlert              redis                      [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// WhenExecutedByAnotherWorkflow
//    → NormalizeAlert
//      → GetRecentDuplicate
//        → SkipRecentDuplicate
//          → SendTelegramAlert
//            → RememberTelegramAlert
// ManualTrigger
//    → CreateTestAlert
//      → NormalizeAlert (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'f2IjxVj9sW3KQRAw',
    name: 'Chatbot Operations Alert',
    active: false,
    isArchived: false,
    settings: { executionOrder: 'v1', callerPolicy: 'workflowsFromSameOwner' },
})
export class ChatbotOperationsAlertWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'bc8523ff-a692-496e-8a80-07412a72bd06',
        name: 'When Executed by Another Workflow',
        type: 'n8n-nodes-base.executeWorkflowTrigger',
        version: 1.2,
        position: [0, 160],
    })
    WhenExecutedByAnotherWorkflow = {
        inputSource: 'passthrough',
    };

    @node({
        id: '35b77e66-c44e-45cc-9b18-c57d9b2faa07',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 352],
    })
    ManualTrigger = {};

    @node({
        id: 'f7c9332e-a0b6-4e18-a110-0650f3c2c44f',
        name: 'Create Test Alert',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [240, 352],
    })
    CreateTestAlert = {
        jsCode: `
return [{
  json: {
    brand: 'SYSTEM',
    event_type: 'TEST',
    priority: 'normal',
    sender_id: '',
    user_message: 'Day la tin nhan kiem tra Telegram tu Chatbot Operations Alert.',
    fallback_reason: 'manual_test',
    rag_score: 0,
    bot_reply: '',
    created_at: new Date().toISOString(),
  },
}];
`,
    };

    @node({
        id: 'c544e692-3195-4e7d-a260-e5cd56c58b1b',
        name: 'Normalize Alert',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [480, 256],
    })
    NormalizeAlert = {
        jsCode: `
const event = $input.first().json || {};

function text(value, maxLength = 500) {
  return String(value || '').replace(/\\s+/g, ' ').trim().slice(0, maxLength);
}

function hash(value) {
  let result = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 0x01000193);
  }
  return (result >>> 0).toString(16).padStart(8, '0');
}

const brand = text(event.brand || 'UNKNOWN', 40).toUpperCase();
const eventType = text(event.event_type || 'REVIEW', 40).toUpperCase();
const priority = text(event.priority || 'normal', 20).toLowerCase();
const senderId = text(event.sender_id || event.senderId || '', 80);
const userMessage = text(event.user_message || event.userMessage || '', 500);
const botReply = text(event.bot_reply || event.botReply || '', 500);
const reason = text(event.fallback_reason || event.fallbackReason || 'unknown', 120);
const score = Number(event.rag_score ?? event.ragScore ?? 0);
const createdAt = text(event.created_at || new Date().toISOString(), 80);
const dedupHash = hash([brand, eventType, senderId, userMessage.toLowerCase()].join('|'));

const priorityLabel = {
  high: 'KHẨN',
  urgent: 'KHẨN',
  normal: 'BÌNH THƯỜNG',
  low: 'THẤP',
}[priority] || priority.toUpperCase();

const reasonLabel = {
  sensitive_case: 'Yêu cầu nhạy cảm: khiếu nại / hoàn tiền',
  no_source: 'Không tìm thấy thông tin phù hợp trong FAQ',
  low_score: 'Độ khớp FAQ thấp',
  guardrail_failed: 'Phản hồi cần Admin kiểm tra',
  manual_test: 'Tin nhắn kiểm tra thủ công',
}[reason] || reason.replace(/_/g, ' ');

function formatVnDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date).replace(',', '');
}

const eventLabel = eventType === 'URGENT' ? 'KHÁCH CẦN XỬ LÝ' : 'CẦN XEM XÉT';
const lines = [
  '[' + brand + ' | ' + eventLabel + ']',
  'Mức độ: ' + priorityLabel,
  ...(senderId ? ['Khách: ...' + senderId.slice(-4)] : []),
  'Thời gian: ' + formatVnDate(createdAt),
  '',
  'Nội dung khách gửi',
  '"' + (userMessage || '(không có nội dung chữ)') + '"',
  ...(botReply ? ['', 'Bot đã phản hồi', '"' + botReply + '"'] : []),
  '',
  'Lý do chuyển Admin',
  reasonLabel,
  '',
  'Độ khớp FAQ: ' + score,
];

return [{
  json: {
    brand,
    event_type: eventType,
    priority,
    sender_id_masked: senderId ? '...' + senderId.slice(-4) : '',
    user_message: userMessage,
    fallback_reason: reason,
    rag_score: score,
    created_at: createdAt,
    dedup_key: 'ops:telegram:dedup:' + dedupHash,
    telegram_text: lines.join('\\n'),
  },
}];
`,
    };

    @node({
        id: '3b33f15d-4b3a-474e-9899-c5e24f7eaf9f',
        name: 'Get Recent Duplicate',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [720, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    GetRecentDuplicate = {
        operation: 'get',
        key: '={{ $json.dedup_key }}',
        propertyName: 'dedupRaw',
        keyType: 'string',
    };

    @node({
        id: '829e1d05-a0c4-41d9-8409-4271d7c588cc',
        name: 'Skip Recent Duplicate',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [960, 256],
    })
    SkipRecentDuplicate = {
        jsCode: `
const duplicate = $input.first().json.dedupRaw;

if (duplicate) {
  return [];
}

return [{
  json: $("Normalize Alert").first().json,
}];
`,
    };

    @node({
        id: '1267a7f3-694f-4614-9c03-ebbc44f38947',
        webhookId: '77edd86d-8add-44d4-b5ae-14d0ed02f834',
        name: 'Send Telegram Alert',
        type: 'n8n-nodes-base.telegram',
        version: 1.2,
        position: [1200, 256],
        onError: 'continueErrorOutput',
    })
    SendTelegramAlert = {
        text: '={{ $json.telegram_text }}',
        chatId: 'SET_TELEGRAM_CHAT_ID_IN_N8N',
        additionalFields: { appendAttribution: false },
    };

    @node({
        id: 'e6ca5f4b-e16d-4b7e-b503-ef28215042a4',
        name: 'Remember Telegram Alert',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1440, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    RememberTelegramAlert = {
        operation: 'set',
        key: '={{ $json.dedup_key }}',
        value: 'sent',
        expire: true,
        ttl: 900,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.WhenExecutedByAnotherWorkflow.out(0).to(this.NormalizeAlert.in(0));
        this.ManualTrigger.out(0).to(this.CreateTestAlert.in(0));
        this.CreateTestAlert.out(0).to(this.NormalizeAlert.in(0));
        this.NormalizeAlert.out(0).to(this.GetRecentDuplicate.in(0));
        this.GetRecentDuplicate.out(0).to(this.SkipRecentDuplicate.in(0));
        this.SkipRecentDuplicate.out(0).to(this.SendTelegramAlert.in(0));
        this.SendTelegramAlert.out(0).to(this.RememberTelegramAlert.in(0));
    }
}
