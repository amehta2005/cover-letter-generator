"""
llm_hook.py — Optional local LLM integration (disabled by default).

To enable:
  1. Install Ollama: https://ollama.com
  2. Pull a model: ollama pull llama3
  3. Set USE_LLM = True in config.py

This module is intentionally isolated so the rest of the app
works perfectly with USE_LLM = False.
"""

import json
import urllib.request
import urllib.error
from typing import Optional

import config


def is_available() -> bool:
    """Check if the configured LLM provider is reachable."""
    if not config.USE_LLM:
        return False
    if config.LLM_PROVIDER == "ollama":
        try:
            req = urllib.request.urlopen(f"{config.LLM_BASE_URL}/api/tags", timeout=3)
            return req.status == 200
        except Exception:
            return False
    return False


def generate(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Send a prompt to the local LLM and return the response text.
    Returns None if LLM is disabled or unavailable.
    """
    if not config.USE_LLM:
        return None

    if config.LLM_PROVIDER == "ollama":
        return _ollama_generate(prompt, system, temperature)

    return None


def _ollama_generate(prompt: str, system: str, temperature: float) -> Optional[str]:
    """Call Ollama's /api/generate endpoint."""
    payload = {
        "model": config.LLM_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{config.LLM_BASE_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "").strip()
    except Exception as e:
        return None


def build_cover_letter_prompt(
    company: str,
    role: str,
    job_description: str,
    keywords: list[str],
    resume_text: str,
    profile_text: str,
    example_texts: list[str],
    rule_based_draft: str,
) -> tuple[str, str]:
    """
    Build (system_prompt, user_prompt) for cover letter generation.

    Passes the rule-based draft as a starting point so the LLM refines
    rather than starts from scratch — faster and more controllable.
    """
    # Trim inputs to stay within context limits
    resume_snippet = resume_text[:2000]
    jd_snippet = job_description[:1500]
    keywords_str = ", ".join(keywords[:15])

    # Use up to 3 example openers to anchor tone
    style_examples = "\n\n---\n\n".join(example_texts[:3])[:1500] if example_texts else ""

    system = (
        "You are a professional cover letter writer. Your output must sound like it was "
        "written by a college student — natural, direct, and confident, not corporate. "
        "Never use em dashes. Never use the word 'consultative' (use 'advisory' instead). "
        "Avoid generic filler phrases. Do not hallucinate experience or skills not mentioned "
        "in the resume or profile. Keep the letter under 350 words."
    )

    user = f"""Refine this draft cover letter for the {role} role at {company}.

PROFILE:
{profile_text[:800]}

RESUME (excerpt):
{resume_snippet}

JOB DESCRIPTION (excerpt):
{jd_snippet}

KEYWORDS TO INCLUDE NATURALLY: {keywords_str}

STYLE REFERENCE (from the applicant's existing letters):
{style_examples}

DRAFT TO REFINE:
{rule_based_draft}

Output ONLY the refined letter body (no subject line, no metadata).
Preserve the same paragraph structure: opening, body1, body2, closing."""

    return system, user
