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
import pandas as pd

from accounting import accounting_cli_functions as aclif
from accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create database
    @classmethod
    def setUpClass(self):
        c.create_db("FluxAccounting.db")
        global conn
        conn = sqlite3.connect("FluxAccounting.db")

    # add a valid user to association_table
    def test_01_add_valid_user(self):
        aclif.add_user(conn, "fluxuser", "1", "acct", "pacct", "10", "100", "60")

        cursor = conn.cursor()
        num_rows = cursor.execute("DELETE FROM association_table").rowcount
        self.assertEqual(num_rows, 1)

    # adding a user with the same user_name as an existing user should
    # return an IntegrityError
    def test_02_add_duplicate_user(self):
        aclif.add_user(conn, "fluxuser", "1", "acct", "pacct", "10", "100", "60")

        aclif.add_user(conn, "fluxuser", "1", "acct", "pacct", "10", "100", "60")

        self.assertRaises(sqlite3.IntegrityError)

    # edit a value for a user in the association table
    def test_03_edit_user_value(self):
        aclif.edit_user(conn, "fluxuser", "max_jobs", "10000")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT max_jobs FROM association_table where user_name='fluxuser'"
        )

        self.assertEqual(cursor.fetchone()[0], 10000)

    # trying to edit a field in a column that doesn't
    # exist should return an OperationalError
    def test_04_edit_bad_field(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.edit_user(conn, "fluxuser", "foo", "bar")

        self.assertEqual(cm.exception.code, 1)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        conn.close()
        os.remove("FluxAccounting.db")
        os.remove("db_creation.log")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestAccountingCLI("test_01_add_valid_user"))
    suite.addTest(TestAccountingCLI("test_02_add_bad_user"))
    suite.addTest(TestAccountingCLI("test_03_add_duplicate_user"))
    suite.addTest(TestAccountingCLI("test_04_edit_user_value"))
    suite.addTest(TestAccountingCLI("test_05_edit_bad_field"))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
