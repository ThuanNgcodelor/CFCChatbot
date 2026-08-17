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



cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/CFCAI/server
source .venv/bin/activate
python main.py
# Mở trình duyệt truy cập Admin Dashboard: http://localhost:8000/admin

docker exec -it zeo-redis redis-cli -a "crS9Lb7f/ywrTCiRP22gc32QCLZpirWIkczbnhjYIdU1o02Z"