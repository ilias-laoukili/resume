# Resume — Ilias Laoukili

Four synchronized LaTeX CV variants (Industry & Research/Academic, English & French) generated deterministically from a single source of truth (`data/profile.yaml`), verified by pre-commit checks, and compiled to PDF via GitHub Actions on every push to `main`.

---

## Quick View

| Track | English | Français |
|---|---|---|
| Industry | [cv_industry_en.pdf](../../releases/latest/download/cv_industry_en.pdf) | [cv_industry_fr.pdf](../../releases/latest/download/cv_industry_fr.pdf) |
| Research / Academic | [cv_research_academic_en.pdf](../../releases/latest/download/cv_research_academic_en.pdf) | [cv_research_academic_fr.pdf](../../releases/latest/download/cv_research_academic_fr.pdf) |

Backwards-compatible aliases (`cv_industry.pdf` and `cv_research_academic.pdf`, pointing to the English versions) are also published in the latest release. Compiled artifacts are also available under the [Actions](../../actions) tab.

---

## Repository Structure

```
.
├── data/
│   └── profile.yaml                      # Single source of truth (facts + EN/FR content)
├── scripts/
│   └── cv.py                             # Deterministic generator, sync checker, 1-page verifier
├── src/
│   ├── cv_industry_en.tex                # Generated — Industry CV (EN)
│   ├── cv_industry_fr.tex                # Generated — Industry CV (FR)
│   ├── cv_research_academic_en.tex       # Generated — Research / Academic CV (EN)
│   └── cv_research_academic_fr.tex       # Generated — Research / Academic CV (FR)
├── tests/
│   └── test_cv.py                        # Unit tests (schema, escaping, determinism, sync)
├── .githooks/
│   └── pre-commit                        # Pre-commit sync, test, and 1-page compile checks
├── .github/
│   └── workflows/
│       └── compile.yml                   # CI/CD verification and PDF release pipeline
├── AGENTS.md                             # Instructions for agents working in this repository
└── README.md
```

---

## Workflow & Local Setup

**Requirements:** Python 3.9+ with `PyYAML`, and a TeX Live distribution with `pdflatex` (`preprint`, `titlesec`, `marvosym`, `enumitem`, `fontawesome5`, `babel-french`).

```bash
# Activate repository pre-commit checks (once per clone)
git config core.hooksPath .githooks

# 1. Edit data/profile.yaml, then regenerate all 4 .tex files
python3 scripts/cv.py build

# 2. Verify schema, EN/FR parity, determinism, and zero drift
python3 scripts/cv.py check
python3 -m unittest discover -s tests -q

# 3. Compile all 4 PDFs into output/ and enforce the 1-page limit
python3 scripts/cv.py compile
```

---

## License

[MIT](LICENSE)
