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
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from memory_manager import log_memory
from swarm_brain import run_swarm, extract_vision_context
from scheduler_node import (
    register_task,
    get_all_tasks,
    start_scheduler,
    set_broadcast,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  X10V Backend — Starting up")
    logger.info("=" * 60)
    start_scheduler()
    set_broadcast(ws_broadcast)
    log_memory("Server", "X10V backend started.")
    yield
    logger.info("X10V Backend — Shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

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
    return {"status": "complete", "verdict": verdict}


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

    return {
        "status": "complete",
        "vision_context": extracted_context,
        "verdict": verdict,
    }


@app.get("/tasks", response_model=list)
async def list_tasks():
    """Return all tasks in the scheduler registry."""
    tasks = get_all_tasks()
    logger.info("📥 GET /tasks — returning %d tasks", len(tasks))
    return tasks


@app.get("/health")
async def health():
    return {"status": "ok", "service": "X10V Backend", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# WebSocket — live swarm terminal
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text("[Server] Connected to X10V Swarm Terminal ✓")
        while True:
            # Keep alive — the frontend may also send commands in future
            data = await ws.receive_text()
            logger.info("WS received from client: %s", data[:100])
            # Echo acknowledgement
            await ws.send_text(f"[Server] ACK: {data[:80]}")
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info("Client disconnected from WebSocket.")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
