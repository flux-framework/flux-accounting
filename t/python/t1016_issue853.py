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
from collections import defaultdict

from unittest import mock

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import jobs_table_subcommands as j


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
            "INSERT INTO jobs (id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, userid, t_submit, t_run, t_inactive, "0", R, jobspec, bank),
        )
        conn.commit()

    @classmethod
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global conn

        conn = sqlite3.connect(self.dbname, timeout=60)

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)

        self.insert_job(1, 50001, "A", 100, 2000, 3000)

        job_records = j.convert_to_obj(j.get_jobs(conn))
        # convert jobs to dictionary to be referenced in unit tests below
        user_jobs = defaultdict(list)
        for job in job_records:
            key = (job.userid, job.bank)
            user_jobs[key].append(job)

        conn.commit()

    # Call update_job_usage so that the banks get their job usage value updated;
    # user1 should have a total usage of 1000 because they ran for 1000 seconds on just
    # one node.
    @mock.patch("time.time", mock.MagicMock(return_value=0))
    def test_01_call_update_usage(self):
        jobs.update_job_usage(conn)
        result = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("1000", result)

    # Insert a new job with a t_run *earlier* than the first job but with a t_inactive
    # *later* than the first job's completion time.
    def test_03_add_new_job(self):
        self.insert_job(2, 50001, "A", 100, 1000, 5000)
        jobs.update_job_usage(conn)

    # update_usage should pick up the new job if even though it has a later t_inactive
    # timestamp, thus giving the new association a total job usage value of 5000 because
    # the second job has a total usage of 4000.
    @mock.patch("time.time", mock.MagicMock(return_value=0))
    def test_04_call_update_usage_again(self):
        result = u.view_user(conn, user="user1", format_string="{job_usage}")
        self.assertIn("5000", result)

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
