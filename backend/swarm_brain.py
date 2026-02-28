"""
swarm_brain.py — The Decision Engine (Multi-Agent Swarm)
=========================================================
Five-stage pipeline, all powered by Groq + live web RAG:

  • Vision  (Groq / llama-4-scout-17b-16e-instruct) — Real pixel-reading from screenshots
  • RAG     (DuckDuckGo / live_rag.py)               — Zero-cost live web context injection
  • Alpha   (Groq / llama-3.1-8b-instant)            — Domain-agnostic rapid analyst
  • Beta    (Groq / llama-3.3-70b-versatile)          — Deep reasoning + RAG cross-reference
  • Gamma   (Groq / llama-3.3-70b-versatile)          — Final arbiter, universal JSON verdict

Output contract (universal):
  {
    "domain":           "finance | code | productivity | general",
    "decision":         "inform | execute | abort | research",
    "rag_context_used": "brief summary of live web data used",
    "reasoning":        "detailed synthesis"
  }

100% Groq Architecture — Single provider, zero mock data, live web RAG.
"""

import json
import logging
import os
import asyncio
from typing import Any, Callable, Coroutine, Optional

from dotenv import load_dotenv
from groq import Groq

from memory_manager import get_relevant_context, log_memory
from live_rag import extract_search_query, search_live_context

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("swarm_brain")

# ---------------------------------------------------------------------------
# Single Groq client — all three agents route through here
# ---------------------------------------------------------------------------
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Type alias for the broadcast callback
BroadcastFn = Optional[Callable[[str], Coroutine[Any, Any, None]]]

# ---------------------------------------------------------------------------
# Model routing
# ---------------------------------------------------------------------------
ALPHA_MODEL  = "llama-3.1-8b-instant"          # fastest — impulse
BETA_MODEL   = "llama-3.3-70b-versatile"       # deep reasoning — sentinel
GAMMA_MODEL  = "llama-3.3-70b-versatile"       # balanced — arbiter
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # multimodal — real screen reading

# ---------------------------------------------------------------------------
# System prompts — domain-agnostic elite analysts
# ---------------------------------------------------------------------------
ALPHA_SYSTEM = (
    "You are Agent Alpha (The Impulse) — an elite, rapid-response AI analyst. "
    "Analyze the extracted screen text and the user's prompt. "
    "Step 1: Identify the domain (Finance, Code, Productivity, Social Media, News, General). "
    "Step 2: Formulate an immediate, highly competent analysis or action plan "
    "based on what is visible. Be specific — cite data points you see. "
    "Provide your assessment in ≤120 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research. "
    "\n\n"
    "CRITICAL CONTEXT RULE: If the extracted text describes the 'X10V Headless Semantic "
    "Automation' dashboard or shows 'Alpha/Beta/Gamma' agent logs, this means the user "
    "accidentally captured their own dashboard. Output a brief ABORT: "
    "'Self-referential UI detected. Switch screen-share to your target application.'"
)

BETA_SYSTEM = (
    "You are Agent Beta (The Sentinel) — the deep-logic and research node. "
    "You receive: (1) the raw screen data, (2) Alpha's rapid hypothesis, and "
    "(3) LIVE INTERNET SEARCH RESULTS scraped in real-time from the web. "
    "Your job: cross-reference the screen data with the live web RAG data. "
    "Identify factual errors, market risks, code bugs, outdated information, "
    "or opportunities Alpha may have missed. "
    "If the RAG data contradicts the screen, flag it explicitly. "
    "Provide your analysis in ≤180 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research."
)

