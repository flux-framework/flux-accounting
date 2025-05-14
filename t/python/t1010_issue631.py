#!/usr/bin/env python3

###############################################################
# Copyright 2025 Lawrence Livermore National Security, LLC
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

from unittest import mock

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as j


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("FluxAccountingTestIssue631.db")
        global conn
        global cur
        global select_historical_usage
        global select_current_usage

        conn = sqlite3.connect("FluxAccountingTestIssue631.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # set the end of the current half-life period in database
        update_stmt = "UPDATE t_half_life_period_table SET end_half_life_period=? WHERE cluster='cluster'"
        cur.execute(update_stmt, ("10000000",))
        conn.commit()

        # add banks
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        b.add_bank(conn, "B", 1, "root")
        b.add_bank(conn, "C", 1, "root")
        b.add_bank(conn, "D", 1, "C")
        b.add_bank(conn, "E", 1, "C")

        # add associations
        u.add_user(conn, username="user1", bank="A", uid=50001)
        u.add_user(conn, username="user2", bank="A", uid=50002)
        u.add_user(conn, username="user3", bank="A", uid=50003)
        u.add_user(conn, username="user4", bank="B", uid=50004)
        u.add_user(conn, username="user5", bank="B", uid=50005)
        u.add_user(conn, username="user6", bank="D", uid=50006)
        u.add_user(conn, username="user7", bank="E", uid=50007)

        # edit the job usage values for the associations so that:
        # Bank | Usage
        # root | 110
        #   A | 50
        #   B | 25
        #   C | 35
        #     D | 25
        #     E | 10
        cur.execute("UPDATE association_table SET job_usage=20 WHERE username='user1'")
        cur.execute("UPDATE association_table SET job_usage=20 WHERE username='user2'")
        cur.execute("UPDATE association_table SET job_usage=10 WHERE username='user3'")
        cur.execute("UPDATE association_table SET job_usage=13 WHERE username='user4'")
        cur.execute("UPDATE association_table SET job_usage=12 WHERE username='user5'")
        cur.execute("UPDATE association_table SET job_usage=25 WHERE username='user6'")
        cur.execute("UPDATE association_table SET job_usage=10 WHERE username='user7'")

        # manually set current job usage factor all associations in the DB
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=20 WHERE username='user1'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=20 WHERE username='user2'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=10 WHERE username='user3'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=13 WHERE username='user4'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=12 WHERE username='user5'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=25 WHERE username='user6'"
        )
        cur.execute(
            "UPDATE job_usage_factor_table SET usage_factor_period_0=10 WHERE username='user7'"
        )

        conn.commit()

    # update the job usage values for all banks in the DB in same half-life period
    @mock.patch("time.time", mock.MagicMock(return_value=10000001))
    def test_01_call_update_usage(self):
        j.update_job_usage(conn)

    # check job usage values for every bank
    def test_02_check_job_usage_value_bank_root(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 110)

    def test_03_check_job_usage_value_bank_A(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 50)

    def test_04_check_job_usage_value_bank_B(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='B'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 25)

    # bank C is made up of two sub banks (D & E) that have total job usage values
    # of 25 and 10, respectively, giving it a total usage of 35
    def test_05_check_job_usage_value_bank_C(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='C'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 35)

    def test_06_check_job_usage_value_bank_D(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='D'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 25)

    def test_07_check_job_usage_value_bank_E(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='E'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 10)

    # simulate a half-period further; update the job usage values for all banks, which will
    # result in a decay of all the previous job usage values
    @mock.patch("time.time", mock.MagicMock(return_value=(100000000 + (604801 * 1.1))))
    def test_08_call_update_usage_new_half_life_period(self):
        j.update_job_usage(conn)

    # associations' job usage values should be affected by a half-life decay
    def test_09_check_job_usage_value_association_user1(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 10.0)

        # since no new jobs were submitted in this new half-life period, the current
        # usage should be 0
        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user1'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        # the current usage from the previous half-life period should now be written to
        # the second slot in job_usage_factor_table
        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user1'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 10.0)

    def test_10_check_job_usage_value_association_user2(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user2'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 10.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user2'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user2'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 10.0)

    def test_11_check_job_usage_value_association_user3(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user3'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 5.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user3'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user3'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 5.0)

    def test_12_check_job_usage_value_association_user4(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user4'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 6.5)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user4'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user4'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 6.5)

    def test_13_check_job_usage_value_association_user5(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user5'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 6.0)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user5'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user5'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 6.0)

    def test_14_check_job_usage_value_association_user6(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user6'")
        historical_usage = cur.fetchone()[0]
        self.assertEqual(historical_usage, 12.5)

        cur.execute(
            "SELECT usage_factor_period_0 FROM job_usage_factor_table WHERE username='user6'"
        )
        current_usage = cur.fetchone()[0]
        self.assertEqual(current_usage, 0.0)

        cur.execute(
            "SELECT usage_factor_period_1 FROM job_usage_factor_table WHERE username='user6'"
        )
        usage_last_half_life = cur.fetchone()[0]
        self.assertEqual(usage_last_half_life, 12.5)

    # make sure banks reflect half-life decay of associations' job usage
    def test_15_check_job_usage_value_bank_root(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='root'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 55.0)

    def test_16_check_job_usage_value_bank_A(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 25.0)

    def test_17_check_job_usage_value_bank_B(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='B'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 12.5)

    def test_18_check_job_usage_value_bank_C(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='C'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 17.5)

    def test_19_check_job_usage_value_bank_D(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='D'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 12.5)

    def test_20_check_job_usage_value_bank_E(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='E'")
        usage = cur.fetchone()[0]

        self.assertEqual(usage, 5.0)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("FluxAccountingTestIssue631.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
