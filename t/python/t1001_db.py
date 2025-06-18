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
import sys

from fluxacct.accounting import create_db as c


class TestDB(unittest.TestCase):
    # create database
    @classmethod
    def setUpClass(self):
        c.create_db("FluxAccounting.db")
        global conn
        global cur
        try:
            conn = sqlite3.connect("file:FluxAccounting.db?mode=rw", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

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

        # sqlite_sequence is an internal table that SQLite
        # uses to keep track of the largest ROWID
        expected = [
            "association_table",
            "bank_table",
            "sqlite_sequence",
            "job_usage_factor_table",
            "t_half_life_period_table",
            "queue_table",
            "project_table",
            "jobs",
            "priority_factor_weight_table",
        ]
        self.assertEqual(list_of_tables, expected)

    # add an association to the association_table
    def test_02_create_association(self):
        conn.execute(
            """
            INSERT INTO association_table
            (creation_time, mod_time, username, userid,
            bank, default_bank, shares, queues)
            VALUES
            (0, 0, "test user", 1234, "test account", "test_account", 0, "")
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
        select_stmt = "SELECT * FROM bank_table"
        cur.execute(select_stmt)
        self.assertEqual(len(cur.fetchall()), 1)

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
        select_stmt = "SELECT * FROM bank_table"
        cur.execute(select_stmt)
        self.assertEqual(len(cur.fetchall()), 2)

    # let's make sure the bank id's get autoincremented
    def test_05_check_bank_ids(self):
        select_stmt = "SELECT bank_id FROM bank_table;"
        cur.execute(select_stmt)
        self.assertEqual(cur.fetchone()[0], 1)
        self.assertEqual(cur.fetchone()[0], 2)

    # if PriorityDecayHalfLife and PriorityUsageResetPeriod
    # are not specified, the job_usage_factor_table will have
    # 4 bins, each representing 1 week's worth of jobs
    def test_06_job_usage_factor_table_default(self):
        c.create_db("flux_accounting_test_1.db")
        columns_query = "PRAGMA table_info(job_usage_factor_table)"
        test_conn = sqlite3.connect("flux_accounting_test_1.db")
        expected = [
            "usage_factor_period_0",
            "usage_factor_period_1",
            "usage_factor_period_2",
            "usage_factor_period_3",
        ]
        test = []
        cursor = test_conn.cursor()
        for row in cursor.execute(columns_query):
            if "usage_factor" in row[1]:
                test.append(row[1])
        self.assertEqual(test, expected)

    # PriorityDecayHalfLife and PriorityUsageResetPeriod should be configurable
    # to create a custom table spanning a customizable period of time
    def test_07_job_usage_factor_table_configurable(self):
        c.create_db(
            "flux_accounting_test_2.db",
            priority_usage_reset_period=10,
            priority_decay_half_life=1,
        )
        columns_query = "PRAGMA table_info(job_usage_factor_table)"
        test_conn = sqlite3.connect("flux_accounting_test_2.db")
        expected = [
            "usage_factor_period_0",
            "usage_factor_period_1",
            "usage_factor_period_2",
            "usage_factor_period_3",
            "usage_factor_period_4",
            "usage_factor_period_5",
            "usage_factor_period_6",
            "usage_factor_period_7",
            "usage_factor_period_8",
            "usage_factor_period_9",
        ]
        test = []
        cursor = test_conn.cursor()
        for row in cursor.execute(columns_query):
            if "usage_factor" in row[1]:
                test.append(row[1])
        self.assertEqual(test, expected)

    # remove database file
    @classmethod
    def tearDownClass(self):
        os.remove("FluxAccounting.db")
        os.remove("flux_accounting_test_1.db")
        os.remove("flux_accounting_test_2.db")


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
