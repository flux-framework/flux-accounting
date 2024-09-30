#!/usr/bin/env python3
###############################################################
# Copyright 2024 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sqlite3
import sqlite3
import sys
import time


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: insert_jobs DATABASE_PATH")

    db_uri = sys.argv[1]

    try:
        conn = sqlite3.connect(db_uri, uri=True)
        cur = conn.cursor()
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(exc)
        sys.exit(1)

    userid = 9999
    t_submit = t_run = 0
    t_inactive_recent = time.time()  # job that just finished
    t_inactive_two_weeks = time.time() - (604861 * 2)  # more than 2 weeks old
    t_inactive_old = time.time() - (604861 * 27)  # more than six months old
    ranks = r = jobspec = ""
    insert_stmt = """
        INSERT INTO jobs
        (id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    cur.execute(
        insert_stmt,
        (
            "1",
            userid,
            t_submit,
            t_run,
            t_inactive_recent,
            ranks,
            r,
            jobspec,
        ),
    )
    cur.execute(
        insert_stmt,
        (
            "2",
            userid,
            t_submit,
            t_run,
            t_inactive_two_weeks,
            ranks,
            r,
            jobspec,
        ),
    )
    cur.execute(
        insert_stmt,
        (
            "3",
            userid,
            t_submit,
            t_run,
            t_inactive_two_weeks,
            ranks,
            r,
            jobspec,
        ),
    )
    cur.execute(
        insert_stmt,
        (
            "4",
            userid,
            t_submit,
            t_run,
            t_inactive_old,
            ranks,
            r,
            jobspec,
        ),
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
