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
import io
import os
import sqlite3
import tempfile
import unittest

from unittest import mock

from fluxacct.database import create as c
from fluxacct.entities import associations as u
from fluxacct.entities import banks as b
from fluxacct.jobs import usage as j


class TestUseridUsageRepair(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.conn = self.create_fixture("periodic")

    def create_fixture(self, mode):
        dbname = os.path.join(self.tmpdir.name, f"{mode}.db")
        c.create_db(
            dbname,
            priority_decay_half_life="100s",
            priority_usage_reset_period="400s",
            decay_method=mode,
        )
        conn = sqlite3.connect(dbname)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        b.add_bank(conn, "B", 1, "root")
        u.add_user(conn, username="user1", uid=1001, bank="A")
        u.add_user(conn, username="user1", uid=3003, bank="B")
        u.add_user(conn, username="user2", uid=4004, bank="A")
        with conn:
            conn.execute("UPDATE association_table SET job_usage=1500")
            conn.execute("UPDATE job_usage_factor_table SET last_job_timestamp=42")
            conn.execute(
                "UPDATE t_half_life_period_table SET end_half_life_period=1000"
            )
            conn.executemany(
                "UPDATE job_usage_per_association_table SET value=? WHERE period=?",
                [(1000, 0), (500, 1), (0, 2), (0, 3)],
            )
        return conn

    def snapshot(self):
        return {
            table: [
                tuple(row)
                for row in self.conn.execute(
                    f"SELECT * FROM {table} ORDER BY username, bank"
                    + (", period" if table == "job_usage_per_association_table" else "")
                )
            ]
            for table in (
                "association_table",
                "job_usage_factor_table",
                "job_usage_per_association_table",
            )
        }

    def check_edit(self, bank):
        before = self.snapshot()
        u.edit_user(self.conn, username="user1", bank=bank, userid=2002)
        expected = {
            ("user1", "A"): 2002,
            ("user1", "B"): 2002 if bank is None else 3003,
            ("user2", "A"): 4004,
        }
        for table in (
            "association_table",
            "job_usage_factor_table",
            "job_usage_per_association_table",
        ):
            for row in self.conn.execute(f"SELECT * FROM {table}"):
                self.assertEqual(row["userid"], expected[row["username"], row["bank"]])
        after = self.snapshot()
        # in usage-factor records only the userid column may change
        self.assertEqual(
            [row[:1] + row[2:] for row in before["job_usage_factor_table"]],
            [row[:1] + row[2:] for row in after["job_usage_factor_table"]],
        )
        # in bin records only the userid column may change
        self.assertEqual(
            [row[:1] + row[2:] for row in before["job_usage_per_association_table"]],
            [row[:1] + row[2:] for row in after["job_usage_per_association_table"]],
        )
        # association records retain everything except userid and mod_time
        self.assertEqual(
            [row[:1] + row[2:4] + row[5:] for row in before["association_table"]],
            [row[:1] + row[2:4] + row[5:] for row in after["association_table"]],
        )
        self.assertFalse(self.conn.in_transaction)
        # edit-user leaves nothing for sync-userids to repair
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(u.sync_userids(self.conn), 0)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(self.snapshot(), after)

    # update the selected bank's userid and bins without changing other associations
    def test_edit_userid_in_one_bank(self):
        self.check_edit("A")

    # update the user's userid and bins in every bank while preserving usage history
    def test_edit_userid_in_all_banks(self):
        self.check_edit(None)

    # repair either or both usage tables by bank; repeated repairs leave data unchanged
    def test_sync_independent_mismatches_and_repeated_repairs(self):
        before = self.snapshot()
        factor = "job_usage_factor_table"
        bins = "job_usage_per_association_table"
        for tables in ((bins,), (factor,), (factor, bins)):
            with self.subTest(tables=tables):
                with self.conn:
                    for table in tables:
                        self.conn.execute(
                            f"UPDATE {table} SET userid=99 WHERE username=?",
                            ("user1",),
                        )
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(u.sync_userids(self.conn), 0)
                self.assertIn("found inconsistent userids", output.getvalue())
                self.assertEqual(self.snapshot(), before)
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(u.sync_userids(self.conn), 0)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(self.conn.in_transaction)

    # an association with different userids per bank is already consistent;
    # sync must not copy one bank's userid onto another bank's rows
    def test_sync_preserves_per_bank_userids(self):
        before = self.snapshot()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(u.sync_userids(self.conn), 0)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(self.snapshot(), before)

    # leave usage rows unchanged when they have no matching association
    def test_sync_skips_orphan_usage_rows(self):
        with self.conn:
            self.conn.execute(
                "INSERT INTO job_usage_factor_table VALUES (?, ?, ?, ?)",
                ("orphan", 99, "A", 42),
            )
            self.conn.execute(
                "INSERT INTO job_usage_per_association_table VALUES (?, ?, ?, ?, ?)",
                ("orphan", 99, "A", 0, 100),
            )
        before = self.snapshot()
        u.sync_userids(self.conn)
        self.assertEqual(self.snapshot(), before)

    # rotate and decay bins correctly even when their userids have not been repaired
    def test_stale_bins_decay_without_metadata_repair(self):
        with self.conn:
            self.conn.execute(
                "UPDATE job_usage_per_association_table SET userid=99 "
                "WHERE username=? AND bank=?",
                ("user1", "A"),
            )
        with mock.patch("time.time", return_value=1150):
            j.update_job_usage(self.conn)
        periods = self.conn.execute(
            "SELECT userid, value FROM job_usage_per_association_table "
            "WHERE username=? AND bank=? ORDER BY period",
            ("user1", "A"),
        ).fetchall()
        self.assertEqual([row[0] for row in periods], [99] * 4)
        self.assertEqual([row[1] for row in periods], [0, 500, 250, 0])
        usage = self.conn.execute(
            "SELECT job_usage FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        ).fetchone()[0]
        self.assertEqual(usage, 750)

    def reject_bin_updates(self):
        self.conn.execute("""
            CREATE TRIGGER reject_bin_userid BEFORE UPDATE OF userid
            ON job_usage_per_association_table
            BEGIN
                SELECT RAISE(ABORT, 'bin update rejected');
            END
            """)
        self.conn.commit()

    # roll back the entire edit on a bin-write failure and keep the connection usable
    def test_edit_rolls_back_when_bin_write_fails(self):
        with self.conn:
            self.conn.execute("UPDATE association_table SET queues='q', projects='p'")
        self.reject_bin_updates()
        before = self.snapshot()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "bin update rejected"):
            u.edit_user(
                self.conn, username="user1", queues="-1", projects="-1", userid=2002
            )
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.conn.in_transaction)
        self.conn.execute("DROP TRIGGER reject_bin_userid")
        u.edit_user(self.conn, username="user1", bank="A", userid=2002)
        u.sync_userids(self.conn)
        self.assertFalse(self.conn.in_transaction)

    # roll back both usage-table repairs if a bin write fails, then allow a retry
    def test_sync_rolls_back_when_bin_write_fails(self):
        with self.conn:
            for table in ("job_usage_factor_table", "job_usage_per_association_table"):
                self.conn.execute(
                    f"UPDATE {table} SET userid=99 WHERE username=?", ("user1",)
                )
        self.reject_bin_updates()
        before = self.snapshot()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "bin update rejected"):
                u.sync_userids(self.conn)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.conn.in_transaction)
        self.conn.execute("DROP TRIGGER reject_bin_userid")
        u.sync_userids(self.conn)
        self.assertFalse(self.conn.in_transaction)

    # edit and synchronize userids without periodic bins or changes to usage history
    def test_continuous_mode_has_no_bins_to_repair(self):
        conn = self.create_fixture("continuous")
        u.edit_user(conn, username="user1", bank="A", userid=2002)
        u.sync_userids(conn)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM job_usage_per_association_table"
            ).fetchone()[0],
            0,
        )
        rows = conn.execute(
            "SELECT a.userid, j.userid, a.job_usage, j.last_job_timestamp "
            "FROM association_table a JOIN job_usage_factor_table j "
            "ON a.username=j.username AND a.bank=j.bank "
            "WHERE a.username=? AND a.bank=?",
            ("user1", "A"),
        ).fetchone()
        self.assertEqual(tuple(rows), (2002, 2002, 1500, 42))
        self.assertFalse(conn.in_transaction)


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
