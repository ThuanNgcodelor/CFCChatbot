cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n
npx --yes n8nac skills validate workflows/local-n8n/zeo_chatbot.workflow.ts
npx --yes n8nac push workflows/local-n8n/zeo_chatbot.workflow.ts --verify


cd /Users/hyden/Documents/N8n/ChatbotN8n
npx --yes n8nac skills validate workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts
npx --yes n8nac push workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts --verify
# Khi n8n báo conflict và bạn muốn lấy bản local ghi đè bản trên giao diện:
npx --yes n8nac resolve d7fctbMhVUmhrNG0 --mode keep-current
# Xem danh sách và trạng thái workflow:
npx --yes n8nac list