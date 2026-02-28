"""
headless_executor.py — The Ghost Hands (Playwright Headless Automation)
========================================================================
Spins up an invisible Chromium instance using a pre-saved user context
(cookies / session state) so the user never has to re-authenticate via 2FA.

All operations are fully async and gracefully handle selector timeouts
without crashing the server.
"""

import logging
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("headless_executor")

STATE_PATH = os.getenv("PLAYWRIGHT_STATE_PATH", "./browser_state.json")

# Timeout for all element interactions (ms)
DEFAULT_TIMEOUT_MS = 15_000


class HeadlessBrowser:
    """
    Async context manager that provisions a Chromium instance with
    pre-saved authentication state.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "HeadlessBrowser":
        self._pw = await async_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        if os.path.isfile(STATE_PATH):
            logger.info("Loading saved browser state from '%s'", STATE_PATH)
            self._context = await self._browser.new_context(storage_state=STATE_PATH)
        else:
            logger.info("No saved state found — launching fresh context.")
            self._context = await self._browser.new_context()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Headless browser shut down cleanly.")

    async def new_page(self) -> Page:
        assert self._context is not None, "Browser context not initialised."
        return await self._context.new_page()

    async def save_state(self):
        """Persist cookies/session so future runs skip login."""
        if self._context:
            await self._context.storage_state(path=STATE_PATH)
            logger.info("Browser state saved → %s", STATE_PATH)


async def execute_web_action(
    url: str,
    target_selector: str,
    action_type: Literal["click", "type", "extract_text", "screenshot"],
    input_text: Optional[str] = None,
    save_state_after: bool = False,
    headless: bool = True,
) -> dict:
    """
    Spin up an invisible Chromium instance, navigate to *url*, and
    perform an action on *target_selector*.

    Supported actions
    -----------------
    - ``click``         — click the element
    - ``type``          — type *input_text* into the element
    - ``extract_text``  — return ``element.inner_text()``
    - ``screenshot``    — take a full-page screenshot (path returned)

    Returns
    -------
    dict  {"success": bool, "data": ..., "error": str | None}
    """
    logger.info(
        "🌐 execute_web_action  url=%s  selector=%s  action=%s",
        url, target_selector, action_type,
    )

    try:
        async with HeadlessBrowser(headless=headless) as hb:
            page = await hb.new_page()

            # Navigate
            logger.info("Navigating to %s …", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            logger.info("Page loaded — title: %s", await page.title())

            # Wait for selector
            logger.info("Waiting for selector '%s' (timeout %d ms) …", target_selector, DEFAULT_TIMEOUT_MS)
            element = await page.wait_for_selector(
                target_selector, timeout=DEFAULT_TIMEOUT_MS
            )

            if element is None:
                raise TimeoutError(f"Selector '{target_selector}' not found.")

            result_data = None

            if action_type == "click":
                await element.click()
                logger.info("✅ Clicked '%s'", target_selector)
                result_data = "clicked"

            elif action_type == "type":
                if input_text is None:
                    raise ValueError("action_type='type' requires input_text.")
                await element.fill(input_text)
                logger.info("✅ Typed '%s' into '%s'", input_text[:40], target_selector)
                result_data = f"typed: {input_text[:80]}"

            elif action_type == "extract_text":
                result_data = await element.inner_text()
                logger.info("✅ Extracted text (%d chars)", len(result_data))

            elif action_type == "screenshot":
                path = f"./screenshot_{url.split('//')[1][:20].replace('/', '_')}.png"
                await page.screenshot(path=path, full_page=True)
                logger.info("✅ Screenshot saved → %s", path)
                result_data = path

            else:
                raise ValueError(f"Unknown action_type: {action_type}")

            if save_state_after:
                await hb.save_state()

            return {"success": True, "data": result_data, "error": None}

    except TimeoutError as e:
        logger.error("⏱ Timeout: %s", e)
        return {"success": False, "data": None, "error": f"Timeout: {e}"}

    except ValueError as e:
        logger.error("❌ ValueError: %s", e)
        return {"success": False, "data": None, "error": str(e)}

    except Exception as e:
        logger.error("❌ Unexpected error in headless_executor: %s", e, exc_info=True)
        return {"success": False, "data": None, "error": f"Unexpected: {e}"}


async def scrape_page_text(url: str, selector: str = "body") -> str:
    """
    Quick helper — navigate to *url* and return the inner text of *selector*.
    Returns empty string on failure (never raises).
    """
    result = await execute_web_action(
        url=url,
        target_selector=selector,
        action_type="extract_text",
    )
    if result["success"]:
        return result["data"]
    logger.warning("scrape_page_text failed for %s: %s", url, result["error"])
    return ""
