import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Learning Queue Export
// Nodes   : 6  |  Connections: 5
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// PopLearningEvent                   redis                      [creds] [alwaysOutput]
// PrepareReviewRow                   code
// AppendLearningQueue                googleSheets               [onError→out(1)] [creds]
// RequeueFailedEvent                 redis                      [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → PopLearningEvent
//      → PrepareReviewRow
//        → AppendLearningQueue
//         .out(1) → RequeueFailedEvent
// ScheduleTrigger
//    → PopLearningEvent (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'sUgJYuP1hj75sERu',
    name: 'Zeo Learning Queue Export',
    active: false,
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1' },
})
export class ZeoLearningQueueExportWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: '1c509c29-9af5-451a-9170-55e7731cc516',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: '5c3ce4f7-b5bd-48d3-9c05-60cf98fc68ea',
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
        id: 'b76c14a4-d4e4-4f04-9fcd-8e1976ffc7b9',
        name: 'Pop Learning Event',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [256, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
        alwaysOutputData: true,
    })
    PopLearningEvent = {
        operation: 'pop',
        list: 'zeo:learning:queue',
        propertyName: 'queueItem',
        tail: false,
    };

    @node({
        id: '67ece074-6e8c-4f80-b0ec-05bb681f1e91',
        name: 'Prepare Review Row',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    PrepareReviewRow = {
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
    fallback_reason: String(event.fallback_reason || 'low_confidence'),
    rag_score: Number(event.rag_score || 0),
    created_at: createdAt,
    admin_answer: '',
    question_examples: '',
    intent: '',
    category: 'faq',
    brand: 'ZeO',
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
        id: 'd3cfed8e-a0b3-498f-b798-72f98e738907',
        name: 'Append Learning Queue',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [768, 192],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
        onError: 'continueErrorOutput',
    })
    AppendLearningQueue = {
        operation: 'append',
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1o4vk2YwTVHbuvJxPedTAELCDeQa7iAszZ1kfDKQx0nk/edit?gid=0#gid=0',
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
        id: '0ccbb4cb-c702-4520-b0f5-bd86900eebbb',
        name: 'Requeue Failed Event',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1016, 352],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    RequeueFailedEvent = {
        operation: 'push',
        list: 'zeo:learning:queue',
        messageData: '={{ $("Prepare Review Row").first().json.queue_payload_raw }}',
        tail: false,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.PopLearningEvent.in(0));
        this.ScheduleTrigger.out(0).to(this.PopLearningEvent.in(0));
        this.PopLearningEvent.out(0).to(this.PrepareReviewRow.in(0));
        this.PrepareReviewRow.out(0).to(this.AppendLearningQueue.in(0));
        this.AppendLearningQueue.out(1).to(this.RequeueFailedEvent.in(0));
    }
}
