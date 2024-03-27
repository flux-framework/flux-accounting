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
import sys

from unittest import mock

from fluxacct.accounting import job_archive_interface as jobs
from fluxacct.accounting import create_db as c
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b


class TestAccountingCLI(unittest.TestCase):
    # create accounting database
    @classmethod
    def setUpClass(self):
        global acct_conn
        global cur

        # create example job-archive database, output file
        global op
        op = "job_records.csv"

        c.create_db("FluxAccountingUsers.db")
        try:
            acct_conn = sqlite3.connect("file:FluxAccountingUsers.db?mode=rw", uri=True)
            cur = acct_conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

        # simulate end of half life period in FluxAccounting database
        update_stmt = """
            UPDATE t_half_life_period_table SET end_half_life_period=?
            WHERE cluster='cluster'
            """
        acct_conn.execute(update_stmt, ("10000000",))
        acct_conn.commit()

        # add bank hierarchy
        b.add_bank(acct_conn, bank="A", shares=1)
        b.add_bank(acct_conn, bank="B", parent_bank="A", shares=1)
        b.add_bank(acct_conn, bank="C", parent_bank="B", shares=1)
        b.add_bank(acct_conn, bank="D", parent_bank="B", shares=1)

        # add users
        u.add_user(acct_conn, username="1001", uid="1001", bank="C")
        u.add_user(acct_conn, username="1002", uid="1002", bank="C")
        u.add_user(acct_conn, username="1003", uid="1003", bank="D")
        u.add_user(acct_conn, username="1004", uid="1004", bank="D")

        jobid = 100
        interval = 0  # add to job timestamps to diversify job-archive records

        @mock.patch("time.time", mock.MagicMock(return_value=9000000))
        def populate_job_archive_db(acct_conn, userid, bank, ranks, nodes, num_entries):
            nonlocal jobid
            nonlocal interval
            t_inactive_delta = 2000

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

            for i in range(num_entries):
                try:
                    acct_conn.execute(
                        """
                        INSERT INTO jobs (
                            id,
                            userid,
                            t_submit,
                            t_run,
                            t_inactive,
                            ranks,
                            R,
                            jobspec
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            jobid,
                            userid,
                            (time.time() + interval) - 2000,
                            (time.time() + interval),
                            (time.time() + interval) + t_inactive_delta,
                            ranks,
                            R_input,
                            '{ "attributes": { "system": { "bank": "' + bank + '"} } }',
                        ),
                    )
                    # commit changes
                    acct_conn.commit()
                # make sure entry is unique
                except sqlite3.IntegrityError as integrity_error:
                    print(integrity_error)

                jobid += 1
                interval += 10000
                t_inactive_delta += 100

        # populate the job-archive DB with fake job entries
        populate_job_archive_db(acct_conn, 1001, "C", "0", "fluke[0]", 2)

        populate_job_archive_db(acct_conn, 1002, "C", "0-1", "fluke[0-1]", 3)
        populate_job_archive_db(acct_conn, 1002, "C", "0", "fluke[0]", 2)

        populate_job_archive_db(acct_conn, 1003, "D", "0-2", "fluke[0-2]", 3)

        populate_job_archive_db(acct_conn, 1004, "D", "0-3", "fluke[0-3]", 4)
        populate_job_archive_db(acct_conn, 1004, "D", "0", "fluke[0]", 4)

    # passing a valid jobid should return
    # its job information
    def test_01_with_jobid_valid(self):
        my_dict = {"jobid": 102}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        print(job_records)
        self.assertEqual(len(job_records), 2)

    # passing a bad jobid should return no records
    def test_02_with_jobid_failure(self):
        my_dict = {"jobid": 000}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing a timestamp before the first job to
    # start should return all of the jobs
    def test_03_after_start_time_all(self):
        my_dict = {"after_start_time": 0}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 19)

    # passing a timestamp after all of the start time
    # of all the completed jobs should return a failure message
    @mock.patch("time.time", mock.MagicMock(return_value=11000000))
    def test_04_after_start_time_none(self):
        my_dict = {"after_start_time": time.time()}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing a timestamp before the end time of the
    # last job should return all of the jobs
    @mock.patch("time.time", mock.MagicMock(return_value=11000000))
    def test_05_before_end_time_all(self):
        my_dict = {"before_end_time": time.time()}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 19)

    # passing a timestamp before the end time of
    # the first completed jobs should return no jobs
    def test_06_before_end_time_none(self):
        my_dict = {"before_end_time": 0}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # passing a user not in the jobs table
    # should return no jobs
    def test_07_by_user_failure(self):
        my_dict = {"user": "9999"}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 1)

    # view_jobs_run_by_username() interacts with a
    # passwd file; for the purpose of these tests,
    # just pass the userid
    def test_08_by_user_success(self):
        my_dict = {"user": "1001"}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 3)

    # passing a combination of params should further
    # refine the query
    @mock.patch("time.time", mock.MagicMock(return_value=9000500))
    def test_09_multiple_params(self):
        my_dict = {"user": "1001", "after_start_time": time.time()}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 2)

    # passing no parameters will result in a generic query
    # returning all results
    def test_10_no_options_passed(self):
        my_dict = {}
        job_records = jobs.output_job_records(acct_conn, op, **my_dict)
        self.assertEqual(len(job_records), 19)

    # users that have run a lot of jobs should have a larger usage factor
    @mock.patch("time.time", mock.MagicMock(return_value=9900000))
    def test_11_calc_usage_factor_many_jobs(self):
        user = "1002"
        bank = "C"
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_0=256 WHERE username='1002' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_1=64 WHERE username='1002' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_2=16 WHERE username='1002' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_3=8 WHERE username='1002' AND bank='C'"
        acct_conn.execute(update_stmt)
        acct_conn.commit()

        usage_factor = jobs.calc_usage_factor(
            acct_conn,
            pdhl=1,
            user=user,
            bank=bank,
            default_bank=bank,
        )
        self.assertEqual(usage_factor, 17044.0)

    # on the contrary, users that have not run a lot of jobs should have
    # a smaller usage factor
    @mock.patch("time.time", mock.MagicMock(return_value=9900000))
    def test_12_calc_usage_factor_few_jobs(self):
        user = "1001"
        bank = "C"
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_0=4096 WHERE username='1001' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_1=256 WHERE username='1001' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_2=32 WHERE username='1001' AND bank='C'"
        acct_conn.execute(update_stmt)
        update_stmt = "UPDATE job_usage_factor_table SET usage_factor_period_3=16 WHERE username='1001' AND bank='C'"
        acct_conn.execute(update_stmt)
        acct_conn.commit()

        usage_factor = jobs.calc_usage_factor(
            acct_conn,
            pdhl=1,
            user=user,
            bank=bank,
            default_bank=bank,
        )
        self.assertEqual(usage_factor, 8500.0)

    # make sure update_t_inactive() updates the last seen job timestamp
    def test_13_update_t_inactive_success(self):
        s_ts = "SELECT last_job_timestamp FROM job_usage_factor_table WHERE username='1003' AND bank='D'"
        cur.execute(s_ts)
        ts_old = float(cur.fetchone()[0])

        self.assertEqual(ts_old, 0.0)

        usage_factor = jobs.calc_usage_factor(
            acct_conn,
            pdhl=1,
            user="1003",
            bank="D",
            default_bank="D",
        )

        cur.execute(s_ts)
        ts_new = float(cur.fetchone()[0])

        self.assertEqual(ts_new, 9092200.0)

    # make sure current usage factor was written to job_usage_factor_table, but
    # historical usage factor was written to association_table
    def test_14_check_usage_factor_in_tables(self):
        select_stmt = "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='1002' AND bank='C'"
        cur.execute(select_stmt)
        usage_factor = cur.fetchone()[0]
        self.assertEqual(usage_factor, 16956.0)

        select_stmt = (
            "SELECT job_usage FROM association_table WHERE username='1002' AND bank='C'"
        )
        cur.execute(select_stmt)
        job_usage = cur.fetchone()[0]
        self.assertEqual(job_usage, 17044.0)

    # re-calculating a job usage factor after the end of the last half-life
    # period should create a new usage bin
    @mock.patch("time.time", mock.MagicMock(return_value=(100000000 + (604800 * 2.1))))
    def test_15_append_jobs_in_diff_half_life_period(self):
        user = "1001"
        bank = "C"

        try:
            acct_conn.execute(
                """
                INSERT INTO jobs (
                    id,
                    userid,
                    t_submit,
                    t_run,
                    t_inactive,
                    ranks,
                    R,
                    jobspec
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "200",
                    "1001",
                    time.time() + 100,
                    time.time() + 300,
                    time.time() + 500,
                    "0",
                    '{"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}',
                    '{ "attributes": { "system": { "bank": "C"} } }',
                ),
            )
            # commit changes
            acct_conn.commit()
        # make sure entry is unique
        except sqlite3.IntegrityError as integrity_error:
            print(integrity_error)

        # re-calculate usage factor for user1001
        usage_factor = jobs.calc_usage_factor(
            acct_conn,
            pdhl=1,
            user=user,
            bank=bank,
            default_bank=bank,
        )
        self.assertEqual(usage_factor, 4366.0)

    # simulate a half-life period further; re-calculate
    # usage for user1001 to make sure its value goes down
    @mock.patch("time.time", mock.MagicMock(return_value=(10000000 + (604800 * 2.1))))
    def test_16_recalculate_usage_after_half_life_period(self):
        user = "1001"
        bank = "C"

        usage_factor = jobs.calc_usage_factor(
            acct_conn,
            pdhl=1,
            user=user,
            bank=bank,
            default_bank=bank,
        )

        self.assertEqual(usage_factor, 2199.5)

    # calling update_job_usage() in the same half-life period should NOT
    # update usage factors for users
    @mock.patch("time.time", mock.MagicMock(return_value=(10000000 + (604799))))
    def test_17_update_job_usage_same_half_life_period(self):
        s_stmt = """
            SELECT job_usage FROM association_table
            WHERE username='1002' AND bank='C'
            """

        cur.execute(s_stmt)
        job_usage = cur.fetchone()[0]
        self.assertEqual(job_usage, 17044.0)

        jobs.update_job_usage(acct_conn, pdhl=1)

        cur.execute(s_stmt)
        job_usage = cur.fetchone()[0]
        self.assertEqual(job_usage, 17044.0)

    # simulate a half-life period further; assure the new end of the
    # current half-life period gets updated
    @mock.patch("time.time", mock.MagicMock(return_value=(10000000 + (604800 * 2.1))))
    def test_18_update_end_half_life_period(self):
        # fetch timestamp of the end of the current half-life period
        s_end_hl = """
            SELECT end_half_life_period
            FROM t_half_life_period_table
            WHERE cluster='cluster'
            """
        cur.execute(s_end_hl)
        old_hl = cur.fetchone()[0]

        jobs.check_end_hl(acct_conn, pdhl=1)

        cur.execute(s_end_hl)
        new_hl = cur.fetchone()[0]

        self.assertGreater(new_hl, old_hl)

    # removing a user from the flux-accounting DB should NOT remove their job
    # usage history from the job_usage_factor_table
    def test_19_keep_job_usage_records_upon_delete(self):
        u.delete_user(acct_conn, username="1001", bank="C")

        select_stmt = """
            SELECT * FROM
            job_usage_factor_table
            WHERE username='1001'
            AND bank='C'
            """
        cur.execute(select_stmt)
        records = len(cur.fetchall())

        self.assertEqual(records, 1)

    # calling update_job_usage in the next half-life period should update usage
    # factors for users
    @mock.patch("time.time", mock.MagicMock(return_value=(10000000 + (604800 * 2.1))))
    def test_20_update_job_usage_next_half_life_period(self):
        s_stmt = """
            SELECT job_usage FROM association_table
            WHERE username='1002' AND bank='C'
            """
        cur.execute(s_stmt)
        job_usage = cur.fetchone()[0]

        self.assertEqual(job_usage, 17044.0)

        jobs.update_job_usage(acct_conn, pdhl=1)

        cur.execute(s_stmt)
        job_usage = cur.fetchone()[0]
        self.assertEqual(job_usage, 8496.0)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        os.remove("job_records.csv")
        os.remove("FluxAccountingUsers.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
