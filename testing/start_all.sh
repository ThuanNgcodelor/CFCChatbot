#!/usr/bin/env zsh
# ══════════════════════════════════════════════════════════════════
# start_all.sh — Khởi động toàn bộ hệ thống CFC AI / ZeO
# Chạy:
#   ./start_all.sh                 # menu tương tác
#   ./start_all.sh --background    # chạy nền, không dừng process ngoài script
#   ./start_all.sh --test          # core local + readiness + unit/API tests
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

SCRIPT_DIR="${0:A:h}"
N8N_ROOT="${SCRIPT_DIR:h}"
SERVER_DIR="$N8N_ROOT/ChatbotN8n/javis/server"
REDIS_DIR="$N8N_ROOT/ChatbotN8n/infra/redis"
LOG_DIR="$N8N_ROOT/logs"
PYTHON_BIN="$SERVER_DIR/.venv/bin/python"
mkdir -p "$LOG_DIR"

wait_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local i=1
  while (( i <= attempts )); do
    if curl --silent --fail --max-time 2 "$url" >/dev/null 2>&1; then
      echo "   ${GREEN}✓${NC} $name sẵn sàng: $url"
      return 0
    fi
    sleep 1
    (( i++ ))
  done
  echo "   ${RED}✗${NC} $name chưa sẵn sàng sau ${attempts}s: $url"
  return 1
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "${RED}Thiếu command bắt buộc: $command_name${NC}"
    return 1
  fi
}

run_core_tests() {
  echo "${BLUE}▶ [TEST 1/2]${NC} Unit tests PriceConstraint..."
  PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m unittest discover \
    -s "$SERVER_DIR/tests" -p 'test_*.py' -v

  echo "${BLUE}▶ [TEST 2/2]${NC} API smoke tests truy vấn giá..."
  local approx_json
  local strict_json
  local direct_link_json
  approx_json=$(curl --silent --fail --max-time 15 \
    -H 'Content-Type: application/json' \
    -d '{"brand":"zeo","sender_id":"startup_price_approx","text":"Có sản phẩm nào khoảng 200k không?"}' \
    http://127.0.0.1:8000/api/chat-pipeline)
  strict_json=$(curl --silent --fail --max-time 15 \
    -H 'Content-Type: application/json' \
    -d '{"brand":"zeo","sender_id":"startup_price_strict","text":"Có nước giặt nào dưới 200k không?"}' \
    http://127.0.0.1:8000/api/chat-pipeline)
  direct_link_json=$(curl --silent --fail --max-time 15 \
    -H 'Content-Type: application/json' \
    -d '{"brand":"zeo","sender_id":"startup_price_approx","text":"Xin link sản phẩm đó đi"}' \
    http://127.0.0.1:8000/api/chat-pipeline)

  APPROX_JSON="$approx_json" STRICT_JSON="$strict_json" DIRECT_LINK_JSON="$direct_link_json" PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -c '
import json, os
for env_name in ("APPROX_JSON", "STRICT_JSON"):
    payload = json.loads(os.environ[env_name])
    assert payload.get("ok") is True, (env_name, payload)
    assert payload.get("intent") in {"shopee_budget_filter", "shopee_budget_filter_no_result"}, (env_name, payload)
    assert payload.get("answer"), (env_name, payload)
link_payload = json.loads(os.environ["DIRECT_LINK_JSON"])
assert link_payload.get("ok") is True, link_payload
assert link_payload.get("intent") == "shopee_product_link", link_payload
assert link_payload.get("shopee_url") not in {
    "",
    None,
    "https://shopee.vn/zeovietnamofficial",
    "https://shopee.vn/cfccobay",
}, link_payload
print("API price + direct product-link smoke tests: OK")
'
}

START_MODE="${1:-}"
if [[ "$START_MODE" == "--help" || "$START_MODE" == "-h" ]]; then
  echo "Dùng: $0 [--background|--test]"
  echo "  --background  Chạy các service nền; chỉ ghi PID do lần chạy này tạo."
  echo "  --test        Chạy Redis/Ollama/FastAPI local, readiness và test giá; không mở tunnel."
  exit 0
fi

if [[ "$START_MODE" == "--test" ]]; then
  require_command docker
  require_command curl
  [[ -x "$PYTHON_BIN" ]] || { echo "${RED}Không tìm thấy Python venv: $PYTHON_BIN${NC}"; exit 1; }

  echo "${BLUE}▶ [0/3]${NC} Khởi động Redis Stack local..."
  (cd "$REDIS_DIR" && docker compose up -d)

  OLLAMA_PID=""
  if ! curl --silent --fail --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    require_command ollama
    echo "${BLUE}▶ [1/3]${NC} Khởi động Ollama local..."
    OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_NUM_PARALLEL=1 \
      ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!
  else
    echo "${GREEN}✓${NC} Ollama đã chạy, tái sử dụng instance hiện có."
  fi
  wait_http "Ollama" "http://127.0.0.1:11434/api/tags" 30

  PY_PID=""
  if ! curl --silent --fail --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "${BLUE}▶ [2/3]${NC} Khởi động FastAPI local..."
    (cd "$SERVER_DIR" && PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port 8000) \
      > "$LOG_DIR/python_api.log" 2>&1 &
    PY_PID=$!
  else
    echo "${GREEN}✓${NC} FastAPI đã chạy, tái sử dụng instance hiện có."
  fi
  wait_http "FastAPI" "http://127.0.0.1:8000/health" 45

  echo "${OLLAMA_PID:-} ${PY_PID:-}" > "$LOG_DIR/test-pids.txt"
  echo "${BLUE}▶ [3/3]${NC} Chạy kiểm thử tự động..."
  run_core_tests
  echo "${GREEN}${BOLD}✅ Core local và test giá hoàn tất.${NC}"
  echo "Logs: $LOG_DIR"
  exit 0
fi

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

if [[ "$START_MODE" == "--background" ]]; then
  MODE=2
else
  echo "${BOLD}Chọn chế độ khởi động:${NC}"
  echo "  ${GREEN}[1]${NC} Mỗi service trong một cửa sổ Terminal riêng"
  echo "  ${YELLOW}[2]${NC} Chạy tất cả nền, log ra file $LOG_DIR/"
  echo ""
  printf "Nhập lựa chọn [1/2, mặc định 1]: "
  read MODE
  MODE=${MODE:-1}
fi

echo ""

# ══════════════════════════════════════════════════════════════════
if [[ "$MODE" == "1" ]]; then
# ── MODE 1: Mỗi service 1 tab Terminal riêng ─────────────────────

  echo "${BLUE}▶ [0/4]${NC} Kiểm tra & Khởi động ${BOLD}Redis Stack (Docker)${NC}..."
  (cd "$REDIS_DIR" && docker compose up -d 2>/dev/null || true)
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
  open_tab "🐍 Python API :8000" "cd '$SERVER_DIR' && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload; exec zsh"

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

  echo "${BLUE}▶ [0/4]${NC} Kiểm tra & Khởi động ${BOLD}Redis Stack (Docker)${NC}..."
  (cd "$REDIS_DIR" && docker compose up -d 2>/dev/null || true)

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
  (cd "$SERVER_DIR" && \
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
