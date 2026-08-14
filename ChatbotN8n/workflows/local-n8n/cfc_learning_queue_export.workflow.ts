import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Learning Queue Export
// Nodes   : 6  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// PopCfcLearningEvent                redis                      [creds] [alwaysOutput]
// PrepareCfcReviewRow                code
// AppendCfcLearningQueue             googleSheets               [onError→out(1)] [creds]
// RequeueFailedCfcEvent              redis                      [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → PopCfcLearningEvent
//      → PrepareCfcReviewRow
//        → AppendCfcLearningQueue
//         .out(1) → RequeueFailedCfcEvent
// ScheduleTrigger
//    → PopCfcLearningEvent (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'hPY4cMva4TOCOXee',
    name: 'CFC Learning Queue Export',
    active: false,
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1' },
})
export class CfcLearningQueueExportWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'f3000001-0000-0000-0000-000000000001',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: 'f3000001-0000-0000-0000-000000000002',
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
                    minutesInterval: 5,
                },
            ],
        },
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000003',
        name: 'Pop CFC Learning Event',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [256, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    PopCfcLearningEvent = {
        operation: 'pop',
        list: 'cfc:learning:queue',
        propertyName: 'queueItem',
        tail: false,
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000004',
        name: 'Prepare CFC Review Row',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    PrepareCfcReviewRow = {
        jsCode: `
const rawEvent = $input.first().json.queueItem;
if (!rawEvent) {
  return [];
}

let event;
try {
  event = typeof rawEvent === 'string' ? JSON.parse(rawEvent) : rawEvent;
} catch (_) {
  event = {
    channel: 'messenger',
    user_message: String(rawEvent),
    fallback_reason: 'invalid_learning_event',
    created_at: new Date().toISOString(),
  };
}

const createdAt = String(event.created_at || new Date().toISOString());
const messageId = String(event.message_id || '');
const senderId = String(event.sender_id || '');
const eventId = messageId || [event.channel || 'messenger', senderId || 'unknown', createdAt].join(':');

return [{
  json: {
    event_id: eventId,
    status: 'pending',
    channel: String(event.channel || 'messenger'),
    sender_id: senderId,
    message_id: messageId,
    user_message: String(event.user_message || ''),
    normalized_message: String(event.normalized_message || ''),
    fallback_reason: String(event.fallback_reason || 'low_confidence'),
    matched_intent: String(event.matched_intent || ''),
    matched_source_id: String(event.matched_source_id || ''),
    reply_type: String(event.reply_type || ''),
    response_mode: String(event.response_mode || ''),
    use_rag: event.use_rag === undefined ? '' : String(Boolean(event.use_rag)),
    rag_score: Number(event.rag_score || 0),
    score_margin: Number(event.score_margin || 0),
    bot_reply: String(event.bot_reply || ''),
    session_summary: String(event.session_summary || ''),
    created_at: createdAt,
    admin_answer: '',
    question_examples: '',
    intent: '',
    category: 'faq',
    brand: 'CFC',
    priority: 50,
    source_id: 'redis_learning_queue',
    reviewed_at: '',
    notes: '',
    queue_payload_raw: typeof rawEvent === 'string' ? rawEvent : JSON.stringify(rawEvent),
  },
}];
`,
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000005',
        name: 'Append CFC Learning Queue',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [768, 192],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
        onError: 'continueErrorOutput',
    })
    AppendCfcLearningQueue = {
        operation: 'append',
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1EBiuH3TVVSwLQE1loQ2bYijlaJPHGGFB9rAXM3xP9Tw/edit?gid=0#gid=0',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 'LearningQueue',
            mode: 'name',
        },
        columns: {
            mappingMode: 'autoMapInputData',
            value: null,
        },
        options: {},
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000006',
        name: 'Requeue Failed CFC Event',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1016, 352],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    RequeueFailedCfcEvent = {
        operation: 'push',
        list: 'cfc:learning:queue',
        messageData: '={{ $("Prepare CFC Review Row").first().json.queue_payload_raw }}',
        tail: false,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.PopCfcLearningEvent.in(0));
        this.ScheduleTrigger.out(0).to(this.PopCfcLearningEvent.in(0));
        this.PopCfcLearningEvent.out(0).to(this.PrepareCfcReviewRow.in(0));
        this.PrepareCfcReviewRow.out(0).to(this.AppendCfcLearningQueue.in(0));
        this.AppendCfcLearningQueue.out(1).to(this.RequeueFailedCfcEvent.in(0));
    }
}
