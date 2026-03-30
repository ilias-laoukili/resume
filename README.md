# Resume — Ilias Lkl

Professional CVs written in LaTeX, automatically compiled to PDF via GitHub Actions on every push to `main`.

---

## Quick View

[Download latest PDF](../../releases/latest/download/resume.pdf) — or browse the compiled artifact under the [Actions](../../actions) tab.

---

## Repository Structure

```
.
├── src/
│   ├── cv_industry.tex          # Industry-focused CV
│   └── cv_research_academic.tex # Research / academic CV
├── .github/
│   └── workflows/
│       └── compile.yml          # CI/CD pipeline
├── .gitignore
└── README.md
```

---

## Compile Locally

**Requirements:** a TeX distribution with `pdflatex` — [TeX Live](https://www.tug.org/texlive/) (Linux/macOS) or [MiKTeX](https://miktex.org/) (Windows).

```bash
# Clone the repository
git clone https://github.com/ilias-laoukili/resume.git
cd resume

# Option A — pdflatex (two passes for cross-references)
pdflatex -output-directory=output src/cv_industry.tex
pdflatex -output-directory=output src/cv_industry.tex

# Option B — latexmk (handles passes automatically)
latexmk -pdf -outdir=output src/cv_industry.tex
```

Replace `cv_industry` with `cv_research_academic` to compile the academic variant.

---

## Tech Stack

| Tool | Purpose |
|---|---|
| LaTeX | Document typesetting |
| GitHub Actions | Automated PDF compilation on push |

---

## License

[MIT](LICENSE)
