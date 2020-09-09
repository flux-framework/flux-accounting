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
        # create example accounting database
        c.create_db("FluxAccounting.db")
        global acct_conn
        global jobs_conn
        acct_conn = sqlite3.connect("FluxAccounting.db")

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
    def test_06_with_jobid_valid(self):
        job_records = aclif.view_jobs_with_jobid(jobs_conn, 102, op)
        self.assertEqual(len(job_records), 1)

    # passing a bad jobid should return a
    # failure message
    def test_07_with_jobid_failure(self):
        job_records = aclif.view_jobs_with_jobid(jobs_conn, 000, op)
        self.assertEqual(job_records, "Job not found in jobs table")

    # passing a timestamp before the first job to
    # start should return all of the jobs
    def test_08_after_start_time_all(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 0, op)
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_09_after_start_time_some(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 2500, op)
        self.assertEqual(len(job_records), 2)

    # passing a timestamp after all of the start time
    # of all the completed jobs should return a failure message
    def test_10_after_start_time_none(self):
        job_records = aclif.view_jobs_after_start_time(jobs_conn, 10000, op)
        self.assertEqual(job_records, "No jobs found after time specified")

    # passing a timestamp after the end time of the
    # last job should return all of the jobs
    def test_11_before_end_time_all(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 5000, op)
        self.assertEqual(len(job_records), 4)

    # passing a timestamp in the middle should return
    # only some of the jobs
    def test_12_before_end_time_some(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 3000, op)
        self.assertEqual(len(job_records), 2)

    # passing a timestamp before the end time of
    # all the completed jobs should return a failure message
    def test_13_before_end_time_none(self):
        job_records = aclif.view_jobs_before_end_time(jobs_conn, 0, op)
        self.assertEqual(job_records, "No jobs found before time specified")

    # passing a user not in the jobs table
    # should return a failure message
    def test_14_by_user_failure(self):
        job_records = aclif.view_jobs_run_by_username(jobs_conn, "9999", op)
        self.assertEqual(job_records, "User not found in jobs table")

    # view_jobs_run_by_username() interacts with a
    # passwd file; for the purpose of these tests,
    # just pass the userid
    def test_15_by_user_success(self):
        job_records = aclif.view_jobs_run_by_username(jobs_conn, "1234", op)
        self.assertEqual(len(job_records), 1)

    # remove databases, log file, and output file
    # let's add a top-level account using the add-bank
    # subcommand
    def test_16_add_bank_success(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        select_stmt = "SELECT * FROM bank_table WHERE bank='root'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_17_add_dup_bank(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        self.assertRaises(sqlite3.IntegrityError)

    # trying to add a sub account with an invalid parent bank
    # name should result in a failure
    def test_18_add_with_invalid_parent_bank(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(
                acct_conn,
                bank="bad_subaccount",
                parent_bank="bad_parentaccount",
                shares=1,
            )

        self.assertEqual(cm.exception.code, -1)

    # now let's add a couple sub accounts whose parent is 'root'
    # and whose total shares equal root's allocation (100 shares)
    def test_19_add_subaccounts(self):
        aclif.add_bank(acct_conn, bank="sub_account_1", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)
        aclif.add_bank(acct_conn, bank="sub_account_2", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_2'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # removing a bank currently in the bank_table
    def test_20_delete_bank_success(self):
        aclif.delete_bank(acct_conn, bank="sub_account_1")
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 0)

    # edit a bank value
    def test_21_edit_bank_value(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        aclif.edit_bank(acct_conn, bank="root", shares=50)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='root'")

        self.assertEqual(cursor.fetchone()[0], 50)

    # trying to edit a parent bank's value to be
    # less than the total amount allocated to all of its
    # sub banks should result in a failure message and exit
    def test_22_edit_parent_bank_failure(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(acct_conn, bank="sub_bank_1", parent_bank="root", shares=25)
            aclif.add_bank(acct_conn, bank="sub_bank_2", parent_bank="root", shares=25)
            aclif.edit_bank(acct_conn, bank="root", shares=49)

        self.assertEqual(cm.exception.code, -1)

    # edit a parent bank that has sub banks successfully
    def test_23_edit_parent_bank_success(self):
        aclif.add_bank(acct_conn, bank="sub_bank_1", shares=25)
        aclif.add_bank(
            acct_conn, bank="sub_bank_1_1", parent_bank="sub_bank_1", shares=5
        )
        aclif.add_bank(
            acct_conn, bank="sub_bank_1_2", parent_bank="sub_bank_1", shares=5
        )
        aclif.edit_bank(acct_conn, bank="sub_bank_1", shares=11)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='sub_bank_1'")

        self.assertEqual(cursor.fetchone()[0], 11)

    # trying to edit a sub bank's shares to be greater
    # than its parent bank's allocation should result
    # in a failure message and exit
    def test_24_edit_sub_bank_greater_than_parent_bank(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(
                acct_conn, bank="sub_bank_2_1", parent_bank="sub_bank_2", shares=5
            )
            aclif.edit_bank(acct_conn, bank="sub_bank_2_1", shares=26)

        self.assertEqual(cm.exception.code, -1)

    # edit the sub bank successfully
    def test_25_edit_sub_bank_successfully(self):
        aclif.add_bank(acct_conn, bank="sub_bank_2_1", shares=26)
        aclif.edit_bank(acct_conn, bank="sub_bank_2_1", shares=24)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='sub_bank_2_1'")

        self.assertEqual(cursor.fetchone()[0], 24)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        jobs_conn.close()
        os.remove("FluxAccounting.db")
        os.remove("db_creation.log")
        os.remove("jobs.db")
        os.remove("job_records.csv")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
