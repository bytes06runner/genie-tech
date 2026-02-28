"""
live_rag.py — Zero-Cost Live Web Context via DuckDuckGo
=========================================================
Provides real-time internet context injection for the swarm debate.
Uses the duckduckgo-search library (text-only, no API key needed).

Functions:
  extract_search_query(text)        — Derive a 3-5 word search query from screen text
  search_live_context(query, max)   — Fetch top DDG results as a synthesized string
"""

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger("live_rag")


def extract_search_query(screen_text: str, user_command: str = "") -> str:
    """
    Derive a concise 3-5 word search query from extracted screen text
    and/or the user's command.

    Strategy:
      1. If user command contains a clear subject, use that + "latest"
      2. Otherwise, grab the first recognizable proper nouns / key phrases
         from the screen text, skipping generic site names
      3. Fallback: first 5 meaningful words of screen text
    """
    # Clean up the inputs
    cmd = user_command.strip()
    text = screen_text.strip()[:500]  # cap to avoid over-processing

    # Try to extract a meaningful subject from the user command
    # Remove common filler words
    filler = {
        "analyze", "this", "what", "do", "you", "see", "tell", "me", "about",
        "the", "is", "are", "show", "look", "at", "can", "please", "help",
        "screen", "chart", "page", "tab", "a", "an", "my", "check",
    }

    # Generic site / platform names that should not be the search subject
    site_noise = {
        "wikipedia", "google", "facebook", "twitter", "reddit", "youtube",
        "instagram", "linkedin", "github", "stack", "overflow", "stackoverflow",
        "amazon", "ebay", "wiki", "portal", "article", "read", "edit",
        "view", "history", "tools", "talk", "donate", "search", "log",
        "create", "account", "main", "menu", "contents", "navigation",
        "free", "encyclopedia", "from", "the", "for", "other", "uses",
        "see", "redirects", "here", "this", "that", "also", "not",
        "self", "referential", "detected", "user", "capturing", "dashboard",
        "external", "data", "text", "button", "logo", "photograph",
    }

    if cmd:
        words = [w for w in re.findall(r"[A-Za-z0-9]+", cmd) if w.lower() not in filler]
        if len(words) >= 2:
            return " ".join(words[:4]) + " latest"

    # Extract from screen text — look for capitalized phrases (likely proper nouns)
    # Filter out generic site/platform names
    caps = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", text)
    if caps:
        # Filter out generic noise phrases
        filtered_caps = [
            c for c in caps[:20]
            if not all(w.lower() in site_noise for w in c.split())
        ]
        if filtered_caps:
            # Prefer the FIRST significant proper noun — usually the page title / main subject
            # Only pick a longer phrase if it appears very early (within first 3)
            best = filtered_caps[0]
            return best + " latest news"

    # Fallback: first meaningful words from screen text (also filtering site noise)
    words = [
        w for w in re.findall(r"[A-Za-z0-9]+", text)
        if len(w) > 2 and w.lower() not in filler and w.lower() not in site_noise
    ]
    if words:
        return " ".join(words[:5])

    return "trending technology news today"


async def search_live_context(query: str, max_results: int = 3) -> str:
    """
    Perform a lightweight text-only DuckDuckGo search and return
    a synthesized string of the top results.

    Runs the synchronous DDGS call in a thread executor to keep
    the async event loop non-blocking.

    Returns "No live context available." on any failure — never crashes.
    """
    logger.info("🌐 RAG search starting: query='%s', max=%d", query, max_results)

    try:
        # Import here to isolate import errors
        from duckduckgo_search import DDGS

        def _sync_search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return results

        # Run blocking I/O in thread pool
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_search)

        if not results:
            logger.warning("🌐 RAG search returned 0 results for: %s", query)
            return "No live context available."

        # Synthesize into a readable block
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"[{i}] {title}\n    {body}\n    Source: {href}")

        synthesized = "\n\n".join(lines)
        logger.info("🌐 RAG search returned %d results (%d chars)", len(results), len(synthesized))
        return synthesized

    except ImportError:
        logger.error("🌐 duckduckgo-search not installed. RAG disabled.")
        return "No live context available (search library missing)."
    except Exception as e:
        logger.error("🌐 RAG search FAILED: %s", e)
        return "No live context available."
