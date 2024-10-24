#!/usr/bin/env python3

###############################################################
# Copyright 2024 Lawrence Livermore National Security, LLC
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
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import formatter as fmt


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("TestFormatter.db")
        global conn
        global cur

        conn = sqlite3.connect("TestFormatter.db")
        cur = conn.cursor()

    # initialize Formatter object with no data in Cursor object
    def test_AccountingFormatter_empty(self):
        with self.assertRaises(ValueError):
            cur.execute("SELECT * FROM bank_table")
            formatter = fmt.AccountingFormatter(cur)

    # add some data to a table and re-initialize formatter
    def test_AccountingFormatter_with_banks(self):
        b.add_bank(conn, bank="root", shares=1)
        b.add_bank(conn, bank="A", shares=1, parent_bank="root")
        b.add_bank(conn, bank="B", shares=1, parent_bank="root")
        b.add_bank(conn, bank="C", shares=1, parent_bank="root")

        cur.execute("SELECT * FROM bank_table")
        formatter = fmt.AccountingFormatter(cur)

        self.assertIsInstance(formatter, fmt.AccountingFormatter)

    # ensure formatter has the correct number of rows
    def test_formatter_get_rows(self):
        cur.execute("SELECT * FROM bank_table")
        formatter = fmt.AccountingFormatter(cur)

        self.assertEqual(len(formatter.get_rows()), 4)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("TestFormatter.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
