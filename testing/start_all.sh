#!/usr/bin/env zsh
# ══════════════════════════════════════════════════════════════════
# start_all.sh — Khởi động toàn bộ hệ thống CFC AI / ZeO
# Chạy: chmod +x start_all.sh && ./start_all.sh
# ══════════════════════════════════════════════════════════════════

set -e

# ── Màu sắc terminal ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo "${BOLD}${CYAN}║       🚀 CFC AI / ZeO — System Startup               ║${NC}"
echo "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

LOG_DIR="$HOME/Documents/David-nguyen/N8n/logs"
mkdir -p "$LOG_DIR"

# ── Hàm mở tab Terminal mới trên macOS ───────────────────────────
open_tab() {
  local title="$1"
  local cmd="$2"
  osascript <<EOF
tell application "Terminal"
  set newTab to do script "$cmd"
  set custom title of (selected tab of front window) to "$title"
end tell
EOF
}

echo "${BOLD}Chọn chế độ khởi động:${NC}"
echo "  ${GREEN}[1]${NC} Mỗi service trong một cửa sổ Terminal riêng (khuyên dùng)"
echo "  ${YELLOW}[2]${NC} Chạy tất cả nền, log ra file $LOG_DIR/"
echo ""
printf "Nhập lựa chọn [1/2, mặc định 1]: "
read MODE
MODE=${MODE:-1}

echo ""

# ══════════════════════════════════════════════════════════════════
if [[ "$MODE" == "1" ]]; then
# ── MODE 1: Mỗi service 1 tab Terminal riêng ─────────────────────

  echo "${BLUE}▶ [0/4]${NC} Kiểm tra & Khởi động ${BOLD}Redis Stack (Docker)${NC}..."
  (cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/infra/redis && docker compose up -d 2>/dev/null || true)
  sleep 1

  echo "${BLUE}▶ [1/4]${NC} Khởi động ${BOLD}n8n${NC}..."
  open_tab "🔁 n8n" "WEBHOOK_URL=https://n8n.dinhduongcantho.io.vn/ N8N_EDITOR_BASE_URL=https://n8n.dinhduongcantho.io.vn N8N_HOST=n8n.dinhduongcantho.io.vn N8N_PROTOCOL=https npx n8n start; exec zsh"
  sleep 1

  echo "${BLUE}▶ [2/4]${NC} Khởi động ${BOLD}Cloudflared Tunnel${NC}..."
  open_tab "☁️ Cloudflared" "cloudflared tunnel run n8n-dinhduongcantho; exec zsh"
  sleep 1

  echo "${BLUE}▶ [3/4]${NC} Khởi động ${BOLD}Ollama${NC}..."
  open_tab "🤖 Ollama" "export OLLAMA_HOST=0.0.0.0:11434; export OLLAMA_CONTEXT_LENGTH=4096; export OLLAMA_NUM_PARALLEL=1; ollama serve; exec zsh"
  sleep 2

  echo "${BLUE}▶ [4/4]${NC} Khởi động ${BOLD}Python FastAPI (Admin Dashboard)${NC}..."
  open_tab "🐍 Python API :8000" "cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload; exec zsh"

  echo ""
  echo "${GREEN}${BOLD}✅ Đã mở 4 tab Terminal & Khởi động hoàn tất:${NC}"
  echo "   ${CYAN}🔁 n8n Webhook / Editor${NC} → https://n8n.dinhduongcantho.io.vn"
  echo "   ${CYAN}🐍 FastAPI Admin UI    ${NC} → https://dinhduongcantho.io.vn/admin (hoặc http://localhost:8000/admin)"
  echo "   ${CYAN}☁️  Cloudflared Tunnel  ${NC} → Đang chạy (n8n & FastAPI)"
  echo "   ${CYAN}🤖 Ollama Local        ${NC} → http://localhost:11434"
  echo "   ${CYAN}🔴 Redis Stack         ${NC} → localhost:6379"
  echo ""

