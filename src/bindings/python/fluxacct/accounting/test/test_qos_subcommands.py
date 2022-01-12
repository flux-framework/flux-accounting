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
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import qos_subcommands as q


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("TestQOSSubcommands.db")
        global acct_conn
        global cur

        acct_conn = sqlite3.connect("TestQOSSubcommands.db")
        cur = acct_conn.cursor()

    # add a valid qos to qos_table
    def test_01_add_valid_qos(self):
        q.add_qos(acct_conn, qos="standby", priority=0)
        cur.execute("SELECT * FROM qos_table WHERE qos='standby'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_02_add_dup_qos(self):
        q.add_qos(acct_conn, qos="standby", priority=0)
        self.assertRaises(sqlite3.IntegrityError)

    # edit a value for a user in the association table
    def test_03_edit_qos_priority(self):
        q.edit_qos(acct_conn, qos="standby", new_priority=1000)
        cur.execute("SELECT priority FROM qos_table where qos='standby'")

        self.assertEqual(cur.fetchone()[0], 1000)

    # remove a QOS currently in the qos_table
    def test_04_delete_qos(self):
        q.delete_qos(acct_conn, qos="standby")
        cur.execute("SELECT * FROM qos_table WHERE qos='standby'")
        rows = cur.fetchall()

        self.assertEqual(len(rows), 0)

    # trying to add a user with a bad QoS should raise a ValueError
    def test_05_add_user_with_bad_qos(self):
        u.add_user(acct_conn, username="u5011", uid="5011", bank="acct", qos="foo")

        self.assertRaises(ValueError)

    # trying to edit a user with a bad QoS should also raise a ValueError
    def test_06_edit_user_with_bad_qos(self):
        u.add_user(acct_conn, username="u5011", uid="5011", bank="acct")
        u.edit_user(acct_conn, username="u5011", qos="foo")

        self.assertRaises(ValueError)

    # if we add multiple QoS to the qos_table, we should be able to specify it
    # in the association_table as well
    def test_07_add_multiple_qos_to_user(self):
        q.add_qos(acct_conn, qos="standby", priority=0)
        q.add_qos(acct_conn, qos="expedite", priority=10000)
        q.add_qos(acct_conn, qos="special", priority=99999)

        u.edit_user(
            acct_conn,
            username="u5011",
            qos="standby,expedite,special",
        )
        cur.execute("SELECT qos FROM association_table WHERE username='u5011'")

        self.assertEqual(cur.fetchone()[0], "standby,expedite,special")

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestQOSSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
