import argparse
import os

from ky_voter_tracker import database as db
from ky_voter_tracker import downloader
from ky_voter_tracker import parser
from ky_voter_tracker import scraper

REG_FIELDS = {
    "month", "total", "democratic", "republican", "other",
    "independent", "libertarian", "green", "constitution", "reform",
    "socialist_workers", "kentucky_party", "male", "female", "source_file",
}

COUNTY_FIELDS = {
    "month", "county_code", "county_name", "precinct_count",
    "democratic", "republican", "other", "independent", "libertarian",
    "green", "constitution", "reform", "socialist_workers",
    "kentucky_party", "male", "female", "total", "source_file",
}

PRECINCT_FIELDS = {
    "month", "county_code", "county_name", "precinct", "c_s_ld_sc",
    "democratic", "republican", "other", "independent", "libertarian",
    "green", "constitution", "reform", "socialist_workers",
    "kentucky_party", "male", "female", "total", "source_file",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kentucky Voter Registration Tracker"
    )
    parser.add_argument("--scrape", action="store_true", help="Fetch download links from KY SBE site")
    parser.add_argument("--download", action="store_true", help="Download new XLS files")
    parser.add_argument("--parse", action="store_true", help="Parse downloaded XLS files into database")
    parser.add_argument("--download-pdf", action="store_true", help="Download new PDF files")
    parser.add_argument("--parse-pdf", action="store_true", help="Parse downloaded PDF files into database")
    parser.add_argument("--all", action="store_true", help="Run full pipeline (scrape + download + parse)")
    parser.add_argument("--refresh", action="store_true", help="Re-download and re-parse all files")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    conn = db.init_db()

    run_all = args.all or not (args.scrape or args.download or args.parse or args.download_pdf or args.parse_pdf)
    links = None

    if args.scrape or run_all:
        print("Scraping download links...")
        links = scraper.get_download_links()
        xls_count = sum(1 for link in links if link["file_type"] == "xls")
        print(f"  Found {len(links)} total links ({xls_count} XLS files)")

    if args.download or run_all:
        if links is None:
            links = scraper.get_download_links()
        xls_links = [link for link in links if link["file_type"] == "xls"]
        print(f"Downloading XLS files (force={args.refresh})...")
        new_files = downloader.download_files(conn, xls_links, force=args.refresh)
        print(f"  Downloaded {len(new_files)} files")

    if args.download_pdf:
        if links is None:
            links = scraper.get_download_links()
        pdf_links = [link for link in links if link["category"] in ("county", "district", "precinct")]
        print(f"Downloading PDF files (force={args.refresh})...")
        new_files = downloader.download_files(conn, pdf_links, force=args.refresh)
        print(f"  Downloaded {len(new_files)} files")

    if args.parse_pdf:
        if links is None:
            links = scraper.get_download_links()
        link_by_filename = {link["filename"]: link for link in links}

        if args.refresh:
            print("Resetting parse flags for refresh...")
            db.reset_parsed_flags(conn)

        unparsed = db.get_unparsed_files(conn)
        pdf_unparsed = [
            e for e in unparsed
            if link_by_filename.get(e["filename"], {}).get("file_type") == "pdf"
        ]
        if not pdf_unparsed:
            print("No PDF files to parse")
        else:
            rows_county_pdf = 0
            rows_precinct = 0
            for entry in pdf_unparsed:
                filename = entry["filename"]
                filepath = os.path.join(downloader.RAW_DIR, filename)
                if not os.path.exists(filepath):
                    continue

                link = link_by_filename.get(filename)
                if link is None or link["month"] is None:
                    continue

                cat = link.get("category")
                month = link["month"]
                print(f"  Parsing {filename} ({month}, {cat})...", end=" ")

                if cat == "county":
                    statewide, counties = parser.parse_county_pdf(filepath, month)
                    for c in counties:
                        co_kwargs = {k: v for k, v in c.items() if k in COUNTY_FIELDS}
                        db.insert_county_stats(conn, **co_kwargs)
                        rows_county_pdf += 1
                    if statewide is not None:
                        reg_kwargs = {k: v for k, v in statewide.items() if k in REG_FIELDS}
                        db.insert_registration(conn, **reg_kwargs)
                    print(f"{len(counties)} counties")
                elif cat == "precinct":
                    prec_rows = parser.parse_precinct_pdf(filepath, month)
                    for r in prec_rows:
                        pr_kwargs = {k: v for k, v in r.items() if k in PRECINCT_FIELDS}
                        db.insert_precinct_stats(conn, **pr_kwargs)
                        rows_precinct += 1
                    print(f"{len(prec_rows)} precincts")
                else:
                    print("skipped (not yet implemented)")

                db.mark_parsed(conn, link["url"])

            print(f"  Inserted {rows_county_pdf} county rows, {rows_precinct} precinct rows from PDFs")

    if args.parse or run_all:
        if links is None:
            links = scraper.get_download_links()
        link_by_filename = {link["filename"]: link for link in links}

        if args.refresh:
            print("Resetting parse flags for refresh...")
            db.reset_parsed_flags(conn)

        unparsed = db.get_unparsed_files(conn)
        if not unparsed:
            print("No files to parse")
        else:
            rows_reg = 0
            rows_county = 0
            for entry in unparsed:
                filename = entry["filename"]
                filepath = os.path.join(downloader.RAW_DIR, filename)
                if not os.path.exists(filepath):
                    continue

                link = link_by_filename.get(filename)
                if link is None or link["month"] is None:
                    continue
                if link.get("file_type") != "xls":
                    continue

                month = link["month"]
                print(f"  Parsing {filename} ({month})...", end=" ")
                statewide, counties = parser.parse_xls(filepath, month)

                reg_kwargs = {k: v for k, v in statewide.items() if k in REG_FIELDS}
                db.insert_registration(conn, **reg_kwargs)
                rows_reg += 1

                for c in counties:
                    co_kwargs = {k: v for k, v in c.items() if k in COUNTY_FIELDS}
                    db.insert_county_stats(conn, **co_kwargs)
                    rows_county += 1

                db.mark_parsed(conn, link["url"])
                print(f"{len(counties)} counties")

            print(f"  Inserted {rows_reg} registration rows, {rows_county} county rows")

    db_path = db.DB_PATH
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"Database size: {size:,} bytes ({size / 1024:.1f} KB)")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
