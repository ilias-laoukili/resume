# Instructions for agents

How an agent working in this repository must behave, and what it must check before starting.

## Before starting

- Read `data/profile.yaml` first. It is the single source of truth for all four CV variants (`cv_industry_en`, `cv_industry_fr`, `cv_research_academic_en`, `cv_research_academic_fr`).
- Never edit `src/cv_*.tex` directly: those files are deterministically generated from `data/profile.yaml`.
- Find what the author changed by hand and never overwrite it.
- Check that the pre-commit checks are active: `git config core.hooksPath` returns `.githooks`.
- Check that the starting point is sound:
  - `python3 scripts/cv.py check` passes;
  - `python3 -m unittest discover -s tests -q` passes.

## How to behave

### With the author

- Answer in French: the verdict first, in simple words, with simple questions.
- Unsolicited advice is allowed; the author keeps the right to set it aside.
- Before changing substantive CV wording (summary, role descriptions, bullets), show the exact proposed wording and wait for approval.

### Single source of truth and synchronization

- All four variants are generated from `data/profile.yaml` by `python3 scripts/cv.py build`.
- Shared facts (identity, links, emails, canonical dates, project URLs) live once in `data/profile.yaml`; never duplicate dates or URLs manually across files.
- Every bilingual field keeps `en` and `fr` directly adjacent. Never update one language without updating the other.
- Every variant must fit on **exactly one page** (`letterpaper`), verified by `python3 scripts/cv.py compile` locally and in GitHub Actions.

### Content accuracy and confidentiality

- Use direct, verifiable, plain language. Never inflate titles, invent metrics, or present unpublished work as published.
- For public-sector roles (such as the Ministère de la Cybersécurité et du Numérique), describe only public, non-confidential scope and responsibilities; never include internal project names, systems, tools, or data.

### Repository and git discipline

- Create no file, in particular no `.md` file, without being asked.
- Never delete with `rm`: move what is replaced to the macOS Trash (`/usr/bin/trash`).
- Do not commit without being asked.
- The agent is at no point a contributor and never presents itself as one: no author, co-author, or contributor mention of the agent in a commit message (no `Co-Authored-By` line), a pull request, a document, the code, or anywhere else.
- Never rewrite a commit: no `amend`, no `rebase`, no `force push`.
- Never bypass the pre-commit checks (no `--no-verify`).
- Generated `.tex` files must come out byte-identical when nothing changed: no build date, no random identifier, no timing. Verify with `python3 scripts/cv.py check`.
- Keep compiled PDFs and LaTeX auxiliary files out of git (`output/`, `*.pdf`, `*.aux`, `*.log`); CI publishes the PDFs to GitHub Releases.

### Code style

- All code, script messages, README, and `AGENTS.md` are in English.
- Use as few dependencies as possible (standard library + PyYAML only).

## Before handing back

- Run `python3 scripts/cv.py check`.
- Run `python3 -m unittest discover -s tests -q`.
- Run `python3 scripts/cv.py compile` to verify LaTeX compilation and the strict 1-page limit for all four PDFs.
- State clearly what was checked and what was not.
