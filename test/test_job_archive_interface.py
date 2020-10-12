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

from accounting import job_archive_interface as jobs
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
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_04_after_start_time_some(self):
        my_dict = {"after_start_time": 2500}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 2)

    # passing a timestamp after all of the start time
    # of all the completed jobs should return a failure message
    def test_05_after_start_time_none(self):
        my_dict = {"after_start_time": 5000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 0)

    # passing a timestamp after the end time of the
    # last job should return all of the jobs
    def test_06_before_end_time_all(self):
        my_dict = {"before_end_time": 5000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_07_before_end_time_some(self):
        my_dict = {"before_end_time": 3000}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 2)

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
        my_dict = {"user": "1234"}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing a combination of params should further
    # refine the query
    def test_11_multiple_params_1(self):
        my_dict = {"user": "1234", "after_start_time": 1009}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    def test_12_multiple_params_2(self):
        my_dict = {"user": "1234", "before_end_time": 1021}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # order of the parameters shouldn't matter
    def test_13_multiple_params_3(self):
        my_dict = {"before_end_time": 5000, "user": "1234"}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing multiple parameters will result in precedence;
    # the first parameter will be used to filter results
    def test_14_multiple_params_4(self):
        my_dict = {"jobid": 102, "after_start_time": 0}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing no parameters will result in a generic query
    # returning all results
    def test_15_no_options_passed(self):
        my_dict = {}
        job_records = jobs.view_job_records(jobs_conn, op, **my_dict)
        self.assertEqual(len(job_records), 4)

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
