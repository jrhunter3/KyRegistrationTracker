# AGENTS.md — Ky Voter Tracker

## Project Overview

Python pipeline + Streamlit dashboard for Kentucky voter registration statistics (2017–present).
Data source: https://elect.ky.gov/Resources/Pages/Registration-Statistics.aspx

## Project Structure

```
ky_voter_tracker/          # Main package
├── __init__.py
├── main.py                # CLI entry point (argparse)
├── scraper.py             # get_download_links() → list[dict]
├── downloader.py          # incremental file downloader
├── parser.py              # XLS → pandas DataFrames
├── database.py            # SQLite operations
├── dashboard.py           # Streamlit app
├── tests/
│   ├── __init__.py
│   └── test_scraper.py    # 21 tests for scraper module
data/
├── raw/                   # downloaded source files (git-ignored)
└── ky_voter.db            # SQLite database (git-ignored)
output/                    # exported graphs (git-ignored)
```

## Architecture & Data Flow

```
scraper.py → downloader.py → parser.py → database.py → dashboard.py
```

- `scraper.py` fetches the KY SBE page and extracts all download links
- `downloader.py` downloads new files only (checks `downloads_log` in SQLite)
- `parser.py` reads `.xls` files with `xlrd`, returns pandas DataFrames
- `database.py` manages SQLite with upserts and filtered queries
- `dashboard.py` is a Streamlit + Plotly interactive dashboard

## Database Schema (SQLite)

**Tables:** `registrations`, `county_stats`, `downloads_log` (Phase 2 adds `district_stats`, `precinct_stats`)

**registrations** — Overall state-wide totals per month (extracted from XLS "Statewide totals" row).  
Columns: month, total, democratic, republican, other, independent, libertarian, green, constitution, reform, socialist_workers, kentucky_party, male, female, source_file.  
UNIQUE(month).

**county_stats** — Per-county per-month data (from XLS files).  
Columns: month, county_code (3-digit), county_name, precinct_count, all party columns, male, female, total, source_file.  
UNIQUE(month, county_code).

**downloads_log** — Tracks download and parse status for incremental updates.  
Columns: url, filename, downloaded_at, file_size, status (pending/downloaded/parsed).

## Key Conventions

### Code Style
- **No comments in code** unless absolutely necessary for clarity
- No docstrings on private functions (prefixed with `_`)
- Public functions get brief docstrings
- Type hints on all function signatures
- Use `link` not `l` as loop variable (ruff E741)
- Maximum line length: default (ruff default of 88)

### Testing
- Framework: `pytest`
- HTTP mocking: `unittest.mock.patch` on `ky_voter_tracker.scraper.requests.get`
- Fixtures: inline (no conftest.py)
- Naming: `TestClass` + `test_method`
- Run tests: `python3 -m pytest ky_voter_tracker/tests/ -v`
- Coverage target: >80% on non-dashboard modules

### Linting & Formatting
- Linter: `ruff`
- Run: `ruff check .`
- Fix: `ruff check --fix .`

### Imports
- Standard library first, then third-party, then local
- One import group per section, no blank lines inside groups

### Error Handling
- Network errors: retry 3x with exponential backoff
- Corrupt XLS: log filename and skip, do not halt
- SQLite: use parameterized queries everywhere, never f-strings

## How to Run

```bash
# Full pipeline
python3 -m ky_voter_tracker.main

# With flags
python3 -m ky_voter_tracker.main --scrape --download --parse

# Dashboard
streamlit run ky_voter_tracker/dashboard.py
```

## Work Rhythm

1. **Plan together** — I help identify and lay out possible changes.
2. **Propose a shortlist** — I recommend 2-3 concrete changes to tackle next.
3. **You approve** — You pick which ones to proceed with.
4. **I implement** — I execute the approved changes.
5. **You review** — You assess what was done.
6. **Pass → repeat from step 1.** Reject → we undo or fix before continuing.

## Implementation Status

