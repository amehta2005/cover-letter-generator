"""
keywords.py — Keyword extraction, TF-IDF scoring, and ATS analysis.

Runs entirely offline.  Uses NLTK if available (better stopword list),
falls back to a built-in list when NLTK data isn't downloaded yet.
"""

import math
import re
import string
from collections import Counter
from typing import Iterable

# ── NLTK (optional) ───────────────────────────────────────────────────────────
try:
    from nltk.corpus import stopwords as _nltk_sw
    from nltk.tokenize import word_tokenize as _nltk_tok
    _NLTK_READY = True
    _NLTK_STOPS = set(_nltk_sw.words("english"))
except Exception:
    _NLTK_READY = False
    _NLTK_STOPS = set()

# ── Built-in fallback stopwords ───────────────────────────────────────────────
_BUILTIN_STOPS = {
    "a","about","above","after","again","against","all","am","an","and","any",
    "are","aren't","as","at","be","because","been","before","being","below",
    "between","both","but","by","can","can't","cannot","could","couldn't","did",
    "didn't","do","does","doesn't","doing","don't","down","during","each","few",
    "for","from","further","get","got","had","hadn't","has","hasn't","have",
    "haven't","having","he","he'd","he'll","he's","her","here","here's","hers",
    "herself","him","himself","his","how","how's","i","i'd","i'll","i'm","i've",
    "if","in","into","is","isn't","it","it's","its","itself","let's","me","more",
    "most","mustn't","my","myself","no","nor","not","of","off","on","once","only",
    "or","other","ought","our","ours","ourselves","out","over","own","same",
    "shan't","she","she'd","she'll","she's","should","shouldn't","so","some",
    "such","than","that","that's","the","their","theirs","them","themselves",
    "then","there","there's","these","they","they'd","they'll","they're",
    "they've","this","those","through","to","too","under","until","up","very",
    "was","wasn't","we","we'd","we'll","we're","we've","were","weren't","what",
    "what's","when","when's","where","where's","which","while","who","who's",
    "whom","why","why's","will","with","won't","would","wouldn't","you","you'd",
    "you'll","you're","you've","your","yours","yourself","yourselves",
    # cover-letter-specific noise words
    "please","dear","sincerely","regards","thank","thanks","position","role",
    "company","team","looking","forward","opportunity","join","work","excited",
    "passion","passionate","strong","background","experience","skills","ability",
    "ability","proven","track","record","currently","seeking","apply","feel",
    "believe","confident","letter","cover","resume","application","hiring",
    "manager","would","also","like","make","sure","help","well","use","used",
    "using","new","good","great","excellent","high","level","key","important",
    "including","ensure","provide","need","needs","required","requires","must",
    "may","best","first","second","third","many","much","part","full","time",
}

STOP_WORDS = _NLTK_STOPS | _BUILTIN_STOPS


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    if _NLTK_READY:
        try:
            tokens = _nltk_tok(text)
            return [t for t in tokens if t.isalpha()]
        except Exception:
            pass
    # Fallback: simple regex split
    return re.findall(r"[a-z][a-z']*[a-z]|[a-z]{2,}", text)


def _clean_tokens(tokens: list[str], min_len: int = 3) -> list[str]:
    return [t for t in tokens if t not in STOP_WORDS and len(t) >= min_len]


# ── N-gram extraction ─────────────────────────────────────────────────────────

def extract_ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# ── TF-IDF scoring ────────────────────────────────────────────────────────────

_MEANINGFUL_BIGRAM_PATTERN = re.compile(
    r'^([\w]+ (?:management|development|strategy|analysis|marketing|operations|'
    r'design|research|analytics|experience|skills|leadership|communication|'
    r'planning|execution|collaboration|performance|growth|data|brand|content|'
    r'digital|product|project|client|customer|business|financial|technical|'
    r'creative|strategic|cross.functional|problem.solving))$', re.I
)


def _is_meaningful_bigram(phrase: str) -> bool:
    """Filter out sliding-window noise bigrams like 'lead brand', 'strategy content'."""
    return bool(_MEANINGFUL_BIGRAM_PATTERN.match(phrase))


def compute_tfidf(
    target_text: str,
    corpus_texts: list[str],
    top_n: int = 20,
    ngram_sizes: tuple[int, ...] = (1, 2),
) -> list[tuple[str, float]]:
    """
    Compute TF-IDF scores for tokens in target_text relative to corpus_texts.

    target_text  — the job description
    corpus_texts — your existing cover letters (background frequency reference)
    Returns a ranked list of (term, score) tuples.
    """
    target_tokens = _clean_tokens(_tokenize(target_text))

    # Build term frequency for target document
    tf_target: Counter = Counter()
    for n in ngram_sizes:
        if n == 1:
            tf_target.update(target_tokens)
        else:
            tf_target.update(extract_ngrams(target_tokens, n))

    if not tf_target:
        return []

    total_target = sum(tf_target.values())
    tf_norm = {term: count / total_target for term, count in tf_target.items()}

    # IDF: how rare is this term across the corpus?
    N = len(corpus_texts) + 1  # +1 to avoid division by zero
    doc_freq: Counter = Counter()
    for doc in corpus_texts:
        doc_tokens = _clean_tokens(_tokenize(doc))
        doc_terms: set[str] = set()
        for n in ngram_sizes:
            if n == 1:
                doc_terms.update(doc_tokens)
            else:
                doc_terms.update(extract_ngrams(doc_tokens, n))
        doc_freq.update(doc_terms)

    scores: dict[str, float] = {}
    for term, tf in tf_norm.items():
        df = doc_freq.get(term, 0) + 1  # +1 smoothing
        idf = math.log(N / df)
        scores[term] = tf * idf

    # Common verbs that should not lead a keyword bigram (they indicate verb phrases, not noun phrases)
    _VERB_LEADS = {
        "lead","leads","leading","manage","manages","managing","build","builds",
        "building","drive","drives","driving","develop","develops","developing",
        "support","use","ensure","provide","work","create","help","make","identify",
    }

    # Filter bigrams: only keep phrases that appear verbatim in the target text
    # AND do not start with a verb (which would make them verb phrases, not skills)
    target_lower = target_text.lower()
    filtered = {
        term: score for term, score in scores.items()
        if " " not in term
        or (
            re.search(r'\b' + re.escape(term) + r'\b', target_lower)
            and term.split()[0] not in _VERB_LEADS
        )
    }
    ranked = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


