#!/usr/bin/env zsh
# stop_all.sh — Dừng toàn bộ service CFC AI / ZeO
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

echo ""
echo "${CYAN}⏹  Đang dừng tất cả service...${NC}"

LOG_DIR="$HOME/Documents/David-nguyen/N8n/logs"

# Đọc PIDs đã lưu
if [[ -f "$LOG_DIR/pids.txt" ]]; then
  read -r N8N_PID CF_PID OLLAMA_PID PY_PID < "$LOG_DIR/pids.txt"
  kill "$N8N_PID" 2>/dev/null && echo "  ✓ n8n stopped (PID $N8N_PID)" || true
  kill "$CF_PID"  2>/dev/null && echo "  ✓ cloudflared stopped (PID $CF_PID)" || true
  kill "$OLLAMA_PID" 2>/dev/null && echo "  ✓ ollama stopped (PID $OLLAMA_PID)" || true
  kill "$PY_PID"  2>/dev/null && echo "  ✓ Python API stopped (PID $PY_PID)" || true
  rm -f "$LOG_DIR/pids.txt"
fi

# Fallback: tắt theo tên
pkill -f "npx n8n" 2>/dev/null || true
pkill -f "cloudflared" 2>/dev/null || true
pkill -f "ollama serve" 2>/dev/null || true
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "python main.py" 2>/dev/null || true
lsof -ti tcp:8000 | xargs kill -9 2>/dev/null || true

echo ""
echo "${GREEN}✅ Đã dừng xong.${NC}"
echo ""
