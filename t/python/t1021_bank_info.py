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
import sys
import os
import time
import sqlite3

from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import create_db as c


class TestBankInfo(unittest.TestCase):
    # create test flux-accounting database
    @classmethod
    def setUpClass(self):
        self.dbname = f"TestDB_{os.path.basename(__file__)[:5]}_{round(time.time())}.db"
        c.create_db(self.dbname)
        global acct_conn
        global cur
        try:
            acct_conn = sqlite3.connect(
                f"file:{self.dbname}?mode=rw", uri=True, timeout=60
            )
            acct_conn.row_factory = sqlite3.Row
            cur = acct_conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

        # set up a bank hierarchy for testing
        b.add_bank(acct_conn, bank="root", shares=100)
        b.add_bank(acct_conn, bank="A", parent_bank="root", shares=50)
        b.add_bank(acct_conn, bank="B", parent_bank="root", shares=50)

        # add associations
        u.add_user(
            acct_conn,
            username="user1",
            bank="A",
            shares=10,
        )
        u.add_user(
            acct_conn,
            username="user2",
            bank="B",
            shares=20,
        )
        u.add_user(
            acct_conn,
            username="user3",
            bank="B",
            shares=5,
        )

    # test basic tree output with users
    def test_01_tree_with_users(self):
        result = b.bank_info(acct_conn, tree="root")
        self.assertIsNotNone(result)
        self.assertIn("root", result)
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertIn("user1", result)
        self.assertIn("user2", result)

    # test tree output without users
    def test_02_tree_without_users(self):
        result = b.bank_info(acct_conn, tree_no_users="root")
        self.assertIsNotNone(result)
        self.assertIn("root", result)
        self.assertIn("A", result)
        # should not include users
        self.assertNotIn("user1", result)
        self.assertNotIn("user2", result)

    # test to_root for a bank
    def test_03_to_root_bank(self):
        result = b.bank_info(acct_conn, to_root="A")
        self.assertIsNotNone(result)
        self.assertIn("A", result)
        self.assertIn("root", result)
        # should not include siblings
        self.assertNotIn("B", result)

    # test to_root for a user
    def test_04_to_root_user(self):
        result = b.bank_info(acct_conn, user="user3")
        self.assertIsNotNone(result)
        self.assertIn("user3", result)
        self.assertIn("B", result)
        self.assertIn("root", result)

    # test verbose output
    def test_05_verbose_output(self):
        result = b.bank_info(acct_conn, tree="root", verbose=True)
        self.assertIsNotNone(result)
        self.assertIn("Usage", result)
        self.assertIn("Type", result)

    # test parsable output
    def test_06_parseable_output(self):
        result = b.bank_info(acct_conn, tree="root", parsable=True)
        self.assertIsNotNone(result)
        # parsable output should use pipe delimiters
        self.assertIn("|", result)

    # test exclude functionality
    def test_07_exclude_bank(self):
        result = b.bank_info(acct_conn, tree="root", exclude="B")
        self.assertIsNotNone(result)
        self.assertIn("A", result)
        # excluded bank should not appear
        self.assertNotIn("B", result)

    # test noheader option
    def test_08_noheader(self):
        result = b.bank_info(acct_conn, tree="root", noheader=True)
        self.assertIsNotNone(result)
        # should not include header
        self.assertNotIn("Name", result)

    # test error for non-existent bank
    def test_09_nonexistent_bank(self):
        with self.assertRaises(ValueError):
            b.bank_info(acct_conn, tree="nonexistent")

    # test error for non-existent user
    def test_10_nonexistent_user(self):
        with self.assertRaises(ValueError):
            b.bank_info(acct_conn, user="nonexistent_user")

    # remove test database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove(self.dbname)


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
