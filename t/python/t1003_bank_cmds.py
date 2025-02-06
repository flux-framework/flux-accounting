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
import sqlite3

from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import create_db as c


class TestAccountingCLI(unittest.TestCase):
    # create test flux-accounting database
    @classmethod
    def setUpClass(self):
        c.create_db("TestBankSubcommands.db")
        global acct_conn
        global cur
        try:
            acct_conn = sqlite3.connect("file:TestBankSubcommands.db?mode=rw", uri=True)
            acct_conn.row_factory = sqlite3.Row
            cur = acct_conn.cursor()
        except sqlite3.OperationalError:
            print(f"Unable to open test database file", file=sys.stderr)
            sys.exit(-1)

    # add a top-level account using add_bank()
    def test_01_add_bank_success(self):
        b.add_bank(acct_conn, bank="root", shares=100)
        cur.execute("SELECT * FROM bank_table WHERE bank='root'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)

    # a root bank already exists, so a ValueError will be raised
    def test_02_add_dup_bank(self):
        with self.assertRaises(ValueError):
            b.add_bank(acct_conn, bank="second_root", shares=100)

    # trying to add a sub account with an invalid parent bank
    # name should result in a ValueError
    def test_03_add_with_invalid_parent_bank(self):
        with self.assertRaises(ValueError):
            b.add_bank(
                acct_conn,
                bank="bad_subaccount",
                parent_bank="bad_parentaccount",
                shares=1,
            )

    # add a couple sub accounts whose parent is 'root'
    def test_04_add_sub_banks(self):
        b.add_bank(acct_conn, bank="sub_account_1", parent_bank="root", shares=50)
        cur.execute("SELECT * FROM bank_table WHERE bank='sub_account_1'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        b.add_bank(acct_conn, bank="sub_account_2", parent_bank="root", shares=50)
        cur.execute("SELECT * FROM bank_table WHERE bank='sub_account_2'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)

    # disable a bank currently in the bank_table
    def test_05_disable_bank_success(self):
        b.delete_bank(acct_conn, bank="sub_account_1")
        cur.execute("SELECT active FROM bank_table WHERE bank='sub_account_1'")
        rows = cur.fetchall()

        self.assertEqual(rows[0][0], 0)

    # disabling a parent bank should disable all of its sub banks
    def test_06_disable_parent_bank(self):
        b.add_bank(acct_conn, bank="B", parent_bank="root", shares=1)
        b.add_bank(acct_conn, bank="D", parent_bank="B", shares=1)
        b.add_bank(acct_conn, bank="E", parent_bank="B", shares=1)
        b.add_bank(acct_conn, bank="C", parent_bank="root", shares=1)
        b.add_bank(acct_conn, bank="F", parent_bank="C", shares=1)
        b.add_bank(acct_conn, bank="G", parent_bank="C", shares=1)

        b.delete_bank(acct_conn, bank="root")
        cur.execute("SELECT active FROM bank_table WHERE bank='root'")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], 0)

        cur.execute("SELECT active FROM bank_table WHERE bank='B'")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], 0)

        cur.execute("SELECT active FROM bank_table WHERE bank='F'")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], 0)

    # edit a bank value
    def test_07_edit_bank_value(self):
        b.edit_bank(acct_conn, bank="root", shares=50)
        cursor = acct_conn.cursor()
        cursor.execute("SELECT shares FROM bank_table where bank='root'")

        self.assertEqual(cursor.fetchone()[0], 50)

    # edit a bank's parent bank
    def test_08_edit_parent_bank_success(self):
        b.add_bank(acct_conn, bank="A", parent_bank="root", shares=1)
        b.add_bank(acct_conn, bank="B", parent_bank="root", shares=1)

        # set bank's parent bank to A
        b.add_bank(acct_conn, bank="C", parent_bank="A", shares=1)

        # change bank's parent bank to B
        b.edit_bank(acct_conn, bank="C", parent_bank="B")

        cursor = acct_conn.cursor()
        cursor.execute("SELECT parent_bank FROM bank_table WHERE bank='C'")

        self.assertEqual(cursor.fetchone()[0], "B")

    # trying to edit a bank's parent bank to a bank that does not
    # exist should raise a ValueError
    def test_09_edit_parent_bank_failure(self):
        with self.assertRaises(ValueError):
            b.edit_bank(acct_conn, bank="C", parent_bank="foo")

    # trying to edit a bank's shares <= 0 should raise
    # a ValueError
    def test_10_edit_bank_value_fail(self):
        with self.assertRaises(ValueError):
            b.add_bank(acct_conn, bank="bad_bank", shares=10)
            b.edit_bank(acct_conn, bank="bad_bank", shares=-1)

    # trying to view a bank that does not exist should raise a ValueError
    def test_11_view_bank_nonexistent(self):
        with self.assertRaises(ValueError):
            b.view_bank(acct_conn, bank="foo")

    # try to add a bank that is currently disabled and make sure that it
    # gets reactivated
    def test_12_reactivate_bank(self):
        # check that bank is disabled
        cur.execute("SELECT active FROM bank_table WHERE bank='G'")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], 0)

        # re-add bank
        b.add_bank(acct_conn, bank="G", parent_bank="C", shares=1)

        cur.execute("SELECT active FROM bank_table WHERE bank='G'")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], 1)

    # actually remove a bank row from the bank_table
    def test_13_delete_bank_force(self):
        b.delete_bank(acct_conn, bank="G", force=True)
        cur.execute("SELECT * FROM bank_table WHERE bank='G'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 0)

    # actually delete multiple banks from bank_table by deleting a parent bank
    def test_14_delete_parent_bank_force(self):
        b.delete_bank(acct_conn, bank="C", force=True)
        cur.execute("SELECT * FROM bank_table WHERE bank='C'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 0)
        cur.execute("SELECT * FROM bank_table WHERE parent_bank='C'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 0)

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