# ── Keyword extraction (public API) ───────────────────────────────────────────

def extract_keywords(
    job_description: str,
    corpus_texts: list[str],
    top_n: int = 20,
    exclude_terms: list[str] = None,
) -> list[str]:
    """
    Return the top keywords from the job description.
    Uses TF-IDF against the examples corpus.

    exclude_terms — words/phrases to suppress (e.g. the role title itself,
    which scores high but isn't a useful skill keyword).
    """
    scored = compute_tfidf(job_description, corpus_texts, top_n=top_n + 10, ngram_sizes=(1, 2))

    exclude_tokens = set()
    for t in (exclude_terms or []):
        # Tokenize each exclude term so "Digital Intern" bans both words
        for word in t.lower().split():
            if len(word) > 2:
                exclude_tokens.add(word)

    def _contains_excluded(term: str) -> bool:
        # Exclude if ANY word in the term is an excluded token
        return any(word in exclude_tokens for word in term.lower().split())

    filtered = [
        term for term, _ in scored
        if not _contains_excluded(term)
    ]
    return filtered[:top_n]


# ── ATS analysis ──────────────────────────────────────────────────────────────

def ats_analysis(
    cover_letter_text: str,
    job_description: str,
    keywords: list[str],
) -> dict:
    """
    Return an ATS alignment report:
      - matched: keywords found in the cover letter
      - missing: keywords not found
      - score: 0-100 coverage score
      - density: keyword density %
    """
    cl_lower = cover_letter_text.lower()
    jd_lower = job_description.lower()

    matched = [kw for kw in keywords if kw.lower() in cl_lower]
    missing = [kw for kw in keywords if kw.lower() not in cl_lower]

    score = round(len(matched) / len(keywords) * 100) if keywords else 0

    # Keyword density: keyword tokens / total tokens in cover letter
    cl_tokens = _clean_tokens(_tokenize(cover_letter_text))
    kw_tokens = sum(1 for t in cl_tokens if any(t in kw for kw in matched))
    density = round(kw_tokens / max(len(cl_tokens), 1) * 100, 1)

    return {
        "matched": matched,
        "missing": missing,
        "score": score,
        "density": density,
        "total_keywords": len(keywords),
    }


# ── Resume-to-JD matching ─────────────────────────────────────────────────────

def match_resume_to_jd(
    resume_text: str,
    job_description: str,
    top_n: int = 5,
) -> list[str]:
    """
    Find the resume sentences/bullets most relevant to the job description.
    Uses token overlap (Jaccard similarity) as a lightweight relevance signal.
    """
    jd_tokens = set(_clean_tokens(_tokenize(job_description)))
    if not jd_tokens:
        return []

    # Split on newlines and bullet characters only — NOT on hyphens, which appear
    # inside compound words like "subscription-based" and "data-driven".
    raw_chunks = [
        c.strip()
        for c in re.split(r'[;\n•]|(?:^|\s)[–](?:\s|$)', resume_text)
        if len(c.strip()) > 20
    ]

    # Filter out lines that don't make good body-paragraph material:
    #   • Skills lists: "Skills: Excel, SAP, Python..."
    #   • Resume header lines: "Social Media Intern   Jan 2024"
    #     (short lines with a year/month at the end and lots of whitespace)
    def _is_unusable_line(chunk: str) -> bool:
        lower = chunk.lower()
        # Skills/education label lines
        if re.match(r'^(skills?|education|experience|summary|objective)\s*:', lower):
            return True
        # High comma density = a list, not a sentence
        words = chunk.split()
        commas = chunk.count(',')
        if len(words) > 3 and commas / len(words) > 0.3:
            return True
        # Resume header lines: ends with a year or month range
        if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\s*$', chunk):
            # Only flag as header if it's short (likely "Title   Date" format)
            if len(words) <= 8:
                return True
        return False

    chunks = [c for c in raw_chunks if not _is_unusable_line(c)]

    scored: list[tuple[str, float]] = []
    for chunk in chunks:
        chunk_tokens = set(_clean_tokens(_tokenize(chunk)))
        if not chunk_tokens:
            continue
        intersection = chunk_tokens & jd_tokens
        union = chunk_tokens | jd_tokens
        jaccard = len(intersection) / len(union)
        scored.append((chunk, jaccard))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_n]]
