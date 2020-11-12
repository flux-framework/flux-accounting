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
    # create database
    @classmethod
    def setUpClass(self):
        c.create_db("FluxAccounting.db")
        global conn
        conn = sqlite3.connect("FluxAccounting.db")

    # create database and make sure it exists
    def test_00_test_create_db(self):
        assert os.path.exists("FluxAccounting.db")

    # make sure association table exists
    def test_01_tables_exist(self):
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        list_of_tables = []
        for table_name in tables:
            table_name = table_name[0]
            list_of_tables.append(table_name)
            table = pd.read_sql_query("SELECT * from %s" % table_name, conn)

        expected = ["association_table", "bank_table"]
        test = list_of_tables[:2]
        self.assertEqual(test, expected)

    # add an association to the association_table
    def test_02_create_association(self):
        conn.execute(
            """
            INSERT INTO association_table
            (creation_time, mod_time, deleted, user_name, admin_level,
            bank, shares, max_jobs, max_wall_pj)
            VALUES
            (0, 0, 0, "test user", 1, "test account", 0, 0,
            0)
            """
        )
        cursor = conn.cursor()
        num_rows = cursor.execute("DELETE FROM association_table").rowcount
        self.assertEqual(num_rows, 1)

    # add a top-level account to the bank_table
    def test_03_create_top_level_account(self):
        conn.execute(
            """
            INSERT INTO bank_table
            (bank, shares)
            VALUES
            ("root", 100)
            """
        )
        cursor = conn.cursor()
        select_stmt = "SELECT * FROM bank_table"
        dataframe = pd.read_sql_query(select_stmt, conn)
        self.assertEqual(len(dataframe.index), 1)

    # let's add a sub account under root
    def test_04_create_sub_account(self):
        conn.execute(
            """
            INSERT INTO bank_table
            (bank, parent_bank, shares)
            VALUES
            ("sub_account_1", "parent_account", 50)
            """
        )
        cursor = conn.cursor()
        select_stmt = "SELECT * FROM bank_table"
        dataframe = pd.read_sql_query(select_stmt, conn)
        self.assertEqual(len(dataframe.index), 2)

    # let's make sure the bank id's get autoincremented
    def test_05_check_bank_ids(self):
        select_stmt = "SELECT bank_id FROM bank_table;"
        dataframe = pd.read_sql_query(select_stmt, conn)
        self.assertEqual(dataframe["bank_id"][0], 1)
        self.assertEqual(dataframe["bank_id"][1], 2)

    # remove database file
    @classmethod
    def tearDownClass(self):
        os.remove("FluxAccounting.db")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestDB("test_00_test_create_db"))
    suite.addTest(TestDB("test_01_tables_exist"))
    suite.addTest(TestDB("test_02_create_association"))
    suite.addTest(TestDB("test_03_create_top_level_account"))
    suite.addTest(TestDB("test_04_create_sub_account"))

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner
    unittest.main(testRunner=TAPTestRunner())
