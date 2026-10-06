"""One local library of the IRS sources the tax knowledge base cites.

Every form, instruction and publication the schema, the leadsheet mapping and
the rule research cite lives under ``sources/<tax year>/``, beside its extracted
text, so nobody (person or agent) has to go back to irs.gov to read a citation.

    python3 docs/irs-source-of-truth/sources/fetch.py            # fetch what is missing
    python3 docs/irs-source-of-truth/sources/fetch.py --stems stems.txt
    python3 docs/irs-source-of-truth/sources/fetch.py --scan taxation/knowledge/schema docs

**Which revision is the tax year's.** An annual form is ``irs-prior/<stem>--<year>.pdf``.
A continuous-use form (1099-DIV, 1099-INT, 1099-K …) has no copy for every year,
so the newest ``irs-prior`` copy at or before the year is the one in force.
``irs-pdf/`` is tried LAST and kept only when the revision it prints is not
after the tax year, because ``irs-pdf/`` serves NEXT year's information returns
(spec 067, docs/TAXATION_LEADSHEET_AUDIT.md §6). What was fetched from where,
and the revision line the PDF prints, is in ``manifest.json``.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = "https://www.irs.gov/pub/irs-prior/{stem}--{year}.pdf"
CURRENT = "https://www.irs.gov/pub/irs-pdf/{stem}.pdf"
#: How far back a continuous-use revision is looked for.
OLDEST = 2016
_AGENT = {"User-Agent": "Mozilla/5.0 (maven-backend irs source library)"}


class Library:
    """The directory for one tax year, and the manifest describing it."""

    def __init__(self, year: int) -> None:
        self.year = year
        self.root = HERE / str(year)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.manifest: dict[str, dict] = (
            json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}
        )

    def has(self, stem: str) -> bool:
        return stem in self.manifest and (self.root / f"{stem}.pdf").exists()

    def record(self, stem: str, url: str, data: bytes, how: str) -> None:
        pdf = self.root / f"{stem}.pdf"
        pdf.write_bytes(data)
        text = Text.of(pdf)
        self.manifest[stem] = {
            "url": url,
            "how": how,
            "revision_printed": Text.revision(text),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "fetched": dt.date.today().isoformat(),
        }

    def save(self) -> None:
        self.manifest_path.write_text(
            json.dumps(dict(sorted(self.manifest.items())), indent=1) + "\n"
        )


class Text:
    """pdftotext -layout beside every PDF; the text is what gets grepped and quoted."""

    @staticmethod
    def of(pdf: Path) -> str:
        out = pdf.with_suffix(".txt")
        subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(out)], check=False, capture_output=True
        )
        Text.reading_order(pdf)
        return out.read_text(errors="replace") if out.exists() else ""

    @staticmethod
    def reading_order(pdf: Path) -> Path:
        """``<stem>.read.txt`` — the same PDF in READING order, beside the -layout text.

        Each rendering breaks a different quotation. ``-layout`` keeps a line number
        out of the middle of its caption, and interleaves a two-column page line by
        line, so a sentence that wraps inside a column reads as two halves with the
        other column between them. Reading order puts the column back together.
        A citation is verified against either (`verify_citations.py`).
        """
        out = pdf.with_name(f"{pdf.stem}.read.txt")
        subprocess.run(["pdftotext", str(pdf), str(out)], check=False, capture_output=True)
        return out

    @staticmethod
    def revision(text: str) -> str | None:
        head = text[:6000]
        for pattern in (
            r"\(Rev\.\s*[A-Za-z]+\s*\d{4}\)",
            r"Rev\.\s*[A-Za-z]+\s*\d{4}",
            r"(?<![-\d])(20[12]\d)(?!\d)",
        ):
            match = re.search(pattern, head)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def printed_year(revision: str | None) -> int | None:
        found = re.findall(r"20\d\d", revision or "")
        return int(found[-1]) if found else None


class Fetcher:
    """Finds the revision of a stem that is in force for the library's year."""

    def __init__(self, library: Library) -> None:
        self.library = library

    def get(self, url: str) -> bytes | None:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=_AGENT), timeout=60
            ) as r:
                data = r.read()
            return data if data[:5] == b"%PDF-" else None
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return None

    def fetch(self, stem: str) -> tuple[str, str | None, bytes | None, str]:
        year = self.library.year
        url = PRIOR.format(stem=stem, year=year)
        data = self.get(url)
        if data:
            return stem, url, data, "irs-prior"
        # A CONTINUOUS-USE revision. `irs-prior` holds only the SUPERSEDED ones,
        # so the revision in force may exist only on `irs-pdf` — which also
        # serves next year's information returns. Take the current copy when
        # the revision it prints is not after the tax year; otherwise the
        # newest archived one at or before it.
        current_url = CURRENT.format(stem=stem)
        current = self.get(current_url)
        if current:
            printed = Text.printed_year(Text.revision(_first_pages(current)))
            if printed is not None and printed <= year:
                return stem, current_url, current, f"irs-pdf, continuous use (prints {printed})"
        for older in range(year - 1, OLDEST - 1, -1):
            url = PRIOR.format(stem=stem, year=older)
            data = self.get(url)
            if data:
                return stem, url, data, f"irs-prior, continuous use ({older})"
        if current:
            return (
                stem,
                current_url,
                current,
                "irs-pdf, revision after the tax year or unprinted — CHECK",
            )
        return stem, None, None, "not found"


def _first_pages(data: bytes) -> str:
    result = subprocess.run(
        ["pdftotext", "-l", "2", "-layout", "-", "-"], input=data, capture_output=True
    )
    return result.stdout.decode(errors="replace")


def stems_from(paths: list[Path]) -> set[str]:
    """Every IRS PDF stem named by a URL in these files."""
    found: set[str] = set()
    for path in paths:
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for f in files:
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            for stem in re.findall(
                r"irs\.gov/pub/irs-(?:prior|pdf)/([a-z0-9]+?)(?:--\d{4})?\.pdf", text
            ):
                found.add(stem)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--stems", type=Path, help="a file of stems, one per line")
    parser.add_argument(
        "--scan", type=Path, nargs="*", default=[], help="files/dirs whose irs.gov URLs name stems"
    )
    parser.add_argument(
        "--reading-order", action="store_true", help="(re)write <stem>.read.txt for every PDF held"
    )
    args = parser.parse_args()

    library = Library(args.year)
    if args.reading_order:
        pdfs = sorted(library.root.glob("*.pdf"))
        for pdf in pdfs:
            Text.reading_order(pdf)
        print(f"{len(pdfs)} PDFs rendered in reading order")
        return 0
    stems = stems_from(args.scan)
    if args.stems:
        stems |= {s.strip() for s in args.stems.read_text().split() if s.strip()}
    wanted = sorted(s for s in stems if not library.has(s))
    fetcher = Fetcher(library)
    missing = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for stem, url, data, how in pool.map(fetcher.fetch, wanted):
            if data:
                library.record(stem, url, data, how)
                print(f"ok   {stem:14} {how}")
            else:
                missing.append(stem)
    library.save()
    (library.root / "not-found.txt").write_text("\n".join(missing) + ("\n" if missing else ""))
    print(f"{len(library.manifest)} in library, {len(missing)} not found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
