"""
composer.py — Rule-based cover letter generation.

Produces natural, ATS-aligned text from:
  - Job description keywords
  - Matched resume bullets
  - User profile (profile.txt)
  - Tone anchors mined from example cover letters

The deterministic rotation keyed on company name ensures each generated
letter feels distinct even when the underlying logic is the same.

No external AI API required.  Plug in llm_hook.py to upgrade quality.
"""

import hashlib
import re
import textwrap
from datetime import date


# ── Sentence template banks ───────────────────────────────────────────────────
# Each bank has multiple variants; the composer picks one deterministically
# based on a hash of (company + role) so the same input always produces the
# same output, but different companies get different-feeling letters.

_OPENING_TEMPLATES = [
    "I am writing to express my interest in the {role} position at {company}. "
    "After learning about the opportunity, I was immediately drawn to how well "
    "it aligns with my background in {skill_area} and my goal of building a "
    "career at the intersection of {interest1} and {interest2}.",

    "When I came across the {role} opening at {company}, I knew right away it "
    "was the kind of opportunity I had been looking for. My experience in "
    "{skill_area}, combined with a genuine passion for {interest1}, makes me "
    "confident I can add real value to your team from day one.",

    "I am applying for the {role} role at {company} because the work your team "
    "is doing in {interest1} is exactly the type of environment I thrive in. "
    "My hands-on background in {skill_area} has prepared me well for the "
    "challenges this role presents.",

    "The {role} opportunity at {company} stands out to me for a straightforward "
    "reason: it sits squarely at the crossroads of {interest1} and {skill_area}, "
    "which is precisely where my experience and ambitions converge.",
]

_BODY1_TEMPLATES = [
    "In my experience at {org}, {achievement}. That work gave me direct exposure "
    "to {keyword1} and {keyword2}, the exact skills your job description highlights "
    "as central to the role.",

    "Most recently at {org}, {achievement}. The role demanded a strong command "
    "of {keyword1}, and my results there demonstrate I can bring the same "
    "rigor to {company}.",

    "At {org}, {achievement}. That experience sharpened my ability to work "
    "across {keyword1} and {keyword2}, two areas that come up repeatedly in "
    "your job description.",

    "Through my work at {org}, {achievement}, building a practical foundation "
    "in {keyword1} and {keyword2}. I am ready to apply that same approach at "
    "{company}.",
]

_BODY2_TEMPLATES = [
    "Beyond my technical background, I bring an entrepreneurial mindset. "
    "Co-founding {venture} taught me how to {entrepreneurial_skill} under "
    "real constraints, which I believe translates directly to the pace "
    "and expectations of a {company_type} environment.",

    "What separates my profile is the combination of analytical depth and "
    "hands-on execution. Launching {venture} while maintaining academic and "
    "extracurricular commitments has sharpened my ability to {entrepreneurial_skill} "
    "and deliver results without waiting for perfect conditions.",

    "I also bring a builder's perspective. Running {venture} from zero "
    "has given me a ground-level understanding of {entrepreneurial_skill}, "
    "which I see as increasingly valuable at companies like {company} that "
    "expect team members to take ownership early.",
]

_BODY3_TEMPLATES = [
    "Academically, my coursework in {academic_focus} has reinforced the "
    "fundamentals behind what I do in practice. Rutgers Business School has "
    "pushed me to think critically about {interest1}, and I have carried that "
    "mindset into every project I have taken on outside the classroom. I am "
    "someone who genuinely enjoys this work, not just as a career path but as "
    "something I think about and pursue on my own time.",

    "What motivates me about {company} specifically is the type of work this "
    "role involves. I have followed brands and organizations operating in "
    "{interest1} closely, and I understand what good execution looks like in "
    "this space. My coursework at Rutgers Business School has given me the "
    "analytical grounding to complement that instinct, and I am eager to apply "
    "both in a real professional setting.",

    "On the academic side, my focus on {academic_focus} at Rutgers Business "
    "School has equipped me with frameworks I actively use when approaching "
    "real problems. I am not just looking for a line on a resume here. "
    "{company} is a place I genuinely want to contribute to, and I have done "
    "my homework on what that actually means.",

    "I take my development seriously outside of class as well. Whether through "
    "running {venture}, shooting commercial photography, or staying current on "
    "trends in {interest1}, I am consistently trying to close the gap between "
    "what I know and what I can actually do. That drive is something I bring "
    "into every role I take on.",
]

_CLOSING_TEMPLATES = [
    "I would welcome the chance to discuss how my background fits your team's "
    "needs. Thank you for your time and consideration, and I look forward to "
    "the possibility of connecting.",

    "Thank you for reviewing my application. I would love the opportunity to "
    "speak further about how I can contribute to {company}, and I am happy to "
    "provide any additional context about my background at your convenience.",

    "I appreciate your time and consideration. I am confident that my "
    "background, work ethic, and genuine interest in this space make me a "
    "strong fit, and I look forward to the possibility of connecting.",

    "Thank you for your time. I am genuinely excited about this role and the "
    "work {company} is doing, and I hope to have the chance to speak with you "
    "soon.",
]


