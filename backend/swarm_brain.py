"""
swarm_brain.py — The Decision Engine (Multi-Agent Swarm)
=========================================================
Six-stage STATELESS pipeline — Gemini primary + Groq secondary:

  • Vision  (Gemini 2.5 Flash)      — Industry-leading multimodal screen reading
  • Router  (Groq / llama-3.1-8b)   — Smart Query Router (search vs local analysis)
  • Alpha   (Groq / llama-3.1-8b)   — Speed-optimised rapid hypothesis + Genius Student Mode
  • Beta    (Gemini 2.5 Flash)      — Deep Analyst: verification + academic audit
  • Gamma   (Gemini 2.5 Flash)      — Final arbiter, rich Markdown JSON verdict

Output contract (universal):
  {
    "domain":           "finance | code | education | general",
    "decision":         "inform | execute | abort",
    "structured_data":  {
        "summary":               "Concise 2-sentence overview",
        "timeline_or_metrics":   [{"key": "...", "value": "..."}]
    },
    "generate_file":    true | false,
    "file_type":        "pdf | md | none",
    "reasoning":        "internal swarm logic for this decision"
  }

STATE ISOLATION: Every function builds prompts from LOCAL variables only.
No global message arrays, no conversation history, no cross-query bleed.
Each API call = completely blank slate.

Architecture: Google Gemini (primary) + Groq (Alpha + Router) + Playwright Deep Scraper.
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
from query_engine import route_query

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("swarm_brain")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

BroadcastFn = Optional[Callable[[str], Coroutine[Any, Any, None]]]

ALPHA_MODEL  = "llama-3.1-8b-instant"
BETA_MODEL   = "gemini-2.5-flash"
GAMMA_MODEL  = "gemini-2.5-flash"
VISION_MODEL = "gemini-2.5-flash"
_STATELESS_PREAMBLE = (
    "CRITICAL INSTRUCTION: Base your analysis STRICTLY and ONLY on the provided "
    "screen text and live scraped data below. You have NO prior context. Do NOT "
    "assume, recall, or reference any previous queries, tickers, companies, or "
    "topics. Every analysis starts from a completely blank slate. "
    "If the provided data is insufficient, say so — do NOT fill gaps with guesses.\n\n"
)

ALPHA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Alpha (The Impulse) — an elite, rapid-response AI analyst and academic genius. "
    "Analyze the extracted screen text and the user's prompt. "
    "Step 1: Identify the domain — Finance, Code, Education (exams, lectures, textbooks), or General. "
    "Step 2: Formulate an immediate, highly competent analysis or action plan "
    "based ONLY on what is visible in the provided data. Be specific — cite data points you see.\n\n"
    "🎓 GENIUS STUDENT MODE:\n"
    "  • If the screen contains a QUESTION PAPER, EXAM, or PROBLEM SET — immediately solve "
    "every visible problem step-by-step. Show your working clearly.\n"
    "  • If the screen contains a CODING PROBLEM (Python, Java, C++, DSA, algorithms) — "
    "write the complete solution code with comments explaining each step.\n"
    "  • If the screen contains LECTURE SLIDES, TEXTBOOK PAGES, or academic text "
    "(computer architecture, quantum mechanics, data structures, etc.) — draft comprehensive "
    "study notes: key concepts, definitions, formulas, and exam-ready bullet points.\n"
    "  • If the screen contains an ARTICLE or DOCUMENTATION — summarize the key points "
    "with structured bullet points.\n\n"
    "For academic/code content, be as thorough as possible — aim for ≤300 words. "
    "For other domains, provide your assessment in ≤150 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research.\n\n"
    "CRITICAL CONTEXT RULE: If the extracted text describes the 'X10V Headless Semantic "
    "Automation' dashboard or shows 'Alpha/Beta/Gamma' agent logs, this means the user "
    "accidentally captured their own dashboard. Output a brief ABORT: "
    "'Self-referential UI detected. Switch screen-share to your target application.'"
)

BETA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Beta (The Deep Analyst) — an advanced research, verification, and academic audit node. "
    "You receive: (1) the raw screen data, (2) Alpha's rapid hypothesis/solution, and "
    "(3) REAL WEBPAGE TEXT scraped live from the internet (if available). "
    "Your job is to AUDIT and ENRICH Alpha's work:\n\n"
    "🔬 VERIFICATION MODE (when live scraped data is available):\n"
    "  • Cross-reference the screen data with the live scraped webpage content.\n"
    "  • Identify factual errors, market risks, code bugs, outdated information, "
    "or opportunities Alpha may have missed.\n"
    "  • If the scraped data contradicts the screen, flag it explicitly with specific data points.\n\n"
    "🎓 ACADEMIC AUDIT MODE (when no live scrape — local analysis):\n"
    "  • If Alpha solved a MATH or PHYSICS problem — check each step for logical fallacies, "
    "arithmetic errors, or incorrect formulas. Verify the final answer.\n"
    "  • If Alpha wrote CODE — check for syntax errors, edge cases, time/space complexity issues, "
    "and suggest optimizations.\n"
    "  • If Alpha summarized an article or lecture — ensure no critical facts, definitions, "
    "or key concepts were omitted. Add any missing context.\n"
    "  • If Alpha generated study notes — verify completeness and add any missing formulas, "
    "theorems, or exam-relevant points.\n\n"
    "Provide your analysis in ≤250 words. "
    "End with a clear RECOMMENDATION: inform, execute, abort, or research."
)

GAMMA_SYSTEM = (
    _STATELESS_PREAMBLE +
    "You are Agent Gamma (The Arbiter) — the final consensus engine and structured data "
    "distiller. You receive Alpha's rapid take and Beta's deep audit/analysis. "
    "Your job is to synthesize their work into CLEAN, STRUCTURED JSON — never long paragraphs.\n\n"

    "You MUST output ONLY a valid JSON object with exactly these six keys:\n"
    "{\n"
    '  "domain": "finance" | "code" | "education" | "general",\n'
    '  "decision": "inform" | "execute" | "abort",\n'
    '  "structured_data": {\n'
    '    "summary": "A concise 2-sentence overview of the final analysis.",\n'
    '    "timeline_or_metrics": [\n'
    '      {"key": "Date, Metric, Step, or Label", "value": "Event, Data Point, or Detail"}\n'
    '    ]\n'
    '  },\n'
    '  "generate_file": true | false,\n'
    '  "file_type": "pdf" | "md" | "none",\n'
    '  "reasoning": "Internal swarm logic for this decision"\n'
    "}\n\n"

    "═══ STRUCTURED DATA DIRECTIVE ═══\n"
    "Stop writing long paragraphs. Distill ALL analysis into the structured_data object.\n"
    "Extract key dates, financial metrics, code steps, or concepts into the "
    "timeline_or_metrics array as DISTINCT key-value pairs.\n\n"

    "DOMAIN-SPECIFIC EXTRACTION RULES:\n\n"

    "📚 Education / History:\n"
    "  • summary: 2 sentences covering the topic and key takeaway.\n"
    "  • timeline_or_metrics: Extract each important date, concept, formula, or "
    "definition as a separate {key, value} pair.\n"
    "  • Example keys: '1776', 'Newton\\'s 2nd Law', 'Time Complexity', 'Definition: Recursion'\n\n"

    "📈 Finance / Stock:\n"
    "  • summary: 2 sentences — asset name, trend, and recommendation.\n"
    "  • timeline_or_metrics: Extract each metric as a pair.\n"
    "  • Example keys: 'CMP', 'P/E Ratio', '52W High', 'RSI', 'Support Level', "
    "'Risk Level', 'Verdict'\n\n"

    "💻 Code:\n"
    "  • summary: 2 sentences — what the code does, any bugs found.\n"
    "  • timeline_or_metrics: Extract each bug, fix step, or implementation step.\n"
    "  • Example keys: 'Bug #1', 'Fix', 'Step 1', 'Step 2', 'Complexity', 'Language'\n"
    "  • For code solutions, put the complete code as the value of a 'Solution Code' key.\n\n"

    "📋 General:\n"
    "  • summary: 2 sentences covering the main finding.\n"
    "  • timeline_or_metrics: Extract each key finding, fact, or recommendation.\n\n"

    "QUANTITY RULES:\n"
    "  • timeline_or_metrics MUST have at least 3 entries and at most 15.\n"
    "  • Each value should be concise — 1-2 sentences max.\n"
    "  • Keys should be short labels (≤5 words), values are the data.\n\n"

    "DECISION GUIDE:\n"
    "  • inform   — presenting analysis, study notes, information to the user\n"
    "  • execute  — actionable recommendation (trade, deploy code, submit answer)\n"
    "  • abort    — data is insufficient, self-referential, or contradictory\n\n"

    "FILE GENERATION RULES:\n"
    "  • Set generate_file to true ONLY IF the user explicitly asks for a file, "
    "PDF, document, download, export, or notes file.\n"
    "  • Keywords: 'pdf', 'download', 'export', 'save', 'document', 'file', "
    "'generate pdf', 'make a doc'.\n"
    "  • Default file_type to 'pdf'. If user says 'markdown' or 'md', use 'md'.\n"
    "  • If generate_file is false, set file_type to 'none'.\n\n"

    "No text outside the JSON object. Escape special characters properly in JSON strings."
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
        vision_prompt = (
            f"User command: {user_command}. "
            "Extract ALL useful information visible in this screenshot. "
            "This could include: text, numbers, code, charts, UI elements, "
            "prices, tickers, error messages, article content, email text, "
            "dashboard metrics, or any other data. "
            "Be highly precise and thorough. Return only the raw data. No markdown."
        )

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
                "max_output_tokens": 2048,
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


async def _call_alpha(text_data: str, broadcast: BroadcastFn = None) -> str:
    """
    Agent Alpha — Groq / llama-3.1-8b-instant (speed-optimised impulse).
    STATELESS: fresh message list, no memory injection, no global state.
    """
    logger.info("🔵 Alpha (Impulse) starting analysis via Groq/%s …", ALPHA_MODEL)
    if broadcast:
        await broadcast(f"[Alpha/Impulse] Starting rapid analysis via Groq/{ALPHA_MODEL} …")

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
            max_tokens=600,
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

    scrape_section = (
        f"=== LIVE SCRAPED WEBPAGE (from {scraped_url}) ===\n{scraped_data}\n=== END SCRAPED DATA ==="
        if scraped_data and scraped_data.strip()
        else "=== NO LIVE SCRAPE PERFORMED ===\nThe Query Router determined no internet search was needed. "
             "Focus on auditing Alpha's analysis using ONLY the screen data."
    )

    local_prompt = (
        "Below is ALL the data you have. You have NO prior context.\n\n"
        f"=== SCREEN DATA ===\n{text_data}\n=== END SCREEN DATA ===\n\n"
        f"=== ALPHA'S HYPOTHESIS / SOLUTION ===\n{alpha_result}\n=== END ALPHA ===\n\n"
        f"{scrape_section}\n\n"
        "Audit Alpha's work thoroughly. If scraped data is available, cross-reference it. "
        "If no scrape was performed, focus on verifying Alpha's logic, math, code, or analysis. "
        "Flag any errors, omissions, or improvements with specific data points."
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
                "max_output_tokens": 2048,
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
    user_command: str = "",
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

    local_prompt = (
        "Below is ALL the data you have. You have NO prior context. "
        "Do NOT reference any previous queries or topics.\n\n"
        f"=== USER COMMAND ===\n{user_command}\n=== END USER COMMAND ===\n\n"
        f"=== ALPHA SAYS ===\n{alpha_result}\n=== END ALPHA ===\n\n"
        f"=== BETA SAYS (audit/verification) ===\n{beta_result}\n=== END BETA ===\n\n"
        f"Scraped web summary: {scraped_summary[:200] if scraped_summary else 'None — local analysis only'}\n\n"
        "Produce your final JSON verdict with keys: domain, decision, structured_data, "
        "generate_file, file_type, reasoning. "
        "Distill everything into structured_data.summary (2 sentences) and "
        "structured_data.timeline_or_metrics (array of {key, value} pairs)."
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
                "max_output_tokens": 8192,
            },
        )

        raw = response.text.strip() if response.text else "{}"
        result = json.loads(raw)

        result.setdefault("domain", "general")
        result.setdefault("decision", "inform")
        result.setdefault("structured_data", {
            "summary": "No summary generated.",
            "timeline_or_metrics": []
        })
        result.setdefault("generate_file", False)
        result.setdefault("file_type", "none")
        result.setdefault("reasoning", "No reasoning provided.")

        sd = result["structured_data"]
        if not isinstance(sd, dict):
            result["structured_data"] = {
                "summary": str(sd)[:200] if sd else "No summary generated.",
                "timeline_or_metrics": []
            }
        else:
            sd.setdefault("summary", "No summary generated.")
            sd.setdefault("timeline_or_metrics", [])
            if not isinstance(sd["timeline_or_metrics"], list):
                sd["timeline_or_metrics"] = []

        if isinstance(result["generate_file"], str):
            result["generate_file"] = result["generate_file"].lower() in ("true", "yes", "1")

        if result["file_type"] not in ("pdf", "md", "none"):
            result["file_type"] = "none"
        if not result["generate_file"]:
            result["file_type"] = "none"

        valid_decisions = ("inform", "execute", "abort")
        if result["decision"] not in valid_decisions:
            result["decision"] = "inform"

    except json.JSONDecodeError:
        result = {
            "domain": "general",
            "decision": "abort",
            "structured_data": {
                "summary": "Gamma returned unparseable output. Raw data could not be processed.",
                "timeline_or_metrics": [
                    {"key": "Error", "value": f"JSON parse failure: {raw[:120]}"}
                ]
            },
            "generate_file": False,
            "file_type": "none",
            "reasoning": f"Gamma returned unparseable output: {raw[:120]}",
        }
        logger.error("Gamma JSON parse error. Raw: %s", raw[:200])
    except Exception as e:
        result = {
            "domain": "general",
            "decision": "abort",
            "structured_data": {
                "summary": f"Gamma encountered an error: {str(e)[:100]}. Safe mode engaged.",
                "timeline_or_metrics": [
                    {"key": "Error", "value": str(e)[:120]}
                ]
            },
            "generate_file": False,
            "file_type": "none",
            "reasoning": f"Gemini Gamma error: {str(e)[:80]}. Safe mode engaged.",
        }
        logger.error("Gamma error: %s", e)

    decision_tag = {
        "inform": "📋 INFORM",
        "execute": "✅ EXECUTE",
        "abort": "🛑 ABORT",
    }.get(result.get("decision"), "❓ UNKNOWN")

    logger.info("🟢 Gamma verdict: %s [%s] — %s", decision_tag, result.get("domain"), result.get("reasoning", "")[:120])
    log_memory("Gamma", json.dumps(result)[:1000])

    if broadcast:
        decision = result.get("decision", "inform")
        colour = {
            "inform": "cyan",
            "execute": "green",
            "abort": "red",
        }.get(decision, "cyan")
        await broadcast(f"[Gamma/Arbiter|{colour}] {json.dumps(result)}")

    return result


async def run_swarm(
    text_data: str,
    user_command: str = "",
    force_vision: bool = False,
    broadcast: BroadcastFn = None,
) -> dict:
    """
    Orchestrate the six-stage STATELESS swarm pipeline:
      1. Smart Query Router — Groq decides: search web or local analysis
      2. (Conditional) Deep Scrape via Playwright — only if Router says SEARCH
      3. Alpha — Groq rapid hypothesis / Genius Student Mode (STATELESS)
      4. Beta  — Gemini deep audit + optional scraped data (STATELESS)
      5. Gamma — Gemini final rich Markdown JSON verdict (STATELESS)

    CRITICAL: All variables are LOCAL. No global message arrays, no conversation
    history, no cross-query state pollution. Each call = blank slate.

    Parameters
    ----------
    text_data : str
        Raw extracted text from a screen/webpage.
    user_command : str
        The user's original command/prompt.
    force_vision : bool
        Reserved for future use.
    broadcast : callable | None
        Async callback to push live logs to the frontend via WebSocket.

    Returns
    -------
    dict  {"domain", "decision", "structured_data", "generate_file", "file_type", "reasoning"}
    """
    local_text = str(text_data)
    local_command = str(user_command)
    local_search_query = ""
    local_scraped_text = ""
    local_scraped_url = ""
    local_alpha_result = ""
    local_beta_result = ""
    local_search_skipped = False

    logger.info("=" * 60)
    logger.info("SWARM INITIATED  |  data length=%d chars  |  vision=%s", len(local_text), force_vision)
    logger.info("=" * 60)

    if broadcast:
        await broadcast("[Swarm] ══════════ SWARM INITIATED ══════════")

    if broadcast:
        await broadcast("[QueryRouter] 🧭 Analyzing intent — search web or local analysis? …")

    try:
        router_decision = route_query(local_command, local_text)
    except Exception as e:
        logger.error("Query Router failed: %s — falling back to regex extraction", e)
        router_decision = extract_search_query(local_text, local_command)

    if router_decision == "NO_SEARCH_NEEDED":
        local_search_skipped = True
        local_scraped_text = "User requested local analysis. No external web search performed."
        local_scraped_url = ""
        logger.info("🧭 Router: NO_SEARCH_NEEDED — skipping Deep Scraper")
        if broadcast:
            await broadcast("[QueryRouter] 🧭 Verdict: NO_SEARCH_NEEDED — local analysis mode activated")
            await broadcast("[DeepScraper] ⏭️ Skipped — no internet search needed for this task")
    else:
        local_search_query = router_decision
        logger.info("🧭 Router: SEARCH → '%s'", local_search_query)
        if broadcast:
            await broadcast(f"[QueryRouter] 🧭 Verdict: SEARCH → \"{local_search_query}\"")
            await broadcast(f"[DeepScraper] 🔍 Searching & scraping the web for: \"{local_search_query}\" …")

        # Deep Scrape (only if Router says search)
        scrape_result = await deep_scrape(local_search_query, timeout_seconds=8)
        local_scraped_text = scrape_result.get("text", "")
        local_scraped_url = scrape_result.get("url", "")

        if broadcast:
            if scrape_result.get("success"):
                preview = local_scraped_text[:80].replace("\n", " ")
                await broadcast(f"[DeepScraper] ✅ Scraped {len(local_scraped_text)} chars from {local_scraped_url}: {preview}…")
            else:
                await broadcast("[DeepScraper] ⚠️ Scrape failed — proceeding with screen data only.")

    local_alpha_result = await _call_alpha(local_text, broadcast)
    await asyncio.sleep(1.5)

    local_beta_result = await _call_beta(
        local_text, local_alpha_result,
        scraped_data=local_scraped_text if not local_search_skipped else "",
        scraped_url=local_scraped_url,
        broadcast=broadcast,
    )
    await asyncio.sleep(1.0)

    gamma_verdict = await _call_gamma(
        local_alpha_result, local_beta_result,
        scraped_summary=local_scraped_text[:300] if not local_search_skipped else "",
        user_command=local_command,
        broadcast=broadcast,
    )

    logger.info("=" * 60)
    logger.info("SWARM COMPLETE  |  verdict=%s", {k: v[:80] if isinstance(v, str) else v for k, v in gamma_verdict.items()})
    logger.info("=" * 60)

    if broadcast:
        decision = gamma_verdict.get("decision", "inform")
        domain = gamma_verdict.get("domain", "general")
        await broadcast(f"[Swarm] ══════════ SWARM COMPLETE ══════════ [{domain.upper()}] decision={decision}")

    return gamma_verdict
