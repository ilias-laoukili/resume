"""Unit tests for the synchronized multi-variant CV generator and data."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import cv  # noqa: E402


class TestLatexConversion(unittest.TestCase):
    def test_escapes_special_characters_and_dashes(self) -> None:
        raw = "AI & ML: 30% gain, $100 #1 a_b — note – range"
        rendered = cv.to_latex(raw)
        self.assertEqual(
            rendered,
            r"AI \& ML: 30\% gain, \$100 \#1 a\_b --- note -- range",
        )

    def test_inline_markup_and_links(self) -> None:
        raw = "Built in **Rust** ([plekton](https://github.com/ilias-laoukili/plekton)) with *zero-copy* `PyO3`."
        rendered = cv.to_latex(raw)
        self.assertIn(r"\textbf{Rust}", rendered)
        self.assertIn(r"\href{https://github.com/ilias-laoukili/plekton}{\color{MidnightBlue}plekton}", rendered)
        self.assertIn(r"\textit{zero-copy}", rendered)
        self.assertIn(r"\texttt{PyO3}", rendered)

    def test_french_ligature_and_apostrophe(self) -> None:
        self.assertEqual(cv.to_latex("Mise en œuvre d’IA"), r"Mise en \oe{}uvre d'IA")


class TestDateFormatting(unittest.TestCase):
    def test_month_range_bilingual(self) -> None:
        dates = {"start": "2026-11", "end": None}
        self.assertEqual(cv.format_dates(dates, "en"), "Nov. 2026 -- Present")
        self.assertEqual(cv.format_dates(dates, "fr"), "Nov. 2026 -- Présent")

    def test_mixed_year_and_month(self) -> None:
        dates = {"start": "2023", "end": "2026-06"}
        self.assertEqual(cv.format_dates(dates, "en"), "2023 -- Jun. 2026")
        self.assertEqual(cv.format_dates(dates, "fr"), "2023 -- Juin 2026")

    def test_term_date(self) -> None:
        dates = {"start_term": {"en": "Fall 2026", "fr": "Automne 2026"}, "end": None}
        self.assertEqual(cv.format_dates(dates, "en"), "Fall 2026 -- Present")
        self.assertEqual(cv.format_dates(dates, "fr"), "Automne 2026 -- Présent")


class TestProfileAndSync(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = cv.load_profile()

    def test_profile_schema_is_valid(self) -> None:
        errors = cv.validate_profile(self.profile)
        self.assertEqual(errors, [], f"Validation errors: {errors}")

    def test_four_variants_are_deterministic_and_synced(self) -> None:
        targets = cv.output_targets(self.profile)
        self.assertEqual(len(targets), 4)
        for track, lang, path in targets:
            first = cv.render_cv(self.profile, track, lang)
            second = cv.render_cv(self.profile, track, lang)
            self.assertEqual(first, second, f"Non-deterministic output for {path.name}")
            self.assertTrue(path.exists(), f"Missing generated file {path}")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                first,
                f"{path.name} drifted from data/profile.yaml; run `python3 scripts/cv.py build`.",
            )

    def test_expected_content_and_no_stale_references(self) -> None:
        for track, lang, path in cv.output_targets(self.profile):
            content = path.read_text(encoding="utf-8")
            self.assertIn("Ministère de la Cybersécurité et du Numérique", content)
            self.assertIn("plekton", content)
            self.assertNotIn("synth-graph-rs", content)
            self.assertNotIn("Manuscript in preparation", content)
            self.assertNotIn("Manuscrit en préparation", content)
            if lang == "fr":
                self.assertIn(r"\usepackage[french]{babel}", content)
                self.assertIn(r"\frenchsetup{StandardLists=true}", content)
            else:
                self.assertIn(r"\usepackage[english]{babel}", content)

    def test_pdf_page_counter_on_minimal_and_compressed_pdf(self) -> None:
        sample = b"%PDF-1.5\n1 0 obj\n<< /Type /Pages /Count 1 /Kids [2 0 R] >>\nendobj\n"
        compressed_obj = zlib.compress(b"<< /Type /Pages /Count 2 /Kids [2 0 R 3 0 R] >>")
        compressed_pdf = b"%PDF-1.5\n1 0 obj\nstream\n" + compressed_obj + b"\nendstream\nendobj\n"
        with tempfile.TemporaryDirectory() as tmp:
            pdf1 = Path(tmp) / "sample1.pdf"
            pdf1.write_bytes(sample)
            self.assertEqual(cv.count_pdf_pages(pdf1), 1)
            pdf2 = Path(tmp) / "sample2.pdf"
            pdf2.write_bytes(compressed_pdf)
            self.assertEqual(cv.count_pdf_pages(pdf2), 2)


if __name__ == "__main__":
    unittest.main()
