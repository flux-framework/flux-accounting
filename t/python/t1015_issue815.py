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
    def setUpClass(self):
        # create test accounting database
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global conn
        global cur

        conn = sqlite3.connect(self.dbname)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # set the end of the current half-life period in database
        update_stmt = "UPDATE t_half_life_period_table SET end_half_life_period=? WHERE cluster='cluster'"
        cur.execute(update_stmt, ("10000000",))
        conn.commit()

        # add banks
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")

        # add associations
        u.add_user(conn, username="user1", bank="A", uid=50001)

        # edit the job usage values for the associations so that:
        # Bank | Usage
        # root | 100
        #   A | 100
        cur.execute("UPDATE association_table SET job_usage=100 WHERE username='user1'")
        # manually set current job usage factor all associations in the DB
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=100 WHERE username='user1'"
        )

        conn.commit()

    # call update_job_usage so that the banks get their job usage value updated
    @mock.patch("time.time", mock.MagicMock(return_value=10000001))
    def test_01_call_update_usage(self):
        j.update_job_usage(conn)

    # check job usage values for every bank
    def test_02_check_job_usage_value_bank_root(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 100)

    def test_03_check_job_usage_value_bank_A(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 100)

    # make sure the historical job usage value and all of the job usage period values
    # are accurate
    #
    # before any half-life decay, the usage for user1 should look like:
    # p0  | p1 | p2 | p3
    # ------------------
    # 100 | 0  | 0  | 0
    def test_04_check_job_usage_value_user1(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 100.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_0 = cur.fetchone()[0]
        self.assertEqual(usage_period_0, 100.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_1 = cur.fetchone()[0]
        self.assertEqual(usage_period_1, 0)

        cur.execute(
            "SELECT usage_factor_period_2 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_2 = cur.fetchone()[0]
        self.assertEqual(usage_period_2, 0)

        cur.execute(
            "SELECT usage_factor_period_3 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_3 = cur.fetchone()[0]
        self.assertEqual(usage_period_3, 0)

    # simulate a half-period further; ensure that the half-life decay is applied properly
    # across all usage period columns
    #
    # after a half-life decay, the usage for user1 should look like:
    # p0 | p1 | p2 | p3
    # -----------------
    # 0  | 50 | 0  | 0
    @mock.patch("time.time", mock.MagicMock(return_value=(100000000 + (604801 * 1.1))))
    def test_05_call_update_usage_new_half_life_period(self):
        j.update_job_usage(conn)

    def test_06_check_job_usage_value_user1_after_first_decay(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 50.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_0 = cur.fetchone()[0]
        self.assertEqual(usage_period_0, 0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_1 = cur.fetchone()[0]
        self.assertEqual(usage_period_1, 50.0)

        cur.execute(
            "SELECT usage_factor_period_2 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_2 = cur.fetchone()[0]
        self.assertEqual(usage_period_2, 0)

        cur.execute(
            "SELECT usage_factor_period_3 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_3 = cur.fetchone()[0]
        self.assertEqual(usage_period_3, 0)

    # simulate another half-period further
    #
    # after another half-life decay, the usage for user1 should look like:
    # p0 | p1 | p2 | p3
    # -----------------
    # 0  | 0  | 25 | 0
    @mock.patch("time.time", mock.MagicMock(return_value=(100000000 + (604801 * 2.1))))
    def test_07_call_update_usage_new_half_life_period(self):
        j.update_job_usage(conn)

    def test_08_check_job_usage_value_user1_after_second_decay(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 25.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_0 = cur.fetchone()[0]
        self.assertEqual(usage_period_0, 0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_1 = cur.fetchone()[0]
        self.assertEqual(usage_period_1, 0)

        cur.execute(
            "SELECT usage_factor_period_2 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_2 = cur.fetchone()[0]
        self.assertEqual(usage_period_2, 25.0)

        cur.execute(
            "SELECT usage_factor_period_3 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_3 = cur.fetchone()[0]
        self.assertEqual(usage_period_3, 0)

    # simulate another half-period further
    #
    # after another half-life decay, the usage for user1 should look like:
    # p0  | p1 | p2 | p3
    # --------------------
    # 0   | 0  | 0  | 12.5
    @mock.patch("time.time", mock.MagicMock(return_value=(100000000 + (604801 * 3.1))))
    def test_09_call_update_usage_new_half_life_period(self):
        j.update_job_usage(conn)

    def test_10_check_job_usage_value_user1_after_third_decay(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 12.5)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_0 = cur.fetchone()[0]
        self.assertEqual(usage_period_0, 0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_1 = cur.fetchone()[0]
        self.assertEqual(usage_period_1, 0)

        cur.execute(
            "SELECT usage_factor_period_2 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_2 = cur.fetchone()[0]
        self.assertEqual(usage_period_2, 0)

        cur.execute(
            "SELECT usage_factor_period_3 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_period_3 = cur.fetchone()[0]
        self.assertEqual(usage_period_3, 12.5)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove(self.dbname)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
