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

- **Stop after each step** for manual verification before proceeding to the next.
- Do not batch multiple steps in one session without explicit user approval.
- After completing a step, present a summary of what was done and the options for what to do next. Let the user choose.

## Implementation Status

- Step 1 ✅ — Scaffold complete (pyproject.toml, .gitignore, package dirs)
- Step 2 ✅ — Scraper complete (437 links parsed, 21 tests)
- Step 3 ✅ — Database Layer (registrations + county_stats + downloads_log, 14 tests)
- Step 4 ✅ — Downloader (incremental, retry 3x with backoff, 6 tests)
- Step 5 ✅ — XLS Parser (county + statewide extraction, 11 tests + real-file integration)
- Step 6 ✅ — Main Pipeline (argparse CLI, scrape → download → parse → store)
- Step 7 🔲 — Dashboard shell (intentionally left unmarked; created out of order — needs UX review)
- Step 8–10 🔲 — Dashboard refinements
- Step 11–16 🔲 — PDF Parsing & Extensions
- Step 17–19 🔲 — Hardening

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