- Step 1 ✅ — Scaffold complete (pyproject.toml, .gitignore, package dirs)
- Step 2 ✅ — Scraper complete (437 links parsed, 21 tests)
- Step 3 ✅ — Database Layer (registrations + county_stats + downloads_log, 14 tests)
- Step 4 ✅ — Downloader (incremental, retry 3x with backoff, 6 tests)
- Step 5 ✅ — XLS Parser (county + statewide extraction, 11 tests + real-file integration)
- Step 6 ✅ — Main Pipeline (argparse CLI, scrape → download → parse → store)
- Step 7  🟡 — Dashboard shell (built, needs UX review — user wants dynamic/selectable approach)
- Step 8a ✅ — Sidebar party multi-select + view mode toggle (Raw/Share %)
- Step 8b 🔲 — Dynamic metric cards (show all selected parties, month-over-month delta)
- Step 9a ✅ — Party Comparison tab (overlaid lines / stacked area / stacked area %, Major vs Alternative grouping)
- Step 9b ✅ — Month-over-month growth rate chart per party
- Step 10a ✅ — County Comparison tab (party selection from sidebar, % of county total toggle)
- Step 10b 🔲 — Layout polish (export buttons, data table, responsive tuning)
- Step YoY 🔲 — Year-over-year comparison chart (user showed interest after MoM growth chart)
- Step 11 ✅ — County PDF Parser (110 PDFs → 12,120 rows, line-based text extraction)
- Step 12 🔲 — District PDF Parsing
- Step 13 ✅ — Precinct PDF Parser (110 PDFs → 359,685 rows, 12/13-col format, span-line C-S-LD-SC)
- Step 14–16 🔲 — Dashboard extensions (choropleth, district views, precinct views)
- Step 17–19 🔲 — Hardening (--from/--until flags, coverage, CI)

See `IMPLEMENTATION_PLAN.md` and `TODO.md` for full details.

## Phase 2 (Deferred)
PDF parsing is planned for Phase 2. Tools: `camelot` / `pdfplumber`.
Dashboard county/district/precinct views also deferred to Phase 2.

### Phase 2 Schema Notes
- **precinct_stats**: Includes `c_s_ld_sc` column for the composite Congressional-Senate-LD-SupremeCourt code found in precinct PDFs.
- **district_stats**: Single normalized table with `district_type` column (congressional/senate/house/supreme_court) rather than four separate tables.
- Both tables mirror the full party + gender column set from `county_stats`.

## Environment
- Python 3.10+
- Dependencies in `pyproject.toml` (install: `pip install -e ".[dev]"`)
- No Docker, no external services, no secrets

---

## Session Context (2026-05-25) — Session 3

### What was completed this session
- **Step 17 hardening:** Added `--from`/`--until` CLI flags (`_filter_links_by_month()` in `main.py`). Filters apply to scrape, download, and parse phases. Works with `--refresh` — only resets parsed flags for in-range files.
- **`reset_parsed_flags_for_urls()`** in `database.py`: selectively resets parsed flags for given URL list using parameterized `IN` clause.
- **14 new tests:** 7 for `_filter_links_by_month`, 4 for `_parse_args`, 3 for `reset_parsed_flags_for_urls`. Total: 105 tests.

### Files changed
- `ky_voter_tracker/main.py` — `--from`/`--until` args, `_filter_links_by_month()`, conditional `reset_parsed_flags` / `reset_parsed_flags_for_urls` per phase, `_parse_args` accepts optional argv for testing
- `ky_voter_tracker/database.py` — `reset_parsed_flags_for_urls()`
- `ky_voter_tracker/tests/test_main.py` — new file: `TestFilterLinksByMonth` (7 tests), `TestParseArgs` (4 tests)
- `ky_voter_tracker/tests/test_database.py` — `TestResetParsedFlagsForUrls` (3 tests)
- `.gitignore` — already updated in session 2
- `AGENTS.md`, `TODO.md` — session tracking

### Known issues
- District 093 in 2022-03 house section was genuinely missing from the source PDF (KY SBE generation error), not a pdfplumber bug. Affects ~0 voters in that specific month.
- Senior citizen house districts (2-digit numbers like `35`, `17`) preserved alongside standard zero-padded counterparts (`035`, `017`) — 5 such rows across all months.
- `scraper.py` retry edge cases (all-retries-fail path, no-extension filename) not covered in tests.

### Next steps (choose one)
1. **Dashboard extensions:** YoY comparison chart, metric cards with MoM delta, choropleth map
2. **Step 14:** County dashboard views (choropleth map, county-level MoM growth)
3. **Step 18:** CI config (GitHub Actions)
