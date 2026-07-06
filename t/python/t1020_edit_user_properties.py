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
from unittest.mock import patch

from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import queue_subcommands as q


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global conn
        global cur

        conn = sqlite3.connect(self.dbname, timeout=60)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # add simple database hierarchy
        b.add_bank(conn, "root", 1)
        b.add_bank(conn, "A", 1, "root")
        u.add_user(conn, username="user1", bank="A", uid=50001)

        # add queues
        q.add_queue(conn, queue="queue_1")
        q.add_queue(conn, queue="queue_2")
        q.add_queue(conn, queue="queue_3")

    def test_01_add_queue_to_user(self):
        # Add queue_1 to user1
        u.edit_user(conn, username="user1", bank="A", add_queue="queue_1")

        # verify queue was added
        cur.execute(
            "SELECT queues FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        )
        result = cur.fetchone()
        self.assertEqual(result[0], "queue_1")

    def test_02_add_another_queue(self):
        u.edit_user(conn, username="user1", bank="A", add_queue="queue_2")

        # verify both queues are present
        cur.execute(
            "SELECT queues FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        )
        result = cur.fetchone()
        queue_list = result[0].split(",")
        self.assertIn("queue_1", queue_list)
        self.assertIn("queue_2", queue_list)

    def test_03_add_duplicate_queue(self):
        # trying to add queue_1 again won't affect existing list
        u.edit_user(conn, username="user1", bank="A", add_queue="queue_1")
        cur.execute(
            "SELECT queues FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        )
        result = cur.fetchone()
        queue_list = result[0].split(",")
        self.assertIn("queue_1", queue_list)
        self.assertIn("queue_2", queue_list)

    def test_04_delete_queue(self):
        u.edit_user(conn, username="user1", bank="A", delete_queue="queue_1")

        # verify queue_1 is removed but queue_2 remains
        cur.execute(
            "SELECT queues FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        )
        result = cur.fetchone()
        queue_list = result[0].split(",") if result[0] else []
        self.assertNotIn("queue_1", queue_list)
        self.assertIn("queue_2", queue_list)

    def test_05_delete_nonexistent_queue(self):
        # try to delete a queue that user doesn't have won't affect existing list
        u.edit_user(conn, username="user1", bank="A", delete_queue="queue_3")
        cur.execute(
            "SELECT queues FROM association_table WHERE username=? AND bank=?",
            ("user1", "A"),
        )
        result = cur.fetchone()
        queue_list = result[0].split(",") if result[0] else []
        self.assertNotIn("queue_1", queue_list)
        self.assertIn("queue_2", queue_list)

    def test_06_cannot_use_queues_with_add_queue(self):
        # verify that --queues and --add-queue cannot be used together
        with self.assertRaisesRegex(
            ValueError, "cannot specify --queues with --add-queue"
        ):
            u.edit_user(
                conn,
                username="user1",
                bank="A",
                queues="queue_1,queue_2",
                add_queue="queue_3",
            )

    def test_07_validate_nonexistent_queue(self):
        # try to add a queue that doesn't exist in queue_table
        with self.assertRaisesRegex(ValueError, "does not exist in queue_table"):
            u.edit_user(conn, username="user1", bank="A", add_queue="nonexistent_queue")

    def test_08_queue_passed_to_both_args(self):
        # a queue passed to both add_queue and delete_queue raises ValueError
        with self.assertRaisesRegex(
            ValueError, "cannot pass queue to both --add-queue and --delete-queue"
        ):
            u.edit_user(
                conn,
                username="user1",
                bank="A",
                add_queue="queue_1",
                delete_queue="queue_1",
            )

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
