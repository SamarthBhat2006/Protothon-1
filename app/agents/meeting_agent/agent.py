import json
import logging
import os
import asyncio
import random
import re
from typing import Optional, List, Dict, Any
import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

# ── Agent System Instructions ──────────────────────────────────────────────────

MASTER_AGENT_INSTRUCTION = """You are an expert AI Meeting Analyzer. Your job is to analyze 
meeting transcripts from engineering teams and extract context, decisions, action items, and a summary.

Return a SINGLE JSON object exactly matching this structure:
{
    "context": {
        "meeting_type": "type of meeting (e.g., Sprint Planning, Design Review, Standup)",
        "feature_areas_discussed": ["list of main topics/feature areas discussed"],
        "general_sentiment": "positive/neutral/negative/tense"
    },
    "decisions": ["list of key decisions made during the meeting"],
    "action_items": [
        {
            "title": "Short actionable task title",
            "description": "Detailed description of what needs to be done",
            "assignee": "Person responsible (or 'Unassigned')",
            "priority": "high/medium/low based on urgency discussed",
            "feature_area": "Related feature or component area",
            "context": "Exact quote or context from the meeting"
        }
    ],
    "summary": "A concise 3-5 bullet point summary of the meeting discussion"
}

Extract ALL actionable tasks — even implicit ones. Return ONLY the JSON object.
"""

async def analyze_meeting_transcript(transcript: str) -> dict:
    """
    Orchestrates the Context, Decision, and Summary agents.
    """
    if not getattr(settings, "OPENROUTER_API_KEY", None):
        logger.warning("OPENROUTER_API_KEY not set — using mock multi-agent analysis")
        return await _mock_analyze_multi(transcript)

    try:
        # Run a single powerful agent to avoid rate limits
        logger.info(f"Orchestrating 1 Master AI agent for transcript ({len(transcript)} characters) to respect severe rate limits...")
        
        try:
            res = await _run_agent("master_agent", MASTER_AGENT_INSTRUCTION, transcript)
        except Exception as e:
            res = e
        
        # Merge results securely
        merged_result = {
            "summary": "",
            "decisions": [],
            "action_items": [],
            "context": {}
        }
        
        if isinstance(res, Exception):
            logger.error(f"Master Agent failed: {res}")
        elif isinstance(res, dict):
            merged_result["context"] = res.get("context", {})
            merged_result["decisions"] = res.get("decisions", [])
            merged_result["action_items"] = res.get("action_items", [])
            merged_result["summary"] = res.get("summary", "")
                    
        return merged_result

    except Exception as e:
        logger.error(f"Master Agent Orchestration error: {e}")
        return await _mock_analyze_multi(transcript)


async def _run_agent(name: str, instruction: str, transcript: str) -> dict:
    """Run AI model via OpenRouter to analyze the transcript."""
    api_key = getattr(settings, "OPENROUTER_API_KEY", None)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": f"Analyze this meeting transcript:\n\n{transcript}"}
        ],
        "temperature": 0.3
    }
    
    url = "https://openrouter.ai/api/v1/chat/completions"

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=60.0) as response:
                    if response.status == 429:
                        wait_time = 45.0 + (attempt * 15.0) + (random.random() * 5.0)
                        logger.warning(f"Agent {name} hit rate limit (429). Waiting {wait_time:.2f}s before retry {attempt+1}/{MAX_RETRIES}...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Agent {name} failed with status {response.status}: {error_text}")
                        if response.status in (403, 401):
                            logger.error(f"Agent {name} failed due to Auth/Permissions. Falling back gracefully.")
                            return _get_fallback_response_for_agent(name, error_type="403")
                        return _get_fallback_response_for_agent(name, error_type=str(response.status))
                    
                    data = await response.json()
                    response_text = data["choices"][0]["message"]["content"] or ""

                    if not response_text:
                        logger.warning(f"Agent {name} returned NO text.")
                    else:
                        logger.info(f"Agent {name} response received ({len(response_text)} chars).")

                    return _parse_agent_response(response_text)

        except Exception as e:
            logger.error(f"Agent {name} execution error: {e}")
            if attempt == MAX_RETRIES - 1:
                return _get_fallback_response_for_agent(name)
            await asyncio.sleep(5.0)

    return _get_fallback_response_for_agent(name)

def _get_fallback_response_for_agent(name: str, error_type: str = "429") -> dict:
    """Provide a safe fallback structure when OpenRouter API fails."""
    
    status_text = f"API Error ({error_type})"
    summary_text = f"The OpenRouter API request failed with error {error_type}. Please check your API key and quota."

    return {
        "context": {
            "meeting_type": f"Unknown ({status_text})",
            "feature_areas_discussed": [status_text],
            "general_sentiment": "Neutral"
        },
        "decisions": [f"{status_text}. Could not extract decisions."],
        "action_items": [
            {
                "title": f"Review API Status ({status_text})",
                "description": summary_text,
                "assignee": "Admin",
                "priority": "high",
                "feature_area": "Infrastructure",
                "context": "System Auto-Generated"
            }
        ],
        "summary": summary_text
    }


def _parse_agent_response(response_text: str) -> dict:
    """Parse the JSON response from an agent."""
    text = response_text.strip()
    if text.startswith("```json"): text = text[7:] # type: ignore
    if text.startswith("```"): text = text[3:] # type: ignore
    if text.endswith("```"): text = text[:-3] # type: ignore
    text = text.strip()

    try:
        parsed = json.loads(text)
        if not parsed:
            logger.warning(f"Parsed JSON is empty for text: {text[:100]}") # type: ignore
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent JSON: {e}")
        logger.error(f"Problematic text: {text}")
        return {}


async def _mock_analyze_multi(transcript: str) -> dict:
    """Mock multi-agent analysis for testing."""
    logger.info("Running mock multi-agent meeting analysis")
    
    # Simulate Context Agent
    context = {
        "meeting_type": "Sprint Planning / Technical Sync",
        "feature_areas_discussed": ["Authentication", "API", "UI/UX", "DevOps"],
        "general_sentiment": "Productive"
    }
    
    # Simulate Summary Agent
    summary = (
        "• Team discussed priorities for the upcoming release\n"
        "• Key bugs and feature improvements were identified\n"
        "• Architecture updates requiring DevOps support were outlined"
    )
    
    # Simulate Decision Agent parsing
    action_items = []
    sentences = transcript.replace(". ", ".\n").split("\n")
    task_keywords = ["need to", "should", "must", "will", "fix", "implement", "update"]

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        if any(kw in sentence.lower() for kw in task_keywords):
            action_items.append({
                "title": sentence[:80].strip("."), # type: ignore
                "description": sentence,
                "assignee": "John" if "John" in sentence else "Unassigned",
                "priority": "high" if "bug" in sentence.lower() else "medium",
                "feature_area": "General",
                "context": sentence,
            })

    return {
        "context": context,
        "summary": summary,
        "decisions": [
            "Login bug fix is the top priority before release",
            "API rate limiting will be implemented",
        ],
        "action_items": action_items if action_items else [{
            "title": "Review meeting transcript for tasks",
            "description": "The meeting transcript should be reviewed",
            "assignee": "Unassigned", "priority": "medium", 
            "feature_area": "General", "context": transcript[:100] # type: ignore
        }],
        "mock": True,
    }