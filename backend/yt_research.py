"""
yt_research.py — YouTube Deep-Research Summarizer
====================================================
Extracts transcripts from YouTube videos and uses Groq to generate
comprehensive, domain-adaptive research summaries with export to JSON, Markdown, and PDF.

Pipeline:
  1. Extract video metadata + transcript via youtube-transcript-api
  2. Pass to Groq Llama-3.1-8b for rapid domain-aware summarisation
  3. Return structured JSON with export-ready formats
"""

import json
import logging
import os
import re
import base64
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger("yt_research")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def get_transcript(video_id: str) -> dict:
    """
    Fetch YouTube transcript + basic metadata.
    Returns: { title, transcript_text, duration_seconds, segment_count }
    """
    import asyncio

    def _fetch():
        from youtube_transcript_api import YouTubeTranscriptApi

        # Fetch transcript
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.fetch(video_id)

        segments = []
        for entry in transcript_list:
            segments.append({
                "text": entry.text,
                "start": entry.start,
                "duration": entry.duration,
            })

        full_text = " ".join(s["text"] for s in segments)
        total_duration = max((s["start"] + s["duration"]) for s in segments) if segments else 0

        return {
            "video_id": video_id,
            "transcript_text": full_text,
            "segment_count": len(segments),
            "duration_seconds": round(total_duration),
            "segments": segments[:5],  # first 5 for preview
        }

    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


