"""
app.py — Flask application for the local cover letter generator.

Run with:
    python app.py
Then open http://127.0.0.1:5001 in your browser.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

import config
from generator import extractor, keywords as kw_module, composer, exporter, llm_hook

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload limit

# ── State loaded once at startup ──────────────────────────────────────────────
_corpus_texts: list[str] = []
_example_openers: list[str] = []
_example_closings: list[str] = []


def _load_defaults():
    """Load the examples corpus on first request (lazy, cached)."""
    global _corpus_texts, _example_openers, _example_closings
    if _corpus_texts:
        return
    print("Loading examples corpus…", flush=True)
    _corpus_texts = extractor.load_examples(config.EXAMPLES_DIR)
    _example_openers = extractor.mine_opener_sentences(_corpus_texts)
    _example_closings = extractor.mine_closing_sentences(_corpus_texts)
    print(f"  Loaded {len(_corpus_texts)} examples, "
          f"{len(_example_openers)} openers, "
          f"{len(_example_closings)} closings.", flush=True)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/defaults", methods=["GET"])
def api_defaults():
    """Return metadata about the default files so the UI can show them."""
    _load_defaults()
    return jsonify({
        "template": _file_info(config.DEFAULT_TEMPLATE),
        "resume":   _file_info(config.DEFAULT_RESUME),
        "profile":  _file_info(config.DEFAULT_PROFILE),
        "examples": {
            "count": len(_corpus_texts),
            "folder": config.EXAMPLES_DIR,
        },
        "llm_available": llm_hook.is_available(),
    })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Generate a tailored cover letter.

    Accepts multipart/form-data with:
      - company        (str, required)
      - role           (str, required)
      - job_description (str, required)
      - hiring_manager (str, optional)
      - template_file  (file, optional — uses default if omitted)
      - resume_file    (file, optional — uses default if omitted)
      - profile_file   (file, optional — uses default if omitted)
    """
    _load_defaults()

    # ── Collect form fields ────────────────────────────────────────────────
    company          = request.form.get("company", "").strip()
    role             = request.form.get("role", "").strip()
    job_description  = request.form.get("job_description", "").strip()
    hiring_manager   = request.form.get("hiring_manager", "").strip()

    if not company or not role or not job_description:
        return jsonify({"error": "company, role, and job_description are required"}), 400

    # ── Resolve file paths (upload overrides default) ─────────────────────
    template_path = _resolve_file("template_file", config.DEFAULT_TEMPLATE, [".docx"])
    resume_path   = _resolve_file("resume_file",   config.DEFAULT_RESUME,   [".docx"])
    profile_path  = _resolve_file("profile_file",  config.DEFAULT_PROFILE,  [".txt"])

    if isinstance(template_path, tuple): return template_path
    if isinstance(resume_path, tuple):   return resume_path
    if isinstance(profile_path, tuple):  return profile_path

    # ── Extract text from inputs ───────────────────────────────────────────
    try:
        resume_text  = extractor.extract_docx_text(resume_path)
        profile_text = extractor.extract_txt(profile_path)
    except Exception as e:
        return jsonify({"error": f"Failed to read input files: {e}"}), 500

    # ── Keyword extraction ─────────────────────────────────────────────────
    # Exclude the role title and company name — they score high but aren't
    # meaningful skill keywords to weave into the letter body.
    keywords = kw_module.extract_keywords(
        job_description,
        _corpus_texts,
        top_n=config.MAX_KEYWORDS,
        exclude_terms=[company, role],
    )

    # ── Resume → JD matching ───────────────────────────────────────────────
    resume_bullets = kw_module.match_resume_to_jd(
        resume_text,
        job_description,
        top_n=config.RESUME_MATCH_TOP_N,
    )

    # ── Compose cover letter ───────────────────────────────────────────────
    sections = composer.compose_cover_letter(
        company=company,
        role=role,
        job_description=job_description,
        keywords=keywords,
        resume_bullets=resume_bullets,
        profile_text=profile_text,
        example_openers=_example_openers,
        example_closings=_example_closings,
        hiring_manager=hiring_manager,
    )

    # ── Optional LLM refinement ────────────────────────────────────────────
    if llm_hook.is_available():
        system_prompt, user_prompt = llm_hook.build_cover_letter_prompt(
            company=company, role=role,
            job_description=job_description, keywords=keywords,
            resume_text=resume_text, profile_text=profile_text,
            example_texts=_corpus_texts[:3],
            rule_based_draft=sections["full_text"],
        )
        refined = llm_hook.generate(user_prompt, system=system_prompt)
        if refined:
            # Re-parse the LLM output back into sections
            paragraphs = [p.strip() for p in refined.split("\n\n") if p.strip()]
            if len(paragraphs) >= 4:
                sections["opening"] = paragraphs[0]
                sections["body1"]   = paragraphs[1]
                sections["body2"]   = paragraphs[2]
                sections["closing"] = paragraphs[3]
                sections["full_text"] = composer.assemble_full_text(sections)

    # ── ATS analysis ───────────────────────────────────────────────────────
    ats = kw_module.ats_analysis(
        sections["full_text"],
        job_description,
        keywords,
    )

    return jsonify({
        "sections": sections,
        "keywords": keywords,
        "ats": ats,
        "llm_used": llm_hook.is_available(),
    })


