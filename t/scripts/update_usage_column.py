#!/usr/bin/env python3
import sys
import os
import sqlite3


def edit_usage_col(conn, username, value):
    # edit value in accounting database
    conn.execute(
        "UPDATE association_table SET job_usage=? WHERE username=?",
        (
            value,
            username,
        ),
    )
    # commit changes
    conn.commit()


def establish_sqlite_connection(path):
    # try to open database file; will exit with -1 if database file not found
    if not os.path.isfile(path):
        print(f"Database file does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        # set foreign keys constraint
        conn.execute("PRAGMA foreign_keys = 1")
    except sqlite3.OperationalError:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        sys.exit(1)

    return conn


def main():
    path = sys.argv[1]
    username = sys.argv[2]
    value = sys.argv[3]

    conn = establish_sqlite_connection(path)

    edit_usage_col(conn, username, value)

    conn.close()


if __name__ == "__main__":
    main()
