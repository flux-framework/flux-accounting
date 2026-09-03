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
import json
import os
import sqlite3
import time
import unittest

from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import create_db as c
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import project_subcommands as p
from fluxacct.accounting import user_subcommands as u


class TestProjectUsage(unittest.TestCase):
    @staticmethod
    def insert_job(job_id, project, t_run, t_inactive, ncores=1, ngpus=0):
        children = {"core": "0" if ncores == 1 else f"0-{ncores - 1}"}
        if ngpus == 1:
            children["gpu"] = "0"
        elif ngpus > 1:
            children["gpu"] = f"0-{ngpus - 1}"

        resources = json.dumps(
            {
                "version": 1,
                "execution": {
                    "R_lite": [{"rank": "0", "children": children}],
                    "starttime": 0,
                    "expiration": 0,
                    "nodelist": ["fluke[0]"],
                },
            }
        )
        jobspec = json.dumps({"attributes": {"system": {"bank": "A"}}})
        conn.execute(
            """
            INSERT INTO jobs
            (id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, project,
            bank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                50001,
                0,
                t_run,
                t_inactive,
                "0",
                resources,
                jobspec,
                project,
                "A",
            ),
        )
        conn.commit()

    @classmethod
    def setUpClass(cls):
        cls.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(cls.dbname)

        global conn
        conn = sqlite3.connect(cls.dbname, timeout=60)
        conn.row_factory = sqlite3.Row

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        p.add_project(conn, "P1")
        p.add_project(conn, "P2")
        p.add_project(conn, "unused")
        u.add_user(conn, username="user1", uid=50001, bank="A")
        conn.execute("UPDATE config_table SET value='0.5' WHERE key='core_weight'")
        conn.execute("UPDATE config_table SET value='2.0' WHERE key='gpu_weight'")
        conn.commit()

        cls.insert_job(1, "P1", 10, 20, ncores=2, ngpus=1)
        cls.insert_job(2, "P2", 10, 30, ncores=4)
        cls.insert_job(3, "*", 10, 40)

    def test_01_update_usage_increments_project_usage(self):
        jobs.update_job_usage(conn)

        rows = conn.execute("SELECT project, usage FROM project_table").fetchall()
        usage = {row["project"]: row["usage"] for row in rows}
        self.assertEqual(usage["P1"], 40.0)
        self.assertEqual(usage["P2"], 60.0)
        self.assertEqual(usage["*"], 45.0)
        self.assertEqual(usage["unused"], 0.0)

    def test_02_update_usage_does_not_double_count_project_usage(self):
        jobs.update_job_usage(conn)

        rows = conn.execute("SELECT project, usage FROM project_table").fetchall()
        usage = {row["project"]: row["usage"] for row in rows}
        self.assertEqual(usage["P1"], 40.0)
        self.assertEqual(usage["P2"], 60.0)
        self.assertEqual(usage["*"], 45.0)

    @classmethod
    def tearDownClass(cls):
        conn.close()
        os.remove(cls.dbname)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
