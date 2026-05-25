import sqlite3
from typing import Optional

DB_PATH = "data/ky_voter.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT    NOT NULL,
    total           INTEGER NOT NULL,
    democratic      INTEGER NOT NULL,
    republican      INTEGER NOT NULL,
    other           INTEGER NOT NULL,
    independent     INTEGER NOT NULL,
    libertarian     INTEGER NOT NULL,
    green           INTEGER NOT NULL,
    constitution    INTEGER NOT NULL,
    reform          INTEGER NOT NULL,
    socialist_workers INTEGER NOT NULL,
    kentucky_party  INTEGER NOT NULL DEFAULT 0,
    male            INTEGER NOT NULL,
    female          INTEGER NOT NULL,
    source_file     TEXT    NOT NULL,
    UNIQUE(month)
);

CREATE TABLE IF NOT EXISTS county_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT    NOT NULL,
    county_code     TEXT    NOT NULL,
    county_name     TEXT    NOT NULL,
    precinct_count  INTEGER NOT NULL,
    democratic      INTEGER NOT NULL,
    republican      INTEGER NOT NULL,
    other           INTEGER NOT NULL,
    independent     INTEGER NOT NULL,
    libertarian     INTEGER NOT NULL,
    green           INTEGER NOT NULL,
    constitution    INTEGER NOT NULL,
    reform          INTEGER NOT NULL,
    socialist_workers INTEGER NOT NULL,
    kentucky_party  INTEGER NOT NULL DEFAULT 0,
    male            INTEGER NOT NULL,
    female          INTEGER NOT NULL,
    total           INTEGER NOT NULL,
    source_file     TEXT    NOT NULL,
    UNIQUE(month, county_code)
);

CREATE TABLE IF NOT EXISTS precinct_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT    NOT NULL,
    county_code     TEXT    NOT NULL,
    county_name     TEXT    NOT NULL,
    precinct        TEXT    NOT NULL,
    c_s_ld_sc       TEXT    NOT NULL,
    democratic      INTEGER NOT NULL,
    republican      INTEGER NOT NULL,
    other           INTEGER NOT NULL,
    independent     INTEGER NOT NULL,
    libertarian     INTEGER NOT NULL,
    green           INTEGER NOT NULL,
    constitution    INTEGER NOT NULL,
    reform          INTEGER NOT NULL,
    socialist_workers INTEGER NOT NULL,
    kentucky_party  INTEGER NOT NULL DEFAULT 0,
    male            INTEGER NOT NULL,
    female          INTEGER NOT NULL,
    total           INTEGER NOT NULL,
    source_file     TEXT    NOT NULL,
    UNIQUE(month, county_code, precinct)
);

CREATE TABLE IF NOT EXISTS district_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT    NOT NULL,
    district_type   TEXT    NOT NULL,
    district_number TEXT    NOT NULL,
    democratic      INTEGER NOT NULL,
    republican      INTEGER NOT NULL,
    other           INTEGER NOT NULL,
    independent     INTEGER NOT NULL,
    libertarian     INTEGER NOT NULL,
    green           INTEGER NOT NULL,
    constitution    INTEGER NOT NULL,
    reform          INTEGER NOT NULL,
    socialist_workers INTEGER NOT NULL,
    kentucky_party  INTEGER NOT NULL DEFAULT 0,
    male            INTEGER NOT NULL,
    female          INTEGER NOT NULL,
    total           INTEGER NOT NULL,
    source_file     TEXT    NOT NULL,
    UNIQUE(month, district_type, district_number)
);