GAMMA_SYSTEM = (
    "You are Agent Gamma (The Arbiter) — the final consensus engine. "
    "You receive Alpha's rapid take and Beta's deep RAG-augmented analysis. "
    "Synthesize their debate into a definitive verdict.\n\n"
    "You MUST output ONLY a valid JSON object with exactly these four keys:\n"
    "{\n"
    '  "domain": "finance" | "code" | "productivity" | "general",\n'
    '  "decision": "inform" | "execute" | "abort" | "research",\n'
    '  "rag_context_used": "brief one-line summary of live web data that influenced the verdict",\n'
    '  "reasoning": "detailed, professional synthesis of screen data + live web context"\n'
    "}\n\n"
    "Decision guide:\n"
    "  • inform   — present findings to the user, no action needed\n"
    "  • execute  — proceed with the suggested action/trade/automation\n"
    "  • abort    — halt, risk too high or data insufficient\n"
    "  • research — more investigation needed before deciding\n\n"
    "No markdown, no code fences, no text outside the JSON object."
)

VISION_SYSTEM = (
    "You are a universal screen analysis agent. The user has shared their screen "
    "and you are seeing a screenshot. Your job is to extract ALL useful information "
    "from whatever is visible — this could be:\n"
    "  • Financial charts, tickers, prices, volumes, trends\n"
    "  • Code editors, terminal output, error messages, file structures\n"
    "  • News articles, emails, social media posts\n"
    "  • Dashboards, spreadsheets, documents, any UI\n\n"
    "Describe exactly what you see: text, numbers, UI layout, data patterns. "
    "Be factual, precise, and thorough. Output plain text, no markdown.\n\n"
    "CRITICAL CONTEXT RULE: If the screenshot shows the 'X10V Headless Semantic "
    "Automation' dashboard or 'Alpha/Beta/Gamma' agent logs, output: "
    "'Self-referential UI detected. The user is capturing the X10V dashboard itself. "
    "No external data to analyze.'"
)


# ---------------------------------------------------------------------------
# Vision extraction — Groq Llama 4 Scout (real multimodal)
# ---------------------------------------------------------------------------

async def extract_vision_context(image_base64: str, user_command: str, broadcast: BroadcastFn = None) -> str:
    """
    Pass a real base64 screenshot to Groq's Llama 4 Scout vision model.
    The model physically reads the pixels — no mock data, no guessing.
    Domain-agnostic: works on finance, code, news, email, anything.
    Returns raw extracted text/data from the user's screen.
    """
    logger.info("👁️ Vision extraction starting via %s (image: %d chars) …", VISION_MODEL, len(image_base64))
    if broadcast:
        await broadcast(f"[Vision] 👁️ Sending screenshot to {VISION_MODEL} for real pixel analysis …")

    try:
        resp = groq_client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"User command: {user_command}. "
                                "Extract ALL useful information visible in this screenshot. "
                                "This could include: text, numbers, code, charts, UI elements, "
                                "prices, tickers, error messages, article content, email text, "
                                "dashboard metrics, or any other data. "
                                "Be highly precise and thorough. Return only the raw data. No markdown."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=600,
        )
        raw_content = resp.choices[0].message.content
        result = raw_content.strip() if raw_content else "Vision model returned empty response."

        logger.info("👁️ Vision extracted: %s", result[:200])
        if broadcast:
            preview = result[:50].replace("\n", " ")
            await broadcast(f"[Vision] 👁️ Successfully extracted screen data: {preview}…")
        return result

    except Exception as e:
        logger.error("👁️ Vision extraction FAILED: %s", e)
        if broadcast:
            await broadcast(f"[Vision] ⚠️ Vision model error: {str(e)[:80]}. Falling back to command text only.")
        return f"Vision extraction failed ({str(e)[:100]}). User command was: {user_command}"


# ---------------------------------------------------------------------------
# Individual agent calls
# ---------------------------------------------------------------------------

