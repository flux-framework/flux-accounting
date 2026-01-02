#!/usr/bin/env python3
###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
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


def populate_db(conn, userid, bank, ranks, nodes, jobid, t_run, t_inactive):
    R_input = """{{
      "version": 1,
      "execution": {{
        "R_lite": [
          {{
            "rank": "{rank}",
            "children": {{
                "core": "0-3",
                "gpu": "0"
             }}
          }}
        ],
        "starttime": 0,
        "expiration": 0,
        "nodelist": [
          "{nodelist}"
        ]
      }}
    }}
    """.format(
        rank=ranks, nodelist=nodes
    )

    try:
        conn.execute(
            """
            INSERT INTO jobs (
                id,
                userid,
                t_submit,
                t_run,
                t_inactive,
                ranks,
                R,
                jobspec,
                bank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jobid,
                userid,
                0,
                t_run,
                t_inactive,
                ranks,
                R_input,
                '{ "attributes": { "system": { "bank": "' + bank + '"} } }',
                bank,
            ),
        )
        # commit changes
        conn.commit()
    # make sure entry is unique
    except sqlite3.IntegrityError as integrity_error:
        print(integrity_error)


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: insert_jobs DATABASE_PATH")

    db_uri = sys.argv[1]

    try:
        conn = sqlite3.connect(db_uri, uri=True)
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(exc)
        sys.exit(1)

    # populate the job-archive DB with fake job entries

    # 2-node job that ran for 60 seconds on January 1st, 2025
    populate_db(conn, 50001, "A", "0-1", "fluke[0-1]", 1, 1735754664, (1735754664 + 60))
    # 1-node job that ran for 60 seconds on April 17th, 2025
    populate_db(conn, 50001, "A", "0", "fluke[0]", 2, 1744913064, (1744913064 + 60))
    # 1-node job that ran for 120 seconds on May 20th, 2025
    populate_db(conn, 50001, "A", "0", "fluke[0]", 3, 1747764264, (1747764264 + 120))
    # 4-node job that ran for 60 seconds on November 10th, 2025
    populate_db(conn, 50001, "A", "0-3", "fluke[0-3]", 4, 1762797864, (1762797864 + 60))
    # 2-node job that ran for 180 seconds on April 18th, 2025
    populate_db(
        conn, 50002, "A", "0-1", "fluke[0-1]", 5, 1744999464, (1744999464 + 180)
    )
    # 1-node job that ran for 60 seconds on December 1st, 2025
    populate_db(conn, 50002, "A", "0", "fluke[0]", 6, 1764612264, (1764612264 + 60))
    # 4-node job that ran for 60 seconds on June 1st, 2025
    populate_db(conn, 50003, "B", "0-3", "fluke[0-3]", 7, 1748801064, (1748801064 + 60))
    # 2-node job that ran for 30 seconds on June 2nd, 2025
    populate_db(conn, 50003, "B", "0-1", "fluke[0-1]", 8, 1748887464, (1748887464 + 30))


if __name__ == "__main__":
    main()
