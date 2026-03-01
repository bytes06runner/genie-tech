"""
server.py — The FastAPI Router (X10V Backend)
===============================================
Ties together: memory_manager, swarm_brain, headless_executor, scheduler_node.

Endpoints:
  POST /schedule_task   — Schedule a future automation job
  POST /instant_analyze — Run the swarm immediately on provided text data
  GET  /tasks           — List all tasks in the scheduler registry
  WS   /ws              — WebSocket for live swarm terminal feed
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from memory_manager import log_memory
from swarm_brain import run_swarm, extract_vision_context
from doc_generator import create_document
from scheduler_node import (
    register_task,
    get_all_tasks,
    start_scheduler,
    set_broadcast,
)
from yt_research import research_youtube_video, generate_pdf_base64
from voice_intent import classify_intent
from rule_engine import (
    DynamicRuleEngine,
    GrowwMockExecutor,
    evaluate_all_rules,
    set_rule_notify,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("server")


class ConnectionManager:
    """Manages active WebSocket connections for live terminal broadcast."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info("🔌 WebSocket connected  (total: %d)", len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        logger.info("🔌 WebSocket disconnected  (total: %d)", len(self.active))

    async def broadcast(self, message: str):
        """Send a log line to every connected frontend terminal."""
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


async def ws_broadcast(message: str):
    """Callback compatible with swarm_brain.BroadcastFn."""
    logger.info("📡 WS broadcast: %s", message[:120])
    await manager.broadcast(message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  X10V Backend — Starting up")
    logger.info("=" * 60)
    start_scheduler()
    set_broadcast(ws_broadcast)
    log_memory("Server", "X10V backend started.")

    # ── Initialize DEX Automation engine ──
    from dex_automation import init_dex_automation_db, set_automation_broadcast, evaluate_dex_orders
    await init_dex_automation_db()
    set_automation_broadcast(ws_broadcast)

    # ── Start DEX order evaluation scheduler (every 60s) ──
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    dex_auto_scheduler = AsyncIOScheduler()
    dex_auto_scheduler.add_job(evaluate_dex_orders, "interval", seconds=60, id="dex_order_eval")
    dex_auto_scheduler.start()
    logger.info("⚡ DEX Automation scheduler started (60s interval)")

    # ── Launch Telegram bot as a subprocess ──
    env = os.environ.copy()
    env["TOKENIZERS_PARALLELISM"] = "false"
    tg_proc = subprocess.Popen(
        [sys.executable, "tg_bot.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    logger.info("🤖 Telegram bot subprocess started (PID %s)", tg_proc.pid)

    yield

    # ── Shutdown: kill the bot subprocess ──
    logger.info("Stopping Telegram bot subprocess (PID %s)…", tg_proc.pid)
    tg_proc.terminate()
    try:
        tg_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        tg_proc.kill()
    logger.info("X10V Backend — Shutting down.")


app = FastAPI(
    title="X10V — Headless Semantic Automation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScheduleTaskRequest(BaseModel):
    description: str = Field(..., example="Analyze OctaFX EUR/USD spread and execute trade")
    run_at: datetime = Field(..., example="2026-02-27T14:30:00")
    scrape_url: str = Field(..., example="https://www.groww.in/stocks/reliance-industries-ltd")
    scrape_selector: str = Field(default="body", example=".stock-price-container")
    action_url: Optional[str] = Field(default=None, example="https://www.groww.in/stocks/reliance-industries-ltd")
    action_selector: Optional[str] = Field(default=None, example="button.buy-btn")
    action_type: Optional[str] = Field(default=None, example="click")
    action_input_text: Optional[str] = Field(default=None)


class InstantAnalyzeRequest(BaseModel):
    text_data: str = Field(
        ...,
        example="Groww Ticker: HDFCBANK, CMP: ₹1,642.30, Change: +1.2%, Volume: 4.3M",
    )
    force_vision: bool = Field(default=False)


class AnalyzeScreenRequest(BaseModel):
    command: str = Field(..., example="Analyze this Reliance chart")
    image_base64: str = Field(..., description="Base64-encoded JPEG screenshot from screen capture")


class TaskResponse(BaseModel):
    id: str
    description: str
    run_at: str
    status: str
    result: Optional[str] = None


@app.post("/schedule_task", response_model=dict)
async def schedule_task(req: ScheduleTaskRequest):
    """Register a future automation job in APScheduler."""
    logger.info("📥 POST /schedule_task — '%s' at %s", req.description, req.run_at)
    await ws_broadcast(f"[Server] New task scheduled: {req.description} at {req.run_at.isoformat()}")

    task = register_task(
        description=req.description,
        run_at=req.run_at,
        scrape_url=req.scrape_url,
        scrape_selector=req.scrape_selector,
        action_url=req.action_url,
        action_selector=req.action_selector,
        action_type=req.action_type,
        action_input_text=req.action_input_text,
    )
    return {"status": "scheduled", "task": task}


@app.post("/instant_analyze", response_model=dict)
async def instant_analyze(req: InstantAnalyzeRequest):
    """Run the swarm immediately on provided DOM text data."""
    logger.info(
        "📥 POST /instant_analyze — %d chars, vision=%s",
        len(req.text_data), req.force_vision,
    )
    await ws_broadcast(f"[Server] Instant analysis requested ({len(req.text_data)} chars)")

    verdict = await run_swarm(
        text_data=req.text_data,
        user_command=req.text_data,
        force_vision=req.force_vision,
        broadcast=ws_broadcast,
    )

    response_payload = {"status": "complete", "verdict": verdict}

    if verdict.get("generate_file") is True:
        file_type = verdict.get("file_type", "pdf")
        if file_type not in ("pdf", "md"):
            file_type = "pdf"
        try:
            file_b64, file_mime = await create_document(
                verdict.get("structured_data", {}), file_type,
                domain=verdict.get("domain", "general")
            )
            # Derive actual file type from mime (PDF may fallback to .md)
            actual_type = "pdf" if file_mime == "application/pdf" else "md"
            response_payload["file_b64"] = file_b64
            response_payload["file_mime"] = file_mime
            response_payload["file_type"] = actual_type
            logger.info("📄 Document generated: %s (%d b64 chars)", file_mime, len(file_b64))
            if ws_broadcast:
                await ws_broadcast(f"[DocGen] 📄 {actual_type.upper()} document generated — ready for download")
        except Exception as e:
            logger.error("📄 Document generation failed: %s", e)
            if ws_broadcast:
                await ws_broadcast(f"[DocGen] ⚠️ Document generation failed: {str(e)[:80]}")

    return response_payload


@app.post("/api/analyze-screen", response_model=dict)
async def analyze_screen(req: AnalyzeScreenRequest):
    """
    Receive a base64 screenshot + user command.
    1. Vision extraction via Groq Llama 3.2 Vision (real pixel reading)
    2. Swarm debate (Alpha/8b → Beta/70b → Gamma/70b-JSON)  → JSON verdict
    All steps are broadcast live via WebSocket.
    """
    logger.info(
        "📥 POST /api/analyze-screen — command='%s', image=%d chars",
        req.command[:80], len(req.image_base64),
    )
    await ws_broadcast(f"[Server] 📸 Screen analysis requested: \"{req.command}\"")

    # Step 1: Vision extraction
    extracted_context = await extract_vision_context(
        image_base64=req.image_base64,
        user_command=req.command,
        broadcast=ws_broadcast,
    )

    # Step 2: Swarm debate on the extracted text
    combined_input = (
        f"User command: {req.command}\n\n"
        f"Screen context (AI-extracted):\n{extracted_context}"
    )
    verdict = await run_swarm(
        text_data=combined_input,
        user_command=req.command,
        force_vision=False,
        broadcast=ws_broadcast,
    )

    response_payload = {
        "status": "complete",
        "vision_context": extracted_context,
        "verdict": verdict,
    }

    if verdict.get("generate_file") is True:
        file_type = verdict.get("file_type", "pdf")
        if file_type not in ("pdf", "md"):
            file_type = "pdf"
        try:
            file_b64, file_mime = await create_document(
                verdict.get("structured_data", {}), file_type,
                domain=verdict.get("domain", "general")
            )
            # Derive actual file type from mime (PDF may fallback to .md)
            actual_type = "pdf" if file_mime == "application/pdf" else "md"
            response_payload["file_b64"] = file_b64
            response_payload["file_mime"] = file_mime
            response_payload["file_type"] = actual_type
            logger.info("📄 Document generated: %s (%d b64 chars)", file_mime, len(file_b64))
            if ws_broadcast:
                await ws_broadcast(f"[DocGen] 📄 {actual_type.upper()} document generated — ready for download")
        except Exception as e:
            logger.error("📄 Document generation failed: %s", e)
            if ws_broadcast:
                await ws_broadcast(f"[DocGen] ⚠️ Document generation failed: {str(e)[:80]}")

    return response_payload


@app.get("/tasks", response_model=list)
async def list_tasks():
    """Return all tasks in the scheduler registry."""
    tasks = get_all_tasks()
    logger.info("📥 GET /tasks — returning %d tasks", len(tasks))
    return tasks


# ═══════════════════════════════════════════════════════
#  YouTube Deep-Research Endpoint
# ═══════════════════════════════════════════════════════

class YouTubeRequest(BaseModel):
    url: str = Field(..., example="https://youtube.com/watch?v=dQw4w9WgXcQ")


class YouTubePDFRequest(BaseModel):
    summary: dict = Field(..., description="The summary JSON object to convert to PDF")


@app.post("/api/youtube-research")
async def youtube_research(req: YouTubeRequest):
    """Extract transcript from a YouTube video, summarize via Groq, return structured data."""
    logger.info("📥 POST /api/youtube-research — URL: %s", req.url)
    await ws_broadcast(f"[Server] 🎬 YouTube research requested: {req.url}")

    result = await research_youtube_video(req.url)

    if "error" in result:
        await ws_broadcast(f"[Server] ⚠️ YouTube research failed: {result['error']}")
        return {"status": "error", "error": result["error"]}

    await ws_broadcast(
        f"[Server] ✅ YouTube research complete — {result['transcript_length']} chars, "
        f"sentiment: {result['summary'].get('sentiment', 'N/A')}"
    )
    return result


@app.post("/api/youtube-pdf")
async def youtube_pdf(req: YouTubePDFRequest):
    """Generate a PDF from a YouTube research summary."""
    logger.info("📥 POST /api/youtube-pdf — generating PDF")
    pdf_b64 = generate_pdf_base64(req.summary)
    return {
        "file_b64": pdf_b64,
        "file_mime": "application/pdf",
        "file_type": "pdf",
    }


# ═══════════════════════════════════════════════════════
#  Voice Intent Classification Endpoint
# ═══════════════════════════════════════════════════════

class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., example="Analyze Apple stock on the daily timeframe")


@app.post("/api/voice-intent")
async def voice_intent(req: VoiceCommandRequest):
    """Classify transcribed voice text into structured intent JSON via Groq."""
    logger.info("📥 POST /api/voice-intent — '%s'", req.transcript[:80])
    await ws_broadcast(f"[Server] 🎤 Voice command received: \"{req.transcript[:60]}…\"")

    intent = await classify_intent(req.transcript)

    await ws_broadcast(
        f"[Server] 🎤 Intent: {intent.get('intent')} "
        f"({intent.get('confidence_score', 0)*100:.0f}% confidence)"
    )
    return {"status": "success", "intent": intent}


# ═══════════════════════════════════════════════════════
#  Dynamic Rule Engine Endpoints
# ═══════════════════════════════════════════════════════

class CreateRuleRequest(BaseModel):
    tg_id: int = Field(default=0, description="Telegram user ID (0 for web users)")
    name: str = Field(..., example="Buy AAPL on RSI dip")
    asset: str = Field(..., example="AAPL")
    conditions: dict = Field(
        ...,
        example={"price_below": 180, "rsi_below": 30, "logic": "AND"},
    )
    action_type: str = Field(default="buy")
    amount_usd: float = Field(default=100.0)


@app.post("/api/rules")
async def create_rule(req: CreateRuleRequest):
    """Create a new dynamic trading rule."""
    logger.info("📥 POST /api/rules — '%s' for %s", req.name, req.asset)
    rule = await DynamicRuleEngine.create_rule(
        tg_id=req.tg_id, name=req.name, asset=req.asset,
        conditions=req.conditions, action_type=req.action_type,
        amount_usd=req.amount_usd,
    )
    await ws_broadcast(f"[RuleEngine] ✅ Rule created: {req.name} — {req.asset}")
    return {"status": "created", "rule": rule}


@app.get("/api/rules/{tg_id}")
async def get_rules(tg_id: int):
    """Get all rules for a user."""
    rules = await DynamicRuleEngine.get_user_rules(tg_id)
    return {"rules": rules}


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule by ID."""
    await DynamicRuleEngine.delete_rule(rule_id)
    return {"status": "deleted"}


@app.get("/api/trades/{tg_id}")
async def get_trades(tg_id: int):
    """Get mock trade history for a user."""
    trades = await GrowwMockExecutor.get_trade_history(tg_id)
    return {"trades": trades}


# ═══════════════════════════════════════════════════════
#  Collaboration Bridge — Web → Telegram
# ═══════════════════════════════════════════════════════

class BridgeSignalRequest(BaseModel):
    tg_user_id: int = Field(..., description="Target Telegram user ID to notify")
    signal_type: str = Field(..., example="voice_command")
    payload: dict = Field(..., example={"command": "Automate buying AAPL", "intent": "set_automation"})


# Store pending signals for the Telegram bot to pick up
_pending_signals: list[dict] = []


@app.post("/api/bridge/signal")
async def send_bridge_signal(req: BridgeSignalRequest):
    """
    Web Dashboard → Telegram Bot bridge.
    Sends a signal from the web frontend to the Telegram bot.
    The bot picks up these signals and DMs the user.
    """
    logger.info("📥 POST /api/bridge/signal — type: %s to user %d", req.signal_type, req.tg_user_id)

    signal = {
        "tg_user_id": req.tg_user_id,
        "signal_type": req.signal_type,
        "payload": req.payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _pending_signals.append(signal)

    await ws_broadcast(
        f"[Bridge] 🌉 Signal sent to Telegram user {req.tg_user_id}: {req.signal_type}"
    )
    return {"status": "signal_queued", "signal": signal}


@app.get("/api/bridge/pending")
async def get_pending_signals():
    """Telegram bot polls this to pick up web dashboard signals."""
    signals = list(_pending_signals)
    _pending_signals.clear()
    return {"signals": signals}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "X10V Backend", "version": "3.0.0-defi"}


# ═══════════════════════════════════════════════════════════════════
#  DEX SCREENER API — Frontend integration
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/dex/search")
async def dex_search(q: str):
    """Search DEX Screener for token pairs."""
    from dex_screener import search_pairs, format_pair_data
    pairs = await search_pairs(q)
    formatted = [format_pair_data(p) for p in pairs[:10]]
    return {"pairs": formatted, "total": len(pairs)}


@app.get("/api/dex/trending")
async def dex_trending():
    """Get trending tokens with AI analysis."""
    from dex_screener import get_trending_with_analysis
    result = await get_trending_with_analysis()
    return result


@app.get("/api/dex/boosted")
async def dex_boosted():
    """Get top boosted tokens."""
    from dex_screener import get_top_boosted, format_pair_data, get_token_data
    import asyncio as _aio
    boosted = await get_top_boosted()
    if not boosted:
        return {"tokens": []}

    enriched = []
    for token in boosted[:10]:
        chain = token.get("chainId", "")
        address = token.get("tokenAddress", "")
        if chain and address:
            pairs = await get_token_data(chain, address)
            if pairs:
                best = max(pairs, key=lambda p: p.get("volume", {}).get("h24", 0))
                enriched.append(format_pair_data(best))
            await _aio.sleep(0.15)

    return {"tokens": enriched}


# ═══════════════════════════════════════════════════════════════════
#  DEX AUTOMATION — Smart order engine
# ═══════════════════════════════════════════════════════════════════

class CreateDexOrderRequest(BaseModel):
    symbol: str = Field(..., example="PEPE")
    chain: str = Field(default="", example="solana")
    side: str = Field(..., example="buy")
    target_price: float = Field(..., example=0.00001)
    amount_usd: float = Field(default=100.0, example=100.0)
    stop_loss: float = Field(default=0, example=0.000008)
    take_profit: float = Field(default=0, example=0.000015)
    wallet_address: str = Field(default="", example="")
    dex: str = Field(default="", example="raydium")
    pair_address: str = Field(default="", example="")
    search_query: str = Field(default="", example="PEPE")


@app.post("/api/dex/orders")
async def create_dex_order(req: CreateDexOrderRequest):
    """Create a new smart DEX order with AI-powered execution."""
    from dex_automation import create_order
    order = await create_order(
        symbol=req.symbol,
        chain=req.chain,
        side=req.side,
        target_price=req.target_price,
        amount_usd=req.amount_usd,
        wallet_address=req.wallet_address,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        dex=req.dex,
        pair_address=req.pair_address,
        search_query=req.search_query,
    )
    await ws_broadcast(
        f"[DexAuto] 📝 New {req.side.upper()} order: {req.symbol} @ ${req.target_price}"
    )
    return {"status": "created", "order": order}


@app.get("/api/dex/orders")
async def list_dex_orders(user_id: str = "web", active_only: bool = False):
    """List DEX orders for a user."""
    from dex_automation import get_active_orders, get_all_orders
    if active_only:
        orders = await get_active_orders(user_id)
    else:
        orders = await get_all_orders(user_id)
    return {"orders": orders}


@app.delete("/api/dex/orders/{order_id}")
async def cancel_dex_order(order_id: str):
    """Cancel an active DEX order."""
    from dex_automation import cancel_order
    success = await cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found or already completed")
    return {"status": "cancelled", "order_id": order_id}


@app.post("/api/dex/analyze")
async def analyze_token(body: dict):
    """Run AI analysis on a specific token for trade recommendation."""
    from dex_automation import analyze_token_for_trade
    symbol = body.get("symbol", "")
    chain = body.get("chain", "")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    result = await analyze_token_for_trade(symbol, chain)
    return result


@app.get("/api/dex/wallet/balance")
async def get_wallet_balance(address: str):
    """Get Algorand wallet balance for connected address."""
    from algorand_indexer import get_algo_balance
    if not address:
        raise HTTPException(status_code=400, detail="address is required")
    balance = await get_algo_balance(address)
    if not balance:
        raise HTTPException(status_code=404, detail="Could not fetch balance")
    return balance


# ═══════════════════════════════════════════════════════════════════
#  PENDING TRANSACTION API — Mini App ↔ Backend handoff
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/pending_tx/{ptx_id}")
async def get_pending_tx(ptx_id: str):
    """
    Fetch a pending unsigned transaction for the Mini App to sign.
    Called by the React webapp when mode=sign_swap.
    """
    from algorand_indexer import get_pending_transaction
    tx = await get_pending_transaction(ptx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Pending transaction not found or already processed")
    return tx


@app.post("/api/pending_tx/{ptx_id}/signed")
async def mark_tx_signed(ptx_id: str, body: dict):
    """
    Mark a pending transaction as signed after the Mini App submits it.
    """
    from algorand_indexer import mark_transaction_signed
    algo_tx_id = body.get("algo_tx_id", "")
    if not algo_tx_id:
        raise HTTPException(status_code=400, detail="algo_tx_id is required")
    await mark_transaction_signed(ptx_id, algo_tx_id)
    return {"status": "ok", "ptx_id": ptx_id, "algo_tx_id": algo_tx_id}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text("[Server] Connected to X10V Swarm Terminal ✓")
        while True:
            data = await ws.receive_text()
            logger.info("WS received from client: %s", data[:100])
            await ws.send_text(f"[Server] ACK: {data[:80]}")
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("Client disconnected from WebSocket.")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