# ── Profile parsing ───────────────────────────────────────────────────────────

def parse_profile(profile_text: str) -> dict[str, str]:
    """
    Parse structured profile.txt into a usable dict.
    Handles the NAME / BACKGROUND / SKILLS / CAREER INTERESTS / INTERESTS
    / TONE PREFERENCES format from the user's actual file.
    """
    profile: dict[str, str] = {}
    current_key = "GENERAL"
    lines: list[str] = []

    for line in profile_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Section headers end with ":"
        if re.match(r'^[A-Z][A-Z /]+:$', line) or re.match(r'^[A-Z][A-Z /]+ PREFERENCES:$', line):
            if lines:
                profile[current_key] = " ".join(lines)
            current_key = line.rstrip(":")
            lines = []
        elif ":" in line and line.split(":")[0].isupper():
            # Inline key: VALUE pairs like  NAME: Aditya Mehta
            k, _, v = line.partition(":")
            profile[k.strip()] = v.strip()
        else:
            lines.append(line)

    if lines:
        profile[current_key] = " ".join(lines)

    return profile


def _get_name(profile_data: dict) -> str:
    return profile_data.get("NAME", "").strip() or "Aditya Mehta"


def _get_interests(profile_data: dict) -> tuple[str, str]:
    interests_raw = profile_data.get("CAREER INTERESTS", profile_data.get("INTERESTS", ""))
    parts = [p.strip() for p in re.split(r'[,.]', interests_raw) if p.strip()]
    i1 = parts[0] if parts else "marketing strategy"
    i2 = parts[1] if len(parts) > 1 else "business development"
    return i1.lower(), i2.lower()


def _get_academic_focus(profile_data: dict) -> str:
    bg = profile_data.get("BACKGROUND", "")
    if "marketing" in bg.lower():
        return "marketing strategy and consumer behavior"
    if "finance" in bg.lower():
        return "finance and data analysis"
    return "marketing, strategy, and entrepreneurship"


def _get_skill_area(profile_data: dict, keywords: list[str]) -> str:
    skills_raw = profile_data.get("SKILLS", "")
    skill_tokens = [s.strip() for s in skills_raw.split(",") if s.strip()]
    # Try to find a skill that overlaps with JD keywords
    for kw in keywords:
        for skill in skill_tokens:
            if kw.lower() in skill.lower() or skill.lower() in kw.lower():
                return skill.lower()
    return skill_tokens[0].lower() if skill_tokens else "marketing and analytics"


# ── Resume parsing for composer ───────────────────────────────────────────────

def _extract_org_and_achievement(resume_bullets: list[str]) -> tuple[str, str]:
    """
    Heuristic: from matched resume bullets, split into (org, achievement).
    Achievement is returned as a lowercase verb phrase suitable for mid-sentence
    insertion, e.g. "led marketing campaigns for chapter initiatives".
    """
    for bullet in resume_bullets:
        # Pattern: "Elected as X at ORG, doing Y"  → org=ORG, achievement="served as X..."
        elected_match = re.match(
            r'(Elected|Selected|Appointed|Promoted)\s+as\s+(.+?)\s+(?:for|at)\s+([A-Z][^,]+?)(?:,\s*(.+))?$',
            bullet
            # No re.I: [A-Z] must match a real capital to identify org names
        )
        if elected_match:
            title = elected_match.group(2)
            org   = elected_match.group(3).strip()
            # Use only the title — the comma-separated activities list is too long
            achievement = f"served as {title.lower()}"
            return org, achievement

        # Pattern: "Led/Built/Managed X at ORG"
        verb_at = re.match(
            r'([A-Z][a-z]+(?:ed|ing)?\s+.{10,}?)\s+(?:at|for)\s+([A-Z][A-Za-z\s&]+?)(?:\s*[,\(]|$)',
            bullet
        )
        if verb_at:
            achievement = verb_at.group(1).strip()
            org = verb_at.group(2).strip()
            return org, achievement.lower()

        # Pattern: "at <Org>" anywhere in the bullet
        at_match = re.search(r'\bat\s+([A-Z][^\s,]{2,}(?:\s+[A-Z][^\s,]{2,})?)', bullet)
        if at_match:
            org = at_match.group(1)
            # Achievement = everything before the "at Org" clause
            achievement = bullet[:at_match.start()].strip().rstrip(",").strip()
            if len(achievement) > 20:
                return org, achievement.lower()

    # Fallback: use the first bullet verbatim as the achievement
    first = resume_bullets[0] if resume_bullets else ""
    # Try to extract a capitalized org-like prefix
    org_match = re.match(r'^([A-Z][A-Za-z\s&]{2,30}?)[\s,\-–]', first)
    org = org_match.group(1).strip() if org_match else "my most recent role"
    return org, first.lower() if first else "led cross-functional marketing initiatives"


