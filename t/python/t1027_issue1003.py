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
#
# When update-usage finds new jobs in a *new* half-life period,
# PeriodicUsageCalculator.calc_usage_factor() must write only the current
# period's usage into period 0 of job_usage_per_association_table. The decayed
# past usage already lives in periods 1..N after apply_decay_factor(), so
# writing the full historical total into period 0 counts that past usage
# twice: once in period 0 and once in periods 1..N. Every subsequent call to
# update-usage then reads that inflated period 0 back and carries the
# duplicate forward.
#
# These tests drive update_job_usage() through three consecutive runs that
# take the three branches of calc_usage_factor() that write period 0, and
# check the period values and the historical job usage after each one. They
# also check that the historical job usage for the association always equals
# the sum of its usage periods.
#
# To keep the timestamps easy to follow, the database is configured with a
# half-life of 100 seconds and a usage reset period of 400 seconds (so each
# association has 4 usage periods), and the first half-life period ends at
# t=1000:
#
#  time:    1000             1100             1200
#  ----------|----------------|----------------|------->
#               run 1 (1150)     run 3 (1250)
#               job 1 (1120-1130)
#               run 2 (1175)
#               job 2 (1150-1170)
import unittest
import os
import sqlite3
import time

from unittest import mock

from fluxacct.database import create as c
from fluxacct.entities import associations as u
from fluxacct.entities import banks as b
from fluxacct.jobs import usage as j

R_ONE_NODE = (
    '{"version": 1, "execution": {"R_lite": [{"rank": "0", '
    '"children": {"core": "0"}}], "starttime": 0, "expiration": 0, '
    '"nodelist": ["fluke0"]}}'
)


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database with a 100-second half-life and a
        # 400-second usage reset period (4 usage periods per association)
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(
            self.dbname,
            priority_decay_half_life="100s",
            priority_usage_reset_period="400s",
        )
        global conn
        global cur

        conn = sqlite3.connect(self.dbname, timeout=60)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # set the end of the current half-life period in database
        update_stmt = "UPDATE t_half_life_period_table SET end_half_life_period=? WHERE cluster='cluster'"
        cur.execute(update_stmt, (1000,))
        conn.commit()

        # add banks
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")

        # add associations
        u.add_user(conn, username="user1", bank="A", uid=50001)

        # give user1 a usage value of 100 in the current period:
        # p0  | p1 | p2 | p3
        # ------------------
        # 100 | 0  | 0  | 0
        cur.execute("UPDATE association_table SET job_usage=100 WHERE username='user1'")
        cur.execute(
            "UPDATE job_usage_per_association_table SET value=100 "
            "WHERE username='user1' AND userid=50001 AND bank='A' AND period=0"
        )
        conn.commit()

    # insert a completed one-node job
    def add_job(self, jobid, t_run, t_inactive):
        conn.execute(
            """
            INSERT INTO jobs (
                id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jobid,
                50001,
                t_run,
                t_run,
                t_inactive,
                "0",
                R_ONE_NODE,
                '{ "attributes": { "system": { "bank": "A"} } }',
                "A",
            ),
        )
        conn.commit()

    def get_periods(self):
        cur.execute(
            "SELECT value FROM job_usage_per_association_table "
            "WHERE username='user1' AND bank='A' ORDER BY period"
        )
        return [row[0] for row in cur.fetchall()]

    def get_job_usage(self):
        cur.execute("SELECT job_usage FROM association_table WHERE username='user1'")
        return cur.fetchone()[0]

    # run 1 (t=1150): job 1 ran for 10 seconds and finished at t=1130, after
    # the half-life period that ended at t=1000 was over, so
    # calc_usage_factor() decays the past periods and writes the new job's
    # usage into period 0
    #
    # after this update, the usage for user1 should look like:
    # p0 | p1 | p2 | p3
    # -----------------
    # 10 | 50 | 0  | 0
    @mock.patch("time.time", mock.MagicMock(return_value=1150))
    def test_01_new_job_in_new_half_life_period(self):
        self.add_job("1", t_run=1120, t_inactive=1130)
        j.update_job_usage(conn)

        self.assertEqual(self.get_job_usage(), 60.0)
        self.assertEqual(self.get_periods(), [10.0, 50.0, 0.0, 0.0])

    def test_02_job_usage_matches_sum_of_periods_after_run_1(self):
        self.assertEqual(self.get_job_usage(), sum(self.get_periods()))

    # run 2 (t=1175): job 2 ran for 20 seconds and finished at t=1170, in the
    # same half-life period as job 1, so its usage gets added to whatever is
    # already in period 0
    #
    # after this update, the usage for user1 should look like:
    # p0 | p1 | p2 | p3
    # -----------------
    # 30 | 50 | 0  | 0
    @mock.patch("time.time", mock.MagicMock(return_value=1175))
    def test_03_new_job_in_same_half_life_period(self):
        self.add_job("2", t_run=1150, t_inactive=1170)
        j.update_job_usage(conn)

        self.assertEqual(self.get_job_usage(), 80.0)
        self.assertEqual(self.get_periods(), [30.0, 50.0, 0.0, 0.0])

    def test_04_job_usage_matches_sum_of_periods_after_run_2(self):
        self.assertEqual(self.get_job_usage(), sum(self.get_periods()))

    # run 3 (t=1250): no new jobs, and another half-life period has passed, so
    # every period is shifted and decayed
    #
    # after this update, the usage for user1 should look like:
    # p0 | p1 | p2 | p3
    # -----------------
    # 0  | 15 | 25 | 0
    @mock.patch("time.time", mock.MagicMock(return_value=1250))
    def test_05_no_jobs_in_new_half_life_period(self):
        j.update_job_usage(conn)

        self.assertEqual(self.get_job_usage(), 40.0)
        self.assertEqual(self.get_periods(), [0.0, 15.0, 25.0, 0.0])

    def test_06_job_usage_matches_sum_of_periods_after_run_3(self):
        self.assertEqual(self.get_job_usage(), sum(self.get_periods()))

    # the bank's usage is aggregated from its associations, so it should also
    # reflect the correct (non-inflated) value
    def test_07_check_job_usage_value_bank_A(self):
        cur.execute("SELECT job_usage FROM bank_table WHERE bank='A'")
        self.assertEqual(cur.fetchone()[0], 40.0)

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