@app.route("/api/export", methods=["POST"])
def api_export():
    """
    Export a (possibly edited) cover letter to DOCX + PDF.

    Accepts JSON body:
      {
        "sections": { date, salutation, opening, body1, body2, closing, name },
        "company": "...",
        "role": "...",
        "template_path": "..." (optional override)
      }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    sections = data.get("sections", {})
    company  = data.get("company", "Company")
    role     = data.get("role", "Role")
    template_path = data.get("template_path", config.DEFAULT_TEMPLATE)

    if not os.path.isfile(template_path):
        template_path = config.DEFAULT_TEMPLATE

    try:
        result = exporter.generate_outputs(template_path, sections, company, role)
    except Exception as e:
        import traceback
        traceback.print_exc()   # print full traceback to Terminal for debugging
        return jsonify({"error": f"Export failed: {e}"}), 500

    if not result.get("docx") or not os.path.isfile(result["docx"]):
        return jsonify({"error": "DOCX file was not created. Check Terminal for details."}), 500

    return jsonify({
        "docx": result["docx"],
        "pdf":  result["pdf"],
        "pdf_error": result.get("pdf_error"),
        "docx_filename": os.path.basename(result["docx"]),
        "pdf_filename":  os.path.basename(result["pdf"]) if result["pdf"] else None,
    })


@app.route("/api/download/<path:filename>")
def api_download(filename):
    """Serve a generated file from the output directory."""
    safe_name = Path(filename).name  # Strip any path traversal attempts
    file_path = os.path.join(config.OUTPUT_DIR, safe_name)
    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=safe_name)


@app.route("/api/outputs", methods=["GET"])
def api_outputs():
    """List previously generated files in the output directory."""
    files = []
    for f in sorted(os.listdir(config.OUTPUT_DIR), reverse=True):
        if f.endswith((".docx", ".pdf")):
            full = os.path.join(config.OUTPUT_DIR, f)
            files.append({
                "name": f,
                "size_kb": round(os.path.getsize(full) / 1024, 1),
                "created": datetime.fromtimestamp(os.path.getctime(full)).strftime("%Y-%m-%d %H:%M"),
            })
    return jsonify(files[:50])  # Cap at 50 most recent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _file_info(path: str) -> dict:
    if os.path.isfile(path):
        return {
            "exists": True,
            "name": os.path.basename(path),
            "size_kb": round(os.path.getsize(path) / 1024, 1),
        }
    return {"exists": False, "name": os.path.basename(path)}


def _resolve_file(form_key: str, default_path: str, allowed_exts: list[str]):
    """
    If the request contains an uploaded file under form_key, save it to a
    temp location and return that path.  Otherwise return default_path.
    Returns an error tuple (jsonify, status) if validation fails.
    """
    uploaded = request.files.get(form_key)
    if uploaded and uploaded.filename:
        ext = os.path.splitext(uploaded.filename)[1].lower()
        if ext not in allowed_exts:
            return jsonify({"error": f"{form_key}: only {allowed_exts} files accepted"}), 400
        # Save to a session-scoped temp file in the output dir
        tmp_path = os.path.join(config.OUTPUT_DIR, f"_upload_{form_key}{ext}")
        uploaded.save(tmp_path)
        return tmp_path
    return default_path


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Cover Letter Generator starting…")
    print(f"  Template : {config.DEFAULT_TEMPLATE}")
    print(f"  Resume   : {config.DEFAULT_RESUME}")
    print(f"  Profile  : {config.DEFAULT_PROFILE}")
    print(f"  Examples : {config.EXAMPLES_DIR}")
    print(f"  Output   : {config.OUTPUT_DIR}")
    print(f"  LLM      : {'enabled' if config.USE_LLM else 'disabled (rule-based mode)'}")
    print("\nOpen http://127.0.0.1:5001 in your browser.\n")
    app.run(host="127.0.0.1", port=5001, debug=False)
