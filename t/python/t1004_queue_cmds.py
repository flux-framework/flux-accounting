#!/usr/bin/env python3

###############################################################
# Copyright 2020 Lawrence Livermore National Security, LLC
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

from fluxacct.accounting import create_db as c
from fluxacct.accounting import queue_subcommands as q


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("TestQueueSubcommands.db")
        global acct_conn
        global cur

        acct_conn = sqlite3.connect("TestQueueSubcommands.db")
        acct_conn.row_factory = sqlite3.Row
        cur = acct_conn.cursor()

    # add a valid queue to queue_table
    def test_01_add_valid_queue(self):
        q.add_queue(acct_conn, queue="queue_1")
        cur.execute("SELECT * FROM queue_table WHERE queue='queue_1'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_02_add_dup_queue(self):
        with self.assertRaises(sqlite3.IntegrityError):
            q.add_queue(acct_conn, queue="queue_1")

    # edit a value for a queue in the queue_table
    def test_03_edit_queue_successfully(self):
        q.edit_queue(acct_conn, queue="queue_1", max_nodes_per_job=100)
        cur.execute("SELECT max_nodes_per_job FROM queue_table WHERE queue='queue_1'")

        self.assertEqual(cur.fetchone()[0], 100)

    # edit multiple fields for a given queue
    def test_04_edit_multiple_fields(self):
        q.edit_queue(
            acct_conn,
            queue="queue_1",
            min_nodes_per_job=1,
            max_nodes_per_job=128,
            max_nodes_per_assoc=1234,
        )
        cur.execute(
            "SELECT min_nodes_per_job, max_nodes_per_job, max_nodes_per_assoc "
            "FROM queue_table WHERE queue='queue_1'"
        )
        results = cur.fetchall()

        self.assertEqual(results[0][0], 1)
        self.assertEqual(results[0][1], 128)
        self.assertEqual(results[0][2], 1234)

    # edit a value with a bad type for a queue in the queue_table
    def test_05_edit_queue_bad_type(self):
        with self.assertRaises(ValueError):
            q.edit_queue(acct_conn, queue="queue_1", max_nodes_per_job="foo")

    # reset a value for a queue in the queue_table
    def test_06_reset_queue_limit(self):
        q.edit_queue(acct_conn, queue="queue_1", max_nodes_per_job=-1)
        cur.execute("SELECT max_nodes_per_job FROM queue_table where queue='queue_1'")

        self.assertEqual(cur.fetchone()[0], 1)

    # remove a queue currently in the queue_table
    def test_07_delete_queue(self):
        q.delete_queue(acct_conn, queue="queue_1")
        cur.execute("SELECT * FROM queue_table WHERE queue='queue_1'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 0)

    # trying to view a queue that does not exist should raise a ValueError
    def test_08_view_queue_nonexistent(self):
        with self.assertRaises(ValueError):
            q.view_queue(acct_conn, "foo")

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestQueueSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
