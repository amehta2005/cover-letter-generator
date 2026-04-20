import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Default data paths (auto-loaded on startup) ───────────────────────────────
DATA_DIR     = os.path.join(BASE_DIR, "data")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")

DEFAULT_TEMPLATE = os.path.join(DATA_DIR, "template.docx")
DEFAULT_RESUME   = os.path.join(DATA_DIR, "resume.docx")
DEFAULT_PROFILE  = os.path.join(DATA_DIR, "profile.txt")

# ── PDF export ────────────────────────────────────────────────────────────────
# Primary: LibreOffice headless (free, cross-platform)
# Fallback: docx2pdf (requires LibreOffice or MS Word installed)
LIBREOFFICE_PATHS = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
    "/usr/bin/libreoffice",                                   # Linux
    "/usr/bin/soffice",                                       # Linux alt
    "soffice",                                                # PATH
    "libreoffice",                                            # PATH alt
]

# ── LLM hook (disabled by default — zero paid API required) ──────────────────
# Set USE_LLM = True and configure LLM_PROVIDER to enable local LLM generation.
# Supported providers: "ollama"
USE_LLM      = False
LLM_PROVIDER = "ollama"       # only used when USE_LLM = True
LLM_MODEL    = "llama3"       # Ollama model name
LLM_BASE_URL = "http://localhost:11434"

# ── Generation tuning ─────────────────────────────────────────────────────────
MAX_KEYWORDS        = 20    # top JD keywords to extract
MIN_KEYWORD_LEN     = 3     # ignore very short tokens
KEYWORD_WINDOW      = 2     # n-gram size for phrase extraction
RESUME_MATCH_TOP_N  = 5     # top matching resume bullets per section
MAX_COVER_LETTER_WORDS = 350

os.makedirs(OUTPUT_DIR, exist_ok=True)
