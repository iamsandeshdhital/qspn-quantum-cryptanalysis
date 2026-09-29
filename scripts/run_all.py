#!/usr/bin/env python
"""One command for the whole deliverable: experiments, figures, report macros, PDF.

    python scripts/run_all.py            # full study (~40 min), then build the PDF
    python scripts/run_all.py --quick    # fast end-to-end check (~4 min)
    python scripts/run_all.py --no-pdf   # skip LaTeX (e.g. no TeX installed)

Each stage is skipped gracefully if its tooling is missing, and a non-zero exit
code is returned only when a stage that *should* have worked failed -- so this
is safe to wire into CI.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "report"


def banner(text: str) -> None:
    print()
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


def run(command: list[str], cwd: Path | None = None) -> int:
    print(f"  $ {' '.join(command)}")
    return subprocess.call(command, cwd=cwd)


def build_pdf() -> int:
    """Run the pdflatex/bibtex/pdflatex/pdflatex cycle.

    Three pdflatex passes are needed, not one: the first writes the .aux file,
    bibtex turns that into .bbl, and the remaining passes resolve citations and
    then the cross-references and table of contents that shift once the
    bibliography changes the pagination.
    """
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        print("  pdflatex not found -- skipping PDF build.")
        print("  Install TeX Live or MiKTeX, then: python scripts/run_all.py --pdf-only")
        return 0

    bibtex = shutil.which("bibtex")
    steps: list[list[str]] = [[pdflatex, "-interaction=nonstopmode", "report.tex"]]
    if bibtex:
        steps.append([bibtex, "report"])
    else:
        print("  bibtex not found -- citations will render as [?].")
    steps.append([pdflatex, "-interaction=nonstopmode", "report.tex"])
    steps.append([pdflatex, "-interaction=nonstopmode", "report.tex"])

    for step in steps:
        # pdflatex returns non-zero for recoverable warnings, so the real check
        # is whether a PDF was produced.
        run(step, cwd=REPORT_DIR)

    pdf = REPORT_DIR / "report.pdf"
    if not pdf.exists():
        print("  ERROR: no PDF produced. See docs/report/report.log")
        return 1
    print(f"  PDF: {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="fast end-to-end check")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--no-pdf", action="store_true", help="skip the LaTeX build")
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help="rebuild macros and PDF from existing results, without simulating",
    )
    args = parser.parse_args(argv)

    started = time.time()

    if not args.pdf_only:
        banner("1/3  Running experiments")
        command = [sys.executable, "-m", "qspn.cli", "--shots", str(args.shots)]
        if args.quick:
            command.append("--quick")
        if (code := run(command, cwd=ROOT)):
            print("experiments failed")
            return code
    else:
        banner("1/3  Skipping experiments (--pdf-only)")

    banner("2/3  Generating report macros and tables from the saved records")
    if (code := run([sys.executable, str(ROOT / "scripts" / "make_report_macros.py")],
                    cwd=ROOT)):
        print("macro generation failed")
        return code

    if args.no_pdf:
        banner("3/3  Skipping PDF build (--no-pdf)")
    else:
        banner("3/3  Building the LaTeX report")
        if (code := build_pdf()):
            return code

    elapsed = time.time() - started
    banner(f"Done in {elapsed / 60:.1f} min")
    print(f"  results  : {ROOT / 'results'}")
    print(f"  summary  : {ROOT / 'results' / 'summary.txt'}")
    print(f"  figures  : {ROOT / 'results' / 'figures'}")
    print(f"  report   : {REPORT_DIR / 'report.pdf'}")
    print(f"  narrative: {ROOT / 'docs' / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
