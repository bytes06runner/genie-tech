"""
voice_intent.py — RNN-Style Voice Intent Classifier via Groq
================================================================
Accepts raw transcribed text from the Web Speech API and uses
Groq Llama-3.1-8b to parse it into structured intent JSON.

Output contract:
  {
    "intent": "analyze_stock | summarize_video | set_automation | trade | monitor | general_query",
    "entities": { "ticker": "AAPL", "timeframe": "1h", "url": "...", ... },
    "confidence_score": 0.0-1.0,
    "raw_text": "original transcription",
    "suggested_action": "human-readable description of what to do next"
  }
"""

import json
import logging
import os
import asyncio

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger("voice_intent")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

INTENT_SYSTEM = """You are an advanced Intent-Classification Neural Network for a financial AI trading platform called X10V.

Your job: Parse the user's voice command into a structured JSON object.

AVAILABLE INTENTS:
- "analyze_stock" → User wants AI analysis of a stock/asset/crypto (extract ticker, timeframe)
- "summarize_video" → User wants to summarize a YouTube video (extract URL or video topic)
- "set_automation" → User wants to schedule an automated trade rule (extract asset, condition, action)
- "trade" → User wants to execute a paper trade (extract asset, amount, side buy/sell)
- "monitor" → User wants to set a price alert/monitor (extract asset, target_price, direction)
- "portfolio" → User wants to view their portfolio/balance
- "general_query" → General financial question or chat

ENTITY EXTRACTION RULES:
- ticker: Normalize to standard format (e.g., "Apple" → "AAPL", "gold" → "XAU/USD", "bitcoin" → "BTC")
- timeframe: "1m", "5m", "1h", "4h", "1d", "1w" (default "1d" if unspecified)
- amount: Dollar amount for trades (default $100 if unspecified)
- url: YouTube URL if mentioned
- condition: Trading condition (e.g., "RSI < 30", "price below 150")
- target_price: Specific price level
- direction: "above" or "below" for monitors

Respond ONLY with valid JSON in this format:
{
    "intent": "one_of_the_intents_above",
    "entities": { extracted entities },
    "confidence_score": 0.0 to 1.0,
    "suggested_action": "one sentence describing what should happen next"
}"""


async def classify_intent(raw_text: str) -> dict:
    """
    Send transcribed voice text to Groq for intent classification.
    Returns structured intent JSON.
    """
    def _call_groq():
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": f"Voice command: \"{raw_text}\""},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        return response.choices[0].message.content

    raw_response = await asyncio.get_event_loop().run_in_executor(None, _call_groq)

    try:
        json_start = raw_response.find('{')
        json_end = raw_response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(raw_response[json_start:json_end])
        else:
            parsed = {
                "intent": "general_query",
                "entities": {},
                "confidence_score": 0.3,
                "suggested_action": "Could not parse intent. Treating as general query.",
            }
    except json.JSONDecodeError:
        parsed = {
            "intent": "general_query",
            "entities": {},
            "confidence_score": 0.3,
            "suggested_action": "Could not parse intent. Treating as general query.",
        }

    parsed["raw_text"] = raw_text
    logger.info("🎤 Voice intent: %s (%.0f%%) → %s",
                parsed.get("intent"), parsed.get("confidence_score", 0) * 100,
                parsed.get("suggested_action", ""))

    return parsed
