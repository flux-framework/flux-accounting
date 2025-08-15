#!/usr/bin/env python3
import sys
import os
import sqlite3


from flux.job.JobID import JobID


def edit_duration_col(conn, id, value):
    """
    Update the actual duration of a job in the jobs table.
    """
    conn.execute(
        "UPDATE jobs SET actual_duration=? WHERE id=?",
        (
            value,
            JobID(id).dec,
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
    id = sys.argv[2]
    value = sys.argv[3]

    conn = establish_sqlite_connection(path)

    edit_duration_col(conn, id, value)

    conn.close()


if __name__ == "__main__":
    main()
