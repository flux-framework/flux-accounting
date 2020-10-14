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
import unittest
import os
import sqlite3
import time

import pandas as pd

from flux.accounting import job_archive_interface as jobs
from flux.accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        global jobs_conn

        # create example job-archive database, output file
        global op
        op = "job_records.csv"

        id = 100

        jobs_conn = sqlite3.connect("file:jobs.db?mode:rwc", uri=True)
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

        def populate_job_archive_db(jobs_conn, userid, username, ranks, num_entries):
            nonlocal id
            nonlocal t_submit
            nonlocal t_sched
            nonlocal t_run
            nonlocal t_cleanup
            nonlocal t_inactive

            for i in range(num_entries):
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
                            id,
                            userid,
                            username,
                            ranks,
                            time.time() - 2000,
                            time.time() - 1000,
                            time.time(),
                            time.time() + 1000,
                            time.time() + 2000,
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

                id += 1
                t_submit += 1000
                t_sched += 1000
                t_run += 1000
                t_cleanup += 1000
                t_inactive += 1000

        # populate the job-archive DB with fake job entries
        populate_job_archive_db(jobs_conn, 1001, "1001", "0", 2)

        populate_job_archive_db(jobs_conn, 1002, "1002", "0-1", 3)
        populate_job_archive_db(jobs_conn, 1002, "1002", "0", 2)

        populate_job_archive_db(jobs_conn, 1003, "1003", "0-2", 3)

        populate_job_archive_db(jobs_conn, 1004, "1004", "0-3", 4)
        populate_job_archive_db(jobs_conn, 1004, "1004", "0", 4)

    # passing a valid jobid should return
    # its job information
    def test_01_with_jobid_valid(self):
        my_dict = {"jobid": 102}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing a bad jobid should return a
    # failure message
    def test_02_with_jobid_failure(self):
        my_dict = {"jobid": 000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 0)

    # passing a timestamp before the first job to
    # start should return all of the jobs
    def test_03_after_start_time_all(self):
        my_dict = {"after_start_time": 0}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 18)

    # passing a timestamp after all of the start time
    # of all the completed jobs should return a failure message
    def test_05_after_start_time_none(self):
        my_dict = {"after_start_time": time.time()}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 0)

    # passing a timestamp after the end time of the
    # last job should return all of the jobs
    def test_06_before_end_time_all(self):
        my_dict = {"before_end_time": time.time() + 10000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 18)

    # passing a timestamp before the end time of
    # all the completed jobs should return a failure message
    def test_08_before_end_time_none(self):
        my_dict = {"before_end_time": 0}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 0)

    # passing a user not in the jobs table
    # should return a failure message
    def test_09_by_user_failure(self):
        my_dict = {"user": "9999"}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 0)

    # view_jobs_run_by_username() interacts with a
    # passwd file; for the purpose of these tests,
    # just pass the userid
    def test_10_by_user_success(self):
        my_dict = {"user": "1001"}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 2)

    # passing a combination of params should further
    # refine the query
    def test_11_multiple_params(self):
        my_dict = {"user": "1001", "after_start_time": time.time() - 1000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 2)

    # passing no parameters will result in a generic query
    # returning all results
    def test_15_no_options_passed(self):
        my_dict = {}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 18)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        jobs_conn.close()
        os.remove("jobs.db")
        os.remove("job_records.csv")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner
    unittest.main(testRunner=TAPTestRunner())
