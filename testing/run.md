WEBHOOK_URL=https://n8n.dinhduongcantho.io.vn/ \
N8N_EDITOR_BASE_URL=https://n8n.dinhduongcantho.io.vn \
N8N_HOST=n8n.dinhduongcantho.io.vn \
N8N_PROTOCOL=https \
npx n8n start

cloudflared tunnel run n8n-dinhduongcantho


export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_CONTEXT_LENGTH=4096
export OLLAMA_NUM_PARALLEL=1
ollama serve



cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
python main.py
# Mở trình duyệt truy cập Admin Dashboard: http://localhost:8000/admin


# Test Ollama NLU Planner an toàn: shadow chỉ ghi trace, không đổi quyết định trả lời.
# Ollama chỉ phân loại intent JSON; giá/link vẫn lấy từ catalog deterministic.
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
export LLM_NLU_MODE=shadow
export LLM_NLU_TIMEOUT=1.6
export LLM_NLU_CONFIDENCE=0.72
uvicorn main:app --host 0.0.0.0 --port 8000 --reload


# Smoke test nên chạy ở shadow trước. Chỉ đổi thành LLM_NLU_MODE=assist
# sau khi regression pass và trace cho thấy planner đủ chính xác.
# 1) shop ơi món nào giá chát nhất vậy
# 2) cho xin link sản phẩm đó
# 3) giá nước xả vải zeo shop ơi
# 4) vậy có biết cái nào giặt đồ nó thơm thơm ko nhỉ

docker exec -it zeo-redis redis-cli -a "crS9Lb7f/ywrTCiRP22gc32QCLZpirWIkczbnhjYIdU1o02Z"


cd /Users/hyden/Documents/David-nguyen/N8n
.venv/bin/python3 ChatbotN8n/javis/server/crawl_shopee_shop.py zeovietnamofficial
