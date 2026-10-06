# IRS source library

Every IRS form, instruction and publication the tax knowledge base cites, for one tax year,
downloaded once so nobody — a person or an agent — reads a citation off irs.gov again.

```
sources/
  fetch.py          # fetch what is missing; records url + revision + sha256
  2025/
    manifest.json   # stem -> {url, how, revision_printed, sha256, bytes, fetched}
    not-found.txt   # stems asked for that the IRS does not publish
    f1040.pdf  f1040.txt     # the PDF and its `pdftotext -layout` text
    i1099r.pdf i1099r.txt
    p502.pdf   p502.txt
    ...
```

**Read the `.txt`, quote from it, cite the `url` in `manifest.json`.** The stem is the IRS's own:
`f` form, `i` instructions, `p` publication; `f1040s1` is Schedule 1, `f1065sk1` is Schedule K-1
(Form 1065), `f1099msc` is 1099-MISC, `f1040s8` is Schedule 8812.

## Which revision is in the library

- **Annual forms**: `irs-prior/<stem>--2025.pdf`, exactly the tax year.
- **Continuous-use forms** (1099-DIV, 1099-INT, 4852, 7203 …): the revision in force for 2025.
  `irs-prior` keeps only SUPERSEDED revisions, so the current one may exist only on `irs-pdf/`;
  it is taken from there only when the revision it prints is not after 2025. Otherwise the newest
  `irs-prior` copy at or before 2025.
- **Never cite `irs-pdf/` for an information return without reading its revision line** —
  it serves NEXT year's forms (the 2026 1099-K, W-2G and 1099-G are there today).
  `manifest.json` `how` says which rule picked each file.

## What is in it

1. Every URL cited by the schema, the leadsheet mapping and the rule research.
2. **The forms that carry a figure to Form 1040**: the 2025 Form 1040 and its schedules, then every
   form a face names as a source, repeated until nothing new appears (business-entity, payroll,
   excise and estate returns excluded), plus each one's instructions.
3. Every recipient information return an individual can receive (W-2/W-2G/W-2c, the 1099, 1098,
   5498 and 1095 families, 3921/3922, 1097-BTC, 1042-S, 8805, 8288-A, 2439, K-1s, K-3).

SSA-1099 and RRB-1099/-R are issued by SSA / the RRB and have no irs.gov PDF; Publication 915
reproduces the SSA-1099 specimen.

## Adding a source

```
python3 docs/irs-source-of-truth/sources/fetch.py --stems <file of stems>
python3 docs/irs-source-of-truth/sources/fetch.py --scan taxation/knowledge/schema docs
```

For a new tax year, pass `--year 2026`; each year is its own directory and never overwrites another.

## Tracking — DECISION PENDING (spec 080 T003)

The library is 226 MB, almost all of it PDF. **Recommended:** track every `*.txt`, `manifest.json`,
`not-found.txt` and `fetch.py`, and gitignore `sources/**/*.pdf`. The `.txt` is what a citation is
verified against (`verify_citations.py`), and `fetch.py` re-creates any PDF from `manifest.json`,
whose `sha256` proves the re-fetched copy is the one that was read.

**This is the requester's call and `.gitignore` is NOT edited until it is answered** — `.gitignore`
is repo-wide. Until then the library is untracked and exists on this disk only.
