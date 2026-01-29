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
import unittest
import os
import sqlite3
import time

from unittest import mock

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as j


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    # make sure usage is updated in the same half-life period
    @mock.patch("time.time", mock.MagicMock(return_value=10000001))
    def setUpClass(self):
        # create test accounting database
        c.create_db("FluxAccountingTest.db")
        global conn
        global cur

        conn = sqlite3.connect("FluxAccountingTest.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # set the end of the current half-life period in database
        update_stmt = "UPDATE t_half_life_period_table SET end_half_life_period=? WHERE cluster='cluster'"
        cur.execute(update_stmt, ("10000000",))
        conn.commit()

        # add banks
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        # add and association
        u.add_user(conn, username="user1", bank="A", uid=50001)

        # insert fake job records into DB to generate some job usage for both the banks
        # and associations under that bank
        try:
            cur.execute(
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
                    "200",
                    "50001",
                    9980000 + 100,
                    9980000 + 300,
                    9980000 + 500,
                    "0",
                    '{"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}',
                    '{ "attributes": { "system": { "bank": "A"} } }',
                    "A",
                ),
            )
            # commit changes
            conn.commit()
        except sqlite3.IntegrityError as integrity_error:
            print(integrity_error)

        j.update_job_usage(conn)

    # make sure that the banks and associations have a job usage value as a result of
    # discovering a new job in the 'jobs' table
    def test_01_check_job_usage_value_bank_root(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage_bank_root = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage_bank_A = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        usage_assoc_user1 = cur.fetchone()[0]

        self.assertEqual(usage_bank_root, 200)
        self.assertEqual(usage_bank_A, 200)
        self.assertEqual(usage_assoc_user1, 200)

    # clearing the usage will reset the usage for bank A and all of its users; the usage
    # change will also be propagated up to the root bank
    def test_02_clear_usage(self):
        j.clear_usage(conn, banks="A")

        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage_bank_A = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        usage_assoc_user1 = cur.fetchone()[0]
        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table "
            "WHERE username='user1'"
        )
        usage_factor_period_0 = cur.fetchone()[0]
        cur.execute(
            "SELECT last_job_timestamp FROM job_usage_factor_table "
            "WHERE username='user1'"
        )
        last_job_timestamp = cur.fetchone()[0]
        cur.execute("SELECT ignore_older_than FROM bank_table WHERE bank='A'")
        ignore_older_than = cur.fetchone()[0]

        self.assertEqual(usage_bank_A, 0)
        self.assertEqual(usage_assoc_user1, 0)
        # ensure most recent usage factor period has been cleared
        self.assertEqual(usage_factor_period_0, 0)
        # ensure the last seen job for the user is also reset
        self.assertEqual(last_job_timestamp, 0)
        # make sure that bank 'A' now ignores any jobs older than right now
        self.assertGreater(ignore_older_than, 0)
        self.assertLessEqual(ignore_older_than, time.time())

    @mock.patch("time.time", mock.MagicMock(return_value=10000001))
    def test_03_check_job_usage_after_ignore(self):
        j.update_job_usage(conn)

        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage_bank_root = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage_bank_A = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        usage_assoc_user1 = cur.fetchone()[0]

        # since the usage for bank 'A' has been cleared, any subsequent job usage updates
        # will still reflect a usage of 0 in bank 'A' and any users under that bank
        self.assertEqual(usage_bank_root, 0)
        self.assertEqual(usage_bank_A, 0)
        self.assertEqual(usage_assoc_user1, 0)

    @mock.patch("time.time", mock.MagicMock(return_value=10000001))
    def test_03_remove_ignore_older_than(self):
        b.edit_bank(conn, bank="A", ignore_older_than=0)
        j.update_job_usage(conn)

        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage_bank_root = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage_bank_A = cur.fetchone()[0]
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        usage_assoc_user1 = cur.fetchone()[0]

        # resetting the 'ignore_older_than' attribute will result in older jobs being
        # counted towards usage if they are within the current usage period
        self.assertEqual(usage_bank_root, 200)
        self.assertEqual(usage_bank_A, 200)
        self.assertEqual(usage_assoc_user1, 200)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("FluxAccountingTest.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
