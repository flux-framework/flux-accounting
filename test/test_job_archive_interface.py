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
import pandas as pd

from accounting import accounting_cli_functions as aclif
from accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        global jobs_conn

        # create example job-archive database, output file
        global op
        op = "job_records.csv"
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

        # add sample jobs to job-archive database
        id = 100
        userid = 1234
        username = "user" + str(userid)
        t_submit = 1000
        t_sched = 1005
        t_run = 1010
        t_cleanup = 1015
        t_inactive = 1020
        for i in range(4):
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
                        "0",
                        t_submit,
                        t_sched,
                        t_run,
                        t_cleanup,
                        t_inactive,
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
            userid += 1000
            username = "user" + str(userid)
            t_submit += 1000
            t_sched += 1000
            t_run += 1000
            t_cleanup += 1000
            t_inactive += 1000

    # passing a valid jobid should return
    # its job information
    def test_01_with_jobid_valid(self):
        job_records = aclif.view_jobs_with_jobid(jobs_conn, 102, op)
        self.assertEqual(len(job_records), 1)

    # passing a bad jobid should return a
    # failure message
    def test_02_with_jobid_failure(self):
        job_records = aclif.view_jobs_with_jobid(jobs_conn, 000, op)
        self.assertEqual(job_records, "Job not found in jobs table")

    # passing a timestamp before the first job to
    # start should return all of the jobs
    def test_03_after_start_time_all(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 0, op)
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_04_after_start_time_some(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 2500, op)
        self.assertEqual(len(job_records), 2)

    # passing a timestamp after all of the start time
    # of all the completed jobs should return a failure message
    def test_05_after_start_time_none(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 10000, op)
        self.assertEqual(job_records, "No jobs found after time specified")

    # passing a timestamp after the end time of the
    # last job should return all of the jobs
    def test_06_before_end_time_all(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 5000, op)
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_07_before_end_time_some(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 3000, op)
        self.assertEqual(len(job_records), 2)

    # passing a timestamp before the end time of
    # all the completed jobs should return a failure message
    def test_08_before_end_time_none(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 0, op)
        self.assertEqual(job_records, "No jobs found before time specified")

    # passing a user not in the jobs table
    # should return a failure message
    def test_09_by_user_failure(self):
        job_records = aclif.view_jobs_run_by_username(jobs_conn, "9999", op)
        self.assertEqual(job_records, "User not found in jobs table")

    # view_jobs_run_by_username() interacts with a
    # passwd file; for the purpose of these tests,
    # just pass the userid
    def test_10_by_user_success(self):
        job_records = aclif.view_jobs_run_by_username(jobs_conn, "1234", op)
        self.assertEqual(len(job_records), 1)

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
    runner = unittest.TextTestRunner()
    runner.run(suite())