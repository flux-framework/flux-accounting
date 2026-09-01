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

from unittest import mock

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import db_info_subcommands as d


def insert_job(conn, job_id, userid, bank, t_submit, t_run, t_inactive, cores="0-3"):
    R = json.dumps(
        {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": cores, "gpu": "0"}}],
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


def usage(conn, user, bank="A"):
    row = conn.execute(
        "SELECT job_usage FROM association_table WHERE username=? AND bank=?",
        (user, bank),
    ).fetchone()
    return row[0]


class TestContinuousUsage(unittest.TestCase):
    # Priority Decay Half-Life: 100 seconds, decay_factor: 0.5.
    # In continuous mode, usage decays by decay_factor ** (elapsed / half_life),
    # so 100 seconds of elapsed time halves the usage.
    @classmethod
    @mock.patch("time.time", mock.MagicMock(return_value=0))
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(
            self.dbname,
            priority_decay_half_life="100s",
            priority_usage_reset_period="400s",
        )
        global conn
        conn = sqlite3.connect(self.dbname, timeout=60)

        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        b.add_bank(conn, "B", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)
        u.add_user(conn, username="user2", bank="A", uid=50002)
        u.add_user(conn, username="user3", bank="B", uid=50003)

        # switch to continuous mode; this establishes a checkpoint at t=0
        d.edit_config(conn, ["usage_calculation_mode=continuous"])

    # A completed job contributes weighted resource-seconds, decayed from its own
    # t_inactive. A 1-node, 100-second job completing at t=100, updated at t=100,
    # has zero elapsed decay -> usage == 100.
    @mock.patch("time.time", mock.MagicMock(return_value=100))
    def test_01_first_job(self):
        insert_job(conn, 1, 50001, "A", 0, 0, 100)
        jobs.update_job_usage(conn)
        self.assertAlmostEqual(usage(conn, "user1"), 100.0, places=4)

    # With no new jobs, an update one half-life later halves existing usage.
    @mock.patch("time.time", mock.MagicMock(return_value=200))
    def test_02_no_job_decay(self):
        jobs.update_job_usage(conn)
        self.assertAlmostEqual(usage(conn, "user1"), 50.0, places=4)

    # A fractional half-life decays proportionally: 50 more seconds -> * 0.5**0.5.
    @mock.patch("time.time", mock.MagicMock(return_value=250))
    def test_03_fractional_decay(self):
        jobs.update_job_usage(conn)
        self.assertAlmostEqual(usage(conn, "user1"), 50.0 * (0.5**0.5), places=4)

    # view-user --job-usage exposes only the mirrored period-0 scalar; all older
    # periods are zero.
    @mock.patch("time.time", mock.MagicMock(return_value=250))
    def test_04_view_user_period0(self):
        breakdown = ast.literal_eval(u.view_user(conn, user="user1", job_usage=True))
        self.assertAlmostEqual(breakdown[0]["value"], 50.0 * (0.5**0.5), places=4)
        for row in breakdown[1:]:
            self.assertEqual(row["value"], 0.0)

    # Cadence invariance: decaying from the same start to the same end yields the
    # same result whether done in one step or many.
    def test_05_cadence_invariance(self):
        dbname = f"TestCadence_{round(time.time())}.db"
        with mock.patch("time.time", mock.MagicMock(return_value=0)):
            c.create_db(dbname, priority_decay_half_life="100s")
            cconn = sqlite3.connect(dbname, timeout=60)
            b.add_bank(cconn, "root", 1)
            b.add_bank(cconn, "A", 1, "root")
            u.add_user(cconn, username="u", bank="A", uid=60001)
            d.edit_config(cconn, ["usage_calculation_mode=continuous"])
        with mock.patch("time.time", mock.MagicMock(return_value=100)):
            insert_job(cconn, 1, 60001, "A", 0, 0, 100)
            jobs.update_job_usage(cconn)
        # one big step: t=100 -> t=500 (four half-lives)
        with mock.patch("time.time", mock.MagicMock(return_value=500)):
            jobs.update_job_usage(cconn)
        one_step = usage(cconn, "u")
        cconn.close()
        os.remove(dbname)

        dbname = f"TestCadence2_{round(time.time())}.db"
        with mock.patch("time.time", mock.MagicMock(return_value=0)):
            c.create_db(dbname, priority_decay_half_life="100s")
            cconn = sqlite3.connect(dbname, timeout=60)
            b.add_bank(cconn, "root", 1)
            b.add_bank(cconn, "A", 1, "root")
            u.add_user(cconn, username="u", bank="A", uid=60001)
            d.edit_config(cconn, ["usage_calculation_mode=continuous"])
        with mock.patch("time.time", mock.MagicMock(return_value=100)):
            insert_job(cconn, 1, 60001, "A", 0, 0, 100)
            jobs.update_job_usage(cconn)
        # four small steps of one half-life each
        for t in (200, 300, 400, 500):
            with mock.patch("time.time", mock.MagicMock(return_value=t)):
                jobs.update_job_usage(cconn)
        many_steps = usage(cconn, "u")
        cconn.close()
        os.remove(dbname)

        self.assertAlmostEqual(one_step, many_steps, places=4)

    # A future-dated completion is excluded until update time passes it, so it
    # remains eligible for a later update.
    def test_06_future_job_excluded(self):
        # a 1-node, 100-second job whose t_inactive is in the future
        with mock.patch("time.time", mock.MagicMock(return_value=300)):
            insert_job(conn, 10, 50002, "A", 400, 400, 500)
            jobs.update_job_usage(conn)
            # future completion is excluded; user2 has no usage yet
            self.assertAlmostEqual(usage(conn, "user2"), 0.0, places=4)
        with mock.patch("time.time", mock.MagicMock(return_value=500)):
            jobs.update_job_usage(conn)
            # updating at the completion time picks it up with zero elapsed decay
            self.assertAlmostEqual(usage(conn, "user2"), 100.0, places=4)

    # Bank usage rolls up: the root bank aggregates all associations.
    @mock.patch("time.time", mock.MagicMock(return_value=250))
    def test_07_bank_rollup(self):
        root = conn.execute(
            "SELECT job_usage FROM bank_table WHERE bank='root'"
        ).fetchone()[0]
        total = sum(
            r[0]
            for r in conn.execute("SELECT job_usage FROM association_table").fetchall()
        )
        self.assertAlmostEqual(root, total, places=4)

    # Editing decay parameters in continuous mode must not clear usage or rebuild
    # bins.
    @mock.patch("time.time", mock.MagicMock(return_value=250))
    def test_08_edit_params_preserves_usage(self):
        before = usage(conn, "user1")
        d.edit_config(conn, ["priority_decay_half_life=200s"])
        self.assertAlmostEqual(usage(conn, "user1"), before, places=4)
        d.edit_config(conn, ["decay_factor=0.25"])
        self.assertAlmostEqual(usage(conn, "user1"), before, places=4)

    # Switching continuous -> periodic preserves the scalar as period 0 and does
    # not replay jobs.
    @mock.patch("time.time", mock.MagicMock(return_value=300))
    def test_09_switch_to_periodic(self):
        before = usage(conn, "user1")
        d.edit_config(conn, ["usage_calculation_mode=periodic"])
        self.assertAlmostEqual(usage(conn, "user1"), before, places=4)
        breakdown = ast.literal_eval(u.view_user(conn, user="user1", job_usage=True))
        self.assertAlmostEqual(breakdown[0]["value"], before, places=4)

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
