"""
deep_scraper.py — Playwright-Powered Deep Web Scraper
=======================================================
Advanced async scraper that goes beyond snippet-level RAG:

  1. Uses DuckDuckGo to find the most relevant URL for a query
  2. Spins up a headless Playwright Chromium browser
  3. Navigates to the URL and extracts clean page text via JS injection
  4. Returns the first 2000 chars of body text to save tokens

Strict 3-second timeout — never hangs the master event loop.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("deep_scraper")


async def deep_scrape(query: str, timeout_seconds: int = 3) -> dict:
    """
    End-to-end deep scrape: DuckDuckGo URL discovery → Playwright extraction.

    Parameters
    ----------
    query : str
        The search query (e.g. "Ferrari stock price today").
    timeout_seconds : int
        Hard ceiling on the entire operation. Default 3s.

    Returns
    -------
    dict  {"url": str, "text": str, "success": bool}
          On failure: {"url": "", "text": "<fallback message>", "success": False}
    """
    try:
        return await asyncio.wait_for(
            _scrape_pipeline(query),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("⏱️ Deep scrape timed out after %ds for: '%s'", timeout_seconds, query)
        return {"url": "", "text": f"Deep scrape timed out ({timeout_seconds}s) for: {query}", "success": False}
    except Exception as e:
        logger.error("💥 Deep scrape unexpected error: %s", e)
        return {"url": "", "text": f"Deep scrape failed: {str(e)[:120]}", "success": False}


async def _scrape_pipeline(query: str) -> dict:
    """Internal pipeline: URL discovery → headless page load → text extraction."""

    url = await _find_url(query)
    if not url:
        return {"url": "", "text": "No relevant URL found for query.", "success": False}

    logger.info("🔗 Deep scraper target URL: %s", url)

    text = await _extract_page_text(url)
    if not text:
        return {"url": url, "text": "Page loaded but no text extracted.", "success": False}

    truncated = text[:2000].strip()
    logger.info("📄 Deep scrape extracted %d chars (truncated to %d) from %s", len(text), len(truncated), url)

    return {"url": url, "text": truncated, "success": True}


async def _find_url(query: str) -> Optional[str]:
    """Use DuckDuckGo text search to find the single most relevant URL."""
    try:
        from duckduckgo_search import DDGS

        def _sync_search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=1))
            return results

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_search)

        if results and results[0].get("href"):
            return results[0]["href"]

        logger.warning("🔗 DuckDuckGo returned no results for: '%s'", query)
        return None

    except Exception as e:
        logger.error("🔗 DuckDuckGo URL lookup failed: %s", e)
        return None


async def _extract_page_text(url: str) -> Optional[str]:
    """
    Launch headless Chromium via Playwright, navigate to URL,
    and inject JS to extract document.body.innerText.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=5000)
            await page.wait_for_timeout(500)
            text = await page.evaluate("document.body.innerText")

            await browser.close()

            return text.strip() if text else None

    except Exception as e:
        logger.error("🌐 Playwright extraction failed for %s: %s", url, e)
        return None