def _extract_venture(profile_data: dict) -> tuple[str, str]:
    """Pick the entrepreneurial venture from the profile."""
    bg = profile_data.get("BACKGROUND", "")
    # Look for "co-founder of X" or "running X" patterns
    venture_match = re.search(
        r'(?:co-founder of|founded|running|launched|started)\s+([A-Z][A-Za-z\s]+(?:LLC|Inc|Co|Platform|App|Business)?)',
        bg
    )
    if venture_match:
        venture = venture_match.group(1).strip()
    else:
        venture = "Atlas Strategy LLC"  # known from profile.txt

    # Noun phrases that fit "understanding of X" grammatically
    entrepreneurial_skills = [
        "what it takes to build a product from zero to paying users",
        "cross-functional ownership and operating without a playbook",
        "how to balance strategy with day-to-day execution under real constraints",
        "the full lifecycle of bringing an idea to market",
    ]
    return venture, entrepreneurial_skills[0]


# ── Deterministic variant selection ──────────────────────────────────────────

def _pick(templates: list[str], seed_str: str) -> str:
    """Pick a template deterministically based on a string seed."""
    idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(templates)
    return templates[idx]


# ── Main composition function ─────────────────────────────────────────────────

def compose_cover_letter(
    company: str,
    role: str,
    job_description: str,
    keywords: list[str],
    resume_bullets: list[str],
    profile_text: str,
    example_openers: list[str] = None,
    example_closings: list[str] = None,
    hiring_manager: str = "",
) -> dict[str, str]:
    """
    Generate a tailored cover letter.

    Returns a dict with keys:
      - date, salutation, opening, body1, body2, closing
      - full_text  (assembled letter for preview / ATS analysis)
    """
    seed = (company + role).lower()
    profile_data = parse_profile(profile_text)
    name = _get_name(profile_data)
    interest1, interest2 = _get_interests(profile_data)
    skill_area = _get_skill_area(profile_data, keywords)
    academic_focus = _get_academic_focus(profile_data)
    org, achievement = _extract_org_and_achievement(resume_bullets)
    venture, entrepreneurial_skill = _extract_venture(profile_data)

    # Prefer multi-word phrases for body paragraph (more readable than single words)
    phrase_kws = [k for k in keywords if " " in k]
    single_kws = [k for k in keywords if " " not in k]
    ordered = phrase_kws + single_kws
    kw1 = ordered[0] if len(ordered) > 0 else skill_area
    kw2 = ordered[1] if len(ordered) > 1 else interest1

    # Classify company type for body2
    company_type = _classify_company_type(job_description)

    # ── Assemble each section ──────────────────────────────────────────────────

    today = date.today().strftime("%B %d, %Y")

    salutation = (
        f"Dear {hiring_manager}," if hiring_manager
        else "Dear Hiring Manager,"
    )

    opening = _pick(_OPENING_TEMPLATES, seed + "open").format(
        role=role, company=company,
        skill_area=skill_area, interest1=interest1, interest2=interest2,
    )

    body1 = _pick(_BODY1_TEMPLATES, seed + "body1").format(
        org=org, achievement=achievement,  # lowercase — follows a comma in all templates
        keyword1=kw1, keyword2=kw2, company=company,
    )

    body2 = _pick(_BODY2_TEMPLATES, seed + "body2").format(
        venture=venture, entrepreneurial_skill=entrepreneurial_skill,
        company=company, company_type=company_type,
    )

    body3 = _pick(_BODY3_TEMPLATES, seed + "body3").format(
        academic_focus=academic_focus, interest1=interest1,
        company=company, venture=venture,
    )

    closing_template = _pick(_CLOSING_TEMPLATES, seed + "close")
    closing = closing_template.format(company=company)

    full_text = "\n\n".join([today, salutation, opening, body1, body2, body3, closing, name])

    return {
        "date": today,
        "salutation": salutation,
        "opening": opening,
        "body1": body1,
        "body2": body2,
        "body3": body3,
        "closing": closing,
        "name": name,
        "full_text": full_text,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _classify_company_type(jd: str) -> str:
    jd_lower = jd.lower()
    if any(w in jd_lower for w in ["startup", "series", "seed", "venture"]):
        return "high-growth startup"
    if any(w in jd_lower for w in ["enterprise", "fortune", "global"]):
        return "large enterprise"
    if any(w in jd_lower for w in ["agency", "consulting", "advisory"]):
        return "client-services"
    return "fast-paced"


# ── Rebuild from edited paragraphs ───────────────────────────────────────────

def assemble_full_text(sections: dict[str, str]) -> str:
    """Re-assemble full letter text from edited section dict (including body3)."""
    parts = [
        sections.get("date", ""),
        sections.get("salutation", ""),
        sections.get("opening", ""),
        sections.get("body1", ""),
        sections.get("body2", ""),
        sections.get("body3", ""),
        sections.get("closing", ""),
        sections.get("name", ""),
    ]
    return "\n\n".join(p for p in parts if p.strip())
