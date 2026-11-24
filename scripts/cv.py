#!/usr/bin/env python3
"""Deterministic LaTeX CV generator, sync checker, and 1-page PDF verifier.

Source of truth: data/profile.yaml
Generated files: src/cv_{industry,research_academic}_{en,fr}.tex

Subcommands:
    build        Generate all 4 LaTeX files deterministically from data/profile.yaml.
    check        Validate profile.yaml, verify determinism, and assert zero drift with src/*.tex.
    compile      Compile all 4 variants to output/ via latexmk/pdflatex and enforce 1-page limit.
    check-pages  Verify that every given PDF file is exactly 1 page.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print(
        "Error: PyYAML is required (pip install pyyaml or system python3-yaml).",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "data" / "profile.yaml"
SRC_DIR = ROOT / "src"
OUTPUT_DIR = ROOT / "output"

LANGUAGES = ("en", "fr")
TRACKS = ("industry", "research_academic")

MONTHS = {
    "en": {
        1: "Jan.",
        2: "Feb.",
        3: "Mar.",
        4: "Apr.",
        5: "May",
        6: "Jun.",
        7: "Jul.",
        8: "Aug.",
        9: "Sep.",
        10: "Oct.",
        11: "Nov.",
        12: "Dec.",
    },
    "fr": {
        1: "Janv.",
        2: "Fév.",
        3: "Mars",
        4: "Avr.",
        5: "Mai",
        6: "Juin",
        7: "Juil.",
        8: "Août",
        9: "Sept.",
        10: "Oct.",
        11: "Nov.",
        12: "Déc.",
    },
}

PRESENT = {"en": "Present", "fr": "Présent"}

REQUIRED_TEX_PACKAGES = (
    ("fullpage.sty", "preprint"),
    ("titlesec.sty", "titlesec"),
    ("marvosym.sty", "marvosym"),
    ("enumitem.sty", "enumitem"),
    ("fontawesome5.sty", "fontawesome5"),
    ("french.ldf", "babel-french"),
)

FORBIDDEN_SUBSTRINGS = ("TODO", "TBD", "FIXME", "synth-graph-rs")

INLINE_TOKEN_RE = re.compile(
    r"\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`"
)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return data


def escape_latex_plain(text: str) -> str:
    """Escape plain text for pdfLaTeX (UTF-8 + T1 fontenc)."""
    out: list[str] = []
    idx = 0
    length = len(text)
    while idx < length:
        if text.startswith("---", idx):
            out.append("---")
            idx += 3
            continue
        if text.startswith("--", idx):
            out.append("--")
            idx += 2
            continue
        ch = text[idx]
        if ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch in ("&", "%", "$", "#", "_", "{", "}"):
            out.append("\\" + ch)
        elif ch == "^":
            out.append(r"\textasciicircum{}")
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        elif ch == "\u2014":  # em dash
            out.append("---")
        elif ch == "\u2013":  # en dash
            out.append("--")
        elif ch in ("\u2018", "\u2019"):
            out.append("'")
        elif ch == "\u0153":
            out.append(r"\oe{}")
        elif ch == "\u0152":
            out.append(r"\OE{}")
        else:
            out.append(ch)
        idx += 1
    return "".join(out)


def escape_latex_url(url: str) -> str:
    return url.replace("%", r"\%").replace("#", r"\#")


def to_latex(text: str) -> str:
    """Convert lightweight inline markup (**bold**, *italic*, `code`, [label](url)) to LaTeX."""
    parts: list[str] = []
    pos = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        if match.start() > pos:
            parts.append(escape_latex_plain(text[pos : match.start()]))
        link_label, link_url, bold, italic, code = match.groups()
        if link_label is not None and link_url is not None:
            parts.append(
                r"\href{"
                + escape_latex_url(link_url)
                + r"}{\color{MidnightBlue}"
                + to_latex(link_label)
                + "}"
            )
        elif bold is not None:
            parts.append(r"\textbf{" + to_latex(bold) + "}")
        elif italic is not None:
            parts.append(r"\textit{" + to_latex(italic) + "}")
        elif code is not None:
            parts.append(r"\texttt{" + escape_latex_plain(code) + "}")
        pos = match.end()
    if pos < len(text):
        parts.append(escape_latex_plain(text[pos:]))
    return "".join(parts)


def parse_date_tuple(raw: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})(?:-(\d{2}))?", raw)
    if not match:
        raise ValueError(f"Invalid date format '{raw}': expected YYYY or YYYY-MM.")
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else 0
    if month < 0 or month > 12:
        raise ValueError(f"Invalid month in date '{raw}'.")
    return year, month


def format_single_date(raw: str, lang: str) -> str:
    year, month = parse_date_tuple(raw)
    if month == 0:
        return str(year)
    return f"{MONTHS[lang][month]} {year}"


def format_dates(dates: dict[str, Any] | None, lang: str) -> str:
    if dates is None:
        return ""
    if "single" in dates:
        return format_single_date(str(dates["single"]), lang)
    if "start_term" in dates:
        start_str = escape_latex_plain(dates["start_term"][lang])
    else:
        start_str = format_single_date(str(dates["start"]), lang)
    end_val = dates.get("end")
    end_str = PRESENT[lang] if end_val is None else format_single_date(str(end_val), lang)
    return f"{start_str} -- {end_str}"


def pick_localized(node: Any, track: str, lang: str) -> Any:
    """Resolve either {en, fr} or {track: {en, fr}}."""
    if isinstance(node, dict) and track in node:
        node = node[track]
    if not isinstance(node, dict) or lang not in node:
        raise ValueError(f"Missing localized value for track='{track}', lang='{lang}' in {node!r}")
    return node[lang]


def render_preamble(track_cfg: dict[str, Any], lang: str) -> str:
    layout = track_cfg["layout"]
    babel_opt = "french" if lang == "fr" else "english"
    french_setup = "\\frenchsetup{StandardLists=true}\n" if lang == "fr" else ""
    return (
        "%------------------------------------------------------------------------------\n"
        "% GENERATED FILE -- DO NOT EDIT DIRECTLY.\n"
        "% Source of truth: data/profile.yaml\n"
        "% Regenerate with: python3 scripts/cv.py build\n"
        "% Template derived from Jake Gutierrez / sb2nov (MIT License).\n"
        "%------------------------------------------------------------------------------\n\n"
        f"\\documentclass[letterpaper,{layout['font_size']}]{{article}}\n\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{latexsym}\n"
        "\\usepackage[empty]{fullpage}\n"
        "\\usepackage{titlesec}\n"
        "\\usepackage{marvosym}\n"
        "\\usepackage[usenames,dvipsnames]{color}\n"
        "\\usepackage{verbatim}\n"
        "\\usepackage{enumitem}\n"
        "\\usepackage[hidelinks]{hyperref}\n"
        "\\usepackage{fancyhdr}\n"
        f"\\usepackage[{babel_opt}]{{babel}}\n"
        f"{french_setup}"
        "\\usepackage{tabularx}\n"
        "\\usepackage{fontawesome5}\n"
        "\\input{glyphtounicode}\n\n"
        "\\pagestyle{fancy}\n"
        "\\fancyhf{}\n"
        "\\fancyfoot{}\n"
        "\\renewcommand{\\headrulewidth}{0pt}\n"
        "\\renewcommand{\\footrulewidth}{0pt}\n\n"
        "% Margins\n"
        f"\\addtolength{{\\oddsidemargin}}{{{layout['oddsidemargin']}}}\n"
        f"\\addtolength{{\\evensidemargin}}{{{layout['oddsidemargin']}}}\n"
        f"\\addtolength{{\\textwidth}}{{{layout['textwidth_add']}}}\n"
        f"\\addtolength{{\\topmargin}}{{{layout['topmargin']}}}\n"
        f"\\addtolength{{\\textheight}}{{{layout['textheight_add']}}}\n\n"
        "\\urlstyle{same}\n\n"
        "\\raggedbottom\n"
        "\\raggedright\n"
        "\\setlength{\\tabcolsep}{0in}\n\n"
        "% Section formatting\n"
        "\\titleformat{\\section}{\n"
        f"  \\vspace{{{layout['section_vspace']}}}\\scshape\\raggedright\\large\n"
        "}{}{0em}{}[\\color{black}\\titlerule \\vspace{-5pt}]\n\n"
        "% Machine-readable / ATS-parsable PDF\n"
        "\\pdfgentounicode=1\n\n"
        "% Custom commands\n"
        "\\newcommand{\\resumeItem}[1]{\n"
        "  \\item\\small{\n"
        "    {#1\\vspace{-2pt}}\n"
        "  }\n"
        "}\n\n"
        "\\newcommand{\\resumeSubheading}[4]{\n"
        f"  \\vspace{{{layout['subheading_vspace']}}}\\item\n"
        "    \\begin{tabular*}{0.97\\textwidth}[t]{l@{\\extracolsep{\\fill}}r}\n"
        "      \\textbf{#1} & #2 \\\\\n"
        "      \\textit{\\small#3} & \\textit{\\small #4} \\\\\n"
        "    \\end{tabular*}\\vspace{-7pt}\n"
        "}\n\n"
        "\\newcommand{\\resumeProjectHeading}[2]{\n"
        "    \\item\n"
        "    \\begin{tabular*}{0.97\\textwidth}{l@{\\extracolsep{\\fill}}r}\n"
        "      \\small#1 & #2 \\\\\n"
        "    \\end{tabular*}\\vspace{-7pt}\n"
        "}\n\n"
        "\\renewcommand\\labelitemii{$\\vcenter{\\hbox{\\tiny$\\bullet$}}$}\n\n"
        "\\newcommand{\\resumeSubHeadingListStart}{\\begin{itemize}[leftmargin=0.15in, label={}]}\n"
        "\\newcommand{\\resumeSubHeadingListEnd}{\\end{itemize}}\n"
        f"\\newcommand{{\\resumeItemListStart}}{{\\begin{{itemize}}[itemsep={layout['itemsep']}]}}\n"
        "\\newcommand{\\resumeItemListEnd}{\\end{itemize}\\vspace{-5pt}}\n\n"
        "\\begin{document}\n"
    )


def render_header(profile: dict[str, Any], track: str, lang: str) -> str:
    identity = profile["identity"]
    name = escape_latex_plain(identity["name"])
    email = identity["emails"][profile["variants"][track]["email_key"]]
    linkedin = identity["links"]["linkedin"]
    github = identity["links"]["github"]
    website = identity["links"]["website"]

    if profile["variants"][track]["header_style"] == "industry":
        location = escape_latex_plain(identity["location"][lang])
        return (
            "\n%----------HEADING----------\n"
            "\\begin{center}\n"
            f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{2pt}}\n"
            f"    \\href{{{escape_latex_url(linkedin['url'])}}}{{\\color{{MidnightBlue}}\\faLinkedin\\ {escape_latex_plain(linkedin['label_industry'])}}} $|$\n"
            f"    \\href{{mailto:{escape_latex_url(email)}}}{{\\color{{MidnightBlue}}\\faEnvelope\\ {escape_latex_plain(email)}}} $|$\n"
            f"    \\href{{{escape_latex_url(github['url'])}}}{{\\color{{MidnightBlue}}\\faGithub\\ {escape_latex_plain(github['label'])}}} $|$\n"
            f"    \\href{{{escape_latex_url(website['url'])}}}{{\\color{{MidnightBlue}}\\faGlobe\\ {escape_latex_plain(website['label'])}}} \\\\\n"
            f"    \\small {location}\n"
            "\\end{center}\n"
        )

    tagline = escape_latex_plain(identity["academic_tagline"][lang])
    return (
        "\n%----------HEADING----------\n"
        "\\begin{center}\n"
        f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}\n"
        f"    \\small {tagline} \\\\ \\vspace{{2pt}}\n"
        f"    \\href{{mailto:{escape_latex_url(email)}}}{{\\color{{MidnightBlue}}\\faEnvelope\\ {escape_latex_plain(email)}}} $|$\n"
        f"    \\href{{{escape_latex_url(github['url'])}}}{{\\color{{MidnightBlue}}\\faGithub\\ {escape_latex_plain(github['label'])}}} $|$\n"
        f"    \\href{{{escape_latex_url(linkedin['url'])}}}{{\\color{{MidnightBlue}}\\faLinkedin\\ {escape_latex_plain(linkedin['label_academic'])}}} $|$\n"
        f"    \\href{{{escape_latex_url(website['url'])}}}{{\\color{{MidnightBlue}}\\faGlobe\\ {escape_latex_plain(website['label'])}}}\n"
        "\\end{center}\n"
    )


def render_bullets(bullets: list[str]) -> str:
    lines = ["    \\resumeItemListStart"]
    for item in bullets:
        lines.append(f"      \\resumeItem{{{to_latex(item)}}}")
    lines.append("    \\resumeItemListEnd")
    return "\n".join(lines)


def render_summary(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    body = to_latex(profile["summary"][track][lang])
    return (
        f"\n\\section{{{escape_latex_plain(title)}}}\n"
        "\\small{\n"
        f"    {body}\n"
        "}\n"
        "\\vspace{-4pt}\n"
    )


def render_education(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    blocks = [f"\n\\section{{{escape_latex_plain(title)}}}", "\\resumeSubHeadingListStart"]
    for entry in profile["education"]:
        if track not in entry["variants"]:
            continue
        inst = to_latex(entry["institution"][lang])
        loc = to_latex(entry["location"][lang])
        deg = to_latex(pick_localized(entry["degree"], track, lang))
        dates = format_dates(entry["dates"], lang)
        bullets = pick_localized(entry["bullets"], track, lang)
        blocks.append(
            "  \\resumeSubheading\n"
            f"    {{{inst}}}{{{loc}}}\n"
            f"    {{{deg}}}{{{dates}}}\n"
            f"{render_bullets(bullets)}\n"
        )
    blocks.append("\\resumeSubHeadingListEnd\n")
    return "\n".join(blocks)


def render_experience(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    blocks = [f"\n\\section{{{escape_latex_plain(title)}}}", "\\resumeSubHeadingListStart"]
    for entry in profile["experience"]:
        if track not in entry["variants"]:
            continue
        role = to_latex(pick_localized(entry["role"], track, lang))
        org = to_latex(entry["organization"][lang])
        loc = to_latex(entry["location"][lang])
        dates = format_dates(entry["dates"], lang)
        bullets = pick_localized(entry["bullets"], track, lang)
        blocks.append(
            "  \\resumeSubheading\n"
            f"    {{{role}}}{{{dates}}}\n"
            f"    {{{org}}}{{{loc}}}\n"
            f"{render_bullets(bullets)}\n"
        )
    blocks.append("\\resumeSubHeadingListEnd\n")
    return "\n".join(blocks)


def render_projects(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    blocks = [f"\n\\section{{{escape_latex_plain(title)}}}", "\\resumeSubHeadingListStart"]
    for entry in profile["projects"]:
        if track not in entry["variants"]:
            continue
        proj_title = to_latex(pick_localized(entry["title"], track, lang))
        tech = to_latex(pick_localized(entry["tech"], track, lang))
        url = entry.get("url")
        if url:
            title_tex = (
                f"\\textbf{{\\href{{{escape_latex_url(url)}}}"
                f"{{\\color{{MidnightBlue}}{proj_title}}}}}"
            )
        else:
            title_tex = f"\\textbf{{{proj_title}}}"
        dates = format_dates(entry.get("dates"), lang)
        bullets = pick_localized(entry["bullets"], track, lang)
        blocks.append(
            "  \\resumeProjectHeading\n"
            f"    {{{title_tex} $|$ \\emph{{{tech}}}}}{{{dates}}}\n"
            f"{render_bullets(bullets)}\n"
        )
    blocks.append("\\resumeSubHeadingListEnd\n")
    return "\n".join(blocks)


def render_skills(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    rows = []
    entries = profile["skills"][track]
    for idx, entry in enumerate(entries):
        label = escape_latex_plain(entry["label"][lang])
        items = to_latex(entry["items"][lang])
        suffix = " \\\\" if idx < len(entries) - 1 else ""
        rows.append(f"    \\textbf{{{label}}}{{: {items}}}{suffix}")
    joined = "\n".join(rows)
    return (
        f"\n\\section{{{escape_latex_plain(title)}}}\n"
        "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
        "  \\small{\\item{\n"
        f"{joined}\n"
        "  }}\n"
        "\\end{itemize}\n"
    )


def render_activities(profile: dict[str, Any], title: str, track: str, lang: str) -> str:
    blocks = [f"\n\\section{{{escape_latex_plain(title)}}}", "\\resumeSubHeadingListStart"]
    for entry in profile["activities"]:
        if track not in entry["variants"]:
            continue
        role = to_latex(entry["role"][lang])
        org = to_latex(entry["organization"][lang])
        loc = to_latex(entry["location"][lang])
        dates = format_dates(entry["dates"], lang)
        bullets = pick_localized(entry["bullets"], track, lang)
        blocks.append(
            "  \\resumeSubheading\n"
            f"    {{{role}}}{{{dates}}}\n"
            f"    {{{org}}}{{{loc}}}\n"
            f"{render_bullets(bullets)}\n"
        )
    blocks.append("\\resumeSubHeadingListEnd\n")
    return "\n".join(blocks)


SECTION_RENDERERS = {
    "summary": render_summary,
    "education": render_education,
    "experience": render_experience,
    "projects": render_projects,
    "skills": render_skills,
    "activities": render_activities,
}


def render_cv(profile: dict[str, Any], track: str, lang: str) -> str:
    track_cfg = profile["variants"][track]
    chunks = [
        render_preamble(track_cfg, lang),
        render_header(profile, track, lang),
    ]
    for section in track_cfg["sections"]:
        key = section["key"]
        title = section["title"][lang]
        chunks.append(SECTION_RENDERERS[key](profile, title, track, lang))
    chunks.append("\n\\end{document}\n")
    return "".join(chunks)


def output_targets(profile: dict[str, Any]) -> list[tuple[str, str, Path]]:
    targets: list[tuple[str, str, Path]] = []
    for track in TRACKS:
        prefix = profile["variants"][track]["file_prefix"]
        for lang in LANGUAGES:
            targets.append((track, lang, SRC_DIR / f"{prefix}_{lang}.tex"))
    return targets


def _check_bilingual(obj: Any, path: str, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{path}: expected mapping with keys {LANGUAGES}.")
        return
    for lang in LANGUAGES:
        val = obj.get(lang)
        if val is None or val == "" or val == []:
            errors.append(f"{path}.{lang}: missing or empty.")


def _check_dates_node(dates: Any, path: str, errors: list[str]) -> None:
    if dates is None:
        return
    if not isinstance(dates, dict):
        errors.append(f"{path}: dates must be a mapping or null.")
        return
    if "single" in dates:
        try:
            parse_date_tuple(str(dates["single"]))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
        return
    if "start_term" in dates:
        _check_bilingual(dates["start_term"], f"{path}.start_term", errors)
        end_val = dates.get("end")
        if end_val is not None:
            try:
                parse_date_tuple(str(end_val))
            except ValueError as exc:
                errors.append(f"{path}.end: {exc}")
        return
    if "start" not in dates:
        errors.append(f"{path}: missing 'start', 'start_term', or 'single'.")
        return
    try:
        start_t = parse_date_tuple(str(dates["start"]))
    except ValueError as exc:
        errors.append(f"{path}.start: {exc}")
        return
    end_val = dates.get("end")
    if end_val is not None:
        try:
            end_t = parse_date_tuple(str(end_val))
        except ValueError as exc:
            errors.append(f"{path}.end: {exc}")
            return
        if end_t < start_t:
            errors.append(f"{path}: end date '{end_val}' precedes start date '{dates['start']}'.")


def _scan_strings(node: Any, path: str, errors: list[str]) -> None:
    if isinstance(node, str):
        for token in FORBIDDEN_SUBSTRINGS:
            if token in node:
                errors.append(f"{path}: contains forbidden token '{token}'.")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", node):
            url = match.group(1)
            if not (url.startswith("https://") or url.startswith("mailto:")):
                errors.append(f"{path}: link '{url}' must start with https:// or mailto:.")
    elif isinstance(node, dict):
        for k, v in node.items():
            _scan_strings(v, f"{path}.{k}", errors)
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _scan_strings(item, f"{path}[{idx}]", errors)


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    identity = profile.get("identity", {})
    if not identity.get("name"):
        errors.append("identity.name: missing.")
    _check_bilingual(identity.get("location"), "identity.location", errors)
    _check_bilingual(identity.get("academic_tagline"), "identity.academic_tagline", errors)
    for link_name, link in identity.get("links", {}).items():
        url = link.get("url", "")
        if not url.startswith("https://"):
            errors.append(f"identity.links.{link_name}.url: must start with https://.")

    for track in TRACKS:
        if track not in profile.get("variants", {}):
            errors.append(f"variants.{track}: missing.")
            continue
        _check_bilingual(profile.get("summary", {}).get(track), f"summary.{track}", errors)
        for idx, sec in enumerate(profile["variants"][track].get("sections", [])):
            if sec.get("key") not in SECTION_RENDERERS:
                errors.append(f"variants.{track}.sections[{idx}].key: unknown '{sec.get('key')}'.")
            _check_bilingual(sec.get("title"), f"variants.{track}.sections[{idx}].title", errors)
        for idx, skill in enumerate(profile.get("skills", {}).get(track, [])):
            _check_bilingual(skill.get("label"), f"skills.{track}[{idx}].label", errors)
            _check_bilingual(skill.get("items"), f"skills.{track}[{idx}].items", errors)

    for group, fields in (
        ("education", ("institution", "location", "degree", "bullets")),
        ("experience", ("role", "organization", "location", "bullets")),
        ("projects", ("title", "tech", "bullets")),
        ("activities", ("role", "organization", "location", "bullets")),
    ):
        seen_ids: set[str] = set()
        for entry in profile.get(group, []):
            eid = entry.get("id", "<missing-id>")
            if eid in seen_ids:
                errors.append(f"{group}.{eid}: duplicate id.")
            seen_ids.add(eid)
            variants = entry.get("variants", [])
            if not variants or any(v not in TRACKS for v in variants):
                errors.append(f"{group}.{eid}.variants: invalid '{variants}'.")
            _check_dates_node(entry.get("dates"), f"{group}.{eid}.dates", errors)
            url = entry.get("url")
            if url is not None and not str(url).startswith("https://"):
                errors.append(f"{group}.{eid}.url: must start with https://.")
            for field in fields:
                val = entry.get(field)
                if isinstance(val, dict) and any(t in val for t in TRACKS):
                    for track in variants:
                        _check_bilingual(val.get(track), f"{group}.{eid}.{field}.{track}", errors)
                else:
                    _check_bilingual(val, f"{group}.{eid}.{field}", errors)

    _scan_strings(profile, "profile", errors)
    return errors


def count_pdf_pages(pdf_path: Path) -> int:
    """Return page count of a PDF without external binaries (handles compressed ObjStm)."""
    data = pdf_path.read_bytes()
    blobs = [data]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.S):
        try:
            blobs.append(zlib.decompress(match.group(1)))
        except zlib.error:
            pass

    counts: list[int] = []
    for blob in blobs:
        counts.extend(
            int(m.group(1))
            for m in re.finditer(rb"/Type\s*/Pages\b[^>]{0,300}/Count\s+(\d+)", blob, flags=re.S)
        )
        counts.extend(
            int(m.group(1))
            for m in re.finditer(rb"/Count\s+(\d+)[^>]{0,300}/Type\s*/Pages\b", blob, flags=re.S)
        )
    if counts:
        return max(counts)

    pages = sum(len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", blob)) for blob in blobs)
    if pages:
        return pages
    raise ValueError(f"Could not determine page count for {pdf_path}")


def cmd_build() -> int:
    profile = load_profile()
    errors = validate_profile(profile)
    if errors:
        for err in errors:
            print(f"schema error: {err}", file=sys.stderr)
        return 1

    SRC_DIR.mkdir(parents=True, exist_ok=True)
    for track, lang, path in output_targets(profile):
        rendered = render_cv(profile, track, lang)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


def cmd_check() -> int:
    profile = load_profile()
    errors = validate_profile(profile)
    if errors:
        for err in errors:
            print(f"schema error: {err}", file=sys.stderr)
        return 1

    expected_names = {path.name for _, _, path in output_targets(profile)}
    actual_tex = {p.name for p in SRC_DIR.glob("*.tex")} if SRC_DIR.exists() else set()
    extra = sorted(actual_tex - expected_names)
    if extra:
        print(
            f"drift error: unexpected untracked .tex files in src/: {', '.join(extra)}",
            file=sys.stderr,
        )
        return 1

    drift_found = False
    for track, lang, path in output_targets(profile):
        first = render_cv(profile, track, lang)
        second = render_cv(profile, track, lang)
        if first != second:
            print(f"determinism error: {path.name} differed across two renders.", file=sys.stderr)
            return 1
        if not path.exists():
            print(f"drift error: missing generated file {path.relative_to(ROOT)}", file=sys.stderr)
            drift_found = True
            continue
        current = path.read_text(encoding="utf-8")
        if current != first:
            drift_found = True
            diff = "".join(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    first.splitlines(keepends=True),
                    fromfile=str(path.relative_to(ROOT)),
                    tofile=f"expected:{path.name}",
                    n=2,
                )
            )
            print(f"drift error: {path.relative_to(ROOT)} is out of sync with data/profile.yaml.", file=sys.stderr)
            print(diff, file=sys.stderr)

    if drift_found:
        print("Run `python3 scripts/cv.py build` to synchronize all 4 variants.", file=sys.stderr)
        return 1

    print("ok: data/profile.yaml is valid and all 4 LaTeX variants are byte-identical and in sync.")
    return 0


def find_missing_tex_packages(env: dict[str, str]) -> list[str]:
    kpsewhich = shutil.which("kpsewhich", path=env.get("PATH"))
    if not kpsewhich:
        return []
    missing: list[str] = []
    for filename, pkg in REQUIRED_TEX_PACKAGES:
        res = subprocess.run(
            [kpsewhich, filename],
            capture_output=True,
            text=True,
            env=env,
        )
        if res.returncode != 0 or not res.stdout.strip():
            missing.append(pkg)
    return missing


def cmd_compile() -> int:
    if cmd_check() != 0:
        return 1

    env = os.environ.copy()
    env["PATH"] = f"{env.get('PATH', '')}:/Library/TeX/texbin"
    pdflatex = shutil.which("pdflatex", path=env["PATH"])
    if not pdflatex:
        print("compile error: pdflatex not found in PATH or /Library/TeX/texbin.", file=sys.stderr)
        return 1

    missing = find_missing_tex_packages(env)
    if missing:
        pkgs = " ".join(missing)
        print(
            f"compile error: missing local TeX Live packages: {pkgs}\n"
            f"Install them once with:\n  sudo tlmgr install {pkgs}",
            file=sys.stderr,
        )
        return 1

    profile = load_profile()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs: list[Path] = []
    for _, _, tex_path in output_targets(profile):
        for _ in range(2):
            res = subprocess.run(
                [
                    pdflatex,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={OUTPUT_DIR}",
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            if res.returncode != 0:
                print(f"compile error: {tex_path.name} failed to compile.", file=sys.stderr)
                print("\n".join(res.stdout.splitlines()[-30:]), file=sys.stderr)
                return 1
        pdfs.append(OUTPUT_DIR / f"{tex_path.stem}.pdf")

    return check_pages_list(pdfs)


def check_pages_list(pdfs: list[Path]) -> int:
    failed = False
    for pdf in pdfs:
        if not pdf.exists():
            print(f"page check error: file not found: {pdf}", file=sys.stderr)
            failed = True
            continue
        pages = count_pdf_pages(pdf)
        if pages != 1:
            print(f"page check error: {pdf} has {pages} pages (expected exactly 1).", file=sys.stderr)
            failed = True
        else:
            print(f"ok: {pdf} (1 page)")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and validate synchronized CV variants.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Generate all 4 LaTeX variants from data/profile.yaml.")
    sub.add_parser("check", help="Validate schema, determinism, and zero drift with src/*.tex.")
    sub.add_parser("compile", help="Compile all 4 PDFs to output/ and enforce the 1-page limit.")
    cp = sub.add_parser("check-pages", help="Verify each listed PDF is exactly 1 page.")
    cp.add_argument("pdfs", nargs="+", type=Path)

    args = parser.parse_args(argv)
    if args.command == "build":
        return cmd_build()
    if args.command == "check":
        return cmd_check()
    if args.command == "compile":
        return cmd_compile()
    if args.command == "check-pages":
        return check_pages_list(args.pdfs)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