async def summarize_transcript(transcript_text: str, video_id: str) -> dict:
    """
    Use Groq Llama-3.1-8b to generate a comprehensive, domain-adaptive summary.
    Automatically detects whether the video is about science, finance, tech, history, etc.
    Returns structured JSON with domain-relevant fields.
    """
    import asyncio

    prompt = f"""You are an elite research analyst with expertise across ALL domains — science, technology, 
finance, history, philosophy, education, engineering, medicine, entertainment, and more.

Analyze the following YouTube video transcript and produce a comprehensive, domain-appropriate research summary.

CRITICAL: Detect the actual topic/domain of the video from the transcript content. 
Do NOT force financial framing onto non-financial content. A video about black holes should 
have physics insights, not stock market analogies. A cooking video should have culinary takeaways, not trading advice.

VIDEO ID: {video_id}
TRANSCRIPT:
{transcript_text[:12000]}

Respond in this EXACT JSON format:
{{
    "title_inferred": "Best guess at the video title based on content",
    "domain": "science | technology | finance | education | history | health | entertainment | philosophy | engineering | other",
    "summary": "2-3 paragraph comprehensive summary capturing the core message and key arguments",
    "key_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],
    "deep_insights": ["domain-relevant insight 1", "insight 2", "insight 3"],
    "mentioned_topics": ["topic1", "topic2", "topic3"],
    "tone": "informative | persuasive | educational | entertaining | analytical | inspirational | neutral",
    "complexity_score": 0.0 to 1.0,
    "important_warnings": ["caveat or limitation 1", "caveat 2"],
    "actionable_takeaways": ["what the viewer should do/learn/remember 1", "takeaway 2", "takeaway 3"],
    "content_type": "explainer | tutorial | analysis | documentary | lecture | interview | review | news | vlog | other"
}}

RULES:
- "deep_insights" must be relevant to the ACTUAL domain (physics insights for physics, code insights for programming, etc.)
- "mentioned_topics" should list specific concepts, people, theories, tools, or subjects discussed
- "important_warnings" should note any limitations, controversies, or caveats mentioned or implied
- "actionable_takeaways" should be practical: what should the viewer learn, explore, or do after watching
- Be thorough, specific, and cite data points from the transcript
- Respond ONLY with valid JSON"""

    def _call_groq():
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    raw = await asyncio.get_event_loop().run_in_executor(None, _call_groq)

    # Parse JSON from response
    try:
        # Find JSON in response
        json_start = raw.find('{')
        json_end = raw.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(raw[json_start:json_end])
        else:
            parsed = {"summary": raw, "key_points": [], "tone": "neutral", "domain": "other"}
    except json.JSONDecodeError:
        parsed = {"summary": raw, "key_points": [], "tone": "neutral", "domain": "other"}

    parsed["video_url"] = f"https://youtube.com/watch?v={video_id}"
    parsed["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    parsed["transcript_length"] = len(transcript_text)

    return parsed


def generate_markdown(summary_data: dict) -> str:
    """Convert summary JSON to a formatted Markdown document — domain-adaptive."""
    title = summary_data.get("title_inferred", "YouTube Research Summary")
    domain = summary_data.get("domain", "general").capitalize()
    tone = summary_data.get("tone", "neutral").capitalize()
    complexity = summary_data.get("complexity_score", "N/A")
    if isinstance(complexity, (int, float)):
        complexity = f"{complexity:.0%}"

    md = f"""# � {title}

**Source:** [{summary_data.get('video_url', 'N/A')}]({summary_data.get('video_url', '#')})
**Analyzed:** {summary_data.get('analyzed_at', 'N/A')}
**Domain:** {domain}
**Tone:** {tone}
**Complexity:** {complexity}
**Content Type:** {summary_data.get('content_type', 'N/A')}

---

## Summary

{summary_data.get('summary', 'No summary available.')}

## Key Points

"""
    for i, point in enumerate(summary_data.get("key_points", []), 1):
        md += f"{i}. {point}\n"

    md += "\n## Deep Insights\n\n"
    for insight in summary_data.get("deep_insights", []):
        md += f"- 💡 {insight}\n"

    topics = summary_data.get("mentioned_topics", [])
    if topics:
        md += f"\n## Key Topics\n\n`{'`, `'.join(topics)}`\n"

    warnings = summary_data.get("important_warnings", [])
    if warnings:
        md += "\n## Important Caveats & Limitations\n\n"
        for w in warnings:
            md += f"- ⚠️ {w}\n"

    md += "\n## Actionable Takeaways\n\n"
    for action in summary_data.get("actionable_takeaways", []):
        md += f"- ✅ {action}\n"

    md += f"\n---\n*Generated by X10V AI Swarm — Omni-Channel Autonomous Intelligence Agent*\n"
    return md


def generate_pdf_base64(summary_data: dict) -> str:
    """Generate a PDF from the summary and return as base64 string."""
    try:
        import markdown as md_lib
        from weasyprint import HTML

        md_text = generate_markdown(summary_data)
        html_body = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])

        styled_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px; line-height: 1.6; color: #1a1a1a; }}
  h1 {{ color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
  h2 {{ color: #1e40af; margin-top: 24px; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  li {{ margin-bottom: 4px; }}
  hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }}
</style></head><body>{html_body}</body></html>"""

        pdf_bytes = HTML(string=styled_html).write_pdf()
        return base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as e:
        logger.error("PDF generation failed: %s — falling back to Markdown", e)
        # Return markdown as base64 text fallback
        md_text = generate_markdown(summary_data)
        return base64.b64encode(md_text.encode("utf-8")).decode("utf-8")


async def research_youtube_video(url: str) -> dict:
    """
    Full pipeline: URL → transcript → Groq summary → structured output.
    Returns everything the frontend needs for display + export.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL. Could not extract video ID."}

    try:
        transcript_data = await get_transcript(video_id)
    except Exception as e:
        logger.error("Transcript fetch failed for %s: %s", video_id, e)
        return {"error": f"Could not fetch transcript: {str(e)}. The video may not have captions."}

    transcript_text = transcript_data["transcript_text"]
    if not transcript_text.strip():
        return {"error": "Video has no transcript/captions available."}

    summary = await summarize_transcript(transcript_text, video_id)

    # Generate export formats
    markdown_text = generate_markdown(summary)

    return {
        "status": "success",
        "video_id": video_id,
        "video_url": f"https://youtube.com/watch?v={video_id}",
        "transcript_preview": transcript_text[:500] + "…" if len(transcript_text) > 500 else transcript_text,
        "transcript_length": len(transcript_text),
        "duration_seconds": transcript_data["duration_seconds"],
        "summary": summary,
        "exports": {
            "json": json.dumps(summary, indent=2),
            "markdown": markdown_text,
        },
    }
