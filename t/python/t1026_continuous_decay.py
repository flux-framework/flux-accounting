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
from unittest import mock

from fluxacct.database import create as c
from fluxacct.database import info as d
from fluxacct.entities import associations as u
from fluxacct.entities import banks as b
from fluxacct.jobs import usage
from fluxacct.jobs.calculators import continuous


def insert_job(conn, job_id, userid, bank, t_run, t_inactive):
    resources = json.dumps(
        {
            "version": 1,
            "execution": {
                "R_lite": [{"rank": "0", "children": {"core": "0"}}],
                "starttime": 0,
                "expiration": 0,
                "nodelist": ["fluke[0]"],
            },
        }
    )
    jobspec = json.dumps({"attributes": {"system": {"bank": bank}}})
    conn.execute(
        """
        INSERT INTO jobs
        (id, userid, t_submit, t_run, t_inactive, ranks, R, jobspec, bank)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, userid, 0, t_run, t_inactive, "0", resources, jobspec, bank),
    )
    conn.commit()


class TestContinuousDecay(unittest.TestCase):
    def setUp(self):
        self.dbname = (
            f"TestDB_continuous_{self._testMethodName}_{round(time.time() * 1000)}.db"
        )
        with mock.patch("time.time", return_value=1000.0):
            c.create_db(self.dbname, decay_method="continuous")
        self.conn = sqlite3.connect(self.dbname, timeout=60)
        self.conn.row_factory = sqlite3.Row
        b.add_bank(self.conn, "root", 1)
        b.add_bank(self.conn, "A", 1, "root")
        u.add_user(self.conn, username="user1", uid=50001, bank="A")
        self.conn.execute(
            "UPDATE config_table SET value='100' "
            "WHERE key='priority_decay_half_life'"
        )
        self.conn.execute(
            "UPDATE config_table SET value='400' "
            "WHERE key='priority_usage_reset_period'"
        )
        self.conn.execute(
            "UPDATE config_table SET value='0.5' WHERE key='decay_factor'"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.remove(self.dbname)

    def association_usage(self):
        return self.conn.execute("""
            SELECT job_usage FROM association_table
            WHERE username='user1' AND bank='A'
            """).fetchone()[0]

    def period_rows(self):
        return self.conn.execute("""
            SELECT period, value FROM job_usage_per_association_table
            WHERE username='user1' AND bank='A'
            ORDER BY period
            """).fetchall()

    def test_01_retention_factor_uses_elapsed_time(self):
        self.assertAlmostEqual(continuous.retention_factor(100.0, 100.0, 0.5), 0.5)
        self.assertAlmostEqual(continuous.retention_factor(200.0, 100.0, 0.5), 0.25)
        self.assertAlmostEqual(continuous.retention_factor(50.0, 100.0, 0.25), 0.5)

    def test_02_decay_applies_without_new_jobs(self):
        self.conn.execute("""
            UPDATE association_table SET job_usage=1000.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.commit()

        with mock.patch("time.time", return_value=1100.0):
            usage.update_job_usage(self.conn)

        self.assertEqual(self.association_usage(), 500.0)
        rows = self.period_rows()
        self.assertEqual(len(rows), 0)

    def test_03_detailed_breakdown_is_unavailable(self):
        with self.assertRaisesRegex(
            ValueError,
            "detailed job usage breakdowns are unavailable in continuous mode",
        ):
            u.view_user(self.conn, user="user1", job_usage=True)

    def test_04_completed_jobs_are_added_once_then_decayed(self):
        insert_job(self.conn, 1, 50001, "A", 1050.0, 1100.0)

        with mock.patch("time.time", return_value=1200.0):
            usage.update_job_usage(self.conn)
        self.assertEqual(self.association_usage(), 25.0)

        last_job_timestamp = self.conn.execute("""
            SELECT last_job_timestamp FROM job_usage_factor_table
            WHERE username='user1' AND bank='A'
            """).fetchone()[0]
        self.assertEqual(last_job_timestamp, 1100.0)

        with mock.patch("time.time", return_value=1300.0):
            usage.update_job_usage(self.conn)
        self.assertEqual(self.association_usage(), 12.5)

    def test_05_decay_parameter_edit_resets_continuous_usage(self):
        self.conn.execute("""
            UPDATE association_table SET job_usage=1000.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.execute("UPDATE bank_table SET job_usage=1000.0 WHERE bank='A'")
        self.conn.commit()

        with mock.patch("time.time", return_value=1100.0):
            d.edit_config(self.conn, ["priority_decay_half_life=10"])

        self.assertEqual(self.association_usage(), 0.0)
        bank_usage = self.conn.execute(
            "SELECT job_usage FROM bank_table WHERE bank='A'"
        ).fetchone()[0]
        self.assertEqual(bank_usage, 0.0)
        last_update = self.conn.execute(
            "SELECT last_update FROM usage_decay_state WHERE cluster='cluster'"
        ).fetchone()[0]
        self.assertEqual(last_update, 1100.0)

        with mock.patch("time.time", return_value=1110.0):
            usage.update_job_usage(self.conn)

        self.assertEqual(self.association_usage(), 0.0)

    def test_06_reset_period_edit_preserves_continuous_usage(self):
        self.conn.execute("""
            UPDATE association_table SET job_usage=1000.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.commit()

        d.edit_config(self.conn, ["priority_usage_reset_period=800"])

        self.assertEqual(self.association_usage(), 1000.0)
        value = self.conn.execute(
            "SELECT value FROM config_table WHERE key='priority_usage_reset_period'"
        ).fetchone()[0]
        self.assertEqual(float(value), 800.0)

    def test_07_continuous_reset_flags_latch(self):
        self.conn.execute("""
            UPDATE association_table SET job_usage=1000.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.commit()

        d.edit_config(
            self.conn,
            ["priority_decay_half_life=10", "priority_usage_reset_period=800"],
        )

        self.assertEqual(self.association_usage(), 0.0)

    def test_08_mode_switches_preserve_then_reset_expected_usage(self):
        self.conn.execute(
            "UPDATE config_table SET value='periodic' " "WHERE key='decay_method'"
        )
        self.conn.execute("""
            UPDATE association_table SET job_usage=42.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.execute("UPDATE bank_table SET job_usage=42.0 WHERE bank='A'")
        self.conn.commit()

        with mock.patch("time.time", return_value=2000.0):
            d.edit_config(self.conn, ["decay_method=continuous"])

        self.assertEqual(self.association_usage(), 42.0)
        rows = self.period_rows()
        self.assertEqual(len(rows), 0)
        last_update = self.conn.execute(
            "SELECT last_update FROM usage_decay_state WHERE cluster='cluster'"
        ).fetchone()[0]
        self.assertEqual(last_update, 2000.0)

        d.edit_config(self.conn, ["decay_method=periodic"])
        rows = self.period_rows()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["value"] == 0.0 for row in rows))
        self.assertEqual(self.association_usage(), 0.0)
        bank_usage = self.conn.execute(
            "SELECT job_usage FROM bank_table WHERE bank='A'"
        ).fetchone()[0]
        self.assertEqual(bank_usage, 0.0)

    def test_09_switch_to_continuous_with_param_edit_preserves_usage(self):
        self.conn.execute(
            "UPDATE config_table SET value='periodic' WHERE key='decay_method'"
        )
        self.conn.execute("""
            UPDATE association_table SET job_usage=42.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.execute("UPDATE bank_table SET job_usage=42.0 WHERE bank='A'")
        self.conn.commit()

        with mock.patch("time.time", return_value=2000.0):
            d.edit_config(
                self.conn, ["decay_method=continuous", "priority_decay_half_life=10"]
            )

        # the mode switch takes precedence over the half-life edit, so usage is
        # preserved instead of being reset
        self.assertEqual(self.association_usage(), 42.0)
        bank_usage = self.conn.execute(
            "SELECT job_usage FROM bank_table WHERE bank='A'"
        ).fetchone()[0]
        self.assertEqual(bank_usage, 42.0)
        half_life = self.conn.execute(
            "SELECT value FROM config_table WHERE key='priority_decay_half_life'"
        ).fetchone()[0]
        self.assertEqual(float(half_life), 10.0)
        self.assertEqual(len(self.period_rows()), 0)
        last_update = self.conn.execute(
            "SELECT last_update FROM usage_decay_state WHERE cluster='cluster'"
        ).fetchone()[0]
        self.assertEqual(last_update, 2000.0)

        # the preserved value decays with the new half-life: one half-life later,
        # half of it remains
        with mock.patch("time.time", return_value=2010.0):
            usage.update_job_usage(self.conn)
        self.assertEqual(self.association_usage(), 21.0)

    def test_10_update_initializes_missing_decay_state(self):
        # an upgraded DB has an empty usage_decay_state table until the first
        # continuous update (or a switch to continuous mode) creates the row
        self.conn.execute("DELETE FROM usage_decay_state")
        self.conn.execute("""
            UPDATE association_table SET job_usage=1000.0
            WHERE username='user1' AND bank='A'
            """)
        self.conn.commit()

        with mock.patch("time.time", return_value=3000.0):
            with self.assertLogs("fluxacct.jobs.usage", level="INFO") as logs:
                usage.update_job_usage(self.conn)
        self.assertIn(
            "initialized continuous job usage decay state",
            "\n".join(logs.output),
        )

        last_update = self.conn.execute(
            "SELECT last_update FROM usage_decay_state WHERE cluster='cluster'"
        ).fetchone()[0]
        self.assertEqual(last_update, 3000.0)
        # the first update only starts the decay clock; nothing decays yet
        self.assertEqual(self.association_usage(), 1000.0)

        # the next update decays from the initialized clock
        with mock.patch("time.time", return_value=3100.0):
            usage.update_job_usage(self.conn)
        self.assertEqual(self.association_usage(), 500.0)

    def test_11_switch_to_continuous_rejects_stored_bad_decay_factor(self):
        self.conn.execute(
            "UPDATE config_table SET value='periodic' WHERE key='decay_method'"
        )
        # Simulate a DB created by the old edit-config validation, which allowed
        # decay_factor=1.
        self.conn.execute("UPDATE config_table SET value='1' WHERE key='decay_factor'")
        self.conn.commit()

        with self.assertRaisesRegex(
            ValueError, "decay_factor must be a floating-point value between 0 and 1"
        ):
            d.edit_config(self.conn, ["decay_method=continuous"])

        method = self.conn.execute(
            "SELECT value FROM config_table WHERE key='decay_method'"
        ).fetchone()[0]
        self.assertEqual(method, "periodic")

    def test_12_human_readable_bank_cutoff_allows_newer_job(self):
        b.edit_bank(
            self.conn,
            bank="A",
            ignore_older_than="Jan 1, 1970 8am",
        )
        insert_job(self.conn, 12, 50001, "A", 9980025.0, 9980050.0)

        with mock.patch("time.time", return_value=9980100.0):
            usage.update_job_usage(self.conn)

        self.assertGreater(self.association_usage(), 0.0)
        last_job_timestamp = self.conn.execute("""
            SELECT last_job_timestamp FROM job_usage_factor_table
            WHERE username='user1' AND bank='A'
            """).fetchone()[0]
        self.assertEqual(last_job_timestamp, 9980050.0)


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