CREATE TABLE IF NOT EXISTS downloads_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,
    filename      TEXT    NOT NULL,
    downloaded_at TEXT    NOT NULL DEFAULT (datetime('now')),
    file_size     INTEGER,
    status        TEXT    NOT NULL DEFAULT 'pending',
    parsed        INTEGER NOT NULL DEFAULT 0
);
"""


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def insert_registration(
    conn: sqlite3.Connection,
    month: str,
    total: int,
    democratic: int,
    republican: int,
    other: int,
    independent: int,
    libertarian: int,
    green: int,
    constitution: int,
    reform: int,
    socialist_workers: int,
    kentucky_party: int,
    male: int,
    female: int,
    source_file: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO registrations
           (month, total, democratic, republican, other, independent,
            libertarian, green, constitution, reform, socialist_workers,
            kentucky_party, male, female, source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (month, total, democratic, republican, other, independent,
         libertarian, green, constitution, reform, socialist_workers,
         kentucky_party, male, female, source_file),
    )
    conn.commit()


def get_registrations(
    conn: sqlite3.Connection,
    from_month: Optional[str] = None,
    until_month: Optional[str] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM registrations"
    params: list[str] = []
    conditions: list[str] = []

    if from_month is not None:
        conditions.append("month >= ?")
        params.append(from_month)
    if until_month is not None:
        conditions.append("month <= ?")
        params.append(until_month)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY month ASC"
    return conn.execute(query, params).fetchall()


def insert_county_stats(
    conn: sqlite3.Connection,
    month: str,
    county_code: str,
    county_name: str,
    precinct_count: int,
    democratic: int,
    republican: int,
    other: int,
    independent: int,
    libertarian: int,
    green: int,
    constitution: int,
    reform: int,
    socialist_workers: int,
    kentucky_party: int,
    male: int,
    female: int,
    total: int,
    source_file: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO county_stats
           (month, county_code, county_name, precinct_count,
            democratic, republican, other, independent, libertarian,
            green, constitution, reform, socialist_workers, kentucky_party,
            male, female, total, source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (month, county_code, county_name, precinct_count,
         democratic, republican, other, independent, libertarian,
         green, constitution, reform, socialist_workers, kentucky_party,
         male, female, total, source_file),
    )
    conn.commit()


def get_county_stats(
    conn: sqlite3.Connection,
    from_month: Optional[str] = None,
    until_month: Optional[str] = None,
    county_code: Optional[str] = None,
    county_name: Optional[str] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM county_stats"
    params: list[str] = []
    conditions: list[str] = []

    if from_month is not None:
        conditions.append("month >= ?")
        params.append(from_month)
    if until_month is not None:
        conditions.append("month <= ?")
        params.append(until_month)
    if county_code is not None:
        conditions.append("county_code = ?")
        params.append(county_code)
    if county_name is not None:
        conditions.append("county_name = ?")
        params.append(county_name)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY month ASC, county_code ASC"
    return conn.execute(query, params).fetchall()


def delete_precinct_stats_by_month(conn: sqlite3.Connection, month: str) -> None:
    conn.execute(
        "DELETE FROM precinct_stats WHERE month = ?",
        (month,),
    )
    conn.commit()


def insert_precinct_stats(
    conn: sqlite3.Connection,
    month: str,
    county_code: str,
    county_name: str,
    precinct: str,
    c_s_ld_sc: str,
    democratic: int,
    republican: int,
    other: int,
    independent: int,
    libertarian: int,
    green: int,
    constitution: int,
    reform: int,
    socialist_workers: int,
    kentucky_party: int,
    male: int,
    female: int,
    total: int,
    source_file: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO precinct_stats
           (month, county_code, county_name, precinct, c_s_ld_sc,
            democratic, republican, other, independent, libertarian,
            green, constitution, reform, socialist_workers, kentucky_party,
            male, female, total, source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (month, county_code, county_name, precinct, c_s_ld_sc,
         democratic, republican, other, independent, libertarian,
         green, constitution, reform, socialist_workers, kentucky_party,
         male, female, total, source_file),
    )
    conn.commit()


def get_precinct_stats(
    conn: sqlite3.Connection,
    from_month: Optional[str] = None,
    until_month: Optional[str] = None,
    county_code: Optional[str] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM precinct_stats"
    params: list[str] = []
    conditions: list[str] = []

    if from_month is not None:
        conditions.append("month >= ?")
        params.append(from_month)
    if until_month is not None:
        conditions.append("month <= ?")
        params.append(until_month)
    if county_code is not None:
        conditions.append("county_code = ?")
        params.append(county_code)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY month ASC, county_code ASC, precinct ASC"
    return conn.execute(query, params).fetchall()


def delete_district_stats_by_month(conn: sqlite3.Connection, month: str) -> None:
    conn.execute(
        "DELETE FROM district_stats WHERE month = ?",
        (month,),
    )
    conn.commit()


def insert_district_stats(
    conn: sqlite3.Connection,
    month: str,
    district_type: str,
    district_number: str,
    democratic: int,
    republican: int,
    other: int,
    independent: int,
    libertarian: int,
    green: int,
    constitution: int,
    reform: int,
    socialist_workers: int,
    kentucky_party: int,
    male: int,
    female: int,
    total: int,
    source_file: str,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO district_stats
           (month, district_type, district_number,
            democratic, republican, other, independent, libertarian,
            green, constitution, reform, socialist_workers, kentucky_party,
            male, female, total, source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (month, district_type, district_number,
         democratic, republican, other, independent, libertarian,
         green, constitution, reform, socialist_workers, kentucky_party,
         male, female, total, source_file),
    )
    conn.commit()


def get_district_stats(
    conn: sqlite3.Connection,
    from_month: Optional[str] = None,
    until_month: Optional[str] = None,
    district_type: Optional[str] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM district_stats"
    params: list[str] = []
    conditions: list[str] = []

    if from_month is not None:
        conditions.append("month >= ?")
        params.append(from_month)
    if until_month is not None:
        conditions.append("month <= ?")
        params.append(until_month)
    if district_type is not None:
        conditions.append("district_type = ?")
        params.append(district_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY month ASC, district_type ASC, district_number ASC"
    return conn.execute(query, params).fetchall()


def mark_downloaded(
    conn: sqlite3.Connection,
    url: str,
    filename: str,
    file_size: Optional[int] = None,
    status: str = "downloaded",
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO downloads_log
           (url, filename, downloaded_at, file_size, status)
           VALUES (?, ?, datetime('now'), ?, ?)""",
        (url, filename, file_size, status),
    )
    conn.commit()


def mark_parsed(conn: sqlite3.Connection, url: str) -> None:
    conn.execute(
        "UPDATE downloads_log SET status = 'parsed' WHERE url = ?",
        (url,),
    )
    conn.commit()


def is_downloaded(conn: sqlite3.Connection, url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM downloads_log WHERE url = ?",
        (url,),
    ).fetchone()
    return row is not None


def get_downloaded_urls(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT url FROM downloads_log"
    ).fetchall()
    return {row["url"] for row in rows}


def get_unparsed_files(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT url, filename FROM downloads_log WHERE status = 'downloaded' AND parsed = 0"
    ).fetchall()


def reset_parsed_flags(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE downloads_log SET parsed = 0, status = 'downloaded' WHERE status = 'parsed'"
    )
    conn.commit()
