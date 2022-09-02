#!/usr/bin/python3

import sys
import sqlite3


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: integrity_check DATABASE_PATH")

    db_uri = sys.argv[1]

    try:
        conn = sqlite3.connect(db_uri, uri=True)
        cur = conn.cursor()
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(exc)
        sys.exit(1)

    cur.execute("PRAGMA integrity_check")
    result = cur.fetchone()[0]
    print("result:", result)


if __name__ == "__main__":
    main()
