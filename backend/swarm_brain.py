"""
swarm_brain.py — The Decision Engine (Multi-Agent Swarm)
=========================================================
Five-stage STATELESS pipeline — Gemini primary + Groq secondary:

  • Vision  (Gemini 2.5 Flash)      — Industry-leading multimodal screen reading
  • Alpha   (Groq / llama-3.1-8b)   — Speed-optimised rapid hypothesis (architectural friction)
  • Beta    (Gemini 2.5 Flash)      — Deep Scraper agent: DDG → Playwright → analysis
  • Gamma   (Gemini 2.5 Flash)      — Final arbiter, native JSON mode verdict

Output contract (universal):
  {
    "domain":           "finance | code | productivity | general",
    "decision":         "inform | execute | abort | research",
    "rag_context_used": "brief summary of live web data used",
    "reasoning":        "detailed synthesis"
  }

STATE ISOLATION: Every function builds prompts from LOCAL variables only.
No global message arrays, no conversation history, no cross-query bleed.
Each API call = completely blank slate.

Architecture: Google Gemini (primary) + Groq (Alpha only) + Playwright Deep Scraper.
"""

import json
import logging
import os
import asyncio
from typing import Any, Callable, Coroutine, Optional

from dotenv import load_dotenv
from groq import Groq
from google import genai

from memory_manager import log_memory
from deep_scraper import deep_scrape
from live_rag import extract_search_query

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("swarm_brain")

# ---------------------------------------------------------------------------
# Clients — stateless singletons (no conversation history stored)
# ---------------------------------------------------------------------------
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Type alias for the broadcast callback
BroadcastFn = Optional[Callable[[str], Coroutine[Any, Any, None]]]

# ---------------------------------------------------------------------------
# Model routing
# ---------------------------------------------------------------------------
ALPHA_MODEL  = "llama-3.1-8b-instant"                   # Groq — fastest impulse
BETA_MODEL   = "gemini-2.5-flash-preview-05-20"         # Gemini — deep scraper analyst
GAMMA_MODEL  = "gemini-2.5-flash-preview-05-20"         # Gemini — final arbiter (JSON mode)
VISION_MODEL = "gemini-2.5-flash-preview-05-20"         # Gemini — multimodal vision

# ---------------------------------------------------------------------------
# STATELESS system prompts — every agent is told to IGNORE prior context
# ---------------------------------------------------------------------------
_STATELESS_PREAMBLE = (
    "CRITICAL INSTRUCTION: Base your analysis STRICTLY and ONLY on the provided "
    "screen text and live scraped data below. You have NO prior context. Do NOT "
    "assume, recall, or reference any previous queries, tickers, companies, or "
    "topics. Every analysis starts from a completely blank slate. "
    "If the provided data is insufficient, say so — do NOT fill gaps with guesses.\n\n"
)

ALPHA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Alpha (The Impulse) — an elite, rapid-response AI analyst. "
    "Analyze the extracted screen text and the user's prompt. "
    "Step 1: Identify the domain (Finance, Code, Productivity, Social Media, News, General). "
    "Step 2: Formulate an immediate, highly competent analysis or action plan "
    "based ONLY on what is visible in the provided data. Be specific — cite data points you see. "
    "Provide your assessment in ≤120 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research. "
    "\n\n"
    "CRITICAL CONTEXT RULE: If the extracted text describes the 'X10V Headless Semantic "
    "Automation' dashboard or shows 'Alpha/Beta/Gamma' agent logs, this means the user "
    "accidentally captured their own dashboard. Output a brief ABORT: "
    "'Self-referential UI detected. Switch screen-share to your target application.'"
)

BETA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Beta (The Deep Analyst) — an advanced research and verification node. "
    "You receive: (1) the raw screen data, (2) Alpha's rapid hypothesis, and "
    "(3) REAL WEBPAGE TEXT scraped live from the internet via a headless browser. "
    "Your job: cross-reference the screen data with the live scraped webpage content. "
    "Identify factual errors, market risks, code bugs, outdated information, "
    "or opportunities Alpha may have missed. "
    "If the scraped data contradicts the screen, flag it explicitly with specific data points. "
    "Provide your analysis in ≤180 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research."
)

GAMMA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Gamma (The Arbiter) — the final consensus engine. "
    "You receive Alpha's rapid take and Beta's deep web-scrape-augmented analysis. "
    "Synthesize their debate into a definitive verdict.\n\n"
    "You MUST output ONLY a valid JSON object with exactly these four keys:\n"
    "{\n"
    '  "domain": "finance" | "code" | "productivity" | "general",\n'
    '  "decision": "inform" | "execute" | "abort" | "research",\n'
    '  "rag_context_used": "brief one-line summary of live scraped web data that influenced the verdict",\n'
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
    _STATELESS_PREAMBLE +
    "You are a universal screen analysis agent powered by Gemini. The user has shared "
    "their screen and you are seeing a screenshot. Your job is to extract ALL useful "
    "information from whatever is visible — this could be:\n"
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
# Vision extraction — Gemini 2.5 Flash (multimodal)
# ---------------------------------------------------------------------------

