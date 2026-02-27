# Resume — Ilias Lkl

A single-page professional CV written in LaTeX, automatically compiled to PDF via GitHub Actions on every push to `main`.

---

## Quick View

[Download latest PDF](../../releases/latest/download/resume.pdf) — or browse the compiled artifact under the [Actions](../../actions) tab.

---

## Repository Structure

```
.
├── src/
│   └── main.tex        # LaTeX source
├── .github/
│   └── workflows/
│       └── compile.yml # CI/CD pipeline
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
pdflatex -output-directory=. src/main.tex
pdflatex -output-directory=. src/main.tex

# Option B — latexmk (handles passes automatically)
latexmk -pdf -outdir=. src/main.tex
```

The output file `main.pdf` will appear in the project root.

---

## Tech Stack

| Tool | Purpose |
|---|---|
| LaTeX | Document typesetting |
| GitHub Actions | Automated PDF compilation on push |

---

## License

[MIT](LICENSE)
