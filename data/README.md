# data/

This folder holds your personal files. They are gitignored and never committed to the repo.

## Required files

| File | Description |
|---|---|
| `template.docx` | Your cover letter DOCX template. Formatting is preserved — only body paragraphs are replaced. |
| `resume.docx` | Your resume in DOCX format. The app matches bullets to the job description. |
| `profile.txt` | Plain text file with your background, skills, and tone preferences. |

## profile.txt format

```
NAME: Your Name

BACKGROUND:
[1-2 sentences: school, major, year, relevant experience highlights]

SKILLS:
[Comma-separated list: marketing strategy, data analysis, Excel, etc.]

CAREER INTERESTS:
[Target roles and industries]

INTERESTS:
[Personal interests]

TONE PREFERENCES:
- [Any voice/style rules you want followed]
```

See `profile.example.txt` for a complete sample.

## examples/ folder (optional but recommended)

Place past cover letters (DOCX or PDF) in the `examples/` folder at the project root.
The app uses them as a reference corpus for TF-IDF keyword scoring — the more examples
you provide, the better it distinguishes role-specific keywords from generic cover letter language.