async def extract_vision_context(image_base64: str, user_command: str, broadcast: BroadcastFn = None) -> str:
    """
    Pass a real base64 screenshot to Gemini 2.5 Flash for vision extraction.
    Gemini's multimodal capabilities provide industry-leading screen reading.
    STATELESS: builds a fresh message list on every call — zero history.
    """
    logger.info("👁️ Vision extraction starting via Gemini/%s (image: %d chars) …", VISION_MODEL, len(image_base64))
    if broadcast:
        await broadcast(f"[Vision] 👁️ Sending screenshot to Gemini {VISION_MODEL} for pixel analysis …")

    try:
        # Build a completely LOCAL prompt — no global state
        vision_prompt = (
            f"User command: {user_command}. "
            "Extract ALL useful information visible in this screenshot. "
            "This could include: text, numbers, code, charts, UI elements, "
            "prices, tickers, error messages, article content, email text, "
            "dashboard metrics, or any other data. "
            "Be highly precise and thorough. Return only the raw data. No markdown."
        )

        # Gemini multimodal: pass image as inline_data part
        response = gemini_client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": VISION_SYSTEM + "\n\n" + vision_prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}},
                    ],
                }
            ],
            config={
                "temperature": 0.2,
                "max_output_tokens": 600,
            },
        )

        result = response.text.strip() if response.text else "Vision model returned empty response."

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
# Individual agent calls — ALL STATELESS (local variables only)
# ---------------------------------------------------------------------------

async def _call_alpha(text_data: str, broadcast: BroadcastFn = None) -> str:
    """
    Agent Alpha — Groq / llama-3.1-8b-instant (speed-optimised impulse).
    STATELESS: fresh message list, no memory injection, no global state.
    """
    logger.info("🔵 Alpha (Impulse) starting analysis via Groq/%s …", ALPHA_MODEL)
    if broadcast:
        await broadcast(f"[Alpha/Impulse] Starting rapid analysis via Groq/{ALPHA_MODEL} …")

    # LOCAL prompt — no prior context, no memory bleed
    local_prompt = (
        "Below is the ONLY data you have. Analyze it from scratch.\n\n"
        f"Live data:\n{text_data}"
    )

    try:
        resp = groq_client.chat.completions.create(
            model=ALPHA_MODEL,
            messages=[
                {"role": "system", "content": ALPHA_SYSTEM},
                {"role": "user", "content": local_prompt},
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


async def _call_beta(
    text_data: str,
    alpha_result: str,
    scraped_data: str = "",
    scraped_url: str = "",
    broadcast: BroadcastFn = None,
) -> str:
    """
    Agent Beta — Gemini 2.5 Flash (deep scraper analyst).
    Receives Alpha's hypothesis + real scraped webpage content.
    STATELESS: fresh message list, no memory injection, no global state.
    """
    logger.info("🟡 Beta (Deep Analyst) starting via Gemini/%s …", BETA_MODEL)
    if broadcast:
        await broadcast(f"[Beta/DeepAnalyst] Starting deep analysis via Gemini/{BETA_MODEL} …")

    # LOCAL prompt — all data is passed explicitly, no global references
    local_prompt = (
        "Below is ALL the data you have. You have NO prior context.\n\n"
        f"=== SCREEN DATA ===\n{text_data}\n=== END SCREEN DATA ===\n\n"
        f"=== ALPHA'S HYPOTHESIS ===\n{alpha_result}\n=== END ALPHA ===\n\n"
        f"=== LIVE SCRAPED WEBPAGE (from {scraped_url}) ===\n{scraped_data}\n=== END SCRAPED DATA ===\n\n"
        "Cross-reference the screen data with the scraped webpage content above. "
        "Flag any contradictions, risks, or opportunities with specific data points."
    )

    try:
        response = gemini_client.models.generate_content(
            model=BETA_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": BETA_SYSTEM + "\n\n" + local_prompt}],
                }
            ],
            config={
                "temperature": 0.2,
                "max_output_tokens": 400,
            },
        )
        result = response.text.strip() if response.text else "Beta returned empty response. Defaulting to caution."
    except Exception as e:
        result = f"Gemini Beta error: {str(e)[:80]}. Defaulting to high-caution state."
        logger.error("Beta error: %s", e)

    logger.info("🟡 Beta result: %s", result[:200])
    log_memory("Beta", result[:500])
    if broadcast:
        await broadcast(f"[Beta/DeepAnalyst] {result}")
    return result


