# Kentucky Voter Registration Tracker

An interactive data pipeline and dashboard for exploring Kentucky voter registration statistics from January 2017 through the present.

**Data source:** [Kentucky State Board of Elections — Registration Statistics](https://elect.ky.gov/Resources/Pages/Registration-Statistics.aspx)

## Features

- **Incremental downloads** — Downloads only new files on each run; never re-downloads cached data.
- **SQLite-backed storage** — All parsed data lives in a single, portable database file.
- **Interactive dashboard** — Powered by Streamlit and Plotly; filter by date range, geographic level, county, district, and party.
- **Four data levels** (planned):
  - Overall state-wide registration
  - County-level breakdown
  - Precinct-level breakdown
  - Congressional, Senate, House, and Supreme Court district breakdown

## Project Structure

```
ky_voter_tracker/
├── main.py               # CLI entry point
├── scraper.py            # Scrapes the KY SBE page for download links
├── downloader.py         # Incremental file downloader
├── parser.py             # XLS/PDF → pandas DataFrames
├── database.py           # SQLite schema and queries
├── dashboard.py          # Streamlit interactive dashboard
├── data/
│   ├── raw/              # Downloaded source files (git-ignored)
│   └── ky_voter.db       # Normalized SQLite database (git-ignored)
├── output/               # Exported graphs (git-ignored)
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_PLAN.md
└── TODO.md
```

## Quick Start

```bash
# Install dependencies (from repo root)
pip install -e ".[dev]"

# Run the full pipeline (scrape → download → parse → store)
python3 -m ky_voter_tracker.main

# Launch the interactive dashboard
streamlit run ky_voter_tracker/dashboard.py
```

## Requirements

- Python 3.10+
- Dependencies listed in `pyproject.toml`
- ~500 MB disk space for downloaded files and database (approximate)

## License

MIT
