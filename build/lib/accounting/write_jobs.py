#!/usr/bin/env python3

###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import sys
import sqlite3
import pandas as pd
import time

import flux.job
import flux.constants
import flux.util
from flux.core.inner import raw


def write_to_db(inactive):
    # open connection to database
    print("Opening JobCompletion DB...")
    conn = sqlite3.connect("JobCompletion.db")
    print("Opened JobCompletion DB successfully\n")

    # insert values into DB one at a time by getting the values from
    # each job completion tuple
    print("Inserting values into DB...\n")
    for job in inactive:
        conn.execute(
            """
            INSERT OR IGNORE INTO inactive
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job["t_submit"],
                job["name"],
                job["t_run"],
                job["t_cleanup"],
                job["userid"],
                job["ntasks"],
                job["t_inactive"],
                job["t_depend"],
                job["priority"],
                job["state"],
                job["t_sched"],
                job["id"],
            ),
        )
        print("insertion into inactive table successful")

    # commit changes
    conn.commit()

    # make sure the writes to DB were successful and we can
    # retrieve them
    sel_statement = "SELECT * FROM inactive"
    print(pd.read_sql_query(sel_statement, conn))
    print()

    conn.close()


def save_last_job():
    # open connection to database
    print("Opening JobCompletion DB...")
    conn = sqlite3.connect("JobCompletion.db")
    print("Opened JobCompletion DB successfully\n")

    # get the last submitted job and query its t_submit and job id
    print("Getting last submitted job...")
    sel_statement = "SELECT id, t_submit FROM inactive ORDER BY t_inactive DESC LIMIT 1"
    cursor = conn.cursor()
    cursor.execute(sel_statement)
    records = cursor.fetchall()

    for row in records:
        last_job_id = row[0]
        last_t_inactive = row[1]

    print("Last job id:", last_job_id, "t_inactive:", last_t_inactive)
    print("Query complete\n")

    # write the last job's job id to a temporary text file for retrieval later
    # if the file doesn't exist yet, it will be created
    print("writing last job id to tmp file...")
    f = open("tmp_id.txt", "w")
    f.truncate(0)
    f.write(last_job_id + "\n")
    f.close()
    print("write complete\n")

    # <demo> show contents of last job's job id
    print("showing contents of tmp file...")
    f = open("tmp_id.txt", "r")
    for line in f:
        print(line)


def main():
    h = flux.Flux()

    attrs = [
        "userid",
        "priority",
        "state",
        "name",
        "ntasks",
        "t_submit",
        "t_depend",
        "t_sched",
        "t_run",
        "t_cleanup",
        "t_inactive",
    ]

    # get jobs that have run in the past 5 minutes
    rpc_handle = flux.job.job_list_inactive(h, time.time() - 300, 1000, attrs)

    try:
        jobs = rpc_handle.get_jobs()
    except EnvironmentError as e:
        print("{}: {}".format("rpc", e.strerror), file=sys.stderr)
        sys.exit(1)

    write_to_db(jobs)
    save_last_job()


main()
