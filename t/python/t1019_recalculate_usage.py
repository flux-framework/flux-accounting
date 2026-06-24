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
import json
import ast
from collections import defaultdict

from unittest import mock

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting import db_info_subcommands as d


class TestAccountingCLI(unittest.TestCase):
    @staticmethod
    def insert_job(job_id, userid, bank, t_submit, t_run, t_inactive):
        R = json.dumps(
            {
                "version": 1,
                "execution": {
                    "R_lite": [{"rank": "0", "children": {"core": "0-3", "gpu": "0"}}],
                    "starttime": 0,
                    "expiration": 0,
                    "nodelist": ["fluke[0]"],
                },
            }
        )
        jobspec = json.dumps({"attributes": {"system": {"bank": bank}}})
        conn.execute(
            "INSERT INTO jobs "
            "(id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, userid, t_submit, t_run, t_inactive, "0", R, jobspec, bank),
        )
        conn.commit()

    @classmethod
    @mock.patch("time.time", mock.MagicMock(return_value=0))
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        # the database is set up with the following parameters:
        # Priority Decay Half-Life: 15 minutes (900 seconds)
        # Priority Usage Reset Period: 1 hour (3600 seconds)
        # So, for each association, a total of 4 rows will be inserted into
        # job_usage_per_association_table where each row represents a 15-minute period.
        # For the sake of these tests, time starts at 0, which means that each row
        # represents the following number of seconds:
        #
        # p0    | p1       | p2         | p3
        # -----------------------------------------
        # 0-900 | 901-1800 | 1801-2700  | 2701-3600
        c.create_db(
            self.dbname,
            priority_decay_half_life="15m",
            priority_usage_reset_period="1h",
        )
        global conn
        global cursor

        conn = sqlite3.connect(self.dbname, timeout=60)
        cursor = conn.cursor()

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)

        # insert 1 1-node, 100-second-long job into DB
        self.insert_job(1, 50001, "A", 1, 499, 599)

        job_records = j.convert_to_obj(j.get_jobs(conn))
        # convert jobs to dictionary to be referenced in unit tests below
        user_jobs = defaultdict(list)
        for job in job_records:
            key = (job.userid, job.bank)
            user_jobs[key].append(job)

        conn.commit()

    # If job usage is updated in the same period as the job above got completed, then it
    # will show up in the first usage bin
    @mock.patch("time.time", mock.MagicMock(return_value=600))
    def test_01_update_usage(self):
        jobs.update_job_usage(conn)
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        # association as a total job usage of 100.0
        self.assertIn("100.0", total_usage)
        # association has the following job usage breakdown:
        #
        # p0  | p1 | p2 | p3
        # ------------------
        # 100 | 0  | 0  | 0
        job_usage_breakdown = ast.literal_eval(
            u.view_user(conn, user="user1", job_usage=True)
        )
        self.assertEqual(len(job_usage_breakdown), 4)
        self.assertEqual(job_usage_breakdown[0]["value"], 100.0)
        self.assertEqual(job_usage_breakdown[1]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[2]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[3]["value"], 0.0)

    # Reconfigure job_usage_per_association_table to have the following parameters:
    # Priority Decay Half-Life: 400 seconds
    # Priority Usage Reset Period: 1200 seconds
    # So, for each association, a total of 3 rows will be inserted into
    # job_usage_per_association_table where each row represents a 400-second period:
    #
    # The usage for every association will be reset to 0.0 and job usage will be
    # calculated from a fresh start.
    @mock.patch("builtins.input", return_value="y")
    @mock.patch("time.time", mock.MagicMock(return_value=1600))
    def test_02_reconfigure_bins(self, mock_input):
        d.edit_config(
            conn, ["priority_usage_reset_period=1200s", "priority_decay_half_life=400s"]
        )
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 1200", result)
        self.assertIn("priority_decay_half_life    | 400", result)

        # make sure association has a total of 3 rows in job_usage_per_association_table
        num_rows = cursor.execute(
            "SELECT * FROM job_usage_per_association_table WHERE username='user1'"
        ).fetchall()
        self.assertEqual(len(num_rows), 3)

        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("0.0", total_usage)
        # association has the following job usage breakdown:
        #
        # p0  | p1 | p2 |
        # ---------------
        # 0   | 0  | 0  |
        job_usage_breakdown = ast.literal_eval(
            u.view_user(conn, user="user1", job_usage=True)
        )
        self.assertEqual(len(job_usage_breakdown), 3)
        self.assertEqual(job_usage_breakdown[0]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[1]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[2]["value"], 0.0)

    # The total usage for the association will include all jobs seen since last
    # reconfiguration
    @mock.patch("time.time", mock.MagicMock(return_value=2500))
    def test_03_insert_new_job(self):
        # insert another 1-node, 1-second-long job
        self.insert_job(2, 50001, "A", 100, 2300, 2400)
        jobs.update_job_usage(conn)

        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("100.0", total_usage)
        job_usage_breakdown = ast.literal_eval(
            u.view_user(conn, user="user1", job_usage=True)
        )
        self.assertEqual(len(job_usage_breakdown), 3)
        self.assertEqual(job_usage_breakdown[0]["value"], 100.0)
        self.assertEqual(job_usage_breakdown[1]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[2]["value"], 0.0)

    # If "n" is input after editing some of the configuration parameters, the changes are
    # not committed and rolled back
    @mock.patch("builtins.input", return_value="n")
    @mock.patch("time.time", mock.MagicMock(return_value=1600))
    def test_04_reconfigure_bins_deny_confirm(self, mock_input):
        d.edit_config(
            conn, ["priority_usage_reset_period=6h", "priority_decay_half_life=1h"]
        )
        # make sure parameters remain the same as before the above edit_config() call
        result = d.list_configs(conn)
        self.assertIn("priority_usage_reset_period | 1200", result)
        self.assertIn("priority_decay_half_life    | 400", result)

    # decay_factor can be changed and the amount of decay applied to past jobs will be
    # different
    @mock.patch("builtins.input", return_value="y")
    @mock.patch("time.time", mock.MagicMock(return_value=2600))
    def test_05_edit_decay_factor(self, mock_input):
        d.edit_config(conn, ["decay_factor=0.1"])
        result = d.list_configs(conn)
        print(result)
        self.assertIn("decay_factor                | 0.1", result)

    @mock.patch("time.time", mock.MagicMock(return_value=3200))
    def test_06_insert_new_job(self):
        # insert another 1-node, 1000-second-long job
        self.insert_job(3, 50001, "A", 100, 2100, 3100)
        jobs.update_job_usage(conn)

        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("1000.0", total_usage)
        job_usage_breakdown = ast.literal_eval(
            u.view_user(conn, user="user1", job_usage=True)
        )
        self.assertEqual(len(job_usage_breakdown), 3)
        self.assertEqual(job_usage_breakdown[0]["value"], 1000.0)
        self.assertEqual(job_usage_breakdown[1]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[2]["value"], 0.0)

    @mock.patch("time.time", mock.MagicMock(return_value=3600))
    def test_07_update_usage_new_decay_factor(self):
        jobs.update_job_usage(conn)
        total_usage = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("100.0", total_usage)
        job_usage_breakdown = ast.literal_eval(
            u.view_user(conn, user="user1", job_usage=True)
        )
        self.assertEqual(len(job_usage_breakdown), 3)
        self.assertEqual(job_usage_breakdown[0]["value"], 0.0)
        self.assertEqual(job_usage_breakdown[1]["value"], 100.0)
        self.assertEqual(job_usage_breakdown[2]["value"], 0.0)

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
