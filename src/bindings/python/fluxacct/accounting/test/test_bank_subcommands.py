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

from fluxacct.accounting import accounting_cli_functions as aclif
from fluxacct.accounting import create_db as c
from fluxacct.accounting import print_hierarchy as p


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
        with self.assertRaises(Exception) as context:
            aclif.add_bank(
                acct_conn,
                bank="bad_subaccount",
                parent_bank="bad_parentaccount",
                shares=1,
            )

        self.assertTrue("Parent bank not found in bank table" in str(context.exception))

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

    # deleting a parent bank should remove all of its sub banks
    def test_06_delete_parent_bank(self):
        aclif.delete_bank(acct_conn, bank="root")
        aclif.delete_bank(acct_conn, bank="sub_account_2")

        aclif.add_bank(acct_conn, bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="B", parent_bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="D", parent_bank="B", shares=1)
        aclif.add_bank(acct_conn, bank="E", parent_bank="B", shares=1)
        aclif.add_bank(acct_conn, bank="C", parent_bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="F", parent_bank="C", shares=1)
        aclif.add_bank(acct_conn, bank="G", parent_bank="C", shares=1)

        aclif.delete_bank(acct_conn, bank="A")
        select_stmt = "SELECT * FROM bank_table"
        dataframe = pd.read_sql_query(select_stmt, acct_conn)

        self.assertEqual(len(dataframe), 0)

    # edit a bank value
    def test_07_edit_bank_value(self):
        aclif.add_bank(acct_conn, bank="root", shares=100)
        aclif.edit_bank(acct_conn, bank="root", shares=50)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='root'")

        self.assertEqual(cursor.fetchone()[0], 50)

    # trying to edit a bank value <= 0 should raise
    # an exception
    def test_08_edit_bank_value_fail(self):
        with self.assertRaises(Exception) as context:
            aclif.add_bank(acct_conn, bank="bad_bank", shares=10)
            aclif.edit_bank(acct_conn, bank="bad_bank", shares=-1)

        self.assertTrue("New shares amount must be >= 0" in str(context.exception))

    # print out the full hierarchy of banks along
    # with their respective associations
    def test_09_print_hierarchy(self):
        aclif.delete_bank(acct_conn, "root")
        aclif.delete_bank(acct_conn, "sub_account_2")
        aclif.delete_bank(acct_conn, "bad_bank")

        aclif.add_bank(acct_conn, bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="B", parent_bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="D", parent_bank="B", shares=1)
        aclif.add_bank(acct_conn, bank="E", parent_bank="B", shares=1)
        aclif.add_bank(acct_conn, bank="C", parent_bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="F", parent_bank="C", shares=1)
        aclif.add_bank(acct_conn, bank="G", parent_bank="C", shares=1)

        aclif.add_user(
            acct_conn,
            username="user1",
            admin_level=1,
            bank="D",
            shares=1,
            max_jobs=100,
            max_wall_pj=60,
        )

        aclif.add_user(
            acct_conn,
            username="user2",
            admin_level=1,
            bank="F",
            shares=1,
            max_jobs=100,
            max_wall_pj=60,
        )

        aclif.add_user(
            acct_conn,
            username="user3",
            admin_level=1,
            bank="F",
            shares=1,
            max_jobs=100,
            max_wall_pj=60,
        )

        aclif.add_user(
            acct_conn,
            username="user4",
            admin_level=1,
            bank="G",
            shares=1,
            max_jobs=100,
            max_wall_pj=60,
        )

        test = p.print_full_hierarchy(acct_conn)

        expected = """Bank|User|RawShares
A||1
 B||1
  D||1
   D|user1|1
  E||1
 C||1
  F||1
   F|user2|1
   F|user3|1
  G||1
   G|user4|1
"""

        self.assertEqual(test, expected)

    # having more than one root bank should result
    # in an exception being thrown
    def test_10_print_hierarchy_failure_1(self):
        c.create_db("flux_accounting_failure_1.db")
        acct_conn = sqlite3.connect("flux_accounting_failure_1.db")

        aclif.add_bank(acct_conn, bank="A", shares=1)
        aclif.add_bank(acct_conn, bank="B", shares=1)

        with self.assertRaises(SystemExit) as cm:
            p.print_full_hierarchy(acct_conn)

        self.assertTrue(cm.exception.code, 1)

    # having no root bank should also result in an
    # exception being thrown
    def test_11_print_hierarchy_failure_2(self):
        c.create_db("flux_accounting_failure_2.db")
        acct_conn = sqlite3.connect("flux_accounting_failure_2.db")

        with self.assertRaises(SystemExit) as cm:
            p.print_full_hierarchy(acct_conn)

        self.assertTrue(cm.exception.code, 1)

    # removing a bank should remove any sub banks and
    # associations under those banks
    def test_12_delete_bank_recursive(self):
        c.create_db("flux_accounting_delete_bank_1.db")
        acct_conn = sqlite3.connect("flux_accounting_delete_bank_1.db")

        aclif.add_bank(acct_conn, bank="A", shares=1)
        aclif.add_bank(acct_conn, parent_bank="A", bank="B", shares=1)
        aclif.add_bank(acct_conn, parent_bank="A", bank="C", shares=1)
        aclif.add_bank(acct_conn, parent_bank="C", bank="D", shares=1)

        aclif.add_user(acct_conn, "user1", "B")
        aclif.add_user(acct_conn, "user2", "B")
        aclif.add_user(acct_conn, "user3", "B")
        aclif.add_user(acct_conn, "user4", "B")
        aclif.add_user(acct_conn, "user5", "D")
        aclif.add_user(acct_conn, "user6", "D")

        aclif.delete_bank(acct_conn, bank="C")

        test = p.print_full_hierarchy(acct_conn)

        expected = """Bank|User|RawShares
A||1
 B||1
  B|user1|1
  B|user2|1
  B|user3|1
  B|user4|1
"""

        self.assertEqual(test, expected)

    # remove database and log file
    @classmethod
    def tearDownClass(self):
        acct_conn.close()
        os.remove("TestBankSubcommands.db")
        os.remove("flux_accounting_failure_1.db")
        os.remove("flux_accounting_failure_2.db")
        os.remove("flux_accounting_delete_bank_1.db")


def suite():
    suite = unittest.TestSuite()

    return suite


if __name__ == "__main__":
    from pycotap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())
