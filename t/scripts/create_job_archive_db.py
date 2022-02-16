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
import sqlite3
import sys


def populate_job_archive_db(
    jobs_conn, userid, username, ranks, num_entries, starting_jobid
):
    jobid = starting_jobid
    t_inactive_delta = 2000

    for i in range(num_entries):
        jobid += 1
        try:
            jobs_conn.execute(
                """
                INSERT INTO jobs (
                    id,
                    userid,
                    username,
                    ranks,
                    t_submit,
                    t_sched,
                    t_run,
                    t_cleanup,
                    t_inactive,
                    eventlog,
                    jobspec,
                    R
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    jobid,
                    userid,
                    username,
                    ranks,
                    100000000 - 2000,
                    100000000 - 1000,
                    100000000,
                    100000000 + 1000,
                    100000000 + 2000,
                    "eventlog",
                    "jobspec",
                    '{"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}',
                ),
            )
            # commit changes
            jobs_conn.commit()
        # make sure entry is unique
        except sqlite3.IntegrityError as integrity_error:
            print(integrity_error)


def main():
    jobs_conn = sqlite3.connect("file:job-archive.sqlite?mode:rwc", uri=True)
    jobs_conn.execute(
        """
            CREATE TABLE IF NOT EXISTS jobs (
                id            int       NOT NULL,
                userid        int       NOT NULL,
                username      text      NOT NULL,
                ranks         text      NOT NULL,
                t_submit      real      NOT NULL,
                t_sched       real      NOT NULL,
                t_run         real      NOT NULL,
                t_cleanup     real      NOT NULL,
                t_inactive    real      NOT NULL,
                eventlog      text      NOT NULL,
                jobspec       text      NOT NULL,
                R             text      NOT NULL,
                PRIMARY KEY   (id)
        );"""
    )

    # populate the job-archive DB with fake job entries
    populate_job_archive_db(jobs_conn, 5011, "5011", "0", 2, 1000)
    populate_job_archive_db(jobs_conn, 5012, "5012", "0", 3, 2000)
    populate_job_archive_db(jobs_conn, 5013, "5013", "0", 3, 4000)
    populate_job_archive_db(jobs_conn, 5021, "5014", "0", 4, 5000)


if __name__ == "__main__":
    main()
