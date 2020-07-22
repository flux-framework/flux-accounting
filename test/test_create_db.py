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

from accounting import create_db as c


class TestDB(unittest.TestCase):
    # create database and make sure it exists
    def test_00_test_create_db(self):
        c.create_db("FluxAccounting.db")

        assert os.path.exists("FluxAccounting.db")

    # make sure association table exists
    def test_01_user_table_exists(self):
        with sqlite3.connect("FluxAccounting.db") as db:
            cursor = db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            list_of_tables = []
            for table_name in tables:
                table_name = table_name[0]
                list_of_tables.append(table_name)
                table = pd.read_sql_query("SELECT * from %s" % table_name, db)

        expected = "association_table"
        test = list_of_tables[0]
        self.assertEqual(test, expected)

    # add an association to the association_table
    def test_02_create_association(self):
        with sqlite3.connect("FluxAccounting.db") as db:
            db.execute(
                """
            INSERT INTO association_table
            (creation_time, mod_time, deleted, user_name, admin_level,
            account, parent_acct, shares, max_jobs, max_wall_pj)
            VALUES
            (0, 0, 0, "test user", 1, "test account", "parent account", 0, 0,
            0)
            """
            )
            cursor = db.cursor()
            num_rows = cursor.execute("DELETE FROM association_table").rowcount
            self.assertEqual(num_rows, 1)

    # remove database file
    @classmethod
    def tearDownClass(self):
        os.remove("FluxAccounting.db")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestDB("test_00_test_create_db"))
    suite.addTest(TestDB("test_01_user_table_exists"))
    suite.addTest(TestDB("test_02_create_association"))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
