# Cover Letter Generator

A fully local, AI-assisted cover letter generator built with Python and Flask. Paste a job description, and the app produces a tailored, ATS-optimized cover letter in both DOCX and PDF — in under 10 seconds, with no API keys, no cloud dependency, and no cost.

Built as a personal productivity tool to eliminate the repetitive work of customizing cover letters for every application while maintaining a natural, non-generic voice.

---

## What It Does

- **Extracts keywords** from the job description using TF-IDF scoring against a corpus of reference cover letters
- **Matches your resume** to the JD using Jaccard similarity to surface the most relevant bullets
- **Generates a tailored letter** across 5 structured paragraphs using rule-based composition seeded by your background profile
- **Scores ATS alignment** and shows which keywords are matched vs. missing in real time
- **Exports to DOCX and PDF** locally, preserving the formatting of your personal template
- **Editable draft** — every paragraph is editable in the UI before export
- **Optional local LLM** — plug in Ollama (Llama 3, Mistral, etc.) to upgrade generation quality with zero API cost

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| DOCX I/O | python-docx |
| PDF export | LibreOffice headless |
| NLP / Keyword extraction | NLTK, TF-IDF (no external API) |
| Example corpus parsing | pdfplumber |
| Frontend | Vanilla HTML/CSS/JS (single-page, no build tools) |
| LLM hook (optional) | Ollama — local models only |

---

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/cover-letter-generator.git
cd cover-letter-generator

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download NLTK data (one-time, ~3 MB)
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt_tab')"

# 5. Add your personal files to data/ (see data/README.md)

# 6. Start the app
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

---

## PDF Export

PDF generation requires LibreOffice (free, one-time install):

```bash
# macOS
brew install --cask libreoffice

# Linux
sudo apt install libreoffice
```

Without LibreOffice, the app exports DOCX only and shows an install prompt.

---

## Personal Data Files

The `data/` folder holds your personal files (gitignored — see `data/README.md`):

| File | Purpose |
|---|---|
| `data/template.docx` | Your cover letter template — formatting is preserved |
| `data/resume.docx` | Your resume — matched against job descriptions |
| `data/profile.txt` | Your background, tone preferences, and career interests |
| `examples/` | Past cover letters used as a keyword frequency corpus |

---

## How Generation Works

The app runs entirely offline. No data leaves your machine.

1. **Keyword extraction** — TF-IDF scores the job description against your examples corpus. Words that appear in this JD but rarely in your past letters score highest, surfacing role-specific requirements.
2. **Resume matching** — Jaccard similarity finds the resume bullets with the highest token overlap against the JD. Skill-list lines and date headers are filtered out automatically.
3. **Profile parsing** — Structured parsing of `profile.txt` extracts your background, ventures, academic focus, and tone rules.
4. **Paragraph assembly** — Five template banks (opening, body × 3, closing), each with 4 variants selected deterministically by a hash of company+role. Same company always gets the same letter; different companies get different-feeling letters.
5. **ATS scoring** — Keyword coverage and density are measured post-generation and shown in the right panel.

---

## Optional: Local LLM Upgrade

The rule-based mode works without any AI model. To upgrade output quality:

```bash
# Install Ollama: https://ollama.com
ollama pull llama3
```

Then in `config.py`:
```python
USE_LLM = True
LLM_MODEL = "llama3"
```

The LLM refines the rule-based draft rather than starting from scratch — faster and more controllable than generating from a blank prompt.

---

## Project Structure

```
cover-letter-generator/
├── app.py                  Flask server + API routes
├── config.py               Paths, feature flags, tuning constants
├── requirements.txt
├── data/                   Personal files (gitignored)
│   └── README.md           Setup instructions for data files
├── examples/               Reference cover letters (gitignored)
├── output/                 Generated files (gitignored)
├── generator/
│   ├── extractor.py        Text extraction from DOCX, PDF, TXT
│   ├── keywords.py         TF-IDF keyword extraction + ATS scoring
│   ├── composer.py         Rule-based cover letter composition
│   ├── exporter.py         Template fill + PDF export
│   └── llm_hook.py         Ollama integration (disabled by default)
└── templates/
    └── index.html          Single-page UI
```
