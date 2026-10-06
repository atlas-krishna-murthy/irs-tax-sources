# irs-tax-sources

The IRS source library and the tax knowledge-base schema, kept out of `maven-backend`.

- `sources/` — every IRS form, instruction and publication the knowledge base cites, per tax
  year (`2025/`, `2024/`): the PDF, its `pdftotext -layout` text, and `manifest.json`
  (url, revision, sha256). See `sources/README.md`. Read citations here, never off irs.gov.
- `schema/` — a **copy** of `maven-backend/taxation/knowledge/schema` as of commit `a6a615dfd`
  (2026-10-04). The copy in `maven-backend` is still the one its build reads.

Commands in `sources/fetch.py` still give `maven-backend` paths
(`docs/irs-source-of-truth/sources/`); here it is `sources/`.