# ══════════════════════════════════════════════════════════════════
else
# ── MODE 2: Chạy nền, ghi log ra file ────────────────────────────

  # Kill các tiến trình cũ nếu có
  echo "${YELLOW}⏹  Dừng các tiến trình cũ...${NC}"
  pkill -f "npx n8n" 2>/dev/null && echo "   n8n stopped" || true
  pkill -f "cloudflared" 2>/dev/null && echo "   cloudflared stopped" || true
  pkill -f "ollama serve" 2>/dev/null && echo "   ollama stopped" || true
  pkill -f "uvicorn|python main.py" 2>/dev/null && echo "   Python API stopped" || true
  sleep 1

  echo "${BLUE}▶ [0/4]${NC} Kiểm tra & Khởi động ${BOLD}Redis Stack (Docker)${NC}..."
  (cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/infra/redis && docker compose up -d 2>/dev/null || true)

  echo "${BLUE}▶ [1/4]${NC} Khởi động ${BOLD}n8n${NC} → log: $LOG_DIR/n8n.log"
  WEBHOOK_URL=https://n8n.dinhduongcantho.io.vn/ \
  N8N_EDITOR_BASE_URL=https://n8n.dinhduongcantho.io.vn \
  N8N_HOST=n8n.dinhduongcantho.io.vn \
  N8N_PROTOCOL=https \
  npx n8n start > "$LOG_DIR/n8n.log" 2>&1 &
  N8N_PID=$!
  echo "   PID: $N8N_PID"
  sleep 3

  echo "${BLUE}▶ [2/4]${NC} Khởi động ${BOLD}Cloudflared${NC} → log: $LOG_DIR/cloudflared.log"
  cloudflared tunnel run n8n-dinhduongcantho > "$LOG_DIR/cloudflared.log" 2>&1 &
  CF_PID=$!
  echo "   PID: $CF_PID"
  sleep 1

  echo "${BLUE}▶ [3/4]${NC} Khởi động ${BOLD}Ollama${NC} → log: $LOG_DIR/ollama.log"
  export OLLAMA_HOST=0.0.0.0:11434
  export OLLAMA_CONTEXT_LENGTH=4096
  export OLLAMA_NUM_PARALLEL=1
  ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
  OLLAMA_PID=$!
  echo "   PID: $OLLAMA_PID"
  sleep 2

  echo "${BLUE}▶ [4/4]${NC} Khởi động ${BOLD}Python FastAPI${NC} → log: $LOG_DIR/python_api.log"
  (cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server && \
   source .venv/bin/activate && \
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload) > "$LOG_DIR/python_api.log" 2>&1 &
  PY_PID=$!
  echo "   PID: $PY_PID"

  # Lưu PIDs để dừng sau
  echo "$N8N_PID $CF_PID $OLLAMA_PID $PY_PID" > "$LOG_DIR/pids.txt"

  echo ""
  echo "${GREEN}${BOLD}✅ Tất cả đã chạy nền!${NC}"
  echo ""
  echo "   ${CYAN}🔁 n8n Webhook / Editor${NC} → https://n8n.dinhduongcantho.io.vn"
  echo "   ${CYAN}🐍 FastAPI Admin UI    ${NC} → https://dinhduongcantho.io.vn/admin (hoặc http://localhost:8000/admin)"
  echo "   ${CYAN}☁️  Cloudflared PID $CF_PID   ${NC} → tail -f $LOG_DIR/cloudflared.log"
  echo "   ${CYAN}🤖 Ollama      PID $OLLAMA_PID ${NC} → tail -f $LOG_DIR/ollama.log"
  echo "   ${CYAN}🐍 Python API  PID $PY_PID   ${NC} → tail -f $LOG_DIR/python_api.log"
  echo ""
  echo "   ${YELLOW}Dừng tất cả:${NC} ./stop_all.sh"
  echo ""

fi
