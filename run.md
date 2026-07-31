WEBHOOK_URL=https://n8n.dinhduongcantho.io.vn/ \
N8N_EDITOR_BASE_URL=https://n8n.dinhduongcantho.io.vn \
N8N_HOST=n8n.dinhduongcantho.io.vn \
N8N_PROTOCOL=https \
npx n8n start

cloudflared tunnel run n8n-dinhduongcantho