async def _call_alpha(text_data: str, context: str, broadcast: BroadcastFn = None) -> str:
    """Agent Alpha — Groq / llama-3.1-8b-instant (speed-optimised impulse)."""
    logger.info("🔵 Alpha (Impulse) starting analysis via %s …", ALPHA_MODEL)
    if broadcast:
        await broadcast(f"[Alpha/Impulse] Starting rapid analysis via {ALPHA_MODEL} …")

    prompt = f"Context from memory:\n{context}\n\nLive data:\n{text_data}"
    try:
        resp = groq_client.chat.completions.create(
            model=ALPHA_MODEL,
            messages=[
                {"role": "system", "content": ALPHA_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        result = resp.choices[0].message.content.strip()
    except Exception as e:
        result = "API limit reached. Defaulting to safe hold."
        logger.error("Alpha error: %s", e)

    logger.info("🔵 Alpha result: %s", result[:200])
    log_memory("Alpha", result[:500])
    if broadcast:
        await broadcast(f"[Alpha/Impulse] {result}")
    return result


async def _call_beta(text_data: str, alpha_result: str, context: str, rag_context: str = "", broadcast: BroadcastFn = None) -> str:
    """Agent Beta — Groq / llama-3.3-70b-versatile (deep reasoning + RAG cross-reference)."""
    logger.info("🟡 Beta (Sentinel) starting deep reasoning via %s …", BETA_MODEL)
    if broadcast:
        await broadcast(f"[Beta/Sentinel] Starting deep logical analysis via {BETA_MODEL} …")

    prompt = (
        f"Context from memory:\n{context}\n\n"
        f"Live data (screen):\n{text_data}\n\n"
        f"Alpha's rapid hypothesis:\n{alpha_result}\n\n"
        f"=== LIVE INTERNET SEARCH RESULTS (RAG) ===\n{rag_context}\n"
        f"=== END RAG ===\n\n"
        "Cross-reference the screen data with the live web results above. "
        "Flag any contradictions, risks, or opportunities."
    )
    try:
        resp = groq_client.chat.completions.create(
            model=BETA_MODEL,
            messages=[
                {"role": "system", "content": BETA_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        raw_content = resp.choices[0].message.content
        result = raw_content.strip() if raw_content else "Beta returned empty response. Defaulting to caution."
    except Exception as e:
        result = "Risk audit unavailable. Defaulting to high-caution state."
        logger.error("Beta error: %s", e)

    logger.info("🟡 Beta result: %s", result[:200])
    log_memory("Beta", result[:500])
    if broadcast:
        await broadcast(f"[Beta/Sentinel] {result}")
    return result


async def _call_gamma(
    alpha_result: str,
    beta_result: str,
    context: str,
    rag_summary: str = "",
    broadcast: BroadcastFn = None,
) -> dict:
    """Agent Gamma — Groq / llama-3.3-70b-versatile (arbiter, universal JSON via Groq native JSON mode)."""
    logger.info("🟢 Gamma (Arbiter) making final consensus via %s …", GAMMA_MODEL)
    if broadcast:
        await broadcast(f"[Gamma/Arbiter] Synthesising final consensus via {GAMMA_MODEL} …")

    prompt = (
        f"Context:\n{context}\n\n"
        f"Alpha says:\n{alpha_result}\n\n"
        f"Beta says (RAG-augmented):\n{beta_result}\n\n"
        f"RAG summary available: {rag_summary[:200] if rag_summary else 'None'}\n\n"
        "Produce your final JSON verdict with keys: domain, decision, rag_context_used, reasoning."
    )
    try:
        resp = groq_client.chat.completions.create(
            model=GAMMA_MODEL,
            messages=[
                {"role": "system", "content": GAMMA_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)

        # Ensure all four keys exist with sane defaults
        result.setdefault("domain", "general")
        result.setdefault("decision", "inform")
        result.setdefault("rag_context_used", "none")
        result.setdefault("reasoning", "No reasoning provided.")

        # Normalize decision to allowed values
        if result["decision"] not in ("inform", "execute", "abort", "research"):
            result["decision"] = "inform"

    except json.JSONDecodeError:
        result = {
            "domain": "general",
            "decision": "abort",
            "rag_context_used": "none",
            "reasoning": f"Gamma returned unparseable output: {raw[:120]}",
        }
        logger.error("Gamma JSON parse error. Raw: %s", raw[:200])
    except Exception as e:
        result = {
            "domain": "general",
            "decision": "abort",
            "rag_context_used": "none",
            "reasoning": "Swarm network congested. Safe mode engaged.",
        }
        logger.error("Gamma error: %s", e)

    decision_tag = {
        "execute": "✅ EXECUTE",
        "abort": "🛑 ABORT",
        "inform": "📋 INFORM",
        "research": "🔍 RESEARCH",
    }.get(result.get("decision"), "❓ UNKNOWN")

    logger.info("🟢 Gamma verdict: %s [%s] — %s", decision_tag, result.get("domain"), result.get("reasoning", "")[:120])
    log_memory("Gamma", json.dumps(result))

    if broadcast:
        decision = result.get("decision", "inform")
        colour = {"execute": "green", "abort": "red", "inform": "cyan", "research": "yellow"}.get(decision, "green")
        await broadcast(f"[Gamma/Arbiter|{colour}] {json.dumps(result)}")

    return result


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

async def run_swarm(
    text_data: str,
    force_vision: bool = False,
    broadcast: BroadcastFn = None,
) -> dict:
    """
    Orchestrate the five-stage swarm pipeline on TEXT data:
      1. Extract search query from screen text
      2. Live web RAG via DuckDuckGo
      3. Alpha (rapid hypothesis)
      4. Beta  (deep reasoning + RAG cross-reference)
      5. Gamma (final JSON verdict)

    Parameters
    ----------
    text_data : str
        Raw extracted text from a screen/webpage.
    force_vision : bool
        Reserved for future use.
    broadcast : callable | None
        Async callback to push live logs to the frontend via WebSocket.

    Returns
    -------
    dict  {"domain", "decision", "rag_context_used", "reasoning"}
    """
    logger.info("=" * 60)
    logger.info("SWARM INITIATED  |  data length=%d chars  |  vision=%s", len(text_data), force_vision)
    logger.info("=" * 60)

    if broadcast:
        await broadcast("[Swarm] ══════════ SWARM INITIATED ══════════")

    # Retrieve token-capped context from memory
    context = get_relevant_context(text_data[:200], max_tokens=500)

    # ── Stage 1: Extract search query + Live Web RAG ──
    search_query = extract_search_query(text_data, "")
    logger.info("🌐 RAG query extracted: '%s'", search_query)
    if broadcast:
        await broadcast(f"[RAG] 🌐 Searching the web for: \"{search_query}\" …")

    rag_context = await search_live_context(search_query, max_results=3)

    if broadcast:
        rag_preview = rag_context[:80].replace("\n", " ")
        has_data = "No live context" not in rag_context
        if has_data:
            await broadcast(f"[RAG] 🌐 Live web context injected: {rag_preview}…")
        else:
            await broadcast("[RAG] ⚠️ No live web results — proceeding with screen data only.")

    # ── Stage 2: Alpha (rapid hypothesis) ──
    alpha_result = await _call_alpha(text_data, context, broadcast)
    await asyncio.sleep(1.5)   # burst protection — avoid Groq rate-limit flags

    # ── Stage 3: Beta (deep reasoning + RAG cross-reference) ──
    beta_result = await _call_beta(text_data, alpha_result, context, rag_context, broadcast)
    await asyncio.sleep(1.5)   # burst protection — avoid Groq rate-limit flags

    # ── Stage 4: Gamma (final arbiter) ──
    gamma_verdict = await _call_gamma(alpha_result, beta_result, context, rag_context, broadcast)

    logger.info("=" * 60)
    logger.info("SWARM COMPLETE  |  verdict=%s", gamma_verdict)
    logger.info("=" * 60)

    if broadcast:
        decision = gamma_verdict.get("decision", "unknown")
        domain = gamma_verdict.get("domain", "general")
        await broadcast(f"[Swarm] ══════════ SWARM COMPLETE ══════════ [{domain.upper()}] verdict={decision}")

    return gamma_verdict
