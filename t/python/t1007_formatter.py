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

import fluxacct.accounting
from fluxacct.accounting import create_db as c
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import formatter as fmt
from fluxacct.accounting import sql_util as sql


class TestAccountingCLI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # create test accounting database
        c.create_db("TestFormatter.db")
        global conn
        global cur

        conn = sqlite3.connect("TestFormatter.db")
        conn.row_factory = sqlite3.Row
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

    # ensure formatter retrieves only the column names passed by query
    def test_formatter_get_column_names_default(self):
        cur.execute("SELECT * FROM bank_table")
        formatter = fmt.AccountingFormatter(cur)

        self.assertEqual(formatter.get_column_names(), fluxacct.accounting.BANK_TABLE)

    def test_formatter_get_column_names_custom(self):
        cur.execute("SELECT bank_id FROM bank_table")
        formatter = fmt.AccountingFormatter(cur)

        self.assertEqual(formatter.get_column_names(), ["bank_id"])

    # ensure default fields can be accessed for relevant flux-accounting
    # tables in DB
    def test_default_columns_association_table(self):
        cur.execute("PRAGMA table_info (association_table)")
        columns = cur.fetchall()
        association_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.ASSOCIATION_TABLE, association_table)

    def test_default_columns_bank_table(self):
        cur.execute("PRAGMA table_info (bank_table)")
        columns = cur.fetchall()
        bank_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.BANK_TABLE, bank_table)

    def test_default_columns_queue_table(self):
        cur.execute("PRAGMA table_info (queue_table)")
        columns = cur.fetchall()
        queue_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.QUEUE_TABLE, queue_table)

    def test_default_columns_project_table(self):
        cur.execute("PRAGMA table_info (project_table)")
        columns = cur.fetchall()
        project_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.PROJECT_TABLE, project_table)

    def test_default_columns_jobs_table(self):
        cur.execute("PRAGMA table_info (jobs)")
        columns = cur.fetchall()
        jobs_table = [column[1] for column in columns]

        self.assertEqual(fluxacct.accounting.JOBS_TABLE, jobs_table)

    # an exception is raised if the columns passed in are not valid
    def test_validate_columns_invalid(self):
        with self.assertRaises(ValueError):
            sql.validate_columns(["foo"], fluxacct.accounting.ASSOCIATION_TABLE)

    def test_validate_columns_valid(self):
        cur.execute("SELECT username, bank FROM association_table")
        column_names = [description[0] for description in cur.description]

        sql.validate_columns(column_names, fluxacct.accounting.ASSOCIATION_TABLE)

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
