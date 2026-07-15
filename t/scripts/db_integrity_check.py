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

    # check if migration succeeded: every association in job_usage_factor_table
    # should have entries in job_usage_per_association_table
    cur.execute("SELECT username, bank FROM job_usage_factor_table")
    usage_factor_users = cur.fetchall()

    # check if legacy usage columns exist to determine expected period count
    cur.execute("PRAGMA table_info(job_usage_factor_table)")
    columns = cur.fetchall()
    bin_columns = [
        col[1] for col in columns if col[1].startswith("usage_factor_period_")
    ]
    expected_periods = len(bin_columns) if bin_columns else 0

    for username, bank in usage_factor_users:
        cur.execute(
            "SELECT COUNT(*) FROM job_usage_per_association_table WHERE username=? AND bank=?",
            (username, bank),
        )
        count = cur.fetchone()[0]
        if count == 0:
            print(
                f"error: user {username} in bank {bank} missing from job_usage_per_association_table",
                file=sys.stderr,
            )
            sys.exit(1)

        # if legacy columns existed, verify correct number of periods migrated
        if expected_periods > 0 and count != expected_periods:
            print(
                f"error: user {username} in bank {bank} has {count} periods but expected {expected_periods}",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
