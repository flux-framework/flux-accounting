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

from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("TestBankSubcommands.db")
        global acct_conn
        acct_conn = sqlite3.connect("TestBankSubcommands.db")

    # let's add a top-level account using the add-bank
    # subcommand
    def test_01_add_bank_success(self):
        b.add_bank(acct_conn, bank="root", shares=100)
        select_stmt = "SELECT * FROM bank_table WHERE bank='root'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_02_add_dup_bank(self):
        b.add_bank(acct_conn, bank="root", shares=100)
        self.assertRaises(sqlite3.IntegrityError)

    # trying to add a sub account with an invalid parent bank
    # name should result in a failure
    def test_03_add_with_invalid_parent_bank(self):
        with self.assertRaises(Exception) as context:
            b.add_bank(
                acct_conn,
                bank="bad_subaccount",
                parent_bank="bad_parentaccount",
                shares=1,
            )

        self.assertTrue("Parent bank not found in bank table" in str(context.exception))

    # now let's add a couple sub accounts whose parent is 'root'
    # and whose total shares equal root's allocation (100 shares)
    def test_04_add_subaccounts(self):
        b.add_bank(acct_conn, bank="sub_account_1", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)
        b.add_bank(acct_conn, bank="sub_account_2", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_2'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # removing a bank currently in the bank_table
    def test_05_delete_bank_success(self):
        b.delete_bank(acct_conn, bank="sub_account_1")
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 0)

    # deleting a parent bank should remove all of its sub banks
    def test_06_delete_parent_bank(self):
        b.delete_bank(acct_conn, bank="root")
        b.delete_bank(acct_conn, bank="sub_account_2")

        b.add_bank(acct_conn, bank="A", shares=1)
        b.add_bank(acct_conn, bank="B", parent_bank="A", shares=1)
        b.add_bank(acct_conn, bank="D", parent_bank="B", shares=1)
        b.add_bank(acct_conn, bank="E", parent_bank="B", shares=1)
        b.add_bank(acct_conn, bank="C", parent_bank="A", shares=1)
        b.add_bank(acct_conn, bank="F", parent_bank="C", shares=1)
        b.add_bank(acct_conn, bank="G", parent_bank="C", shares=1)

        b.delete_bank(acct_conn, bank="A")
        select_stmt = "SELECT * FROM bank_table"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)

        self.assertEqual(len(dataframe), 0)

    # edit a bank value
    def test_07_edit_bank_value(self):
        b.add_bank(acct_conn, bank="root", shares=100)
        b.edit_bank(acct_conn, bank="root", shares=50)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='root'")

        self.assertEqual(cursor.fetchone()[0], 50)

    # trying to edit a bank value <= 0 should raise
    # an exception
    def test_08_edit_bank_value_fail(self):
        with self.assertRaises(Exception) as context:
            b.add_bank(acct_conn, bank="bad_bank", shares=10)
            b.edit_bank(acct_conn, bank="bad_bank", shares=-1)

        self.assertTrue("New shares amount must be >= 0" in str(context.exception))

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestBankSubcommands.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
