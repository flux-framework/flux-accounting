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
    # create accounting, job-archive databases
    @classmethod
    def setUpClass(self):
        # create example accounting database
        c.create_db("FluxAccounting.db")
        global acct_conn
        acct_conn = sqlite3.connect("FluxAccounting.db")

    # let's add a top-level account using the add-bank
    # subcommand
    def test_01_add_bank_success(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        select_stmt = "SELECT * FROM bank_table WHERE bank='root'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # let's make sure if we try to add it a second time,
    # it fails gracefully
    def test_02_add_dup_bank(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        self.assertRaises(sqlite3.IntegrityError)

    # trying to add a sub account with an invalid parent bank
    # name should result in a failure
    def test_03_add_with_invalid_parent_bank(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(
                acct_conn,
                bank="bad_subaccount",
                parent_bank="bad_parentaccount",
                shares=1,
            )

        self.assertEqual(cm.exception.code, -1)

    # now let's add a couple sub accounts whose parent is 'root'
    # and whose total shares equal root's allocation (100 shares)
    def test_04_add_subaccounts(self):
        aclif.add_bank(acct_conn, bank="sub_account_1", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)
        aclif.add_bank(acct_conn, bank="sub_account_2", parent_bank="root", shares=50)
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_2'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 1)

    # removing a bank currently in the bank_table
    def test_05_delete_bank_success(self):
        aclif.delete_bank(acct_conn, bank="sub_account_1")
        select_stmt = "SELECT * FROM bank_table WHERE bank='sub_account_1'"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)
        self.assertEqual(len(dataframe.index), 0)

    # edit a bank value
    def test_06_edit_bank_value(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        aclif.edit_bank(acct_conn, bank="root", shares=50)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='root'")

        self.assertEqual(cursor.fetchone()[0], 50)

    # trying to edit a parent bank's value to be
    # less than the total amount allocated to all of its
    # sub banks should result in a failure message and exit
    def test_07_edit_parent_bank_failure(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(acct_conn, bank="sub_bank_1", parent_bank="root", shares=25)
            aclif.add_bank(acct_conn, bank="sub_bank_2", parent_bank="root", shares=25)
            aclif.edit_bank(acct_conn, bank="root", shares=49)

        self.assertEqual(cm.exception.code, -1)

    # edit a parent bank that has sub banks successfully
    def test_08_edit_parent_bank_success(self):
        aclif.add_bank(acct_conn, bank="sub_bank_1", shares=25)
        aclif.add_bank(
            acct_conn, bank="sub_bank_1_1", parent_bank="sub_bank_1", shares=5
        )
        aclif.add_bank(
            acct_conn, bank="sub_bank_1_2", parent_bank="sub_bank_1", shares=5
        )
        aclif.edit_bank(acct_conn, bank="sub_bank_1", shares=11)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='sub_bank_1'")

        self.assertEqual(cursor.fetchone()[0], 11)

    # trying to edit a sub bank's shares to be greater
    # than its parent bank's allocation should result
    # in a failure message and exit
    def test_09_edit_sub_bank_greater_than_parent_bank(self):
        with self.assertRaises(SystemExit) as cm:
            aclif.add_bank(
                acct_conn, bank="sub_bank_2_1", parent_bank="sub_bank_2", shares=5
            )
            aclif.edit_bank(acct_conn, bank="sub_bank_2_1", shares=26)

        self.assertEqual(cm.exception.code, -1)

    # edit the sub bank successfully
    def test_10_edit_sub_bank_successfully(self):
        aclif.add_bank(acct_conn, bank="sub_bank_2_1", shares=26)
        aclif.edit_bank(acct_conn, bank="sub_bank_2_1", shares=24)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='sub_bank_2_1'")

        self.assertEqual(cursor.fetchone()[0], 24)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("FluxAccounting.db")
        os.remove("db_creation.log")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
