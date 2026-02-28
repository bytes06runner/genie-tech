"""
scheduler_node.py — The Offline Engine (APScheduler)
=====================================================
Registers future jobs that, at the scheduled time:
  1. Scrape live data via headless_executor
  2. Feed data to swarm_brain for safety check
  3. If Gamma approves → execute the Playwright action
"""

import logging
import json
from datetime import datetime
from typing import Optional, Callable, Coroutine, Any
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from headless_executor import scrape_page_text, execute_web_action
from swarm_brain import run_swarm, BroadcastFn
from memory_manager import log_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("scheduler_node")

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 3},
)

# In-memory task registry (used by the frontend queue view)
task_registry: dict[str, dict] = {}

_broadcast_fn: BroadcastFn = None


def set_broadcast(fn: BroadcastFn):
    global _broadcast_fn
    _broadcast_fn = fn


async def _scheduled_job(
    task_id: str,
    scrape_url: str,
    scrape_selector: str,
    action_url: Optional[str],
    action_selector: Optional[str],
    action_type: Optional[str],
    action_input_text: Optional[str],
    description: str,
):
    """
    Full pipeline executed at the scheduled time:
      scrape → swarm → (conditional) execute
    """
    logger.info("⏰ SCHEDULED JOB FIRED  task_id=%s  desc='%s'", task_id, description)
    task_registry[task_id]["status"] = "scraping"
    if _broadcast_fn:
        await _broadcast_fn(f"[Scheduler] ⏰ Job fired: {description}")

    logger.info("Scraping %s [%s] …", scrape_url, scrape_selector)
    if _broadcast_fn:
        await _broadcast_fn(f"[Scheduler] Scraping live data from {scrape_url} …")

    raw_text = await scrape_page_text(scrape_url, scrape_selector)

    if not raw_text:
        logger.error("Scrape returned empty — aborting job %s", task_id)
        task_registry[task_id]["status"] = "failed"
        task_registry[task_id]["result"] = "Scrape failed — no data retrieved."
        log_memory("Scheduler", f"Job {task_id} FAILED at scrape step.")
        if _broadcast_fn:
            await _broadcast_fn(f"[Scheduler|red] Scrape failed for task {task_id}. Job aborted.")
        return

    logger.info("Scraped %d chars of live data.", len(raw_text))
    task_registry[task_id]["status"] = "swarm_debating"

    logger.info("Running swarm analysis …")
    if _broadcast_fn:
        await _broadcast_fn("[Scheduler] Feeding data to swarm for safety check …")

    verdict = await run_swarm(raw_text, broadcast=_broadcast_fn)

    if verdict.get("decision") != "execute":
        logger.info("🛑 Swarm VETOED task %s: %s", task_id, verdict.get("reasoning"))
        task_registry[task_id]["status"] = "vetoed"
        task_registry[task_id]["result"] = verdict
        log_memory("Scheduler", f"Job {task_id} VETOED: {verdict.get('reasoning')}")
        if _broadcast_fn:
            await _broadcast_fn(f"[Scheduler|red] Swarm vetoed task: {verdict.get('reasoning')}")
        return

    # --- Step 3: Execute the Playwright action ---
    if action_url and action_selector and action_type:
        logger.info("Executing Playwright action on %s …", action_url)
        task_registry[task_id]["status"] = "executing"
        if _broadcast_fn:
            await _broadcast_fn(f"[Scheduler] ✅ Swarm approved — executing action on {action_url} …")

        exec_result = await execute_web_action(
            url=action_url,
            target_selector=action_selector,
            action_type=action_type,
            input_text=action_input_text,
        )

        if exec_result["success"]:
            logger.info("✅ Action executed successfully for task %s", task_id)
            task_registry[task_id]["status"] = "completed"
            task_registry[task_id]["result"] = exec_result["data"]
            log_memory("Scheduler", f"Job {task_id} COMPLETED: {exec_result['data']}")
            if _broadcast_fn:
                await _broadcast_fn(f"[Scheduler|green] ✅ Task completed: {description}")
        else:
            logger.error("❌ Action failed for task %s: %s", task_id, exec_result["error"])
            task_registry[task_id]["status"] = "failed"
            task_registry[task_id]["result"] = exec_result["error"]
            log_memory("Scheduler", f"Job {task_id} FAILED at execution: {exec_result['error']}")
            if _broadcast_fn:
                await _broadcast_fn(f"[Scheduler|red] ❌ Execution failed: {exec_result['error']}")
    else:
        logger.info("Analysis-only job %s complete. Swarm approved.", task_id)
        task_registry[task_id]["status"] = "completed"
        task_registry[task_id]["result"] = verdict
        log_memory("Scheduler", f"Job {task_id} COMPLETED (analysis only).")
        if _broadcast_fn:
            await _broadcast_fn(f"[Scheduler|green] ✅ Analysis complete: {description}")


def register_task(
    description: str,
    run_at: datetime,
    scrape_url: str,
    scrape_selector: str = "body",
    action_url: Optional[str] = None,
    action_selector: Optional[str] = None,
    action_type: Optional[str] = None,
    action_input_text: Optional[str] = None,
) -> dict:
    """
    Register a new scheduled task. Returns the task metadata dict.
    """
    task_id = uuid4().hex[:12]
    task_meta = {
        "id": task_id,
        "description": description,
        "run_at": run_at.isoformat(),
        "status": "pending",
        "result": None,
    }
    task_registry[task_id] = task_meta

    scheduler.add_job(
        _scheduled_job,
        trigger="date",
        run_date=run_at,
        id=task_id,
        kwargs={
            "task_id": task_id,
            "scrape_url": scrape_url,
            "scrape_selector": scrape_selector,
            "action_url": action_url,
            "action_selector": action_selector,
            "action_type": action_type,
            "action_input_text": action_input_text,
            "description": description,
        },
        replace_existing=True,
    )

    logger.info(
        "📅 Task registered  id=%s  run_at=%s  desc='%s'",
        task_id, run_at.isoformat(), description,
    )
    log_memory("Scheduler", f"Registered task {task_id}: {description} at {run_at.isoformat()}")

    return task_meta


def get_all_tasks() -> list[dict]:
    """Return the full task registry as a list."""
    return list(task_registry.values())


def start_scheduler():
    """Start the APScheduler if not already running."""
    if not scheduler.running:
        scheduler.start()
        logger.info("🚀 APScheduler started.")
    else:
        logger.info("APScheduler already running.")
