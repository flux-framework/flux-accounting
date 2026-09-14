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


def insert_job(
    db_conn,
    job_id,
    project,
    t_run,
    t_inactive,
    ncores=1,
    ngpus=0,
    resources=None,
):
    children = {"core": "0" if ncores == 1 else f"0-{ncores - 1}"}
    if ngpus == 1:
        children["gpu"] = "0"
    elif ngpus > 1:
        children["gpu"] = f"0-{ngpus - 1}"

    if resources is None:
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
    db_conn.execute(
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
    db_conn.commit()


class TestProjectUsage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(cls.dbname)

        cls.conn = sqlite3.connect(cls.dbname, timeout=60)
        cls.conn.row_factory = sqlite3.Row

        b.add_bank(cls.conn, "root", 1)
        b.add_bank(cls.conn, "A", 1, "root")
        p.add_project(cls.conn, "P1")
        p.add_project(cls.conn, "P2")
        p.add_project(cls.conn, "unused")
        u.add_user(cls.conn, username="user1", uid=50001, bank="A")
        cls.conn.execute("UPDATE config_table SET value='0.5' WHERE key='core_weight'")
        cls.conn.execute("UPDATE config_table SET value='2.0' WHERE key='gpu_weight'")
        cls.conn.commit()

        insert_job(cls.conn, 1, "P1", 10, 20, ncores=2, ngpus=1)
        insert_job(cls.conn, 2, "P2", 10, 30, ncores=4)
        insert_job(cls.conn, 3, "*", 10, 40)

    def test_01_update_usage_increments_project_usage(self):
        jobs.update_job_usage(self.conn)

        rows = self.conn.execute("SELECT project, usage FROM project_table").fetchall()
        usage = {row["project"]: row["usage"] for row in rows}
        self.assertEqual(usage["P1"], 40.0)
        self.assertEqual(usage["P2"], 60.0)
        self.assertEqual(usage["*"], 45.0)
        self.assertEqual(usage["unused"], 0.0)

    def test_02_update_usage_does_not_double_count_project_usage(self):
        jobs.update_job_usage(self.conn)

        rows = self.conn.execute("SELECT project, usage FROM project_table").fetchall()
        usage = {row["project"]: row["usage"] for row in rows}
        self.assertEqual(usage["P1"], 40.0)
        self.assertEqual(usage["P2"], 60.0)
        self.assertEqual(usage["*"], 45.0)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.dbname)


class TestRebuildProjectUsage(unittest.TestCase):
    def setUp(self):
        self.dbname = (
            f"TestDB_rebuild_{self._testMethodName}_{round(time.time() * 1000)}.db"
        )
        c.create_db(self.dbname)
        self.conn = sqlite3.connect(self.dbname, timeout=60)
        self.conn.row_factory = sqlite3.Row

        b.add_bank(self.conn, "root", 1)
        b.add_bank(self.conn, "A", 1, "root")
        p.add_project(self.conn, "P1")
        p.add_project(self.conn, "P2")
        p.add_project(self.conn, "unused")
        u.add_user(self.conn, username="user1", uid=50001, bank="A")
        self.conn.execute("UPDATE config_table SET value='0.5' WHERE key='core_weight'")
        self.conn.execute("UPDATE config_table SET value='2.0' WHERE key='gpu_weight'")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.remove(self.dbname)

    def project_usage(self):
        rows = self.conn.execute("SELECT project, usage FROM project_table").fetchall()
        return {row["project"]: row["usage"] for row in rows}

    def test_rebuild_sets_checkpoint_for_pending_jobs(self):
        insert_job(self.conn, 1, "P1", 10, 20, ncores=2, ngpus=1)
        self.conn.execute("UPDATE project_table SET usage=7.0 WHERE project='P1'")
        self.conn.commit()

        jobs.rebuild_project_usage(self.conn)
        self.assertEqual(self.project_usage()["P1"], 40.0)
        state = self.conn.execute(
            "SELECT last_job_timestamp FROM project_usage_state WHERE project='P1'"
        ).fetchone()[0]
        self.assertEqual(state, 20.0)

        jobs.update_job_usage(self.conn)
        self.assertEqual(self.project_usage()["P1"], 40.0)
        jobs.rebuild_project_usage(self.conn)
        self.assertEqual(self.project_usage()["P1"], 40.0)

        insert_job(self.conn, 2, "P1", 30, 40)
        jobs.update_job_usage(self.conn)
        self.assertEqual(self.project_usage()["P1"], 55.0)
        state = self.conn.execute(
            "SELECT last_job_timestamp FROM project_usage_state WHERE project='P1'"
        ).fetchone()[0]
        self.assertEqual(state, 40.0)

    def test_rebuild_includes_jobs_ignored_by_regular_updates(self):
        insert_job(self.conn, 1, "P1", 10, 20, ncores=2, ngpus=1)
        jobs.update_job_usage(self.conn)

        self.conn.execute("UPDATE bank_table SET ignore_older_than=100 WHERE bank='A'")
        self.conn.execute("UPDATE project_table SET usage=999.0")
        self.conn.commit()
        insert_job(self.conn, 2, "P2", 30, 40, ncores=4)

        jobs.rebuild_project_usage(self.conn)
        usage = self.project_usage()
        self.assertEqual(usage["P1"], 40.0)
        self.assertEqual(usage["P2"], 30.0)
        self.assertEqual(usage["unused"], 0.0)

    def test_rebuild_reports_skipped_jobs(self):
        insert_job(self.conn, 1, "", 10, 20)
        insert_job(self.conn, 2, "removed", 10, 20)
        insert_job(self.conn, 3, "P1", 10, 20, resources="invalid")

        with self.assertLogs(jobs.LOGGER, level="WARNING") as logs:
            skipped = jobs.rebuild_project_usage(self.conn)

        self.assertEqual(skipped["missing_project"], 1)
        self.assertEqual(skipped["invalid_resources"], 1)
        self.assertEqual(skipped["unregistered_projects"], {"removed": 1})
        self.assertTrue(
            any("project 'removed' is not registered" in x for x in logs.output)
        )

    def test_rebuild_rolls_back_on_database_error(self):
        self.conn.execute("UPDATE project_table SET usage=7.0 WHERE project='P1'")
        self.conn.execute("""
            CREATE TRIGGER reject_project_usage
            BEFORE UPDATE OF usage ON project_table
            BEGIN
                SELECT RAISE(ABORT, 'project update rejected');
            END
            """)
        self.conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            jobs.rebuild_project_usage(self.conn)
        self.assertEqual(self.project_usage()["P1"], 7.0)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
