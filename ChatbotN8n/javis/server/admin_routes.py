"""
admin_routes.py — FastAPI Router cho CFC AI Admin Dashboard
Modules: Status, n8n, Customers, Learning Queue, Settings,
         Documents Upload, Shopee CRUD, Sheet Sync, Analytics,
         Chat History, Export CSV, Admin Notes, AI LQ Suggest
"""

import csv
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_settings: dict = {}


def _auto_get_redis_env_pass() -> str:
    """Tự động đọc mật khẩu Redis từ file .env nếu có."""
    for p in [
        Path(__file__).resolve().parents[2] / "infra" / "redis" / ".env",
        Path(__file__).parent / ".env",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("REDIS_PASSWORD="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _cfg() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        _settings = {}
    
    # Tự động điền redis password nếu đang trống
    if not _settings.get("redis", {}).get("password"):
        env_pass = _auto_get_redis_env_pass()
        if env_pass:
            _settings.setdefault("redis", {})["password"] = env_pass

    return _settings


def _get_redis(decode: bool = True) -> aioredis.Redis:
    c = _cfg()["redis"]
    return aioredis.Redis(
        host=c.get("host", "127.0.0.1"),
        port=int(c.get("port", 6379)),
        password=c.get("password", "") or None,
        db=int(c.get("db", 0)),
        decode_responses=decode,
    )


def _n8n_cfg() -> dict:
    return _cfg().get("n8n", {"url": "https://n8n.dinhduongcantho.io.vn", "api_key": ""})


class SettingsUpdateRequest(BaseModel):
    redis: Optional[dict] = None
    ollama: Optional[dict] = None
    n8n: Optional[dict] = None
    rag: Optional[dict] = None
    ai_providers: Optional[dict] = None
    telegram: Optional[dict] = None
    shopee: Optional[dict] = None  # shopee_sheet_url


@router.get("/settings")
async def get_settings():
    """Lấy cấu hình hiện tại để hiển thị trên giao diện Cài đặt."""
    return _cfg()


@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Lưu cấu hình API keys và kết nối trực tiếp từ giao diện Admin."""
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    current_cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}

    if req.redis:
        current_cfg.setdefault("redis", {}).update(req.redis)
    if req.ollama:
        current_cfg.setdefault("ollama", {}).update(req.ollama)
    if req.n8n:
        current_cfg.setdefault("n8n", {}).update(req.n8n)
    if req.rag:
        current_cfg.setdefault("rag", {}).update(req.rag)
    if req.ai_providers:
        current_cfg.setdefault("ai_providers", {}).update(req.ai_providers)
    if req.telegram:
        current_cfg.setdefault("telegram", {}).update(req.telegram)
    if req.shopee:
        current_cfg.setdefault("shopee", {}).update(req.shopee)

    cfg_path.write_text(json.dumps(current_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    _settings = current_cfg

    # Refresh module caches
    try:
        import rag_search, embedder, ai_engine, telegram_notifier
        rag_search._redis_pool = None
        rag_search._settings = {}
        embedder._settings = {}
        ai_engine._settings = {}
        telegram_notifier._settings = {}
    except Exception:
        pass

    return {
        "success": True,
        "message": "Đã lưu cài đặt và API keys thành công!",
        "settings": current_cfg,
    }


# ─────────────────────────────────────────────────────
# MODULE 1: STATUS & DASHBOARD STATS
# ─────────────────────────────────────────────────────

@router.get("/status")
async def system_status():
    """Trạng thái tất cả dịch vụ: Redis, Ollama, n8n, Python API."""
    cfg = _cfg()
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {}
    }

    # Redis
    try:
        r = _get_redis()
        await r.ping()
        info = await r.info("server")
        result["services"]["redis"] = {
            "status": "ok",
            "version": info.get("redis_version", "?"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
        }
        await r.aclose()
    except Exception as e:
        result["services"]["redis"] = {"status": "error", "detail": str(e)}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{cfg['ollama']['base_url']}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            result["services"]["ollama"] = {
                "status": "ok",
                "models": models,
                "embed_model": cfg["ollama"]["embed_model"],
                "embed_ready": any(cfg["ollama"]["embed_model"].split(":")[0] in m for m in models),
            }
    except Exception as e:
        result["services"]["ollama"] = {"status": "error", "detail": str(e)}

    # n8n
    n8n = _n8n_cfg()
    try:
        headers = {"X-N8N-API-KEY": n8n["api_key"]} if n8n.get("api_key") else {}
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{n8n['url']}/api/v1/workflows", headers=headers)
            if resp.status_code == 200:
                wf_data = resp.json()
                workflows = wf_data.get("data", [])
                active_count = sum(1 for w in workflows if w.get("active"))
                result["services"]["n8n"] = {
                    "status": "ok",
                    "url": n8n["url"],
                    "total_workflows": len(workflows),
                    "active_workflows": active_count,
                }
            else:
                result["services"]["n8n"] = {"status": "no_api_key", "url": n8n["url"]}
    except Exception as e:
        result["services"]["n8n"] = {"status": "error", "detail": str(e)}

    # Python API itself
    result["services"]["python_api"] = {"status": "ok", "version": "1.0.0"}

    return result


@router.get("/stats/today")
async def stats_today():
    """Thống kê hôm nay: số khách, brand, lead stage, intent phổ biến."""
    r = _get_redis()
    try:
        stats = {
            "zeo": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "cfc": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "total_customers": 0,
        }

        for brand in ["zeo", "cfc"]:
            pattern = f"{brand}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            stats[brand]["customers"] = len(keys)
            stats["total_customers"] += len(keys)

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                stage = profile.get("lead_stage", "new")
                stats[brand]["lead_stages"][stage] = stats[brand]["lead_stages"].get(stage, 0) + 1
                intent = profile.get("last_intent", "")
                if intent:
                    stats[brand]["top_intents"][intent] = stats[brand]["top_intents"].get(intent, 0) + 1

            # Sort top intents
            stats[brand]["top_intents"] = dict(
                sorted(stats[brand]["top_intents"].items(), key=lambda x: -x[1])[:8]
            )

        # Learning queue counts
        for brand in ["zeo", "cfc"]:
            lq_key = f"{brand}:learning:queue"
            lq_len = await r.llen(lq_key) if await r.exists(lq_key) else 0
            stats[brand]["learning_queue_count"] = lq_len

        return stats
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE 2: N8N CONTROL
# ─────────────────────────────────────────────────────

async def _n8n_request(method: str, path: str, body: dict = None):
    n8n = _n8n_cfg()
    headers = {
        "Content-Type": "application/json",
        "X-N8N-API-KEY": n8n.get("api_key", ""),
    }
    url = f"{n8n['url']}/api/v1{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        elif method == "PATCH":
            resp = await client.patch(url, headers=headers, json=body or {})
        else:
            raise ValueError(f"Unknown method: {method}")
    return resp


@router.get("/n8n/workflows")
async def list_n8n_workflows():
    """Danh sách workflow n8n và trạng thái active."""
    try:
        resp = await _n8n_request("GET", "/workflows?limit=50")
        if resp.status_code != 200:
            return {"error": f"n8n trả về {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        workflows = [
            {
                "id": w["id"],
                "name": w["name"],
                "active": w.get("active", False),
                "updatedAt": w.get("updatedAt", ""),
                "tags": [t["name"] for t in w.get("tags", [])],
            }
            for w in data
        ]
        return {"workflows": workflows, "total": len(workflows)}
    except Exception as e:
        return {"error": str(e), "workflows": []}


@router.post("/n8n/workflows/{workflow_id}/toggle")
async def toggle_workflow(workflow_id: str):
    """Bật hoặc tắt một workflow."""
    try:
        # Lấy trạng thái hiện tại
        resp = await _n8n_request("GET", f"/workflows/{workflow_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Workflow không tìm thấy")
        wf = resp.json()
        is_active = wf.get("active", False)

        if is_active:
            resp2 = await _n8n_request("POST", f"/workflows/{workflow_id}/deactivate")
        else:
            resp2 = await _n8n_request("POST", f"/workflows/{workflow_id}/activate")

        return {"id": workflow_id, "name": wf.get("name"), "active": not is_active, "changed": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/n8n/executions")
async def list_executions(limit: int = Query(20, le=50)):
    """Lịch sử chạy workflow gần nhất."""
    try:
        resp = await _n8n_request("GET", f"/executions?limit={limit}&status=all")
        if resp.status_code != 200:
            return {"error": f"n8n {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        executions = [
            {
                "id": e["id"],
                "workflowId": e.get("workflowId"),
                "workflowName": e.get("workflowData", {}).get("name", "?"),
                "status": e.get("status", "?"),
                "startedAt": e.get("startedAt", ""),
                "stoppedAt": e.get("stoppedAt", ""),
            }
            for e in data
        ]
        return {"executions": executions}
    except Exception as e:
        return {"error": str(e), "executions": []}


@router.post("/n8n/sync-knowledge")
async def trigger_knowledge_sync(brand: str = Query("all")):
    """Trigger đồng bộ Knowledge từ Google Sheets lên Redis + Vector Index."""
    from knowledge_sync import sync_brand
    if brand == "all":
        zeo = await sync_brand("zeo")
        cfc = await sync_brand("cfc")
        return {"zeo": zeo, "cfc": cfc}
    result = await sync_brand(brand)
    return result


# ─────────────────────────────────────────────────────
# n8n: EXECUTIONS THEO TỪNG WORKFLOW (PHÂN TRANG)
# ─────────────────────────────────────────────────────

@router.get("/n8n/workflows/{workflow_id}/executions")
async def list_workflow_executions(
    workflow_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=5, le=100),
    status: str = Query("all"),  # all | success | error | running | waiting
):
    """Lịch sử execution của 1 workflow, có phân trang và filter trạng thái."""
    try:
        # n8n API hỗ trợ filter theo workflowId
        params = f"?workflowId={workflow_id}&limit={limit}&includeData=false"
        if status != "all":
            params += f"&status={status}"
        resp = await _n8n_request("GET", f"/executions{params}")
        if resp.status_code != 200:
            return {"error": f"n8n {resp.status_code}", "executions": [], "total": 0}

        data = resp.json()
        all_execs = data.get("data", [])
        total = data.get("count", len(all_execs))

        # Thống kê nhanh
        stats = {"success": 0, "error": 0, "running": 0, "waiting": 0, "other": 0}
        parsed = []
        for e in all_execs:
            st = e.get("status", "other")
            stats[st] = stats.get(st, 0) + 1
            started = e.get("startedAt", "")
            stopped = e.get("stoppedAt", "")
            duration_ms = None
            if started and stopped:
                try:
                    from datetime import datetime as _dt
                    t0 = _dt.fromisoformat(started.replace("Z", "+00:00"))
                    t1 = _dt.fromisoformat(stopped.replace("Z", "+00:00"))
                    duration_ms = int((t1 - t0).total_seconds() * 1000)
                except Exception:
                    pass
            parsed.append({
                "id": e["id"],
                "workflowId": e.get("workflowId", workflow_id),
                "workflowName": e.get("workflowData", {}).get("name", "?"),
                "status": st,
                "mode": e.get("mode", ""),
                "startedAt": started,
                "stoppedAt": stopped,
                "durationMs": duration_ms,
                "retryOf": e.get("retryOf"),
            })

        return {
            "executions": parsed,
            "total": total,
            "page": page,
            "limit": limit,
            "stats": stats,
            "pages": max(1, (total + limit - 1) // limit),
        }
    except Exception as e:
        return {"error": str(e), "executions": [], "total": 0}


@router.get("/n8n/workflows/{workflow_id}/detail")
async def workflow_detail(workflow_id: str):
    """Chi tiết workflow: node count, tags, updatedAt, active status."""
    try:
        resp = await _n8n_request("GET", f"/workflows/{workflow_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Workflow không tìm thấy")
        w = resp.json()
        nodes = w.get("nodes", [])
        node_types = {}
        for n in nodes:
            t = n.get("type", "").split(".")[-1]
            node_types[t] = node_types.get(t, 0) + 1
        return {
            "id": w["id"],
            "name": w.get("name"),
            "active": w.get("active", False),
            "updatedAt": w.get("updatedAt"),
            "createdAt": w.get("createdAt"),
            "nodeCount": len(nodes),
            "nodeTypes": node_types,
            "tags": [t["name"] for t in w.get("tags", [])],
            "settings": w.get("settings", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────
# n8n: FILE STATUS — kiểm tra file .ts đã thay đổi chưa
# ─────────────────────────────────────────────────────

_WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows" / "local-n8n"

# Map workflow_id → filename (đọc từ file .ts bằng regex)
def _discover_workflow_files() -> dict:
    """Quét thư mục workflows/local-n8n/*.ts, trả dict {workflow_id: path}."""
    result = {}
    if not _WORKFLOW_DIR.exists():
        return result
    for ts_file in _WORKFLOW_DIR.glob("*.workflow.ts"):
        content = ts_file.read_text(encoding="utf-8", errors="ignore")
        import re as _re
        # Tìm @workflow({ id: '...' })
        m = _re.search(r"@workflow\(\s*\{[^}]*?id\s*:\s*['\"]([^'\"]+)['\"]", content, _re.DOTALL)
        if m:
            result[m.group(1)] = ts_file
    return result


@router.get("/n8n/file-status")
async def n8n_file_status():
    """
    Kiểm tra file .ts local có thay đổi chưa push lên n8n không.
    Logic: So sánh mtime của file local với updatedAt từ n8n API.
    Nếu file local mới hơn → has_changes = True (cần push).
    Nếu bằng hoặc cũ hơn → không có thay đổi.
    """
    files_info = []
    try:
        # Bước 1: Lấy danh sách file local
        wf_map = _discover_workflow_files()
        if not wf_map:
            return {"files": [], "note": "Không tìm thấy file .ts trong workflows/local-n8n/"}

        # Bước 2: Lấy updatedAt từ n8n API một lần cho tất cả workflows
        n8n_updated: dict = {}  # {workflow_id: datetime}
        try:
            resp = await _n8n_request("GET", "/workflows?limit=50")
            if resp.status_code == 200:
                for w in resp.json().get("data", []):
                    raw_ts = w.get("updatedAt", "")
                    if raw_ts:
                        try:
                            n8n_updated[w["id"]] = datetime.fromisoformat(
                                raw_ts.replace("Z", "+00:00")
                            )
                        except Exception:
                            pass
        except Exception:
            pass  # Không lấy được n8n data → fallback về Redis

        # Bước 3: Lấy timestamp từ deploy-log trong Redis làm fallback
        r = _get_redis()
        redis_push_ts: dict = {}  # {workflow_id: float}
        for wf_id in wf_map:
            raw = await r.get(f"n8n:deploy:last:{wf_id}")
            if raw:
                try:
                    redis_push_ts[wf_id] = float(raw)
                except Exception:
                    pass

        # Bước 4: So sánh và build kết quả
        for wf_id, ts_path in wf_map.items():
            stat = ts_path.stat()
            file_mtime = stat.st_mtime
            file_mtime_dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc)

            # Ưu tiên: so với n8n updatedAt → chính xác nhất
            if wf_id in n8n_updated:
                n8n_dt = n8n_updated[wf_id]
                # Có thay đổi nếu file local mới hơn n8n, tính thêm buffer 60s
                # (để tránh hiện "chưa push" do lệch đồng hồ nhỏ)
                has_changes = (file_mtime_dt - n8n_dt).total_seconds() > 60
                baseline_source = "n8n"
                baseline_at = n8n_dt.isoformat()
            elif wf_id in redis_push_ts:
                # Fallback: so với Redis deploy log
                push_dt = datetime.fromtimestamp(redis_push_ts[wf_id], tz=timezone.utc)
                has_changes = (file_mtime_dt - push_dt).total_seconds() > 60
                baseline_source = "deploy_log"
                baseline_at = push_dt.isoformat()
            else:
                # Workflow chưa bao giờ được theo dõi → không hiện badge
                # (không có gì để so sánh, không kết luận "chưa push")
                has_changes = False
                baseline_source = "none"
                baseline_at = None

            files_info.append({
                "workflow_id": wf_id,
                "filename": ts_path.name,
                "last_modified": file_mtime_dt.isoformat(),
                "baseline_at": baseline_at,
                "baseline_source": baseline_source,
                "has_changes": has_changes,
            })

    except Exception as e:
        return {"error": str(e), "files": []}
    return {"files": files_info}


# ─────────────────────────────────────────────────────
# n8n: DEPLOY — Chạy n8nac push, xử lý conflict tự động
# ─────────────────────────────────────────────────────

import asyncio as _asyncio
import subprocess as _subprocess


async def _run_cmd(cmd: list, cwd: str) -> tuple:
    """Chạy shell command async, trả về (returncode, stdout, stderr)."""
    proc = await _asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=_asyncio.subprocess.PIPE,
        stderr=_asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


class DeployRequest(BaseModel):
    workflow_file: str  # e.g. "cfc_cobay_chatbot.workflow.ts"
    auto_resolve_conflict: bool = True  # Tự động resolve conflict bằng keep-current


@router.post("/n8n/deploy")
async def deploy_workflow(req: DeployRequest):
    """
    Deploy workflow lên n8n bằng n8nac push.
    Nếu conflict → tự động resolve --mode keep-current rồi push lại.
    Sau deploy → tự động bật lại workflow nếu bị tắt do quá trình push.
    Ghi log vào Redis.
    """
    r = _get_redis()
    workspace = str(Path(__file__).resolve().parents[2])  # ChatbotN8n/
    ts_path = _WORKFLOW_DIR / req.workflow_file

    if not ts_path.exists():
        raise HTTPException(status_code=404, detail=f"File không tồn tại: {req.workflow_file}")

    # Lấy workflow_id từ file
    wf_map = _discover_workflow_files()
    wf_id = next((k for k, v in wf_map.items() if v.name == req.workflow_file), None)
    if not wf_id:
        raise HTTPException(status_code=400, detail="Không tìm thấy workflow ID trong file .ts")

    logs = []
    deploy_ok = False
    error_msg = ""

    # Lưu trạng thái active TRƯỚC khi push để restore sau
    was_active = False
    try:
        resp_before = await _n8n_request("GET", f"/workflows/{wf_id}")
        if resp_before.status_code == 200:
            was_active = resp_before.json().get("active", False)
            logs.append(f"📋 Trạng thái trước push: {'Active' if was_active else 'Inactive'}")
    except Exception:
        pass

    def _has_conflict(out: str, err: str) -> bool:
        """n8nac push --verify trả rc=0 dù có conflict → phải check stdout/stderr."""
        combined = (out + err).lower()
        return "conflict detected" in combined or "💥 conflict" in combined

    try:
        # Bước 1: n8nac push --verify
        logs.append(f"▶ Pushing {req.workflow_file}...")
        push_cmd = ["npx", "--yes", "n8nac", "push", f"workflows/local-n8n/{req.workflow_file}", "--verify"]
        rc, out, err = await _run_cmd(push_cmd, cwd=workspace)
        logs.append(f"stdout: {out.strip()}")
        if err.strip():
            logs.append(f"stderr: {err.strip()}")

        # ⚠️ FIX: n8nac trả rc=0 kể cả khi có conflict → phải check stdout
        if rc == 0 and not _has_conflict(out, err):
            deploy_ok = True
            logs.append("✅ Push thành công!")

        elif _has_conflict(out, err) and req.auto_resolve_conflict:
            # Bước 2: Conflict → resolve --mode keep-current
            logs.append(f"⚠️ Phát hiện conflict. Đang resolve với keep-current (giữ code local)...")
            resolve_cmd = ["npx", "--yes", "n8nac", "resolve", wf_id, "--mode", "keep-current"]
            rc2, out2, err2 = await _run_cmd(resolve_cmd, cwd=workspace)
            logs.append(f"resolve: {out2.strip()}")
            if err2.strip():
                logs.append(f"resolve stderr: {err2.strip()}")

            if rc2 == 0:
                # Bước 3: Push lại sau resolve
                logs.append("▶ Push lại sau resolve...")
                rc3, out3, err3 = await _run_cmd(push_cmd, cwd=workspace)
                logs.append(f"re-push: {out3.strip()}")
                if err3.strip():
                    logs.append(f"re-push stderr: {err3.strip()}")
                if rc3 == 0 and not _has_conflict(out3, err3):
                    deploy_ok = True
                    logs.append("✅ Push thành công sau resolve!")
                else:
                    error_msg = (out3 + err3).strip()
                    logs.append(f"❌ Re-push thất bại: {error_msg[:200]}")
            else:
                error_msg = f"Resolve thất bại: {out2} {err2}"
                logs.append(f"❌ {error_msg[:200]}")
        else:
            error_msg = (out + err).strip()
            logs.append(f"❌ Push thất bại (rc={rc}): {error_msg[:200]}")

    except Exception as e:
        error_msg = str(e)
        logs.append(f"❌ Exception: {e}")

    # Ghi deploy log vào Redis
    now_ts = datetime.now(timezone.utc)
    log_entry = json.dumps({
        "workflow_id": wf_id,
        "filename": req.workflow_file,
        "success": deploy_ok,
        "error": error_msg,
        "logs": logs,
        "deployed_at": now_ts.isoformat(),
    }, ensure_ascii=False)
    await r.rpush("n8n:deploy:log", log_entry)
    await r.ltrim("n8n:deploy:log", -50, -1)

    if deploy_ok:
        # Cập nhật timestamp push cuối vào Redis
        await r.set(f"n8n:deploy:last:{wf_id}", str(now_ts.timestamp()))

        # ⚠️ FIX: n8nac push thường deactivate workflow → tự động bật lại nếu trước đó Active
        if was_active:
            try:
                resp_after = await _n8n_request("GET", f"/workflows/{wf_id}")
                if resp_after.status_code == 200:
                    is_still_active = resp_after.json().get("active", False)
                    if not is_still_active:
                        logs.append("🔄 Workflow bị tắt sau push → đang bật lại...")
                        await _n8n_request("POST", f"/workflows/{wf_id}/activate")
                        logs.append("✅ Đã bật lại workflow (Active)!")
                    else:
                        logs.append("✅ Workflow vẫn Active sau push.")
            except Exception as e:
                logs.append(f"⚠️ Không thể kiểm tra/bật lại workflow: {e}")

        # Cập nhật log entry sau khi đã bật lại
        await r.lset("n8n:deploy:log", -1, json.dumps({
            "workflow_id": wf_id,
            "filename": req.workflow_file,
            "success": deploy_ok,
            "error": error_msg,
            "logs": logs,
            "deployed_at": now_ts.isoformat(),
        }, ensure_ascii=False))

        # Thông báo WebSocket
        await r.publish("n8n:deploy:event", json.dumps({
            "wf_id": wf_id, "filename": req.workflow_file, "status": "success"
        }))

    if not deploy_ok:
        raise HTTPException(status_code=500, detail={"error": error_msg, "logs": logs})

    return {
        "ok": True,
        "workflow_id": wf_id,
        "filename": req.workflow_file,
        "logs": logs,
        "deployed_at": now_ts.isoformat(),
    }



@router.get("/n8n/deploy-log")
async def get_deploy_log():
    """Lịch sử các lần deploy workflow gần nhất (tối đa 50)."""
    r = _get_redis()
    try:
        raw_logs = await r.lrange("n8n:deploy:log", -30, -1)
        entries = [json.loads(l) for l in raw_logs]
        entries.reverse()  # Mới nhất lên đầu
        return {"logs": entries, "total": len(entries)}
    except Exception as e:
        return {"error": str(e), "logs": []}


# ─────────────────────────────────────────────────────
# n8n: WEBSOCKET — File Watcher real-time
# ─────────────────────────────────────────────────────

from fastapi import WebSocket, WebSocketDisconnect

# Giữ danh sách client đang kết nối
_ws_clients: list = []


@router.websocket("/n8n/ws/file-watch")
async def websocket_file_watch(websocket: WebSocket):
    """
    WebSocket endpoint: Push thông báo real-time khi file .ts thay đổi
    hoặc khi có deploy mới.
    Client kết nối tới: ws://localhost:8000/admin/n8n/ws/file-watch
    """
    await websocket.accept()
    _ws_clients.append(websocket)

    # Snapshot mtime hiện tại
    file_mtimes: dict = {}
    wf_map = _discover_workflow_files()
    for wf_id, ts_path in wf_map.items():
        try:
            file_mtimes[wf_id] = ts_path.stat().st_mtime
        except Exception:
            pass

    try:
        # Gửi trạng thái ban đầu
        await websocket.send_json({"type": "connected", "message": "File watcher ready", "files": len(wf_map)})

        while True:
            # Poll mỗi 3 giây
            await _asyncio.sleep(3)
            wf_map = _discover_workflow_files()
            changed = []
            for wf_id, ts_path in wf_map.items():
                try:
                    mtime = ts_path.stat().st_mtime
                    if mtime != file_mtimes.get(wf_id, 0):
                        file_mtimes[wf_id] = mtime
                        changed.append({
                            "workflow_id": wf_id,
                            "filename": ts_path.name,
                            "modified_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                        })
                except Exception:
                    pass

            if changed:
                await websocket.send_json({"type": "file_changed", "changed": changed})

    except (WebSocketDisconnect, _asyncio.CancelledError):
        pass
    except Exception:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


async def _broadcast_ws(event: dict):
    """Broadcast event đến tất cả WebSocket client đang kết nối."""
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ─────────────────────────────────────────────────────
# MODULE 3: CUSTOMER CONVERSATIONS
# ─────────────────────────────────────────────────────

@router.get("/customers")
async def list_customers(brand: str = Query("all"), page: int = 1, page_size: int = 20):
    """Danh sách khách hàng và thông tin profile."""
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand]
        all_customers = []

        for b in brands:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                sender_id = key.split(":")[-1]
                all_customers.append({
                    "sender_id": sender_id,
                    "brand": b.upper(),
                    "fb_name": profile.get("fb_name", ""),
                    "phone": profile.get("phone", "") or profile.get("customer_phone", ""),
                    "area": profile.get("area", "") or profile.get("customer_location", ""),
                    "lead_stage": profile.get("lead_stage", "new"),
                    "last_intent": profile.get("last_intent", ""),
                    "last_need": profile.get("last_need", ""),
                    "last_seen_at": profile.get("last_seen_at", ""),
                    "first_seen_at": profile.get("first_seen_at", ""),
                })

        # Sort by last_seen_at desc
        all_customers.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
        total = len(all_customers)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "customers": all_customers[start:end],
        }
    finally:
        await r.aclose()


@router.get("/customers/{brand}/{sender_id}/session")
async def get_customer_session(brand: str, sender_id: str):
    """Xem session chat của 1 khách."""
    r = _get_redis()
    b = brand.lower()
    try:
        profile_raw = await r.get(f"{b}:customer:messenger:{sender_id}")
        session_raw = await r.get(f"{b}:session:messenger:{sender_id}")

        profile = json.loads(profile_raw) if profile_raw else {}
        session = json.loads(session_raw) if session_raw else {}

        return {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "profile": profile,
            "session": session,
        }
    finally:
        await r.aclose()


class CustomerUpdateRequest(BaseModel):
    fb_name: Optional[str] = None
    phone: Optional[str] = None
    area: Optional[str] = None
    lead_stage: Optional[str] = None
    last_intent: Optional[str] = None
    admin_notes: Optional[str] = None  # B3: Admin notes nội bộ
    admin_tags: Optional[List[str]] = None  # B3: Tags [HOT LEAD, CHỜ BÁO GIÁ, ...]


@router.put("/customers/{brand}/{sender_id}")
async def update_customer(brand: str, sender_id: str, req: CustomerUpdateRequest):
    """Chỉnh sửa thông tin khách hàng (SĐT, Khu vực, Tên, Lead stage) trong Redis."""
    r = _get_redis()
    b = brand.lower()
    customer_key = f"{b}:customer:messenger:{sender_id}"
    session_key = f"{b}:session:messenger:{sender_id}"
    try:
        raw_cust = await r.get(customer_key)
        profile = json.loads(raw_cust) if raw_cust else {}

        if req.fb_name is not None:
            profile["fb_name"] = req.fb_name
        if req.phone is not None:
            profile["phone"] = req.phone
            profile["customer_phone"] = req.phone
        if req.area is not None:
            profile["area"] = req.area
            profile["customer_location"] = req.area
        if req.lead_stage is not None:
            profile["lead_stage"] = req.lead_stage
        if req.last_intent is not None:
            profile["last_intent"] = req.last_intent
        if req.admin_notes is not None:
            profile["admin_notes"] = req.admin_notes
        if req.admin_tags is not None:
            profile["admin_tags"] = req.admin_tags

        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        await r.set(customer_key, json.dumps(profile, ensure_ascii=False))

        # Cập nhật cả session tương ứng nếu có
        raw_sess = await r.get(session_key)
        if raw_sess:
            sess = json.loads(raw_sess)
            if req.phone is not None:
                sess["customer_phone"] = req.phone
            if req.area is not None:
                sess["customer_location"] = req.area
            if req.lead_stage is not None:
                sess["lead_stage"] = req.lead_stage
            await r.set(session_key, json.dumps(sess, ensure_ascii=False))

        # Tự động bắn thông báo Telegram nếu có SĐT hoặc Lead sẵn sàng
        phone_val = profile.get("phone", "") or profile.get("customer_phone", "")
        if phone_val and len(re.findall(r"\d", phone_val)) >= 9:
            try:
                from telegram_notifier import notify_new_lead
                await notify_new_lead(
                    brand=brand,
                    phone=phone_val,
                    area=profile.get("area", "") or profile.get("customer_location", ""),
                    fb_name=profile.get("fb_name", ""),
                    need=profile.get("last_intent", "") or profile.get("last_need", ""),
                    sender_id=sender_id,
                )
            except Exception:
                pass

        return {"success": True, "message": "Đã cập nhật thông tin khách hàng thành công!", "profile": profile}
    finally:
        await r.aclose()


@router.delete("/customers/{brand}/{sender_id}")
async def delete_customer(brand: str, sender_id: str):
    """Xóa hoàn toàn hồ sơ và session của khách hàng khỏi Redis."""
    r = _get_redis()
    b = brand.lower()
    try:
        await r.delete(f"{b}:customer:messenger:{sender_id}")
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã xóa hoàn toàn khách hàng {sender_id} khỏi Redis"}
    finally:
        await r.aclose()


@router.delete("/customers/{brand}/{sender_id}/session")
async def reset_customer_session(brand: str, sender_id: str):
    """Reset session chat (giúp bot bắt đầu lại hội thoại)."""
    r = _get_redis()
    b = brand.lower()
    try:
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã reset session của {sender_id}"}
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE 4: LEARNING QUEUE
# ─────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    intent: str
    question_examples: str  # Phân cách bằng ";"
    answer: str
    category: str = "faq"
    answer_mode: str = "rewrite"
    risk_level: str = "low"


@router.get("/learning-queue")
async def get_learning_queue(brand: str = Query("all"), limit: int = 50):
    """Lấy danh sách câu hỏi bot chưa chắc / khách phàn nàn để review."""
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand]
        items = []

        for b in brands:
            lq_key = f"{b}:learning:queue"
            # Thử cả 2 kiểu key
            lq_key_alt = f"{b}:kb:learning:queue"

            for key in [lq_key, lq_key_alt]:
                key_type = await r.type(key)
                if key_type == "none":
                    continue

                if key_type == "list":
                    raw_items = await r.lrange(key, 0, limit - 1)
                elif key_type == "set":
                    raw_items = list(await r.smembers(key))[:limit]
                else:
                    continue

                for raw in raw_items:
                    try:
                        item = json.loads(raw)
                        item["brand"] = b.upper()
                        item["queue_key"] = key
                        items.append(item)
                    except Exception:
                        items.append({"raw": raw, "brand": b.upper(), "queue_key": key})

        return {"total": len(items), "items": items}
    finally:
        await r.aclose()


@router.post("/learning-queue/dismiss")
async def dismiss_queue_item(brand: str, queue_key: str, raw_value: str):
    """Xóa 1 item khỏi learning queue (bỏ qua)."""
    r = _get_redis()
    try:
        removed = await r.lrem(queue_key, 1, raw_value)
        return {"success": removed > 0}
    finally:
        await r.aclose()


@router.post("/learning-queue/approve")
async def approve_and_add_to_faq(brand: str, req: ApproveRequest):
    """
    Duyệt 1 câu từ Learning Queue → thêm vào Redis KB snapshot + re-sync vector.
    NOTE: Cần tự thêm vào Google Sheets riêng nếu muốn persist lâu dài.
    """
    from knowledge_sync import sync_brand, ensure_index, build_embed_text
    from embedder import embed_text as get_embed, vec_to_bytes, get_embed_dim

    r = _get_redis(decode=False)
    r_text = _get_redis(decode=True)

    try:
        # Đọc snapshot hiện tại
        kb_key = f"{brand.lower()}:kb:basic:active"
        raw = await r_text.get(kb_key)
        if not raw:
            raise HTTPException(status_code=404, detail=f"KB key '{kb_key}' không tìm thấy")

        data = json.loads(raw)
        if isinstance(data, dict):
            items_raw = data.get("snapshot_json") or data.get("knowledgeItems") or "[]"
            items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
            wrapper = data
        else:
            items = data
            wrapper = None

        # Tạo item mới
        new_item = {
            "active": True,
            "brand": brand.upper(),
            "category": req.category,
            "intent": req.intent,
            "question_examples": req.question_examples,
            "answer": req.answer,
            "priority": 80,
            "source_id": f"learning_approved_{int(time.time())}",
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "audience": "customer",
            "answer_mode": req.answer_mode,
            "risk_level": req.risk_level,
        }

        # Thêm vào list và lưu lại
        items.append(new_item)
        if wrapper:
            wrapper["snapshot_json"] = json.dumps(items, ensure_ascii=False)
            await r_text.set(kb_key, json.dumps(wrapper, ensure_ascii=False))
        else:
            await r_text.set(kb_key, json.dumps(items, ensure_ascii=False))

        # Re-sync vector index cho item mới
        cfg = _cfg()
        index_name = f"{brand.lower()}:vec:faq"
        embed_dim = get_embed_dim()
        await ensure_index(r, index_name, embed_dim)

        embed_text_str = build_embed_text(new_item)
        vec = await get_embed(embed_text_str)
        if vec:
            doc_key = f"{index_name}:doc:{new_item['source_id']}:{req.intent}"
            await r.hset(doc_key, mapping={
                "embedding": vec_to_bytes(vec),
                "intent": req.intent,
                "brand": brand.upper(),
                "category": req.category,
                "answer": req.answer,
                "answer_mode": req.answer_mode,
                "risk_level": req.risk_level,
                "source_id": new_item["source_id"],
                "priority": 80,
            })

        return {"success": True, "intent": req.intent, "message": "Đã thêm vào KB và cập nhật Vector Index"}
    finally:
        await r.aclose()
        await r_text.aclose()


@router.post("/test/query")
async def test_query(query: str, brand: str = "zeo"):
    """Test 1 câu hỏi qua Semantic Search — xem bot sẽ trả lời gì."""
    from rag_search import semantic_search
    result = await semantic_search(query=query, brand=brand, top_k=5)
    return result


# ─────────────────────────────────────────────────────
# MODULE: DOCUMENT KNOWLEDGE INGESTION (.md / .txt)
# ─────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents():
    """Danh sách tất cả tài liệu Markdown / Text trong thư mục knowledge/."""
    knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    docs = []
    for file in knowledge_dir.glob("*"):
        if file.suffix.lower() in [".md", ".txt"]:
            stat = file.stat()
            docs.append({
                "name": file.name,
                "size_kb": round(stat.st_size / 1024, 2),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "brand": "CFC" if "cfc" in file.name.lower() or "co_bay" in file.name.lower() else "ZEO",
            })
    return {"total": len(docs), "documents": docs}


@router.post("/documents/sync")
async def sync_all_documents():
    """Quét và đồng bộ toàn bộ tài liệu Markdown trong knowledge/ vào Redis Vector Index."""
    from document_ingestor import ingest_knowledge_folder
    res = await ingest_knowledge_folder()
    return {"success": True, "message": "Đã đồng bộ toàn bộ tài liệu Markdown vào Redis Vector Index", "result": res}


class ExtractFaqRequest(BaseModel):
    document_name: Optional[str] = None
    text: Optional[str] = None
    brand: str = "zeo"


@router.post("/documents/extract-faq")
async def extract_faqs_endpoint(req: ExtractFaqRequest):
    """Dùng AI tự động sinh các câu hỏi - câu trả lời FAQ chuẩn từ tài liệu."""
    from document_ingestor import ai_extract_faqs
    doc_text = req.text or ""
    if not doc_text and req.document_name:
        doc_path = Path(__file__).resolve().parents[2] / "knowledge" / req.document_name
        if doc_path.exists():
            doc_text = doc_path.read_text(encoding="utf-8")

    if not doc_text:
        raise HTTPException(status_code=400, detail="Không có nội dung tài liệu để trích xuất")

    faqs = await ai_extract_faqs(doc_text, brand=req.brand)
    return {"success": True, "brand": req.brand, "faqs_count": len(faqs), "faqs": faqs}


# ─────────────────────────────────────────────────────
# MODULE: CHAT HISTORY (B1)
# ─────────────────────────────────────────────────────

@router.get("/customers/{brand}/{sender_id}/history")
async def get_customer_history(brand: str, sender_id: str):
    """Lấy toàn bộ lịch sử hội thoại của 1 khách hàng từ Redis."""
    r = _get_redis()
    b = brand.lower()
    try:
        # Lịch sử lưu theo nhiều key pattern
        history_keys = [
            f"{b}:history:messenger:{sender_id}",
            f"{b}:chat:history:{sender_id}",
            f"{b}:session:history:{sender_id}",
        ]
        messages = []
        for hkey in history_keys:
            key_type = await r.type(hkey)
            if key_type == "list":
                raw_msgs = await r.lrange(hkey, 0, 100)
                for raw in raw_msgs:
                    try:
                        msg = json.loads(raw)
                        messages.append(msg)
                    except Exception:
                        messages.append({"raw": str(raw)})
                break
            elif key_type == "string":
                raw = await r.get(hkey)
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            messages = parsed
                        else:
                            messages = [parsed]
                    except Exception:
                        pass
                break

        # Nếu không có key history riêng, lấy từ session
        if not messages:
            session_raw = await r.get(f"{b}:session:messenger:{sender_id}")
            if session_raw:
                sess = json.loads(session_raw)
                # Lấy các trường chat trong session
                history_field = sess.get("conversation_history") or sess.get("messages") or []
                if isinstance(history_field, list):
                    messages = history_field
                elif isinstance(history_field, str):
                    try:
                        messages = json.loads(history_field)
                    except Exception:
                        pass

        return {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "total_messages": len(messages),
            "messages": messages,
        }
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE: EXPORT CSV (B2)
# ─────────────────────────────────────────────────────

@router.get("/customers/export")
async def export_customers_csv(
    brand: str = Query("all"),
    has_phone: Optional[bool] = None,
    lead_stage: Optional[str] = None,
):
    """Xuất danh sách khách hàng ra file CSV."""
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        all_customers = []
        for b in brands:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=200)
                for key in keys:
                    raw = await r.get(key)
                    if not raw:
                        continue
                    try:
                        profile = json.loads(raw)
                    except Exception:
                        continue
                    sender_id = key.split(":")[-1]
                    phone_val = profile.get("phone", "") or profile.get("customer_phone", "")
                    stage = profile.get("lead_stage", "new")

                    # Filters
                    if has_phone is True and not phone_val:
                        continue
                    if has_phone is False and phone_val:
                        continue
                    if lead_stage and stage != lead_stage:
                        continue

                    all_customers.append({
                        "brand": b.upper(),
                        "sender_id": sender_id,
                        "fb_name": profile.get("fb_name", ""),
                        "phone": phone_val,
                        "area": profile.get("area", "") or profile.get("customer_location", ""),
                        "lead_stage": stage,
                        "last_intent": profile.get("last_intent", ""),
                        "admin_notes": profile.get("admin_notes", ""),
                        "admin_tags": ", ".join(profile.get("admin_tags", [])),
                        "first_seen_at": profile.get("first_seen_at", ""),
                        "last_seen_at": profile.get("last_seen_at", ""),
                    })
                if cursor == 0:
                    break

        # Sort by last_seen_at desc
        all_customers.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)

        # Build CSV
        output = io.StringIO()
        fieldnames = ["brand", "sender_id", "fb_name", "phone", "area",
                      "lead_stage", "last_intent", "admin_notes", "admin_tags",
                      "first_seen_at", "last_seen_at"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_customers)

        filename = f"cfc_ai_customers_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE: TELEGRAM ENDPOINTS
# ─────────────────────────────────────────────────────

class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str


@router.post("/telegram/test")
async def test_telegram_endpoint(req: TelegramTestRequest):
    """Kiểm thử gửi tin nhắn qua Telegram Bot."""
    from telegram_notifier import test_telegram
    res = await test_telegram(req.bot_token, req.chat_id)
    return res


# ─────────────────────────────────────────────────────
# MODULE: SHOPEE CATALOG CRUD (A2a)
# ─────────────────────────────────────────────────────

def _shopee_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge" / "shopee_catalog.json"


def _load_raw_catalog() -> list:
    p = _shopee_catalog_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_catalog(items: list):
    p = _shopee_catalog_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    # Invalidate cache
    try:
        import shopee_matcher
        shopee_matcher._catalog_cache = None
    except Exception:
        pass


class ShopeeProductRequest(BaseModel):
    brand: str
    name: str
    variant: Optional[str] = ""
    price: Optional[str] = ""
    promotion: Optional[str] = ""
    shopee_url: str
    keywords: Optional[List[str]] = []


@router.get("/shopee/catalog")
async def get_shopee_catalog():
    """Lấy toàn bộ danh mục sản phẩm Shopee hiện có."""
    items = _load_raw_catalog()
    # Thêm index cho từng item
    for i, item in enumerate(items):
        item["_idx"] = i
    return {"total": len(items), "products": items}


@router.post("/shopee/products")
async def add_shopee_product(req: ShopeeProductRequest):
    """Thêm sản phẩm Shopee mới vào catalog."""
    items = _load_raw_catalog()
    new_item = {
        "brand": req.brand.upper(),
        "name": req.name,
        "variant": req.variant or "",
        "price": req.price or "",
        "promotion": req.promotion or "",
        "shopee_url": req.shopee_url,
        "keywords": req.keywords or [],
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    items.append(new_item)
    _save_catalog(items)
    return {"success": True, "total": len(items), "product": new_item}


@router.put("/shopee/products/{idx}")
async def update_shopee_product(idx: int, req: ShopeeProductRequest):
    """Cập nhật thông tin sản phẩm Shopee theo index."""
    items = _load_raw_catalog()
    if idx < 0 or idx >= len(items):
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    items[idx].update({
        "brand": req.brand.upper(),
        "name": req.name,
        "variant": req.variant or "",
        "price": req.price or "",
        "promotion": req.promotion or "",
        "shopee_url": req.shopee_url,
        "keywords": req.keywords or [],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save_catalog(items)
    return {"success": True, "product": items[idx]}


@router.delete("/shopee/products/{idx}")
async def delete_shopee_product(idx: int):
    """Xóa sản phẩm Shopee theo index."""
    items = _load_raw_catalog()
    if idx < 0 or idx >= len(items):
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    removed = items.pop(idx)
    _save_catalog(items)
    return {"success": True, "removed": removed, "total": len(items)}


@router.post("/shopee/sync-sheet")
async def sync_shopee_from_sheet(sheet_url: Optional[str] = None):
    """Sync danh mục Shopee từ Google Sheets CSV URL."""
    cfg = _cfg()
    url = sheet_url or cfg.get("shopee", {}).get("sheet_url", "")
    if not url:
        raise HTTPException(status_code=400, detail="Chưa cấu hình Google Sheets URL cho Shopee")

    # Chuyển URL Google Sheets sang CSV export URL
    if "spreadsheets/d/" in url:
        sheet_id = url.split("/d/")[1].split("/")[0]
        gid = ""
        if "gid=" in url:
            gid = url.split("gid=")[1].split("&")[0].split("#")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        if gid:
            csv_url += f"&gid={gid}"
    else:
        csv_url = url  # Assume already CSV URL

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(csv_url, headers={"User-Agent": "CFC-AI-Bot/2.0"})
            resp.raise_for_status()

        csv_text = resp.text
        reader = csv.DictReader(io.StringIO(csv_text))
        new_items = []
        for row in reader:
            # Flexible column mapping
            def g(*keys):
                for k in keys:
                    for col in row:
                        if col.lower().strip() == k.lower():
                            return str(row[col]).strip()
                return ""

            shopee_url = g("link shopee", "shopee_url", "link", "url")
            name = g("tên sp", "ten sp", "name", "tên sản phẩm", "ten san pham")
            if not shopee_url or not name:
                continue
            new_items.append({
                "brand": g("brand", "thương hiệu", "thuong hieu").upper() or "ZEO",
                "name": name,
                "variant": g("quy cách", "quy cach", "variant"),
                "price": g("giá", "gia", "price"),
                "promotion": g("ưu đãi", "uu dai", "promotion", "khuyến mãi"),
                "shopee_url": shopee_url,
                "keywords": [k.strip() for k in g("từ khóa", "tu khoa", "keywords").split(",") if k.strip()],
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

        # Merge: keep manual items + overwrite sheet items by name
        existing = _load_raw_catalog()
        sheet_names = {item["name"].lower() for item in new_items}
        kept = [item for item in existing if item.get("name", "").lower() not in sheet_names and not item.get("synced_at")]
        merged = kept + new_items
        _save_catalog(merged)

        # Lưu thời gian sync vào Redis
        try:
            r = _get_redis()
            await r.set("cfc:shopee:last_sync", datetime.now().isoformat())
            await r.aclose()
        except Exception:
            pass

        return {
            "success": True,
            "synced_count": len(new_items),
            "total": len(merged),
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi sync Google Sheets: {str(e)}")


@router.get("/shopee/last-sync")
async def get_shopee_last_sync():
    """Lấy thời gian sync Shopee catalog lần cuối."""
    try:
        r = _get_redis()
        last = await r.get("cfc:shopee:last_sync")
        await r.aclose()
        return {"last_sync": last or None}
    except Exception:
        return {"last_sync": None}


# ─────────────────────────────────────────────────────
# MODULE: DOCUMENT UPLOAD (A1)
# ─────────────────────────────────────────────────────

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), brand: str = Query("auto")):
    """Upload file .md trực tiếp từ trình duyệt vào thư mục knowledge/ và vector hóa ngay."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".md", ".txt"]:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .md và .txt")

    knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    dest = knowledge_dir / file.filename

    content = await file.read()
    dest.write_bytes(content)
    logger.info("Uploaded document: %s (%d bytes)", file.filename, len(content))

    # Auto-ingest ngay sau khi upload
    try:
        from document_ingestor import ingest_single_file
        result = await ingest_single_file(str(dest))
    except ImportError:
        from document_ingestor import ingest_knowledge_folder
        result = await ingest_knowledge_folder()

    return {
        "success": True,
        "filename": file.filename,
        "size_kb": round(len(content) / 1024, 2),
        "ingest_result": result,
        "message": f"Đã upload và vector hóa '{file.filename}' thành công!",
    }


class ImportSheetRequest(BaseModel):
    sheet_url: str
    brand: str = "zeo"


@router.post("/documents/import-sheet")
async def import_document_from_sheet(req: ImportSheetRequest):
    """Import nội dung tài liệu từ Google Sheets (dạng FAQ 2 cột: Câu hỏi | Câu trả lời) vào Vector Index."""
    # Convert Google Sheets URL to CSV export
    url = req.sheet_url.strip()
    if "spreadsheets/d/" in url:
        sheet_id = url.split("/d/")[1].split("/")[0]
        gid = ""
        if "gid=" in url:
            gid = url.split("gid=")[1].split("&")[0].split("#")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        if gid:
            csv_url += f"&gid={gid}"
    else:
        csv_url = url

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(csv_url, headers={"User-Agent": "CFC-AI-Bot/2.0"})
            resp.raise_for_status()
        csv_text = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tải Google Sheets: {str(e)}")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Sheet trống hoặc không đọc được")

    # Convert sheet rows to Markdown text
    md_lines = [f"# Import từ Google Sheets — {datetime.now().strftime('%Y-%m-%d')}\n"]
    cols = list(rows[0].keys())
    is_faq_format = len(cols) >= 2

    if is_faq_format:
        # 2-column FAQ format
        q_col, a_col = cols[0], cols[1]
        for row in rows:
            q = str(row.get(q_col, "")).strip()
            a = str(row.get(a_col, "")).strip()
            if q and a:
                md_lines.append(f"## {q}\n{a}\n")
    else:
        # Single-column content
        for row in rows:
            line = " | ".join(str(v).strip() for v in row.values() if str(v).strip())
            if line:
                md_lines.append(line)

    md_content = "\n".join(md_lines)
    brand_prefix = "cfc" if req.brand.lower() == "cfc" else "zeo"
    fname = f"{brand_prefix}_sheet_import_{int(time.time())}.md"
    knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    fpath = knowledge_dir / fname
    fpath.write_text(md_content, encoding="utf-8")

    # Ingest ngay
    try:
        from document_ingestor import ingest_single_file
        result = await ingest_single_file(str(fpath))
    except ImportError:
        from document_ingestor import ingest_knowledge_folder
        result = await ingest_knowledge_folder()

    return {
        "success": True,
        "rows_imported": len(rows),
        "filename": fname,
        "format": "faq" if is_faq_format else "content",
        "ingest_result": result,
        "message": f"Đã import {len(rows)} dòng từ Google Sheets và vector hóa thành công!",
    }


# ─────────────────────────────────────────────────────
# MODULE: AI LEARNING QUEUE SUGGEST (C1)
# ─────────────────────────────────────────────────────

@router.post("/learning/ai-suggest")
async def ai_suggest_from_learning_queue(brand: str = Query("all")):
    """AI tự phân tích Learning Queue: gom nhóm câu tương tự + đề xuất intent + câu trả lời."""
    from ai_engine import generate_ai_text

    # Lấy learning queue
    r = _get_redis()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        raw_questions = []
        for b in brands:
            for lq_key in [f"{b}:learning:queue", f"{b}:kb:learning:queue"]:
                key_type = await r.type(lq_key)
                if key_type == "list":
                    items = await r.lrange(lq_key, 0, 50)
                elif key_type == "set":
                    items = list(await r.smembers(lq_key))[:50]
                else:
                    continue
                for raw in items:
                    try:
                        item = json.loads(raw)
                        q = item.get("user_message") or item.get("query") or str(raw)
                        raw_questions.append({"brand": b.upper(), "question": q, "raw": raw})
                    except Exception:
                        raw_questions.append({"brand": b.upper(), "question": str(raw), "raw": raw})
    finally:
        await r.aclose()

    if not raw_questions:
        return {"success": True, "suggestions": [], "message": "Learning Queue trống!"}

    # Gửi cho AI phân tích
    q_list = "\n".join([f"- [{i+1}] ({q['brand']}) {q['question']}" for i, q in enumerate(raw_questions[:30])])
    prompt = f"""Bạn là chuyên gia phân tích FAQ chatbot ZeO/CFC bán hàng phân bón và nước giặt.

Dưới đây là {len(raw_questions[:30])} câu hỏi khách hàng mà chatbot CHƯA trả lời được (Learning Queue):

{q_list}

Hãy:
1. Gom nhóm các câu có ý nghĩa tương đồng lại với nhau
2. Đặt tên intent ngắn gọn cho từng nhóm (VD: "wholesale_price", "product_usage", "return_policy")
3. Viết câu trả lời chuẩn tiếng Việt cho từng nhóm (ngắn gọn, thân thiện, chuyên nghiệp)

Traả về JSON array:
[{{"intent": "tên_intent", "brand": "ZEO/CFC", "sample_questions": ["câu hỏi mẫu"], "suggested_answer": "câu trả lời gợi ý", "question_indices": [1,2,3]}}]

Chỉ trả về JSON, không giải thích thêm."""

    ai_raw = await generate_ai_text(prompt, max_tokens=2000)
    suggestions = []
    try:
        # Extract JSON from response
        json_start = ai_raw.find("[")
        json_end = ai_raw.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            suggestions = json.loads(ai_raw[json_start:json_end])
    except Exception:
        suggestions = [{"intent": "ai_error", "suggested_answer": ai_raw, "sample_questions": [], "brand": brand.upper()}]

    return {
        "success": True,
        "total_questions": len(raw_questions),
        "suggestions": suggestions,
        "raw_questions": raw_questions[:30],
    }


# ─────────────────────────────────────────────────────
# MODULE: TREND ANALYTICS (C3)
# ─────────────────────────────────────────────────────

@router.get("/analytics/weekly")
async def weekly_analytics():
    """Trả về số liệu trend 7 ngày gần nhất (snapshot hàng ngày từ Redis)."""
    r = _get_redis()
    try:
        labels = []
        new_customers = []
        leads_count = []
        lq_counts = []

        from datetime import timedelta
        today = datetime.now()
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            label = day.strftime("%d/%m")
            labels.append(label)
            snap_key = f"cfc:analytics:daily:{day.strftime('%Y-%m-%d')}"
            snap_raw = await r.get(snap_key)
            if snap_raw:
                snap = json.loads(snap_raw)
                new_customers.append(snap.get("new_customers", 0))
                leads_count.append(snap.get("leads_with_phone", 0))
                lq_counts.append(snap.get("learning_queue", 0))
            else:
                new_customers.append(0)
                leads_count.append(0)
                lq_counts.append(0)

        # Top intents 7 ngày (aggregate)
        intent_agg: dict = {}
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="cfc:analytics:daily:*", count=50)
            for key in keys:
                snap_raw = await r.get(key)
                if snap_raw:
                    snap = json.loads(snap_raw)
                    for intent, count in snap.get("top_intents", {}).items():
                        intent_agg[intent] = intent_agg.get(intent, 0) + count
            if cursor == 0:
                break

        top_intents_7d = sorted(intent_agg.items(), key=lambda x: x[1], reverse=True)[:8]

        return {
            "labels": labels,
            "new_customers": new_customers,
            "leads_with_phone": leads_count,
            "learning_queue": lq_counts,
            "top_intents_7d": dict(top_intents_7d),
        }
    finally:
        await r.aclose()


@router.post("/analytics/snapshot")
async def save_daily_snapshot():
    """Lưu snapshot số liệu ngày hôm nay vào Redis (gọi bởi scheduler)."""
    r = _get_redis()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        snap_key = f"cfc:analytics:daily:{today_str}"

        # Count customers & leads
        total_new = 0
        leads = 0
        lq_total = 0
        top_intents: dict = {}

        for b in ["zeo", "cfc"]:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=f"{b}:customer:messenger:*", count=200)
                for key in keys:
                    raw = await r.get(key)
                    if not raw:
                        continue
                    try:
                        profile = json.loads(raw)
                    except Exception:
                        continue
                    # Count today's new customers
                    first_seen = profile.get("first_seen_at", "")
                    if first_seen.startswith(today_str):
                        total_new += 1
                    # Count leads with phone
                    phone = profile.get("phone", "") or profile.get("customer_phone", "")
                    if phone and len(re.findall(r"\d", phone)) >= 9:
                        leads += 1
                    # Aggregate intents
                    intent = profile.get("last_intent", "")
                    if intent:
                        top_intents[intent] = top_intents.get(intent, 0) + 1
                if cursor == 0:
                    break
            # Learning queue count
            for lq_key in [f"{b}:learning:queue", f"{b}:kb:learning:queue"]:
                kt = await r.type(lq_key)
                if kt == "list":
                    lq_total += await r.llen(lq_key)
                elif kt == "set":
                    lq_total += await r.scard(lq_key)

        snap = {
            "date": today_str,
            "new_customers": total_new,
            "leads_with_phone": leads,
            "learning_queue": lq_total,
            "top_intents": dict(sorted(top_intents.items(), key=lambda x: x[1], reverse=True)[:10]),
            "saved_at": datetime.now().isoformat(),
        }
        await r.setex(snap_key, 60 * 60 * 24 * 8, json.dumps(snap, ensure_ascii=False))  # 8 ngày TTL
        return {"success": True, "snapshot": snap}
    finally:
        await r.aclose()


# ─────────────────────────────────────────────────────
# MODULE: AI EXECUTIVE REPORTER ENDPOINTS
# ─────────────────────────────────────────────────────

@router.get("/reports/latest")
async def get_latest_report_endpoint():
    """Lấy bản tin báo cáo kinh doanh gần nhất đã lưu trong Redis."""
    from ai_reporter import get_latest_report
    report = await get_latest_report()
    return {"has_report": report is not None, "report": report}


@router.post("/reports/generate")
async def generate_report_endpoint(send_telegram: bool = False):
    """Kích hoạt AI quét dữ liệu và tạo Bản Tin Báo Cáo Điều Hành mới."""
    from ai_reporter import generate_daily_executive_report
    res = await generate_daily_executive_report(send_telegram=send_telegram)
    return res

