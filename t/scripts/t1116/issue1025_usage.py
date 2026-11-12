#!/usr/bin/env python3

###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
# Drive the issue #1025 usage regression with fixed timestamps.
# Usage: flux python issue1025_usage.py DBPATH COMMAND [TIMESTAMP]
# Commands: seed, add-job, update, userids, snapshot.

import json
import sqlite3
import sys
from unittest import mock

from fluxacct.jobs.usage import update_job_usage


def main():
    conn = sqlite3.connect("file:" + sys.argv[1] + "?mode=rw", uri=True)
    command = sys.argv[2]
    with conn:
        if command == "seed":
            conn.execute(
                "UPDATE t_half_life_period_table SET end_half_life_period=1000"
            )
            conn.execute("UPDATE association_table SET job_usage=1500")
            conn.executemany(
                "UPDATE job_usage_per_association_table SET value=? WHERE period=?",
                [(1000, 0), (500, 1), (0, 2), (0, 3)],
            )
        elif command == "add-job":
            resources = json.dumps(
                {
                    "version": 1,
                    "execution": {
                        "R_lite": [{"rank": "0", "children": {"core": "0"}}],
                        "starttime": 0,
                        "expiration": 0,
                        "nodelist": ["fluke0"],
                    },
                }
            )
            jobspec = json.dumps({"attributes": {"system": {"bank": "A"}}})
            conn.execute(
                "INSERT INTO jobs "
                "(id,userid,t_submit,t_run,t_inactive,ranks,R,jobspec,bank) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (1, 2002, 1255, 1255, 1270, "0", resources, jobspec, "A"),
            )
        elif command == "update":
            with mock.patch("time.time", return_value=float(sys.argv[3])):
                update_job_usage(conn)
        elif command == "userids":
            association = conn.execute(
                "SELECT userid FROM association_table WHERE username=? AND bank=?",
                ("user1", "A"),
            ).fetchone()[0]
            factor = conn.execute(
                "SELECT userid FROM job_usage_factor_table WHERE username=? AND bank=?",
                ("user1", "A"),
            ).fetchone()[0]
            print(json.dumps([association, factor]))
        elif command == "snapshot":
            periods = [
                row[0]
                for row in conn.execute(
                    "SELECT value FROM job_usage_per_association_table "
                    "WHERE username=? AND bank=? ORDER BY period",
                    ("user1", "A"),
                )
            ]
            usage = conn.execute(
                "SELECT job_usage FROM association_table WHERE username=? AND bank=?",
                ("user1", "A"),
            ).fetchone()[0]
            print(json.dumps({"periods": periods, "job_usage": usage}))
        else:
            raise ValueError(command)
    conn.close()


if __name__ == "__main__":
    main()