async def _call_gamma(
    alpha_result: str,
    beta_result: str,
    scraped_summary: str = "",
    broadcast: BroadcastFn = None,
) -> dict:
    """
    Agent Gamma — Gemini 2.5 Flash (arbiter, native JSON mode).
    Uses response_mime_type: application/json for enforced schema.
    STATELESS: fresh message list, no memory injection, no global state.
    """
    logger.info("🟢 Gamma (Arbiter) making final consensus via Gemini/%s …", GAMMA_MODEL)
    if broadcast:
        await broadcast(f"[Gamma/Arbiter] Synthesising final consensus via Gemini/{GAMMA_MODEL} …")

    # LOCAL prompt — zero prior context
    local_prompt = (
        "Below is ALL the data you have. You have NO prior context. "
        "Do NOT reference any previous queries or topics.\n\n"
        f"=== ALPHA SAYS ===\n{alpha_result}\n=== END ALPHA ===\n\n"
        f"=== BETA SAYS (web-scrape-augmented) ===\n{beta_result}\n=== END BETA ===\n\n"
        f"Scraped web summary: {scraped_summary[:200] if scraped_summary else 'None'}\n\n"
        "Produce your final JSON verdict with keys: domain, decision, rag_context_used, reasoning."
    )

    try:
        response = gemini_client.models.generate_content(
            model=GAMMA_MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": GAMMA_SYSTEM + "\n\n" + local_prompt}],
                }
            ],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "max_output_tokens": 400,
            },
        )

        raw = response.text.strip() if response.text else "{}"
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
            "reasoning": f"Gemini Gamma error: {str(e)[:80]}. Safe mode engaged.",
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
# Public orchestrator — FULLY STATELESS
# ---------------------------------------------------------------------------

async def run_swarm(
    text_data: str,
    force_vision: bool = False,
    broadcast: BroadcastFn = None,
) -> dict:
    """
    Orchestrate the five-stage STATELESS swarm pipeline:
      1. Extract search query from screen text (local derivation)
      2. Deep Scrape via Playwright (DDG URL → headless browser → page text)
      3. Alpha — Groq rapid hypothesis (STATELESS)
      4. Beta  — Gemini deep analysis + scraped web cross-reference (STATELESS)
      5. Gamma — Gemini final JSON verdict (STATELESS, native JSON mode)

    CRITICAL: All variables are LOCAL. No global message arrays, no conversation
    history, no cross-query state pollution. Each call = blank slate.

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
    # ── ALL LOCAL VARIABLES — no global state ──
    local_text = str(text_data)  # defensive copy
    local_search_query = ""
    local_scraped_text = ""
    local_scraped_url = ""
    local_alpha_result = ""
    local_beta_result = ""

    logger.info("=" * 60)
    logger.info("SWARM INITIATED  |  data length=%d chars  |  vision=%s", len(local_text), force_vision)
    logger.info("=" * 60)

    if broadcast:
        await broadcast("[Swarm] ══════════ SWARM INITIATED ══════════")

    # ── Stage 1: Extract search query + Deep Scrape ──
    local_search_query = extract_search_query(local_text, "")
    logger.info("🌐 Search query extracted: '%s'", local_search_query)
    if broadcast:
        await broadcast(f"[DeepScraper] 🔍 Searching & scraping the web for: \"{local_search_query}\" …")

    scrape_result = await deep_scrape(local_search_query, timeout_seconds=8)
    local_scraped_text = scrape_result.get("text", "")
    local_scraped_url = scrape_result.get("url", "")

    if broadcast:
        if scrape_result.get("success"):
            preview = local_scraped_text[:80].replace("\n", " ")
            await broadcast(f"[DeepScraper] ✅ Scraped {len(local_scraped_text)} chars from {local_scraped_url}: {preview}…")
        else:
            await broadcast("[DeepScraper] ⚠️ Scrape failed — proceeding with screen data only.")

    # ── Stage 2: Alpha (Groq — rapid hypothesis, STATELESS) ──
    local_alpha_result = await _call_alpha(local_text, broadcast)
    await asyncio.sleep(1.5)  # burst protection

    # ── Stage 3: Beta (Gemini — deep analysis + scraped data, STATELESS) ──
    local_beta_result = await _call_beta(
        local_text, local_alpha_result,
        scraped_data=local_scraped_text,
        scraped_url=local_scraped_url,
        broadcast=broadcast,
    )
    await asyncio.sleep(1.0)  # burst protection

    # ── Stage 4: Gamma (Gemini — final arbiter, STATELESS, JSON mode) ──
    gamma_verdict = await _call_gamma(
        local_alpha_result, local_beta_result,
        scraped_summary=local_scraped_text[:300],
        broadcast=broadcast,
    )

    logger.info("=" * 60)
    logger.info("SWARM COMPLETE  |  verdict=%s", gamma_verdict)
    logger.info("=" * 60)

    if broadcast:
        decision = gamma_verdict.get("decision", "unknown")
        domain = gamma_verdict.get("domain", "general")
        await broadcast(f"[Swarm] ══════════ SWARM COMPLETE ══════════ [{domain.upper()}] verdict={decision}")

    return gamma_verdict
