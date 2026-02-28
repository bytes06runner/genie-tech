"""
query_engine.py — Smart Query Router (Pre-Scrape Intelligence)
================================================================
Ultra-fast Groq-powered routing layer that runs BEFORE the Deep Scraper.
Determines whether live web data is needed or if the screen content alone
is sufficient for analysis (e.g., exam papers, lecture slides, static articles).

Returns:
  • "NO_SEARCH_NEEDED"  — Skip deep_scraper entirely (local analysis mode)
  • A 3-5 word search query — Feed to deep_scraper for live web enrichment

Model: Groq / llama-3.1-8b-instant (~200ms latency)
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger("query_engine")

# ---------------------------------------------------------------------------
# Client — stateless singleton
# ---------------------------------------------------------------------------
_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
_ROUTER_MODEL = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# System prompt for the routing agent
# ---------------------------------------------------------------------------
_ROUTER_SYSTEM = (
    "You are a routing agent for an AI automation platform. Your ONLY job is to "
    "decide whether live internet data is needed to answer the user's request.\n\n"
    "You receive two inputs:\n"
    "  1. The user's command/prompt\n"
    "  2. Extracted screen text (what the AI sees on screen)\n\n"
    "RULES:\n"
    "  • If the user is asking a general knowledge question, asking to solve a "
    "visible exam/question paper, asking to summarize or explain visible text, "
    "asking to debug visible code, asking to generate notes from visible lecture "
    "slides, or any task that can be completed using ONLY the visible screen data "
    "— output EXACTLY the string: NO_SEARCH_NEEDED\n\n"
    "  • If the user asks for LIVE data (e.g., 'What is the current stock price?', "
    "'Any news on this?', 'latest updates', 'what happened recently', 'current market', "
    "'trending'), output a highly specific 3-5 word search query based on the screen "
    "context. Examples:\n"
    "    - Screen shows Ferrari Wikipedia → 'Ferrari latest corporate news'\n"
    "    - Screen shows HDFC Bank chart → 'HDFC Bank stock price today'\n"
    "    - Screen shows React code → 'React 19 breaking changes'\n\n"
    "OUTPUT FORMAT: Return ONLY the routing decision — either 'NO_SEARCH_NEEDED' or "
    "the search query string. No explanations, no punctuation, no extra text."
)


def route_query(user_command: str, screen_text: str) -> str:
    """
    Classify the user's intent and return either NO_SEARCH_NEEDED
    or a targeted 3-5 word search query.

    STATELESS: fresh message list on every call. ~200ms via Groq.
    """
    logger.info("🧭 Query Router — classifying intent …")

    # Build LOCAL prompt — no global state
    local_prompt = (
        f"=== USER COMMAND ===\n{user_command}\n=== END COMMAND ===\n\n"
        f"=== SCREEN TEXT (first 600 chars) ===\n{screen_text[:600]}\n=== END SCREEN TEXT ===\n\n"
        "Based on the above, should I search the web? "
        "Output ONLY 'NO_SEARCH_NEEDED' or a 3-5 word search query."
    )

    try:
        resp = _groq_client.chat.completions.create(
            model=_ROUTER_MODEL,
            messages=[
                {"role": "system", "content": _ROUTER_SYSTEM},
                {"role": "user", "content": local_prompt},
            ],
            temperature=0.0,
            max_tokens=30,
        )
        raw = resp.choices[0].message.content.strip()

        # Normalize — strip quotes, periods, extra whitespace
        cleaned = raw.strip("\"'`.!").strip()

        if "NO_SEARCH_NEEDED" in cleaned.upper():
            logger.info("🧭 Router verdict: NO_SEARCH_NEEDED (local analysis mode)")
            return "NO_SEARCH_NEEDED"

        # Ensure query is reasonable length (3-8 words)
        words = cleaned.split()
        if len(words) > 8:
            cleaned = " ".join(words[:6])
        if len(words) < 2:
            # Too short — fall back to extracting from screen text
            logger.warning("🧭 Router returned too-short query: '%s'. Passing through.", cleaned)

        logger.info("🧭 Router verdict: SEARCH → '%s'", cleaned)
        return cleaned

    except Exception as e:
        logger.error("🧭 Query Router FAILED: %s — defaulting to search mode", e)
        # On failure, fall back to the old regex-based extraction
        from live_rag import extract_search_query
        return extract_search_query(screen_text, user_command)
